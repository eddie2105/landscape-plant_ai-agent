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


def build_coverage_analysis(candidate_df, months=None):
    """Count recorded plant-species evidence for the displayed months.

    These are counts of selected plant records, not planting quantities,
    canopy area, or flower abundance.
    """
    rows = []
    for number, key in enumerate(MONTH_KEYS, start=1):
        if months and number not in months:
            continue
        flower = int(candidate_df[f"flower_{key}"].sum()) if f"flower_{key}" in candidate_df else 0
        fruit = int(candidate_df[f"fruit_{key}"].sum()) if f"fruit_{key}" in candidate_df else 0
        leaf = int(candidate_df[f"leaf_{key}"].sum()) if f"leaf_{key}" in candidate_df else 0
        review = candidate_df["needs_review"].map(normalize_boolean) if "needs_review" in candidate_df else pd.Series(False, index=candidate_df.index)
        rows.append({
            "月份": MONTH_LABELS[number], "花": flower, "果": fruit, "葉": leaf,
            "花_需複查": int((review & candidate_df[f"flower_{key}"].map(normalize_boolean)).sum()) if f"flower_{key}" in candidate_df else 0,
            "果_需複查": int((review & candidate_df[f"fruit_{key}"].map(normalize_boolean)).sum()) if f"fruit_{key}" in candidate_df else 0,
            "葉_需複查": int((review & candidate_df[f"leaf_{key}"].map(normalize_boolean)).sum()) if f"leaf_{key}" in candidate_df else 0,
        })
    return pd.DataFrame(rows)


__all__ = ["build_coverage_analysis", "build_seasonal_matrix"]
