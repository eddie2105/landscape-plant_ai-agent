# Streamlit Forest Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the existing Streamlit app into a natural forest-style dashboard without changing Google Sheets, OpenAI, plant matching, or seasonal matrix behavior.

**Architecture:** Keep the implementation in `app.py` and add small helper functions for CSS and reusable HTML snippets so the visual layer can be tested. Keep Streamlit native components for dataframes, text input, buttons, expanders, and status messages. Update `render_app()` to use a left control column and a right results area while preserving the existing data flow.

**Tech Stack:** Python, Streamlit, pandas, unittest, scoped CSS injected through `st.markdown()`.

---

## File Structure

- Modify: `app.py`
  - Add dashboard CSS helper.
  - Add HTML helper functions for safe dashboard cards and metric cards.
  - Refactor `render_app()` into a forest dashboard layout.
- Modify: `tests/test_app_core.py`
  - Add tests for CSS palette, safe card rendering, and metric card HTML.

## Task 1: Add Testable Dashboard Presentation Helpers

**Files:**
- Modify: `tests/test_app_core.py`
- Modify: `app.py`

- [ ] **Step 1: Write failing tests for dashboard CSS and card helpers**

Modify the import block in `tests/test_app_core.py` to include:

```python
from app import (
    DASHBOARD_CSS,
    REQUIRED_ENV_VARS,
    SYSTEM_PROMPT,
    dashboard_card,
    metric_card,
    ask_ai,
    build_context,
    build_seasonal_matrix,
    find_missing_settings,
    find_related_plants,
    find_related_plants_by_ids,
    hide_internal_id_columns,
    parse_ai_json,
)
```

Add these tests inside `AppCoreTests`:

```python
    def test_dashboard_css_uses_forest_palette_and_card_classes(self):
        self.assertIn("#0f1f1a", DASHBOARD_CSS)
        self.assertIn("#1d332a", DASHBOARD_CSS)
        self.assertIn("#9bd86f", DASHBOARD_CSS)
        self.assertIn(".forest-card", DASHBOARD_CSS)
        self.assertIn(".forest-metric", DASHBOARD_CSS)

    def test_dashboard_card_escapes_content_and_adds_title(self):
        html = dashboard_card("AI 回答", "<script>alert('x')</script>")

        self.assertIn("AI 回答", html)
        self.assertIn("&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("forest-card", html)

    def test_metric_card_escapes_value_and_label(self):
        html = metric_card("資料來源", "<Google Sheets>")

        self.assertIn("資料來源", html)
        self.assertIn("&lt;Google Sheets&gt;", html)
        self.assertIn("forest-metric", html)
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_app_core.AppCoreTests.test_dashboard_css_uses_forest_palette_and_card_classes tests.test_app_core.AppCoreTests.test_dashboard_card_escapes_content_and_adds_title tests.test_app_core.AppCoreTests.test_metric_card_escapes_value_and_label -v
```

Expected: fail or error because `DASHBOARD_CSS`, `dashboard_card`, and `metric_card` do not exist yet.

- [ ] **Step 3: Implement the presentation helpers**

Add this import near the top of `app.py`:

```python
from html import escape
```

Add this constant after `RELATED_PLANT_COLUMNS`:

