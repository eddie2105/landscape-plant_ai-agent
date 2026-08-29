"""Application settings helpers."""

import os

from dotenv import load_dotenv


DEAD_LOCAL_PROXY = "127.0.0.1:9"
PROXY_ENV_VARS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
]

REQUIRED_ENV_VARS = [
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    "PLANTS_SPREADSHEET_ID",
    "PLANTS_WORKSHEET_NAME",
    "DISPLAY_MATRIX_SPREADSHEET_ID",
    "DISPLAY_MATRIX_WORKSHEET_NAME",
    "OPENAI_API_KEY",
]


def disable_dead_local_proxy():
    """Remove a dead local proxy that can block Google/OpenAI requests."""
    for name in PROXY_ENV_VARS:
        value = os.environ.get(name, "")
        if DEAD_LOCAL_PROXY in value:
            os.environ.pop(name, None)


def load_settings():
    """Load base app settings from .env."""
    load_dotenv()
    # ``.env`` may itself define a stale local proxy.  Clear it *after*
    # loading environment values, otherwise later API clients still inherit it.
    disable_dead_local_proxy()
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
    """Return required environment settings that are missing or blank."""
    return [
        name
        for name in REQUIRED_ENV_VARS
        if not str(settings.get(name) or "").strip()
    ]


def load_matrix_settings():
    """Load base settings and add merged matrix worksheet settings."""
    settings = load_settings()
    settings["DISPLAY_MATRIX_MERGED_SPREADSHEET_ID"] = os.getenv(
        "DISPLAY_MATRIX_MERGED_SPREADSHEET_ID"
    ) or os.getenv("PLANTS_MERGED_SPREADSHEET_ID")
    settings["DISPLAY_MATRIX_MERGED_WORKSHEET_NAME"] = os.getenv(
        "DISPLAY_MATRIX_MERGED_WORKSHEET_NAME", "display_matrix_merged"
    )
    return settings


__all__ = [
    "DEAD_LOCAL_PROXY",
    "PROXY_ENV_VARS",
    "REQUIRED_ENV_VARS",
    "disable_dead_local_proxy",
    "find_missing_settings",
    "load_matrix_settings",
    "load_settings",
]
