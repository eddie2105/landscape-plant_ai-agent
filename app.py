import json
import os
from html import escape

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

DASHBOARD_CSS = """
<style>
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(184, 199, 178, 0.16), transparent 28rem),
            linear-gradient(135deg, #2f3d38 0%, #3f4f49 52%, #51635b 100%);
        color: #f1f0ea;
    }

    .forest-header {
        background:
            linear-gradient(135deg, rgba(111, 129, 120, 0.96), rgba(81, 99, 91, 0.92)),
            #6f8178;
        border: 1px solid rgba(184, 199, 178, 0.26);
        border-radius: 8px;
        box-shadow: 0 24px 60px rgba(37, 46, 42, 0.28);
        margin: 0.5rem 0 1.1rem;
        min-height: 13rem;
        padding: 2rem;
    }

    .forest-kicker {
        color: #d7ddcf;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0;
        margin-bottom: 0.75rem;
        text-transform: uppercase;
    }

    .forest-title {
        color: #f1f0ea;
        font-size: 2.5rem;
        font-weight: 900;
        letter-spacing: 0;
        line-height: 1.12;
        margin: 0;
        max-width: 56rem;
    }

    .forest-subtitle {
        color: #e0e1da;
        font-size: 1rem;
        line-height: 1.7;
        margin-top: 1rem;
        max-width: 42rem;
    }

    .forest-card {
        background: rgba(81, 99, 91, 0.92);
        border: 1px solid rgba(184, 199, 178, 0.24);
        border-radius: 8px;
        box-shadow: 0 18px 40px rgba(37, 46, 42, 0.24);
        color: #f1f0ea;
        margin: 0.75rem 0;
        padding: 1rem 1.1rem;
    }

    .forest-card-title {
        color: #d7ddcf;
        font-size: 0.9rem;
        font-weight: 700;
        letter-spacing: 0;
        margin-bottom: 0.45rem;
    }

    .forest-card-body {
        color: #ecebe4;
        line-height: 1.65;
        white-space: pre-wrap;
    }

    .forest-section-title {
        background: rgba(81, 99, 91, 0.92);
        border: 1px solid rgba(184, 199, 178, 0.24);
        border-radius: 8px;
        color: #d7ddcf;
        font-size: 0.9rem;
        font-weight: 800;
        letter-spacing: 0;
        margin: 0.85rem 0 0.45rem;
        padding: 0.75rem 1rem;
    }

    .forest-metric {
        background: rgba(47, 61, 56, 0.9);
        border: 1px solid rgba(184, 199, 178, 0.28);
        border-radius: 8px;
        min-height: 5.5rem;
        padding: 0.85rem 1rem;
    }

    .forest-metric-label {
        color: #c8d0c4;
        font-size: 0.82rem;
        font-weight: 600;
        letter-spacing: 0;
        margin-bottom: 0.35rem;
    }

    .forest-metric-value {
        color: #d7ddcf;
        font-size: 1.35rem;
        font-weight: 800;
        line-height: 1.2;
        overflow-wrap: anywhere;
    }

    div[data-testid="stTextArea"] textarea {
        background: rgba(47, 61, 56, 0.86);
        border-color: rgba(184, 199, 178, 0.42);
        color: #f1f0ea;
    }

    div[data-testid="stTextArea"] textarea:focus {
        border-color: #b8c7b2;
        box-shadow: 0 0 0 1px #b8c7b2;
    }

    .stButton > button[kind="primary"] {
        background: #b8c7b2;
        border-color: #b8c7b2;
        color: #2f3d38;
        font-weight: 800;
    }

    .stButton > button[kind="primary"]:hover {
        background: #d7ddcf;
        border-color: #d7ddcf;
        color: #2f3d38;
    }

    div[data-testid="stDataFrame"],
    div[data-testid="stDataFrameResizable"] {
        background: rgba(47, 61, 56, 0.72);
        border: 1px solid rgba(184, 199, 178, 0.18);
        border-radius: 8px;
        overflow: hidden;
    }
</style>
"""


def inject_dashboard_css():
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)


def dashboard_card(title, body):
    return (
        '<div class="forest-card">'
        f'<div class="forest-card-title">{escape(str(title))}</div>'
        f'<div class="forest-card-body">{escape(str(body))}</div>'
        '</div>'
    )


def metric_card(label, value):
    return (
        '<div class="forest-metric">'
        f'<div class="forest-metric-label">{escape(str(label))}</div>'
        f'<div class="forest-metric-value">{escape(str(value))}</div>'
        '</div>'
    )


