"""AI context builders."""

import json

from ..資料.normalizer import as_text
from ..推薦.scoring import _active_months


def format_months(months):
    return "、".join(str(month) for month in months) or "無"


def build_ai_context(candidate_df, filters, max_rows=20):
    rows = []
    fields = ("plant_id", "chinese_name", "scientific_name", "plant_type", "growth_form", "flower_color", "fruit_color", "leaf_color", "ornamental_part", "flowering_period", "fruiting_period", "season_notes", "confidence", "needs_review", "match_score", "match_reasons")
    for _, row in candidate_df.head(max_rows).iterrows():
        item = {field: as_text(row.get(field)) for field in fields}
        item["花期月份"] = format_months(_active_months(row, "flower"))
        item["果期月份"] = format_months(_active_months(row, "fruit"))
        item["葉觀賞月份"] = format_months(_active_months(row, "leaf"))
        rows.append(item)
    return json.dumps({"applied_filters": filters, "candidates": rows}, ensure_ascii=False)


__all__ = ["build_ai_context", "format_months"]
