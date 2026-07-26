"""Recommendation scoring and selection helpers."""

import pandas as pd

from ..資料.normalizer import as_text, normalize_boolean
from ..查詢.schema import MONTH_FIELD_PREFIXES, MONTH_KEYS, SCORE_WEIGHTS
from ..查詢.search import _row_matches_values


def _active_months(row, prefix):
    return [index for index, key in enumerate(MONTH_KEYS, start=1) if normalize_boolean(row.get(f"{prefix}_{key}"))]


def _palette_parts(row, palette_colors):
    return [
        label
        for label, column in (("花", "flower_color"), ("果", "fruit_color"), ("葉", "leaf_color"))
        if _row_matches_values(row.get(column), palette_colors)
    ]


def score_candidates(df, filters):
    scored = df.copy()
    scores, reasons = [], []
    for _, row in scored.iterrows():
        score, row_reasons = 0, []
        for part, prefix in MONTH_FIELD_PREFIXES.items():
            matched_months = set(_active_months(row, prefix)).intersection(filters.get("months", []))
            if matched_months and (not filters.get("ornamental_parts") or part in filters["ornamental_parts"]):
                points = len(matched_months) * SCORE_WEIGHTS[f"{prefix}_month"]
                score += points; row_reasons.append(f"{part}{'、'.join(map(str, sorted(matched_months)))}月")
        for filter_name, column, weight, label in (
            ("plant_types", "plant_type", "plant_type", "植物型態"), ("growth_forms", "growth_form", "growth_form", "生長型態"),
            ("flower_colors", "flower_color", "flower_color", "花色"), ("fruit_colors", "fruit_color", "fruit_color", "果色"), ("leaf_colors", "leaf_color", "leaf_color", "葉色"),
        ):
            if filters.get(filter_name) and _row_matches_values(row.get(column), filters[filter_name]):
                score += SCORE_WEIGHTS[weight]; row_reasons.append(label)
        palette_parts = _palette_parts(row, filters.get("design_palette_colors", []))
        if palette_parts:
            score += SCORE_WEIGHTS["palette_color"]
            row_reasons.append(f"{filters.get('design_palette_name', '指定')}色系（{'／'.join(palette_parts)}）")
        confidence = as_text(row.get("confidence")).casefold()
        score += SCORE_WEIGHTS.get(f"{confidence}_confidence", 0)
        if row.get("needs_review"):
            score += SCORE_WEIGHTS["needs_review"]
        active_total = len(set().union(*(_active_months(row, prefix) for prefix in MONTH_FIELD_PREFIXES.values())))
        if filters.get("requires_year_round_interest"):
            score += active_total
            if active_total == 12: row_reasons.append("全年皆有觀賞訊號")
        if filters.get("requires_seasonal_change") and (as_text(row.get("season_notes")) or as_text(row.get("flowering_period")) or as_text(row.get("fruiting_period"))):
            score += 2; row_reasons.append("具有季節資料")
        scores.append(score); reasons.append("、".join(row_reasons) or "符合基本候選條件")
    scored["match_score"], scored["match_reasons"] = scores, reasons
    confidence_rank = {"high": 3, "medium": 2, "low": 1}
    scored["_confidence_rank"] = scored["confidence"].map(confidence_rank).fillna(0)
    return scored.sort_values(["match_score", "_confidence_rank", "chinese_name"], ascending=[False, False, True]).drop(columns="_confidence_rank")


def _landscape_layer(row):
    text = f"{as_text(row.get('plant_type'))} {as_text(row.get('growth_form'))}"
    if "喬木" in text:
        return "高層"
    if "灌木" in text:
        return "中層"
    if any(value in text for value in ("地被", "草本", "花壇", "香草")):
        return "低層"
    return "其他型態"


def select_recommendations(candidate_df, filters):
    """Keep ordinary searches ranked, but diversify an explicitly requested landscape composition."""
    requested_count = filters.get("requested_count", 8)
    if candidate_df.empty or not filters.get("requires_composition"):
        return candidate_df.head(requested_count).copy()

    remaining = candidate_df.copy()
    selected = []
    # Give a garden composition a backbone, middle mass, and foreground when data permits.
    for layer in ("高層", "中層", "低層", "其他型態"):
        layer_rows = remaining[remaining.apply(_landscape_layer, axis=1) == layer]
        if not layer_rows.empty and len(selected) < requested_count:
            selected.append(layer_rows.iloc[0])
            remaining = remaining.drop(layer_rows.index[0])
    palette_colors = filters.get("design_palette_colors", [])
    if palette_colors:
        represented_parts = {
            part
            for row in selected
            for part in _palette_parts(row, palette_colors)
        }
        for part in ("花", "果", "葉"):
            if part in represented_parts or len(selected) >= requested_count:
                continue
            role_rows = remaining[
                remaining.apply(lambda row: part in _palette_parts(row, palette_colors), axis=1)
            ]
            if not role_rows.empty:
                selected.append(role_rows.iloc[0])
                remaining = remaining.drop(role_rows.index[0])
                represented_parts.add(part)
    for _, row in remaining.iterrows():
        if len(selected) >= requested_count:
            break
        selected.append(row)
    return pd.DataFrame(selected, columns=candidate_df.columns)


__all__ = ["SCORE_WEIGHTS", "score_candidates", "select_recommendations"]