```python
DASHBOARD_CSS = """
<style>
:root {
    --forest-bg: #0f1f1a;
    --forest-bg-soft: #132820;
    --forest-card: #1d332a;
    --forest-card-2: #223b31;
    --forest-line: rgba(155, 216, 111, 0.18);
    --forest-text: #f2f7f0;
    --forest-muted: #aebcaf;
    --forest-accent: #9bd86f;
    --forest-accent-2: #d6e879;
}

.stApp {
    background:
        radial-gradient(circle at 18% 8%, rgba(155, 216, 111, 0.12), transparent 28%),
        linear-gradient(135deg, #0b1714 0%, var(--forest-bg) 46%, #10241d 100%);
    color: var(--forest-text);
}

.block-container {
    padding-top: 2.2rem;
    padding-bottom: 3rem;
    max-width: 1380px;
}

h1, h2, h3 {
    color: var(--forest-text);
    letter-spacing: 0;
}

[data-testid="stCaptionContainer"],
.stMarkdown p {
    color: var(--forest-muted);
}

.forest-header {
    border: 1px solid var(--forest-line);
    background: rgba(29, 51, 42, 0.72);
    border-radius: 18px;
    padding: 1.25rem 1.4rem;
    box-shadow: 0 18px 60px rgba(0, 0, 0, 0.22);
    margin-bottom: 1rem;
}

.forest-kicker {
    color: var(--forest-accent-2);
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 0.35rem;
}

.forest-title {
    color: var(--forest-text);
    font-size: clamp(2rem, 4vw, 3.4rem);
    font-weight: 800;
    line-height: 1.08;
    margin: 0;
}

.forest-subtitle {
    color: var(--forest-muted);
    margin-top: 0.7rem;
    font-size: 1rem;
}

.forest-card {
    border: 1px solid var(--forest-line);
    background: rgba(29, 51, 42, 0.88);
    border-radius: 16px;
    padding: 1rem 1.1rem;
    box-shadow: 0 14px 36px rgba(0, 0, 0, 0.2);
    margin-bottom: 1rem;
}

.forest-card-title {
    color: var(--forest-accent);
    font-size: 0.95rem;
    font-weight: 800;
    margin-bottom: 0.55rem;
}

.forest-card-body {
    color: var(--forest-text);
}

.forest-metric {
    border: 1px solid var(--forest-line);
    background: linear-gradient(180deg, rgba(34, 59, 49, 0.94), rgba(29, 51, 42, 0.94));
    border-radius: 14px;
    padding: 0.9rem 1rem;
    min-height: 5.25rem;
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.18);
}

.forest-metric-label {
    color: var(--forest-muted);
    font-size: 0.8rem;
    margin-bottom: 0.35rem;
}

.forest-metric-value {
    color: var(--forest-accent);
    font-size: 1.35rem;
    font-weight: 800;
}

.stTextArea textarea {
    background: rgba(15, 31, 26, 0.82);
    color: var(--forest-text);
    border: 1px solid var(--forest-line);
    border-radius: 14px;
}

.stButton > button {
    background: linear-gradient(135deg, var(--forest-accent), var(--forest-accent-2));
    color: #102018;
    border: 0;
    border-radius: 999px;
    font-weight: 800;
    padding: 0.65rem 1.2rem;
}

[data-testid="stDataFrame"] {
    border: 1px solid var(--forest-line);
    border-radius: 14px;
    overflow: hidden;
}
</style>
"""
```

Add these helper functions after `DASHBOARD_CSS`:

```python
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
```

- [ ] **Step 4: Run all core tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_app_core -v
```

Expected: all tests pass.

- [ ] **Step 5: Run syntax check**

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py
```

Expected: exit code 0.

## Task 2: Apply Forest Dashboard Layout To Streamlit Page

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Inject CSS and replace plain header with forest header**

Inside `render_app()`, immediately after `st.set_page_config(...)`, add:

```python
    inject_dashboard_css()
```

Replace the existing `st.title(...)` and `st.caption(...)` calls with:

```python
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
```

- [ ] **Step 2: Replace Streamlit metric widgets with dashboard metric cards**

Replace:

```python
    metric_columns = st.columns(4)
    metric_columns[0].metric("植栽筆數", len(plants_df))
    metric_columns[1].metric("display_matrix 筆數", len(display_df))
    metric_columns[2].metric("OpenAI model", settings["OPENAI_MODEL"])
    metric_columns[3].metric("資料來源", "Google Sheets API")
```

with:

```python
    metric_columns = st.columns(4)
    metric_columns[0].markdown(metric_card("植栽筆數", len(plants_df)), unsafe_allow_html=True)
    metric_columns[1].markdown(metric_card("display_matrix 筆數", len(display_df)), unsafe_allow_html=True)
    metric_columns[2].markdown(metric_card("OpenAI model", settings["OPENAI_MODEL"]), unsafe_allow_html=True)
    metric_columns[3].markdown(metric_card("資料來源", "Google Sheets API"), unsafe_allow_html=True)
```

- [ ] **Step 3: Create left question column and right result column**

Replace the current question input section:

```python
    question = st.text_area(
        "請輸入你的植栽問題：",
        placeholder="例如：請推薦適合半日照且有季節觀賞性的植栽。",
        height=140,
    )
    ask_clicked = st.button("詢問 AI", type="primary")

    if ask_clicked:
        ...
```

with:

