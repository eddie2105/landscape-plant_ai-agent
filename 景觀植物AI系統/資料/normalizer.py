"""Matrix normalization helpers."""

import re

import pandas as pd

from ..查詢.schema import COLOR_ALIASES, MONTH_FIELD_PREFIXES, MONTH_KEYS


def as_text(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def normalize_boolean(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not pd.isna(value):
        return bool(value)
    return as_text(value).casefold() in {"true", "1", "yes", "y", "on", "是"}


def normalize_multivalue_text(value):
    text = as_text(value).translate(str.maketrans({"，": ",", "、": ",", "；": ",", "／": "/"}))
    values = []
    for item in re.split(r"[,;/\s]+", text):
        item = item.strip().replace("色", "")
        item = COLOR_ALIASES.get(item, item)
        if item and item not in values:
            values.append(item)
    return values


def normalize_matrix_data(df):
    matrix = df.copy()
    for column in ["plant_id", "chinese_name", "scientific_name", "plant_type", "growth_form", "confidence", "needs_review"]:
        if column in matrix:
            matrix[column] = matrix[column].map(as_text)
    for prefix in MONTH_FIELD_PREFIXES.values():
        for key in MONTH_KEYS:
            column = f"{prefix}_{key}"
            if column in matrix:
                matrix[column] = matrix[column].map(normalize_boolean)
            else:
                matrix[column] = False
    matrix["needs_review"] = matrix.get("needs_review", False).map(normalize_boolean)
    if "updated_at" in matrix:
        matrix["updated_at"] = pd.to_datetime(matrix["updated_at"], errors="coerce")
    return matrix


def extract_filter_options(df, column):
    if column not in df:
        return []
    values = []
    for value in df[column]:
        for item in normalize_multivalue_text(value):
            if item not in values:
                values.append(item)
    return sorted(values)


def build_filter_options(df):
    return {
        "plant_types": sorted(filter(None, df.get("plant_type", pd.Series(dtype=str)).map(as_text).unique())),
        "growth_forms": sorted(filter(None, df.get("growth_form", pd.Series(dtype=str)).map(as_text).unique())),
        "flower_colors": extract_filter_options(df, "flower_color"),
        "fruit_colors": extract_filter_options(df, "fruit_color"),
        "leaf_colors": extract_filter_options(df, "leaf_color"),
        "plant_names": sorted(filter(None, df.get("chinese_name", pd.Series(dtype=str)).map(as_text).unique()), key=len, reverse=True),
    }


__all__ = [
    "as_text",
    "build_filter_options",
    "extract_filter_options",
    "normalize_boolean",
    "normalize_matrix_data",
    "normalize_multivalue_text",
]
