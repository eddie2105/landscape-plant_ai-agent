"""Matrix data loading helpers."""

import json
from pathlib import Path

import gspread
import pandas as pd
import streamlit as st

from 景觀植物AI系統.設定.settings import load_matrix_settings
from 景觀植物AI系統.資料.normalizer import normalize_matrix_data


LOCAL_MATRIX_FALLBACK = Path("data/display_matrix_merged_preview.csv")


def load_google_sheet(
    spreadsheet_id,
    worksheet_name,
    service_account_file,
    service_account_json=None,
):
    """Load a Google Sheets worksheet as a DataFrame while preserving string IDs."""
    credential_json = str(service_account_json or "").strip()
    if credential_json:
        try:
            credentials = json.loads(credential_json)
        except json.JSONDecodeError as exc:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON") from exc
        client = gspread.service_account_from_dict(credentials)
    else:
        client = gspread.service_account(filename=service_account_file)
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name)
    df = pd.DataFrame(worksheet.get_all_records(numericise_ignore=["all"]))

    if "plant_id" in df.columns:
        df["plant_id"] = df["plant_id"].astype(str).str.strip()

    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_matrix():
    """Load the merged display matrix from Google Sheets or the local CSV fallback."""
    settings = load_matrix_settings()
    try:
        if not settings["DISPLAY_MATRIX_MERGED_SPREADSHEET_ID"]:
            raise RuntimeError("Missing merged matrix spreadsheet id")
        raw = load_google_sheet(
            settings["DISPLAY_MATRIX_MERGED_SPREADSHEET_ID"],
            settings["DISPLAY_MATRIX_MERGED_WORKSHEET_NAME"],
            settings["GOOGLE_SERVICE_ACCOUNT_FILE"],
            settings.get("GOOGLE_SERVICE_ACCOUNT_JSON"),
        )
        return normalize_matrix_data(raw), "Google Sheets API"
    except Exception as exc:
        if not LOCAL_MATRIX_FALLBACK.exists():
            raise RuntimeError(
                "Google Sheet loading failed and local CSV fallback was not found."
            ) from exc
        raw = pd.read_csv(LOCAL_MATRIX_FALLBACK, dtype={"plant_id": str})
        return normalize_matrix_data(raw), "Local CSV fallback"


__all__ = ["LOCAL_MATRIX_FALLBACK", "load_google_sheet", "load_matrix"]