def dashboard_section_title(title):
    return f'<div class="forest-section-title">{escape(str(title))}</div>'


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
    # Streamlit 單頁 MVP：提問、回答、相關植栽、季節矩陣與資料預覽。
    st.set_page_config(
        page_title="Planting Knowledge Agent｜植栽知識 AI 助理",
        page_icon="🌿",
        layout="wide",
    )
    inject_dashboard_css()
    st.markdown(
        """
        <section class="forest-header">
            <div class="forest-kicker">Google Sheets Grounded Plant Agent</div>
            <h1 class="forest-title">Planting Knowledge Agent｜植栽知識 AI 助理</h1>
            <div class="forest-subtitle">使用 Google Sheets 作為資料來源，讓 AI 依據植栽資料回答景觀設計問題。</div>
        </section>
        """,
        unsafe_allow_html=True,
    )

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
        st.error("找不到指定的 worksheet，請確認 WORKSHEET_NAME 是否存在於 Google Sheet。")
        return
    except Exception as exc:
        st.error("Google Sheet 讀取失敗，請確認 spreadsheet id、worksheet name，以及 service account 設定。")
        with st.expander("錯誤技術細節", expanded=False):
            st.code(f"{type(exc).__module__}.{type(exc).__name__}: {exc}")
        return

    metric_columns = st.columns(4)
    metric_columns[0].markdown(metric_card("植栽筆數", len(plants_df)), unsafe_allow_html=True)
    metric_columns[1].markdown(metric_card("display_matrix 筆數", len(display_df)), unsafe_allow_html=True)
    metric_columns[2].markdown(metric_card("OpenAI model", settings["OPENAI_MODEL"]), unsafe_allow_html=True)
    metric_columns[3].markdown(metric_card("資料來源", "Google Sheets API"), unsafe_allow_html=True)

    control_col, result_col = st.columns([0.34, 0.66], gap="large")

    with control_col:
        st.markdown(
            dashboard_card(
                "提問控制台",
                "AI 會根據 Google Sheet 裡的 plants 與 display_matrix 回答。",
            ),
            unsafe_allow_html=True,
        )
        question = st.text_area(
            "請輸入植栽或景觀設計問題",
            placeholder="例如：請推薦適合半日照、四季有觀賞效果的植栽。",
            height=180,
        )
        ask_clicked = st.button("詢問 AI", type="primary", use_container_width=True)
        st.markdown(
            dashboard_card(
                "資料狀態",
                f"目前模型：{settings['OPENAI_MODEL']}｜資料來源：Google Sheets API",
            ),
            unsafe_allow_html=True,
        )

    with result_col:
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
                    st.error("OpenAI API 呼叫失敗，請確認 OPENAI_API_KEY 與 OPENAI_MODEL 設定。")
                    with st.expander("錯誤技術細節", expanded=False):
                        st.code(f"{type(exc).__module__}.{type(exc).__name__}: {exc}")
                else:
                    answer = ai_result.get("answer", "")
                    plant_ids = ai_result.get("plant_ids", [])

                    st.markdown(dashboard_section_title("AI 回答"), unsafe_allow_html=True)
                    st.markdown(answer)

                    related_plants = find_related_plants_by_ids(plant_ids, plants_df)
                    st.markdown(dashboard_section_title("相關植栽資料"), unsafe_allow_html=True)
                    matched_ids = set(related_plants["plant_id"].tolist()) if not related_plants.empty else set()
                    missing_ids = [
                        plant_id
                        for plant_id in plant_ids
                        if plant_id not in matched_ids
                    ]
                    if missing_ids:
                        st.warning(
                            "AI 回傳的部分 plant_ids 在 plants 資料中找不到："
                            + ", ".join(missing_ids)
                        )
                    if related_plants.empty:
                        st.info("沒有找到可對應的相關植栽資料。")
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
                    st.markdown(dashboard_section_title("AI 推薦植栽的季節矩陣"), unsafe_allow_html=True)
                    st.caption("🌸 = 花期　🍃 = 葉色觀賞期　🌸🍃 = 同時有花期與葉色觀賞")
                    if seasonal_matrix.empty:
                        st.info("沒有找到可對應的季節矩陣資料。")
                    else:
                        st.dataframe(
                            hide_internal_id_columns(seasonal_matrix),
                            hide_index=True,
                            use_container_width=True,
                        )
        else:
            st.markdown(
                dashboard_card(
                    "AI 回答",
                    "輸入植栽或景觀設計問題後，這裡會顯示依據 Google Sheet 產生的回答。",
                ),
                unsafe_allow_html=True,
            )

    with st.expander("Google Sheet 原始資料預覽", expanded=False):
        st.subheader("plants")
        st.dataframe(hide_internal_id_columns(plants_df), hide_index=True, use_container_width=True)
        st.subheader("display_matrix")
        st.dataframe(hide_internal_id_columns(display_df), hide_index=True, use_container_width=True)


if __name__ == "__main__":
    render_app()
