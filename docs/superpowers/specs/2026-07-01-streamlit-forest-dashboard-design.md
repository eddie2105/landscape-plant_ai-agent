# Streamlit Forest Dashboard Design

## Goal

Refine the current Streamlit MVP into a natural forest-style dashboard while keeping the existing Google Sheets, OpenAI, plant matching, and seasonal matrix behavior unchanged.

The target feel is:

```text
深墨綠背景
霧面卡片
柔和葉綠 accent
少量暖黃色點綴
森林資料控制台
```

This should improve visual polish without turning the MVP into a fragile custom frontend.

## Design Direction

Use Streamlit native layout plus scoped CSS.

The app should feel like a dashboard inspired by forest ecology and planting data:

- background: deep green-black
- card surfaces: muted dark moss green
- accent: soft leaf green
- secondary accent: warm yellow-green
- text: high-contrast off-white and muted gray
- shape: subtle rounded corners, restrained shadows
- mood: calm, professional, nature-oriented

Avoid heavy animation, decorative blobs, complex custom components, and React-like pixel-perfect layout.

## Layout

Use a two-zone dashboard layout:

```text
Top
  Title, subtitle, compact status badges

Left column
  Question input
  Ask AI button
  Model / data source / sheet row counts

Right main area
  AI answer card
  Recommended plant data card
  Seasonal matrix card

Bottom
  Collapsed Google Sheet raw data expander
```

The layout should remain usable on narrower screens by stacking columns naturally through Streamlit.

## Components

### Header

Show:

```text
Planting Knowledge Agent｜植栽知識 AI 助理
```

Subtitle:

```text
使用 Google Sheets 作為資料來源，讓 AI 依據植栽資料回答景觀設計問題。
```

The header should be visually strong but not oversized. It should sit on the same dashboard background, not inside a large hero card.

### Status Cards

Show four compact dashboard metrics:

- 植栽筆數
- display_matrix 筆數
- OpenAI model
- 資料來源

These should look like dark glass/matte cards with green accent text.

### Question Panel

The question input and button should live in the left column.

The panel should include:

- text area
- primary ask button
- short helper text that reminds the user answers are based on Google Sheet data

The app should still warn if the user clicks the button with an empty question.

### AI Answer Card

The answer should be displayed in a card-like section.

Keep the current Markdown rendering so the three-section answer format remains readable:

```text
一、推薦植栽
二、判斷依據
三、設計提醒
```

### Related Plants Card

Show the related plant dataframe inside a card-like section.

Continue hiding internal `plant_id` from user-facing tables.

If no plants match:

```text
未找到可對應的植栽資料。
```

### Seasonal Matrix Card

Show the seasonal matrix in a dashboard card.

Legend:

```text
🌸 = 花期
🍃 = 葉色觀賞期
🌸🍃 = 同時有花期與葉色觀賞
```

Continue hiding internal `plant_id` from the displayed matrix.

## CSS Scope

Add a helper such as:

```python
def inject_dashboard_css():
    ...
```

Call it inside `render_app()` after `st.set_page_config()`.

The CSS may target Streamlit containers and custom wrapper classes created with `st.markdown()`.

Keep the CSS focused on:

- page background
- text color
- card surfaces
- metric cards
- button style
- dataframe container styling where practical
- expander styling where practical

Do not rewrite the app as raw HTML.

## Behavior

Do not change:

- `.env` loading
- Google Sheets loading
- dead proxy cleanup
- OpenAI prompt behavior
- JSON parsing
- `plant_ids` matching
- seasonal matrix generation
- existing tests

The change is visual and layout-focused.

## Acceptance Criteria

The visual refresh is complete when:

- `streamlit run app.py` starts successfully.
- Existing tests still pass.
- `app.py` compiles.
- The page uses the natural forest dashboard palette.
- Header, question panel, metrics, AI answer, related plants, and seasonal matrix appear as visually distinct dashboard sections.
- Google Sheet raw data preview remains collapsed by default.
- Existing AI and Google Sheet behavior remains unchanged.

