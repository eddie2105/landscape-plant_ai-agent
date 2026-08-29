# 景觀植物 AI 系統

這是一個以植物資料庫為基礎的景觀植栽提案工具。使用者用自然語言描述需求，系統會從植物清單中篩選候選植物，並產生可追溯的植栽建議與景觀搭配說明。

例如，你可以輸入：「幫我規劃夏天有變化、春天有櫻花的庭院。」

## 主要功能

- 用繁體中文輸入季節、花果葉、顏色、植物型態或主題植物。
- 從既有植物資料中挑選候選植物，不自行捏造植物資料。
- 依植物型態建立高、中、低層的初步景觀搭配。
- 顯示植物的花、果、葉季節紀錄與 12 個月季相熱圖。
- 標示需要人工複查的資料，讓結果更容易驗證。

## 安裝

請先安裝 Python，接著在專案根目錄執行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 環境設定

複製設定檔：

```powershell
Copy-Item .env.example .env
```

在 `.env` 填入 Google Sheets 與 OpenAI 的設定：

```text
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/service_account.json
DISPLAY_MATRIX_MERGED_SPREADSHEET_ID=你的 Google Sheet ID
DISPLAY_MATRIX_MERGED_WORKSHEET_NAME=display_matrix_merged
OPENAI_API_KEY=你的 OpenAI API Key
OPENAI_MODEL=gpt-4.1-mini
```

將 Google service account JSON 放到：

```text
credentials/service_account.json
```

並將 Google Sheet 分享給該 service account 的電子郵件帳號。完整設定請參考 [.env.example](.env.example)。

## 啟動 Streamlit

從專案根目錄執行：

```powershell
.\.venv\Scripts\python.exe -m streamlit run "景觀植物AI系統\介面\streamlit_app.py"
```

終端機會顯示實際網址，通常是：

```text
http://localhost:8501
```

## 使用方式

1. 開啟 Streamlit 網頁後，在輸入框描述你的需求。
2. 可直接點選範例問題，或自行輸入，例如：

   ```text
   幫我規劃夏天有變化、春天有櫻花的庭院。
   ```

3. 按下「生成可追溯的植栽提案」。
4. 查看設計解讀、搭配植栽、推薦植物、季相熱圖與資料品質提醒。

## 注意事項

- 植物資料來自 Google Sheets；若沒有設定資料來源，系統無法提供查詢結果。
- OpenAI API 用於產生自然語言設計解讀；未設定時，系統仍會顯示 Python 篩選的結果。
- `needs_review` 標示代表資料需要人工複查，不能直接作為施工或定案依據。
