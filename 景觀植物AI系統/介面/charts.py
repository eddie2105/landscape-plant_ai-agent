"""Chart and matrix data builders for the Streamlit UI."""

import pandas as pd

from ..資料.normalizer import as_text, normalize_boolean
from ..查詢.schema import MONTH_FIELD_PREFIXES, MONTH_KEYS, MONTH_LABELS


def build_seasonal_matrix(candidate_df):
    rows = []
    for _, row in candidate_df.iterrows():
        matrix_row = {"植物": f"{as_text(row.get('chinese_name'))} ({as_text(row.get('plant_id'))})"}
        for number, key in enumerate(MONTH_KEYS, start=1):
            values = [part for part, prefix in MONTH_FIELD_PREFIXES.items() if normalize_boolean(row.get(f"{prefix}_{key}"))]
            matrix_row[MONTH_LABELS[number]] = "＋".join(values) if values else "-"
        rows.append(matrix_row)
    return pd.DataFrame(rows, columns=["植物", *MONTH_LABELS.values()])


def build_coverage_analysis(candidate_df):
    rows = []
    for number, key in enumerate(MONTH_KEYS, start=1):
        flower = int(candidate_df[f"flower_{key}"].sum()) if f"flower_{key}" in candidate_df else 0
        fruit = int(candidate_df[f"fruit_{key}"].sum()) if f"fruit_{key}" in candidate_df else 0
        leaf = int(candidate_df[f"leaf_{key}"].sum()) if f"leaf_{key}" in candidate_df else 0
        any_interest = int(candidate_df[[f"flower_{key}", f"fruit_{key}", f"leaf_{key}"]].any(axis=1).sum()) if not candidate_df.empty else 0
        rows.append({"月份": MONTH_LABELS[number], "花": flower, "果": fruit, "葉": leaf, "任一觀賞特徵": any_interest})
    return pd.DataFrame(rows)


__all__ = ["build_coverage_analysis", "build_seasonal_matrix"]
