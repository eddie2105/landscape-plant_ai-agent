# Planting Knowledge Agent Streamlit MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Streamlit MVP where users ask planting questions and receive Google-Sheet-grounded AI answers with related plant rows and a seasonal matrix.

**Architecture:** Keep `test_google_sheet_openai.py` as the existing command-line smoke test. Add `app.py` as the Streamlit app, with core behavior split into focused functions inside the file for the MVP. Add `tests/test_app_core.py` using Python standard-library `unittest` for deterministic logic that does not call Google Sheets or OpenAI.

**Tech Stack:** Python, Streamlit, pandas, python-dotenv, gspread, OpenAI Python SDK, unittest.

---

## File Structure

- Create: `app.py`
  - Streamlit entry point.
  - Contains settings loading, Google Sheet loading, context building, OpenAI call, related plant matching, seasonal matrix generation, and UI rendering.
- Create: `tests/test_app_core.py`
  - Unit tests for pure functions in `app.py`: required setting validation, related plant matching, plant ID preservation, seasonal matrix rendering.
- Keep: `test_google_sheet_openai.py`
  - Existing command-line integration/smoke test. Do not delete it.
- Keep: `requirements.txt`
  - Current dependencies already include Streamlit, pandas, python-dotenv, gspread, google-auth, and OpenAI.

## Task 1: Create Pure Core Tests

**Files:**
- Create: `tests/test_app_core.py`
- Create: `app.py`

- [ ] **Step 1: Write failing tests for settings, plant matching, and seasonal matrix**

Create `tests/test_app_core.py`:

```python
import unittest

import pandas as pd

from app import (
    REQUIRED_ENV_VARS,
    build_seasonal_matrix,
    find_missing_settings,
    find_related_plants,
)


class AppCoreTests(unittest.TestCase):
    def test_find_missing_settings_returns_only_empty_required_values(self):
        settings = {name: "value" for name in REQUIRED_ENV_VARS}
        settings["OPENAI_API_KEY"] = ""
        settings["PLANTS_SPREADSHEET_ID"] = None

        self.assertEqual(
            find_missing_settings(settings),
            ["PLANTS_SPREADSHEET_ID", "OPENAI_API_KEY"],
        )

    def test_find_related_plants_matches_chinese_name_and_scientific_name(self):
        plants_df = pd.DataFrame(
            [
                {
                    "plant_id": "001",
                    "chinese_name": "春不老",
                    "scientific_name": "Ardisia squamulosa",
                },
                {
                    "plant_id": "002",
                    "chinese_name": "厚葉石斑木",
                    "scientific_name": "Rhaphiolepis indica",
                },
                {
                    "plant_id": "003",
                    "chinese_name": "山黃梔",
                    "scientific_name": "Gardenia jasminoides",
                },
            ]
        )
        answer = "可考慮春不老，也可以搭配 Rhaphiolepis indica。"

        related = find_related_plants(answer, plants_df)

        self.assertEqual(related["plant_id"].tolist(), ["001", "002"])

    def test_find_related_plants_preserves_leading_zero_plant_ids(self):
        plants_df = pd.DataFrame(
            [
                {
                    "plant_id": "001",
                    "chinese_name": "春不老",
                    "scientific_name": "Ardisia squamulosa",
                }
            ]
        )

        related = find_related_plants("春不老適合列入候選。", plants_df)

        self.assertEqual(related.iloc[0]["plant_id"], "001")

    def test_build_seasonal_matrix_uses_symbols_for_flower_and_leaf_values(self):
        plants_df = pd.DataFrame(
            [
                {"plant_id": "001", "chinese_name": "春不老"},
                {"plant_id": "002", "chinese_name": "厚葉石斑木"},
            ]
        )
        display_df = pd.DataFrame(
            [
                {
                    "plant_id": "001",
                    "flower_jan": 1,
                    "leaf_jan": 0,
                    "flower_feb": 0,
                    "leaf_feb": 1,
                    "flower_mar": 1,
                    "leaf_mar": 1,
                },
                {
                    "plant_id": "002",
                    "flower_jan": 0,
                    "leaf_jan": 0,
                    "flower_feb": 0,
                    "leaf_feb": 0,
                    "flower_mar": 0,
                    "leaf_mar": 1,
                },
            ]
        )

        matrix = build_seasonal_matrix(plants_df, display_df)

        self.assertEqual(matrix.loc[0, "plant_id"], "001")
        self.assertEqual(matrix.loc[0, "植物名稱"], "春不老")
        self.assertEqual(matrix.loc[0, "1月"], "🌸")
        self.assertEqual(matrix.loc[0, "2月"], "🍃")
        self.assertEqual(matrix.loc[0, "3月"], "🌸🍃")
        self.assertEqual(matrix.loc[1, "1月"], "")
        self.assertEqual(matrix.loc[1, "3月"], "🍃")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Add minimal `app.py` function stubs so imports resolve but tests fail on behavior**

Create `app.py`:

```python
REQUIRED_ENV_VARS = [
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    "PLANTS_SPREADSHEET_ID",
    "PLANTS_WORKSHEET_NAME",
    "DISPLAY_MATRIX_SPREADSHEET_ID",
    "DISPLAY_MATRIX_WORKSHEET_NAME",
    "OPENAI_API_KEY",
]