```python
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
            "請輸入你的植栽問題：",
            placeholder="例如：請推薦適合半日照且有季節觀賞性的植栽。",
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
            ...
        else:
            st.markdown(
                dashboard_card(
                    "AI 回答",
                    "輸入植栽或景觀設計問題後，這裡會顯示依據 Google Sheet 產生的回答。",
                ),
                unsafe_allow_html=True,
            )
```

Move the existing `if ask_clicked:` block into the `with result_col:` block. Keep the existing logic inside it unchanged except for the wrapper updates in later steps.

- [ ] **Step 4: Wrap answer and result sections with forest card markers**

Inside the successful AI response branch, replace:

```python
                st.subheader("AI 回答")
                st.markdown(answer)
```

with:

```python
                st.markdown('<div class="forest-card">', unsafe_allow_html=True)
                st.markdown('<div class="forest-card-title">AI 回答</div>', unsafe_allow_html=True)
                st.markdown(answer)
                st.markdown("</div>", unsafe_allow_html=True)
```

Replace:

```python
                st.subheader("相關植栽資料")
```

with:

```python
                st.markdown('<div class="forest-card">', unsafe_allow_html=True)
                st.markdown('<div class="forest-card-title">相關植栽資料</div>', unsafe_allow_html=True)
```

After the related plants dataframe or empty info message block, add:

```python
                st.markdown("</div>", unsafe_allow_html=True)
```

Replace:

```python
                st.subheader("AI 推薦植栽的季節矩陣")
                st.caption("🌸 = 花期　🍃 = 葉色觀賞期　🌸🍃 = 同時有花期與葉色觀賞")
```

with:

```python
                st.markdown('<div class="forest-card">', unsafe_allow_html=True)
                st.markdown('<div class="forest-card-title">AI 推薦植栽的季節矩陣</div>', unsafe_allow_html=True)
                st.caption("🌸 = 花期　🍃 = 葉色觀賞期　🌸🍃 = 同時有花期與葉色觀賞")
```

After the seasonal matrix dataframe or empty info message block, add:

```python
                st.markdown("</div>", unsafe_allow_html=True)
```

- [ ] **Step 5: Keep raw data preview collapsed at the bottom**

Leave this block at the root level of `render_app()`, after the two-column layout:

```python
    with st.expander("Google Sheet 原始資料預覽", expanded=False):
        st.subheader("plants")
        st.dataframe(plants_df, hide_index=True, use_container_width=True)
        st.subheader("display_matrix")
        st.dataframe(display_df, hide_index=True, use_container_width=True)
```

Do not move it inside `control_col` or `result_col`.

- [ ] **Step 6: Run tests and syntax check**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_app_core -v
.\.venv\Scripts\python.exe -m py_compile app.py
```

Expected: tests pass and compile succeeds.

## Task 3: Verify Streamlit App Manually

**Files:**
- Modify only if verification reveals a defect: `app.py` or `tests/test_app_core.py`

- [ ] **Step 1: Run non-network verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_app_core -v
.\.venv\Scripts\python.exe -m py_compile app.py test_google_sheet_openai.py connection_checks.py
```

Expected: tests pass and compile succeeds.

- [ ] **Step 2: Start Streamlit**

Run:

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

Expected: Streamlit starts at `http://localhost:8501`.

- [ ] **Step 3: Browser smoke check**

Open:

```text
http://localhost:8501
```

Verify:

- The page uses the dark forest palette.
- Header appears in a forest dashboard block.
- Four metric cards are visible.
- Left column contains the question input and ask button.
- Right column shows the empty AI answer placeholder before asking.
- After asking a valid question, the AI answer, related plants, and seasonal matrix appear as distinct dashboard sections.
- `Google Sheet 原始資料預覽` remains collapsed by default.
- No `plant_id` appears in the displayed user-facing dataframes.

- [ ] **Step 4: Stop Streamlit**

Press `Ctrl+C` in the Streamlit terminal.

Expected: server stops cleanly.

## Task 4: Commit Visual Refresh

**Files:**
- Modify: `app.py`
- Modify: `tests/test_app_core.py`

- [ ] **Step 1: Review git diff**

Run:

```powershell
git diff -- app.py tests/test_app_core.py
```

Expected: diff only contains dashboard CSS/helpers, tests for helpers, and layout changes.

- [ ] **Step 2: Stage files**

Run:

```powershell
git add app.py tests/test_app_core.py
```

- [ ] **Step 3: Commit**

Run:

```powershell
git commit -m "feat: add forest dashboard styling"
```

Expected: commit succeeds.

