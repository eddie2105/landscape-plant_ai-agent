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


def _recorded_plant_ids(candidate_df, column, review_only=False):
    """Return distinct plant IDs with a recorded seasonal value in ``column``."""
    if column not in candidate_df or "plant_id" not in candidate_df:
        return set()
    active = candidate_df[column].map(normalize_boolean)
    if review_only:
        active &= candidate_df.get("needs_review", pd.Series(False, index=candidate_df.index)).map(normalize_boolean)
    return {
        as_text(plant_id)
        for plant_id in candidate_df.loc[active, "plant_id"]
        if as_text(plant_id)
    }


def build_coverage_analysis(candidate_df, requested_months=None, requested_parts=None):
    """Build fixed 12-month evidence counts at the distinct-plant-id grain.

    Counts are records of selected plant species, not planting quantities,
    canopy area, or flower abundance.  The heatmap always includes all months;
    query months are retained as a display/tooltip flag only.
    """
    requested_months = set(requested_months or [])
    requested_parts = requested_parts or list(MONTH_FIELD_PREFIXES)
    requested_parts = [part for part in requested_parts if part in MONTH_FIELD_PREFIXES]
    rows = []
    for number, key in enumerate(MONTH_KEYS, start=1):
        active_by_part = {
            part: _recorded_plant_ids(candidate_df, f"{prefix}_{key}")
            for part, prefix in MONTH_FIELD_PREFIXES.items()
        }
        review_by_part = {
            part: _recorded_plant_ids(candidate_df, f"{prefix}_{key}", review_only=True)
            for part, prefix in MONTH_FIELD_PREFIXES.items()
        }
        requested_ids = set().union(*(active_by_part[part] for part in requested_parts)) if requested_parts else set()
        requested_review_ids = set().union(*(review_by_part[part] for part in requested_parts)) if requested_parts else set()
        rows.append({
            "月份序號": number,
            "月份": MONTH_LABELS[number],
            "查詢指定月份": "是" if number in requested_months else "否",
            "花": len(active_by_part["花"]),
            "果": len(active_by_part["果"]),
            "葉": len(active_by_part["葉"]),
            "花_需複查": len(review_by_part["花"]),
            "果_需複查": len(review_by_part["果"]),
            "葉_需複查": len(review_by_part["葉"]),
            "指定觀賞特徵植物數": len(requested_ids),
            "指定觀賞特徵需複查數": len(requested_review_ids),
        })
    return pd.DataFrame(rows)


__all__ = ["build_coverage_analysis", "build_seasonal_matrix"]