def find_missing_settings(settings):
    return []


def find_related_plants(answer, plants_df):
    return plants_df.iloc[0:0].copy()


def build_seasonal_matrix(plants_df, display_df):
    return display_df.iloc[0:0].copy()
```

- [ ] **Step 3: Run tests and verify they fail for the expected behavior**

Run:

```powershell
python -m unittest tests.test_app_core -v
```

Expected: FAIL, with assertion failures showing missing settings, related plant matching, and seasonal matrix behavior are not implemented yet.

## Task 2: Implement Core Pure Functions

**Files:**
- Modify: `app.py`
- Test: `tests/test_app_core.py`

- [ ] **Step 1: Implement required setting validation, related matching, and seasonal matrix**

Replace the stub content in `app.py` with:

```python
import os

import pandas as pd
from dotenv import load_dotenv


REQUIRED_ENV_VARS = [
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    "PLANTS_SPREADSHEET_ID",
    "PLANTS_WORKSHEET_NAME",
    "DISPLAY_MATRIX_SPREADSHEET_ID",
    "DISPLAY_MATRIX_WORKSHEET_NAME",
    "OPENAI_API_KEY",
]

MONTHS = [
    ("jan", "1月"),
    ("feb", "2月"),
    ("mar", "3月"),
    ("apr", "4月"),
    ("may", "5月"),
    ("jun", "6月"),
    ("jul", "7月"),
    ("aug", "8月"),
    ("sep", "9月"),
    ("oct", "10月"),
    ("nov", "11月"),
    ("dec", "12月"),
]


