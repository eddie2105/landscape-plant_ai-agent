# Planting Knowledge Agent Streamlit MVP Design

## Goal

Build a Stage 1 Streamlit MVP named:

```text
Planting Knowledge Agent｜植栽知識 AI 助理
```

The app lets a user ask planting or landscape design questions. It reads plant data from Google Sheets, asks OpenAI to answer using only that Google Sheet data, then displays the answer, related plant rows, and a seasonal display matrix.

This MVP is not a traditional search/filter tool. The main experience is a question-and-answer flow grounded in the spreadsheet data.

## Confirmed Product Decisions

- Layout: single-column report style.
- Implementation direction: keep `test_google_sheet_openai.py` as a command-line API test, and add a Streamlit `app.py`.
- App structure: use clear functions in `app.py` first; do not split into many modules yet.
- AI answer format: natural language, not JSON.
- AI data rule: answer only from the provided Google Sheet data.
- Related plant matching: match AI answer text against `chinese_name` and `scientific_name`.
- `plant_id` format: preserve Google Sheet values exactly, such as `001`, `002`; do not add prefixes like `P001`.
- Insufficient data response: explain that the table is insufficient and mention the missing information type.
- Seasonal matrix symbols: use `🌸`, `🍃`, and `🌸🍃`.
- Final reminder: always append `實際配置仍需依基地日照、土壤、排水、維護條件與設計風格確認。`
- Google Sheet raw data preview: show in a collapsed Streamlit expander.

## Data Sources

The app reads two Google Sheets through `gspread` and a service account.

### plants

Environment variables:

```env
PLANTS_SPREADSHEET_ID=...
PLANTS_WORKSHEET_NAME=plants
```

Expected columns:

```text
plant_id
chinese_name
scientific_name
plant_type
light_condition
flower_color
flower_color_group
leaf_color
leaf_color_group
display_type
flower_impact
has_seasonal_image
```

### display_matrix

Environment variables:

```env
DISPLAY_MATRIX_SPREADSHEET_ID=...
DISPLAY_MATRIX_WORKSHEET_NAME=display_matrix
```

Expected columns:

```text
plant_id
flower_jan
flower_feb
flower_mar
flower_apr
flower_may
flower_jun
flower_jul
flower_aug
flower_sep
flower_oct
flower_nov
flower_dec
leaf_jan
leaf_feb
leaf_mar
leaf_apr
leaf_may
leaf_jun
leaf_jul
leaf_aug
leaf_sep
leaf_oct
leaf_nov
leaf_dec
```

`plant_id` connects `plants` and `display_matrix`.

## Environment Variables

The app reads configuration from `.env`:

```env
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/service_account.json

PLANTS_SPREADSHEET_ID=...
PLANTS_WORKSHEET_NAME=plants

DISPLAY_MATRIX_SPREADSHEET_ID=...
DISPLAY_MATRIX_WORKSHEET_NAME=display_matrix

OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
```

## Architecture

Keep the existing command-line test file:

```text
test_google_sheet_openai.py
```

Add the Streamlit app:

```text
app.py
```

Initial `app.py` functions:

```text
load_settings()
load_google_sheet()
build_context()
ask_ai()
find_related_plants()
build_seasonal_matrix()
render_app()
```

Data flow:

```text
.env
→ Google Sheets API reads plants and display_matrix
→ User enters a question
→ OpenAI answers using only the Google Sheet context
→ App matches chinese_name/scientific_name in the answer
→ App gets exact plant_id values from plants
→ App filters display_matrix by plant_id
→ App renders answer, related plants, seasonal matrix, and raw data preview
```

## AI Prompt Design

The OpenAI call receives:

- user question
- CSV-style text context from `plants`
- CSV-style text context from `display_matrix`

System prompt requirements:

```text
你是一位景觀植栽知識助理。
只能根據提供的 Google Sheet 資料回答。
不可以使用外部知識或自行補充資料表沒有的資訊。
如果資料不足，請說明目前資料表不足以判斷，並指出缺少哪類資料。
回答必須使用台灣繁體中文。
如果推薦或提到植物，請使用資料表中的 chinese_name 或 scientific_name。
回答最後必須加上：
實際配置仍需依基地日照、土壤、排水、維護條件與設計風格確認。
```

