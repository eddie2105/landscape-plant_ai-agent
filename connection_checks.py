import os

import gspread
from dotenv import load_dotenv
from openai import OpenAI


REQUIRED_ENV_VARS = [
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    "PLANTS_SPREADSHEET_ID",
    "PLANTS_WORKSHEET_NAME",
    "DISPLAY_MATRIX_SPREADSHEET_ID",
    "DISPLAY_MATRIX_WORKSHEET_NAME",
    "OPENAI_API_KEY",
]


def load_settings():
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


def find_missing_settings(settings):
    return [
        name
        for name in REQUIRED_ENV_VARS
        if not str(settings.get(name) or "").strip()
    ]


def public_settings_summary(settings):
    return {
        "GOOGLE_SERVICE_ACCOUNT_FILE": settings.get("GOOGLE_SERVICE_ACCOUNT_FILE"),
        "PLANTS_SPREADSHEET_ID": settings.get("PLANTS_SPREADSHEET_ID"),
        "PLANTS_WORKSHEET_NAME": settings.get("PLANTS_WORKSHEET_NAME"),
        "DISPLAY_MATRIX_SPREADSHEET_ID": settings.get("DISPLAY_MATRIX_SPREADSHEET_ID"),
        "DISPLAY_MATRIX_WORKSHEET_NAME": settings.get("DISPLAY_MATRIX_WORKSHEET_NAME"),
        "OPENAI_API_KEY": "present" if settings.get("OPENAI_API_KEY") else "missing",
        "OPENAI_MODEL": settings.get("OPENAI_MODEL"),
    }


def check_google_sheets(settings, client=None):
    client = client or gspread.service_account(
        filename=settings["GOOGLE_SERVICE_ACCOUNT_FILE"]
    )
    sheet_configs = [
        (settings["PLANTS_SPREADSHEET_ID"], settings["PLANTS_WORKSHEET_NAME"]),
        (
            settings["DISPLAY_MATRIX_SPREADSHEET_ID"],
            settings["DISPLAY_MATRIX_WORKSHEET_NAME"],
        ),
    ]

    results = []
    for spreadsheet_id, worksheet_name in sheet_configs:
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(worksheet_name)
        sample = worksheet.get("A1:E5")
        results.append({"worksheet": worksheet_name, "sample_rows": len(sample)})

    return results


def check_openai(settings, client=None):
    client = client or OpenAI(api_key=settings["OPENAI_API_KEY"])
    models = client.models.list()
    data = list(models.data)
    return {
        "model": settings["OPENAI_MODEL"],
        "models_returned": len(data),
        "first_model": data[0].id if data else None,
    }


def run_checks():
    settings = load_settings()
    missing = find_missing_settings(settings)
    if missing:
        raise RuntimeError(f"Missing required environment settings: {', '.join(missing)}")

    return {
        "settings": public_settings_summary(settings),
        "google_sheets": check_google_sheets(settings),
        "openai": check_openai(settings),
    }
