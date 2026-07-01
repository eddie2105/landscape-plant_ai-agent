import json
import os

import gspread
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI


DEAD_LOCAL_PROXY = "127.0.0.1:9"
PROXY_ENV_VARS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
]


def disable_dead_local_proxy():
    # Codex / sandbox 可能會注入無效的本機 proxy，導致 Google / OpenAI 連線失敗。
    # 這裡只移除已知的壞 proxy，而且只影響目前這個 Python 程序。
    for name in PROXY_ENV_VARS:
        value = os.environ.get(name, "")
        if DEAD_LOCAL_PROXY in value:
            os.environ.pop(name, None)


disable_dead_local_proxy()


REQUIRED_ENV_VARS = [
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    "PLANTS_SPREADSHEET_ID",
    "PLANTS_WORKSHEET_NAME",
    "DISPLAY_MATRIX_SPREADSHEET_ID",
    "DISPLAY_MATRIX_WORKSHEET_NAME",
    "OPENAI_API_KEY",
]


MONTHS = {
    "jan": "1月",
    "feb": "2月",
    "mar": "3月",
    "apr": "4月",
    "may": "5月",
    "jun": "6月",
    "jul": "7月",
    "aug": "8月",
    "sep": "9月",
    "oct": "10月",
    "nov": "11月",
    "dec": "12月",
}


FINAL_REMINDER = "實際配置仍需依基地日照、土壤、排水、維護條件與設計風格確認。"

SYSTEM_PROMPT = f"""你是一位景觀植栽知識助理。
你只能根據提供的 Google Sheet 資料回答，不得使用外部知識，也不得捏造資料表中不存在的資訊。

你的任務分成兩層：
1. answer：用台灣繁體中文提供完整推薦說明，並且必須使用固定三段式格式。
2. plant_ids：回傳 answer 中實際推薦、提到或比較的植物 plant_id，讓 Python 可以精準回查資料表與季相圖。

嚴格規則：
- answer 的所有植物資訊都必須來自提供的 Google Sheet。
- 如果資料不足，請在 answer 說明「目前資料表不足以判斷」，並指出缺少哪一類資訊。
- 如果推薦或提及植物，請使用資料表中的 chinese_name 或 scientific_name。
- plant_ids 只能包含資料表中存在的 plant_id。
- plant_id 必須是字串，並保留前導零，例如 "001"，不可改成 1。
- 不可用中文名或學名代替 plant_id。
- answer 不可出現 plant_id 或編號，例如 "001"、"002"；plant_id 只能放在 JSON 的 plant_ids 欄位。
- 最終回答必須在 answer 內附上這句提醒：{FINAL_REMINDER}
- 只能輸出 JSON，不要輸出 Markdown，不要使用 ```json code block，不要在 JSON 前後加任何說明。

answer 必須使用以下段落格式，並保留換行：
一、推薦植栽
低層植栽：
1. 中文名｜scientific_name

中層植栽：
1. 中文名｜scientific_name

高層植栽：
1. 中文名｜scientific_name

如果某一層級在資料表中沒有合適植物，請在該層寫「目前資料表未找到合適選項」。

二、判斷依據
根據目前資料表，說明以上低層植栽、中層植栽、高層植栽符合哪些條件，例如日照、觀花、花色、葉色、季節表現、配置用途等。

三、設計提醒
{FINAL_REMINDER}

JSON 格式必須完全符合：
{{
  "answer": "一、推薦植栽\\n低層植栽：\\n1. 中文名｜scientific_name\\n\\n中層植栽：\\n1. 中文名｜scientific_name\\n\\n高層植栽：\\n1. 中文名｜scientific_name\\n\\n二、判斷依據\\n根據目前資料表，以上低層植栽、中層植栽、高層植栽符合...\\n\\n三、設計提醒\\n實際配置仍需依基地日照、土壤、排水、維護條件與設計風格確認。",
  "plant_ids": ["001", "002"]
}}

如果找不到合適植物，請回傳：
{{
  "answer": "一、推薦植栽\\n低層植栽：\\n目前資料表未找到合適選項\\n\\n中層植栽：\\n目前資料表未找到合適選項\\n\\n高層植栽：\\n目前資料表未找到合適選項\\n\\n二、判斷依據\\n缺少或不符合的條件是...\\n\\n三、設計提醒\\n{FINAL_REMINDER}",
  "plant_ids": []
}}"""

RELATED_PLANT_COLUMNS = [
    "plant_id",
    "chinese_name",
    "scientific_name",
    "plant_type",
    "light_condition",
    "flower_color",
    "leaf_color",
    "display_type",
    "flower_impact",
]


