import os

import gspread
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")

PLANTS_SPREADSHEET_ID = os.getenv("PLANTS_SPREADSHEET_ID")
PLANTS_WORKSHEET_NAME = os.getenv("PLANTS_WORKSHEET_NAME")

DISPLAY_MATRIX_SPREADSHEET_ID = os.getenv("DISPLAY_MATRIX_SPREADSHEET_ID")
DISPLAY_MATRIX_WORKSHEET_NAME = os.getenv("DISPLAY_MATRIX_WORKSHEET_NAME")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def load_google_sheet(spreadsheet_id, worksheet_name):
    gc = gspread.service_account(filename=GOOGLE_SERVICE_ACCOUNT_FILE)
    spreadsheet = gc.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name)

    records = worksheet.get_all_records()
    df = pd.DataFrame(records)

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


def ask_ai(question, context):
    client = OpenAI(api_key=OPENAI_API_KEY)

    system_prompt = """
你是一位景觀植栽知識助理。

回答規則：
1. 只能根據提供的資料表內容回答。
2. 不可以自行編造資料表沒有的資訊。
3. 如果資料不足，請回答「目前資料表不足以判斷」。
4. 使用台灣繁體中文回答。
5. 回答最後一定要加上：
「實際配置仍需依基地日照、土壤、排水、維護條件與設計風格確認。」
"""

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": system_prompt},
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


def main():
    print("正在讀取 Google Sheet...")

    plants_df = load_google_sheet(
        PLANTS_SPREADSHEET_ID,
        PLANTS_WORKSHEET_NAME,
    )

    display_df = load_google_sheet(
        DISPLAY_MATRIX_SPREADSHEET_ID,
        DISPLAY_MATRIX_WORKSHEET_NAME,
    )

    print(f"成功讀取 plants：{len(plants_df)} 筆")
    print(f"成功讀取 display_matrix：{len(display_df)} 筆")

    question = input("\n請輸入你的植栽問題：\n> ")

    context = build_context(plants_df, display_df)

    print("\nAI 回答中...\n")
    answer = ask_ai(question, context)

    print(answer)


if __name__ == "__main__":
    main()
