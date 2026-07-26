# 景觀植物 AI 系統

這個 package 是專案新的維護入口，目標是讓資料夾名稱直接反映系統責任。

目前已完成核心實作分檔：

- `設定/`: `.env`、外部服務設定、merged matrix 設定。
- `資料/`: Google Sheets / CSV 載入與資料正規化入口。
- `查詢/`: 自然語言 filter、manual filter 合併、DataFrame 搜尋。
- `推薦/`: 候選植物評分與推薦選擇。
- `AI回答/`: AI context、一般回答、設計提案、輸出驗證。
- `介面/`: Streamlit app 入口與圖表資料入口。

舊的 `matrix_question_app` 相容轉出口已集中放到 `舊版相容/matrix_question_app/`。新程式碼應該優先從 `景觀植物AI系統/` 底下的分層模組 import。

後續維護建議：

1. 新增 filter 規則時，優先改 `查詢/filters.py`。
2. 搜尋條件命中邏輯改 `查詢/search.py`。
3. 推薦排序和景觀配置選擇改 `推薦/scoring.py`。
4. AI prompt、grounded answer、設計提案驗證改 `AI回答/generator.py`。
5. Streamlit 畫面流程改 `介面/streamlit_app.py`。