def load_settings():
    # 從 .env 讀取執行設定，避免把密鑰與 Google Sheet ID 寫死在程式裡。
    load_dotenv()
    return {
        "GOOGLE_SERVICE_ACCOUNT_FILE": os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"),
        "PLANTS_SPREADSHEET_ID": os.getenv("PLANTS_SPREADSHEET_ID"),
        "PLANTS_WORKSHEET_NAME": os.getenv("PLANTS_WORKSHEET_NAME"),
        "DISPLAY_MATRIX_SPREADSHEET_ID": os.getenv("DISPLAY_MATRIX_SPREADSHEET_ID"),
        "DISPLAY_MATRIX_WORKSHEET_NAME": os.getenv("DISPLAY_MATRIX_WORKSHEET_NAME"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    }


def load_google_sheet(spreadsheet_id, worksheet_name, service_account_file):
    # 使用 service account JSON 讀取指定的 Google Sheet worksheet。
    client = gspread.service_account(filename=service_account_file)
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name)

    # 保留儲存格文字格式，避免 plant_id 例如 "001" 被轉成 "1"。
    df = pd.DataFrame(worksheet.get_all_records(numericise_ignore=["all"]))

    if "plant_id" in df.columns:
        df["plant_id"] = df["plant_id"].astype(str).str.strip()

    return df


def build_context(plants_df, display_df):
    # 只把兩張 Google Sheet 資料表提供給模型當作回答依據。
    plants_csv = plants_df.to_csv(index=False)
    display_csv = display_df.to_csv(index=False)
    return (
        "以下是植栽基本資料 plants：\n"
        f"{plants_csv}\n"
        "以下是花期與葉色月份矩陣 display_matrix：\n"
        f"{display_csv}"
    )


def parse_ai_json(raw_text):
    text = _as_text(raw_text)
    cleaned = text.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                data = None
        else:
            data = None

    if not isinstance(data, dict):
        return {"answer": text, "plant_ids": []}

    plant_ids = data.get("plant_ids", [])
    if not isinstance(plant_ids, list):
        plant_ids = []

    return {
        "answer": _as_text(data.get("answer")),
        "plant_ids": [
            _as_text(plant_id)
            for plant_id in plant_ids
            if _as_text(plant_id)
        ],
    }


def ask_ai(question, context, api_key, model, client=None):
    # 透過 prompt 規則限制 AI 只能根據提供的表格資料回答。
    client = client or OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""使用者問題：
{question}