The AI returns natural-language text. The app does not require JSON.

If data is insufficient, the answer should follow this style:

```text
目前資料表不足以判斷，因為資料表中沒有提供耐旱性或高度資訊。
實際配置仍需依基地日照、土壤、排水、維護條件與設計風格確認。
```

## Related Plant Matching

After the AI answer is returned, the app searches the answer text for each row's:

- `chinese_name`
- `scientific_name`

If either value appears in the answer, that row is related.

The app preserves `plant_id` exactly as it appears in Google Sheets. For example:

```text
001
002
```

It must not convert these to numbers or add prefixes such as:

```text
P001
P002
```

Related plant columns shown in the app:

```text
plant_id
chinese_name
scientific_name
plant_type
light_condition
flower_color
leaf_color
display_type
flower_impact
```

If no related plants are found:

```text
未找到可對應的植栽資料。
```

## Seasonal Matrix

The seasonal matrix filters `display_matrix` by the related `plant_id` values.

Months are shown from 1 to 12.

Cell rendering:

```text
flower_month = 1 and leaf_month = 1 → 🌸🍃
flower_month = 1 → 🌸
leaf_month = 1 → 🍃
otherwise → empty string
```

Legend:

```text
🌸 = 花期
🍃 = 葉色觀賞期
🌸🍃 = 同時有花期與葉色觀賞
```

If no related plants are found, the seasonal matrix is not shown or shows the same no-related-plant message.

## Streamlit Page Layout

Single-column report-style layout:

```text
Planting Knowledge Agent｜植栽知識 AI 助理
使用 Google Sheets 作為資料來源，讓 AI 依據植栽資料回答景觀設計問題。

[植栽筆數] [display_matrix 筆數] [OpenAI model] [資料來源]

請輸入你的植栽問題：
[text_area]
[詢問 AI]

AI 回答
[natural-language answer]

相關植栽資料
[filtered plant table]

AI 提及植栽的季節矩陣
[1-12 month matrix using 🌸 / 🍃 / 🌸🍃]

Google Sheet 原始資料預覽
[collapsed expander showing plants and display_matrix]
```

## Error Handling

The app should show clear Streamlit messages instead of crashing.

Missing environment variables:

```text
.env 缺少必要設定：<variable_name>
```

Google Sheet read error:

```text
Google Sheet 讀取失敗，請檢查 spreadsheet id、worksheet name，以及 service account 權限。
```

Worksheet name error:

```text
找不到指定的 worksheet，請檢查 WORKSHEET_NAME 是否與 Google Sheet 分頁名稱一致。
```

OpenAI error:

```text
OpenAI API 呼叫失敗，請檢查 OPENAI_API_KEY 或 OPENAI_MODEL 設定。
```

AI answer succeeds but no plants can be matched:

```text
未找到可對應的植栽資料。
```

## Acceptance Criteria

The MVP is complete when:

- `streamlit run app.py` starts the app.
- The app reads both Google Sheets.
- The page shows the number of `plants` rows.
- The page shows the number of `display_matrix` rows.
- The page shows the current OpenAI model.
- The page shows data source as Google Sheets API.
- The user can enter a plant or landscape design question.
- The user can click `詢問 AI`.
- OpenAI returns a Taiwan Traditional Chinese answer based only on the provided Google Sheet context.
- If the sheet data is insufficient, the answer says the table is insufficient and explains what information is missing.
- The answer always ends with `實際配置仍需依基地日照、土壤、排水、維護條件與設計風格確認。`
- The app matches related plants by `chinese_name` and `scientific_name`.
- The app preserves exact `plant_id` values such as `001` and `002`.
- The app displays related plant rows below the AI answer.
- The app displays a seasonal matrix using `🌸`, `🍃`, and `🌸🍃`.
- The bottom of the page includes a collapsed expander with raw Google Sheet data.

## Future Features Out of Scope

Do not implement these in this MVP:

- Google Drive image auto matching by `plant_id`.
- Google Drive API image loading.
- Web crawler for plant reference websites.
- AI extraction from reference URLs.
- Google Sheets API write-back.
- `review_status` workflow.
- Line Messaging API integration.
- React frontend integration.
