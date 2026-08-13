"""DataFrame search helpers."""

import re

import pandas as pd

from ..資料.normalizer import normalize_boolean, normalize_multivalue_text
from .schema import MONTH_FIELD_PREFIXES, MONTH_KEYS


def _row_matches_values(value, choices):
    normalized = set(normalize_multivalue_text(value))
    requested = {
        item
        for choice in choices
        for item in normalize_multivalue_text(choice)
    }
    return bool(normalized.intersection(requested))


def _row_matches_plant_name(row, terms):
    """Match explicit names without allowing Latin substring false positives."""
    chinese_name = str(row.get("chinese_name", "") or "")
    scientific_name = str(row.get("scientific_name", "") or "").casefold()
    for term in terms:
        term = str(term or "").strip()
        if not term:
            continue
        if any("\u4e00" <= character <= "\u9fff" for character in term):
            if term in chinese_name:
                return True
        elif re.search(rf"(?<![a-z]){re.escape(term.casefold())}(?![a-z])", scientific_name):
            return True
    return False


def _month_match(row, months, parts):
    if not months:
        return True
    requested_parts = parts or list(MONTH_FIELD_PREFIXES)
    for month in months:
        key = MONTH_KEYS[month - 1]
        if any(normalize_boolean(row.get(f"{MONTH_FIELD_PREFIXES[part]}_{key}")) for part in requested_parts):
            return True
    return False


def apply_filters(df, filters):
    if not filters:
        return df.copy()
    matches = pd.Series(True, index=df.index)
    simple_fields = {
        "plant_types": "plant_type", "growth_forms": "growth_form", "flower_colors": "flower_color",
        "fruit_colors": "fruit_color", "leaf_colors": "leaf_color",
    }
    for filter_name, column in simple_fields.items():
        choices = filters.get(filter_name, [])
        if choices:
            matches &= df[column].map(lambda value: _row_matches_values(value, choices))
    if filters.get("plant_name_terms"):
        matches &= df.apply(lambda row: _row_matches_plant_name(row, filters["plant_name_terms"]), axis=1)
    if filters.get("design_palette_colors"):
        palette = filters["design_palette_colors"]
        matches &= df.apply(
            lambda row: any(
                _row_matches_values(row.get(column), palette)
                for column in ("flower_color", "fruit_color", "leaf_color")
            ),
            axis=1,
        )
    if filters.get("confidence"):
        matches &= df["confidence"].isin(filters["confidence"])
    if filters.get("ornamental_parts") and not filters.get("months"):
        requested = set(filters["ornamental_parts"])
        color_backed_parts = {
            "花" if filters.get("flower_colors") else "",
            "果" if filters.get("fruit_colors") else "",
            "葉" if filters.get("leaf_colors") else "",
        }
        parts_needing_ornamental_label = requested.difference(color_backed_parts)
        if parts_needing_ornamental_label:
            matches &= df["ornamental_part"].map(
                lambda value: bool(set(normalize_multivalue_text(value)).intersection(parts_needing_ornamental_label))
            )
    if filters.get("months"):
        if filters.get("requires_full_month_coverage"):
            requested_parts = filters.get("ornamental_parts") or list(MONTH_FIELD_PREFIXES)
            matches &= df.apply(
                lambda row: all(
                    any(
                        normalize_boolean(row.get(f"{MONTH_FIELD_PREFIXES[part]}_{MONTH_KEYS[month - 1]}"))
                        for part in requested_parts
                    )
                    for month in filters["months"]
                ),
                axis=1,
            )
        else:
            matches &= df.apply(lambda row: _month_match(row, filters["months"], filters.get("ornamental_parts", [])), axis=1)
    if filters.get("exclude_needs_review"):
        matches &= ~df["needs_review"]
    return df.loc[matches].copy()


def find_relaxed_candidates(df, filters):
    """Offer a labelled near match when the exact supported conditions return no rows."""
    for field, label in (
        ("flower_colors", "花色"), ("fruit_colors", "果色"), ("leaf_colors", "葉色"),
        ("plant_types", "植物型態"), ("growth_forms", "生長型態"), ("months", "月份"),
    ):
        if not filters.get(field):
            continue
        relaxed = {**filters, field: []}
        matches = apply_filters(df, relaxed)
        if not matches.empty:
            return matches, label
    return df.iloc[0:0].copy(), ""


__all__ = ["apply_filters", "find_relaxed_candidates"]