資料表內容：
{context}
""",
            },
        ],
    )
    return parse_ai_json(response.output_text)


def find_missing_settings(settings):
    # 只回報必要但缺少或空白的設定值。
    return [
        name
        for name in REQUIRED_ENV_VARS
        if not _as_text(settings.get(name)).strip()
    ]


def _as_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def find_related_plants(answer, plants_df):
    # AI 會用自然語言回答，所以用表內中文名 / 學名反推相關植栽列。
    answer_text = _as_text(answer).casefold()
    matches = []

    for _, row in plants_df.iterrows():
        chinese_name = _as_text(row.get("chinese_name")).casefold()
        scientific_name = _as_text(row.get("scientific_name")).casefold()
        matches.append(
            bool(chinese_name and chinese_name in answer_text)
            or bool(scientific_name and scientific_name in answer_text)
        )

    return plants_df.loc[matches].copy()


def find_related_plants_by_ids(plant_ids, plants_df):
    if not plant_ids:
        return pd.DataFrame(columns=plants_df.columns)

    clean_ids = {_as_text(plant_id) for plant_id in plant_ids if _as_text(plant_id)}
    plants = plants_df.copy()
    plants["plant_id"] = plants["plant_id"].astype(str).str.strip()

    return plants[plants["plant_id"].isin(clean_ids)].copy()


def hide_internal_id_columns(df):
    return df.drop(columns=["plant_id"], errors="ignore")


def _is_active(value):
    # Google Sheets 的月份標記可能是布林值、數字或文字。
    if pd.isna(value):
        return False
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if not normalized:
            return False
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def _seasonal_symbol(flower_value, leaf_value):
    has_flower = _is_active(flower_value)
    has_leaf = _is_active(leaf_value)

    if has_flower and has_leaf:
        return "🌸🍃"
    if has_flower:
        return "🌸"
    if has_leaf:
        return "🍃"
    return ""


def build_seasonal_matrix(plants_df, display_df):
    # 用文字型 plant_id 精準連接相關植栽與 display_matrix，保留前導零。
    display_rows_by_id = {
        _as_text(row.get("plant_id")): row
        for _, row in display_df.iterrows()
    }
    rows = []

    for _, plant in plants_df.iterrows():
        plant_id = _as_text(plant.get("plant_id"))
        if plant_id not in display_rows_by_id:
            continue

        display_row = display_rows_by_id[plant_id]
        matrix_row = {
            "plant_id": plant_id,
            "植物名稱": _as_text(plant.get("chinese_name")),
        }

        for month_key, month_label in MONTHS.items():
            matrix_row[month_label] = _seasonal_symbol(
                display_row.get(f"flower_{month_key}"),
                display_row.get(f"leaf_{month_key}"),
            )

        rows.append(matrix_row)

    return pd.DataFrame(rows, columns=["plant_id", "植物名稱", *MONTHS.values()])


def render_app():
    # Streamlit 單頁 MVP：提問、回答、相關植栽、季節矩陣與原始資料預覽。
    st.set_page_config(
        page_title="Planting Knowledge Agent｜植栽知識 AI 助理",
        page_icon="🌿",
        layout="wide",
    )
    st.title("Planting Knowledge Agent｜植栽知識 AI 助理")
    st.caption("使用 Google Sheets 作為資料來源，讓 AI 依據植栽資料回答景觀設計問題。")

    settings = load_settings()
    missing_settings = find_missing_settings(settings)
    if missing_settings:
        st.error(f".env 缺少必要設定：{', '.join(missing_settings)}")
        return

    try:
        plants_df = load_google_sheet(
            settings["PLANTS_SPREADSHEET_ID"],
            settings["PLANTS_WORKSHEET_NAME"],
            settings["GOOGLE_SERVICE_ACCOUNT_FILE"],
        )
        display_df = load_google_sheet(
            settings["DISPLAY_MATRIX_SPREADSHEET_ID"],
            settings["DISPLAY_MATRIX_WORKSHEET_NAME"],
            settings["GOOGLE_SERVICE_ACCOUNT_FILE"],
        )
    except gspread.exceptions.WorksheetNotFound:
        st.error("找不到指定的 worksheet，請檢查 WORKSHEET_NAME 是否與 Google Sheet 分頁名稱一致。")
        return
    except Exception as exc:
        st.error("Google Sheet 讀取失敗，請檢查 spreadsheet id、worksheet name，以及 service account 權限。")
        with st.expander("錯誤技術細節", expanded=False):
            st.code(f"{type(exc).__module__}.{type(exc).__name__}: {exc}")
        return

    metric_columns = st.columns(4)
    metric_columns[0].metric("植栽筆數", len(plants_df))
    metric_columns[1].metric("display_matrix 筆數", len(display_df))
    metric_columns[2].metric("OpenAI model", settings["OPENAI_MODEL"])
    metric_columns[3].metric("資料來源", "Google Sheets API")

    question = st.text_area(
        "請輸入你的植栽問題：",
        placeholder="例如：請推薦適合半日照且有季節觀賞性的植栽。",
        height=140,
    )
    ask_clicked = st.button("詢問 AI", type="primary")

    if ask_clicked:
        if not question.strip():
            st.warning("請先輸入問題。")
        else:
            context = build_context(plants_df, display_df)
            try:
                with st.spinner("AI 回答中..."):
                    ai_result = ask_ai(
                        question,
                        context,
                        settings["OPENAI_API_KEY"],
                        settings["OPENAI_MODEL"],
                    )
            except Exception as exc:
                st.error("OpenAI API 呼叫失敗，請檢查 OPENAI_API_KEY 或 OPENAI_MODEL 設定。")
                with st.expander("錯誤技術細節", expanded=False):
                    st.code(f"{type(exc).__module__}.{type(exc).__name__}: {exc}")
            else:
                answer = ai_result.get("answer", "")
                plant_ids = ai_result.get("plant_ids", [])

                st.subheader("AI 回答")
                st.markdown(answer)

                related_plants = find_related_plants_by_ids(plant_ids, plants_df)
                st.subheader("相關植栽資料")
                matched_ids = set(related_plants["plant_id"].tolist()) if not related_plants.empty else set()
                missing_ids = [
                    plant_id
                    for plant_id in plant_ids
                    if plant_id not in matched_ids
                ]
                if missing_ids:
                    st.warning(
                        "AI 回傳的部分 plant_ids 在 plants 資料表中找不到："
                        + ", ".join(missing_ids)
                    )
                if related_plants.empty:
                    st.info("未找到可對應的植栽資料。")
                else:
                    visible_columns = [
                        column
                        for column in RELATED_PLANT_COLUMNS
                        if column in related_plants.columns
                    ]
                    st.dataframe(
                        hide_internal_id_columns(related_plants[visible_columns]),
                        hide_index=True,
                        use_container_width=True,
                    )

                seasonal_matrix = build_seasonal_matrix(related_plants, display_df)
                st.subheader("AI 推薦植栽的季節矩陣")
                st.caption("🌸 = 花期　🍃 = 葉色觀賞期　🌸🍃 = 同時有花期與葉色觀賞")
                if seasonal_matrix.empty:
                    st.info("未找到可對應的季節矩陣資料。")
                else:
                    st.dataframe(
                        hide_internal_id_columns(seasonal_matrix),
                        hide_index=True,
                        use_container_width=True,
                    )

    with st.expander("Google Sheet 原始資料預覽", expanded=False):
        st.subheader("plants")
        st.dataframe(plants_df, hide_index=True, use_container_width=True)
        st.subheader("display_matrix")
        st.dataframe(display_df, hide_index=True, use_container_width=True)


if __name__ == "__main__":
    render_app()