def load_settings():
    load_dotenv()
    settings = {
        "GOOGLE_SERVICE_ACCOUNT_FILE": os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"),
        "PLANTS_SPREADSHEET_ID": os.getenv("PLANTS_SPREADSHEET_ID"),
        "PLANTS_WORKSHEET_NAME": os.getenv("PLANTS_WORKSHEET_NAME"),
        "DISPLAY_MATRIX_SPREADSHEET_ID": os.getenv("DISPLAY_MATRIX_SPREADSHEET_ID"),
        "DISPLAY_MATRIX_WORKSHEET_NAME": os.getenv("DISPLAY_MATRIX_WORKSHEET_NAME"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    }
    return settings


def find_missing_settings(settings):
    return [
        name
        for name in REQUIRED_ENV_VARS
        if not str(settings.get(name) or "").strip()
    ]


def _as_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def find_related_plants(answer, plants_df):
    if plants_df.empty:
        return plants_df.copy()

    answer_text = _as_text(answer)
    matched_indexes = []

    for index, row in plants_df.iterrows():
        chinese_name = _as_text(row.get("chinese_name"))
        scientific_name = _as_text(row.get("scientific_name"))
        if chinese_name and chinese_name in answer_text:
            matched_indexes.append(index)
            continue
        if scientific_name and scientific_name in answer_text:
            matched_indexes.append(index)

    return plants_df.loc[matched_indexes].copy()


def _is_active(value):
    if pd.isna(value):
        return False
    if isinstance(value, str):
        return value.strip() in {"1", "true", "True", "TRUE", "yes", "Yes", "YES"}
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
    if plants_df.empty or display_df.empty:
        return pd.DataFrame()

    related_ids = plants_df["plant_id"].astype(str).tolist()
    matrix_source = display_df[display_df["plant_id"].astype(str).isin(related_ids)].copy()
    if matrix_source.empty:
        return pd.DataFrame()

    name_lookup = dict(
        zip(
            plants_df["plant_id"].astype(str),
            plants_df["chinese_name"].astype(str),
        )
    )
    rows = []

    for _, source_row in matrix_source.iterrows():
        plant_id = _as_text(source_row.get("plant_id"))
        row = {
            "plant_id": plant_id,
            "植物名稱": name_lookup.get(plant_id, ""),
        }
        for month_key, month_label in MONTHS:
            row[month_label] = _seasonal_symbol(
                source_row.get(f"flower_{month_key}", 0),
                source_row.get(f"leaf_{month_key}", 0),
            )
        rows.append(row)

    return pd.DataFrame(rows)
```

- [ ] **Step 2: Run core unit tests and verify they pass**

Run:

```powershell
python -m unittest tests.test_app_core -v
```

Expected: PASS for all 4 tests.

## Task 3: Add Google Sheet Loading and Context Building

**Files:**
- Modify: `app.py`
- Test: `tests/test_app_core.py`

- [ ] **Step 1: Add tests for context text preserving plant IDs**

Append this test method inside `AppCoreTests` in `tests/test_app_core.py`:

```python
    def test_build_context_includes_both_tables_and_preserves_plant_id_text(self):
        from app import build_context

        plants_df = pd.DataFrame(
            [{"plant_id": "001", "chinese_name": "春不老"}]
        )
        display_df = pd.DataFrame(
            [{"plant_id": "001", "flower_jan": 1, "leaf_jan": 0}]
        )

        context = build_context(plants_df, display_df)

        self.assertIn("以下是植栽基本資料 plants：", context)
        self.assertIn("以下是花期與葉色月份矩陣 display_matrix：", context)
        self.assertIn("001", context)
        self.assertIn("春不老", context)
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```powershell
python -m unittest tests.test_app_core.AppCoreTests.test_build_context_includes_both_tables_and_preserves_plant_id_text -v
```

Expected: ERROR or FAIL because `build_context` is not implemented yet.

- [ ] **Step 3: Implement Google Sheet loading and context building**

Add these imports near the top of `app.py`:

```python
import gspread
```

Add these functions below `find_missing_settings`:

```python
def load_google_sheet(spreadsheet_id, worksheet_name, service_account_file):
    gc = gspread.service_account(filename=service_account_file)
    spreadsheet = gc.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name)
    records = worksheet.get_all_records()
    df = pd.DataFrame(records)
    if "plant_id" in df.columns:
        df["plant_id"] = df["plant_id"].astype(str).str.strip()
    return df


def build_context(plants_df, display_df):
    plants_text = plants_df.to_csv(index=False)
    display_text = display_df.to_csv(index=False)

    return f"""
以下是植栽基本資料 plants：

{plants_text}

以下是花期與葉色月份矩陣 display_matrix：

{display_text}
"""
```

- [ ] **Step 4: Run all core tests**

Run:

```powershell
python -m unittest tests.test_app_core -v
```

Expected: PASS for all tests.

## Task 4: Add OpenAI Answer Function

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add OpenAI imports and prompt constants**

Add this import near the top of `app.py`:

```python
from openai import OpenAI
```

Add this constant after `MONTHS`:

```python
FINAL_REMINDER = "實際配置仍需依基地日照、土壤、排水、維護條件與設計風格確認。"

SYSTEM_PROMPT = f"""
你是一位景觀植栽知識助理。
只能根據提供的 Google Sheet 資料回答。
不可以使用外部知識或自行補充資料表沒有的資訊。
如果資料不足，請說明目前資料表不足以判斷，並指出缺少哪類資料。
回答必須使用台灣繁體中文。
如果推薦或提到植物，請使用資料表中的 chinese_name 或 scientific_name。
回答最後必須加上：
{FINAL_REMINDER}
"""
```

- [ ] **Step 2: Add `ask_ai` implementation**

Add this function below `build_context`:

```python
def ask_ai(question, context, api_key, model):
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""
使用者問題：
{question}

資料表內容：
{context}
""",
            },
        ],
    )
    return response.output_text
```

- [ ] **Step 3: Run syntax check**

Run:

```powershell
python -m py_compile app.py
```

Expected: exit code 0.

## Task 5: Build Streamlit UI

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add Streamlit import and display columns**

Add this import near the top of `app.py`:

```python
import streamlit as st
```

Add this constant after `SYSTEM_PROMPT`:

```python
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
```

- [ ] **Step 2: Add `render_app` implementation**

Add this function near the bottom of `app.py`:

```python
def render_app():
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
        st.error(".env 缺少必要設定：" + ", ".join(missing_settings))
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
    except Exception:
        st.error("Google Sheet 讀取失敗，請檢查 spreadsheet id、worksheet name，以及 service account 權限。")
        return

    metric_cols = st.columns(4)
    metric_cols[0].metric("植栽筆數", len(plants_df))
    metric_cols[1].metric("display_matrix 筆數", len(display_df))
    metric_cols[2].metric("OpenAI model", settings["OPENAI_MODEL"])
    metric_cols[3].metric("資料來源", "Google Sheets API")

    question = st.text_area(
        "請輸入你的植栽問題：",
        placeholder="例如：請推薦適合半日照且有季節觀賞性的植栽。",
        height=140,
    )

    if st.button("詢問 AI", type="primary"):
        if not question.strip():
            st.warning("請先輸入問題。")
            return

        context = build_context(plants_df, display_df)
        with st.spinner("AI 回答中..."):
            try:
                answer = ask_ai(
                    question,
                    context,
                    settings["OPENAI_API_KEY"],
                    settings["OPENAI_MODEL"],
                )
            except Exception:
                st.error("OpenAI API 呼叫失敗，請檢查 OPENAI_API_KEY 或 OPENAI_MODEL 設定。")
                return

        st.subheader("AI 回答")
        st.write(answer)

        related_plants_df = find_related_plants(answer, plants_df)

        st.subheader("相關植栽資料")
        if related_plants_df.empty:
            st.info("未找到可對應的植栽資料。")
        else:
            visible_columns = [
                column
                for column in RELATED_PLANT_COLUMNS
                if column in related_plants_df.columns
            ]
            st.dataframe(
                related_plants_df[visible_columns],
                use_container_width=True,
                hide_index=True,
            )

            seasonal_matrix_df = build_seasonal_matrix(related_plants_df, display_df)
            st.subheader("AI 提及植栽的季節矩陣")
            st.caption("🌸 = 花期　🍃 = 葉色觀賞期　🌸🍃 = 同時有花期與葉色觀賞")
            if seasonal_matrix_df.empty:
                st.info("未找到可對應的季節矩陣資料。")
            else:
                st.dataframe(
                    seasonal_matrix_df,
                    use_container_width=True,
                    hide_index=True,
                )

    with st.expander("Google Sheet 原始資料預覽", expanded=False):
        st.subheader("plants")
        st.dataframe(plants_df, use_container_width=True, hide_index=True)
        st.subheader("display_matrix")
        st.dataframe(display_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    render_app()
```

- [ ] **Step 3: Run syntax check**

Run:

```powershell
python -m py_compile app.py
```

Expected: exit code 0.

## Task 6: Verify Locally

**Files:**
- Modify only if verification reveals a defect: `app.py` or `tests/test_app_core.py`

- [ ] **Step 1: Run unit tests**

Run:

```powershell
python -m unittest tests.test_app_core -v
```

Expected: all tests pass.

- [ ] **Step 2: Run syntax checks**

Run:

```powershell
python -m py_compile app.py test_google_sheet_openai.py
```

Expected: exit code 0.

- [ ] **Step 3: Start Streamlit app**

Run:

```powershell
streamlit run app.py
```

Expected: Streamlit starts and prints a local URL.

- [ ] **Step 4: Manual smoke test in browser**

Open the Streamlit URL and verify:

- Header says `Planting Knowledge Agent｜植栽知識 AI 助理`.
- Status cards show plant count, display matrix count, model, and data source.
- Bottom `Google Sheet 原始資料預覽` expander is collapsed by default.
- Asking a question returns a Taiwan Traditional Chinese answer.
- If the answer mentions a known `chinese_name` or `scientific_name`, related plant rows appear.
- `plant_id` values such as `001` keep their leading zeros.
- Seasonal matrix shows `🌸`, `🍃`, or `🌸🍃`.

- [ ] **Step 5: Stop Streamlit after verification**

Press `Ctrl+C` in the Streamlit terminal.

Expected: server stops cleanly.

## Task 7: Optional Cleanup After MVP Works

**Files:**
- Modify: `.gitignore`
- Do not modify if `.superpowers/` should remain visible for brainstorming artifacts.

- [ ] **Step 1: Decide whether to ignore visual brainstorming artifacts**

If the team does not want browser companion files tracked, add this line to `.gitignore`:

```gitignore
.superpowers/
```

- [ ] **Step 2: Check Git status only after repository issue is resolved**

Run:

```powershell
git status --short
```

Expected: Git works after repository setup is repaired. If it still says this is not a Git repository, skip commit steps until the repo is fixed.

