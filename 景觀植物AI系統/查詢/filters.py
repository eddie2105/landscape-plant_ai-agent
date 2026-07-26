"""Natural-language filter parsing helpers."""

import json
import re

from openai import OpenAI

from ..資料.normalizer import as_text, normalize_boolean
from .schema import (
    COLOR_ALIASES,
    DEFAULT_FILTERS,
    DESIGN_PALETTES,
    DESIGN_STYLE_PROFILES,
    FILTER_LIST_FIELDS,
    MONTH_FIELD_PREFIXES,
    PLAIN_LANGUAGE_TYPE_ALIASES,
    SEASON_MONTHS,
    UNSUPPORTED_TERM_LABELS,
)


def _months_from_question(question):
    text = as_text(question).replace("到", "-").replace("至", "-").replace("~", "-")
    months = set()
    for term, values in SEASON_MONTHS.items():
        if term in text:
            months.update(values)
    for start, end in re.findall(r"(\d{1,2})\s*(?:月)?\s*-\s*(\d{1,2})\s*月?", text):
        start_number, end_number = int(start), int(end)
        if 1 <= start_number <= 12 and 1 <= end_number <= 12:
            current = start_number
            while True:
                months.add(current)
                if current == end_number:
                    break
                current = 1 if current == 12 else current + 1
    for number in re.findall(r"(\d{1,2})\s*月", text):
        if 1 <= int(number) <= 12:
            months.add(int(number))
    return sorted(months)


def extract_known_filters(question, options):
    """Translate common everyday terms before asking the model for remaining intent."""
    text = as_text(question)
    normalized_text = text.replace("粉色", "粉紅色").replace("橙色", "橘色")
    filters = DEFAULT_FILTERS.copy()
    filters["months"] = _months_from_question(normalized_text)
    for part, words in (("花", ("花", "開花", "花期")), ("果", ("果", "果實", "結果")), ("葉", ("葉", "葉色", "觀葉"))):
        if any(word in normalized_text for word in words):
            filters["ornamental_parts"].append(part)

    for phrase, plant_type in PLAIN_LANGUAGE_TYPE_ALIASES.items():
        if phrase in normalized_text and plant_type in options["plant_types"]:
            filters["plant_types"] = [plant_type]
            break

    for color in sorted(options["flower_colors"], key=len, reverse=True):
        if not color or color not in normalized_text.replace("色", ""):
            continue
        if any(color in matched_color for matched_color in filters["flower_colors"]):
            continue
        filters["flower_colors"].append(color)
    if "花" not in normalized_text:
        filters["flower_colors"] = []
    filters["requires_year_round_interest"] = any(word in normalized_text for word in ("四季", "全年", "整年"))
    filters["requires_seasonal_change"] = any(word in normalized_text for word in ("季節變化", "四季變化"))
    filters["requires_composition"] = any(word in normalized_text for word in ("庭院", "花園", "景觀", "搭配", "一組"))
    for style_name, profile in DESIGN_STYLE_PROFILES.items():
        if any(keyword in normalized_text for keyword in profile["keywords"]):
            filters["design_palette_name"] = style_name
            filters["design_palette_colors"] = profile["colors"]
            filters["design_style_description"] = profile["description"]
            filters["requires_composition"] = True
            break
    filters["unverified_terms"] = sorted({label for term, label in UNSUPPORTED_TERM_LABELS.items() if term in normalized_text})
    return filters


def merge_known_and_ai_filters(ai_filters, known_filters):
    """Known everyday terms are deterministic; AI only fills what the user did not say plainly."""
    merged = {**DEFAULT_FILTERS, **ai_filters}
    for field in FILTER_LIST_FIELDS:
        if known_filters.get(field):
            merged[field] = known_filters[field]
    for field in ("requires_year_round_interest", "requires_seasonal_change", "requires_composition"):
        if known_filters.get(field):
            merged[field] = True
    merged["unverified_terms"] = known_filters.get("unverified_terms", [])
    if known_filters.get("design_palette_name"):
        merged["design_palette_name"] = known_filters["design_palette_name"]
        merged["design_palette_colors"] = known_filters["design_palette_colors"]
        merged["design_style_description"] = known_filters.get("design_style_description", "")
        for field in ("flower_colors", "fruit_colors", "leaf_colors"):
            merged[field] = known_filters.get(field, [])
    return merged


def _parse_json(raw_text, fallback):
    text = as_text(raw_text).replace("```json", "").replace("```", "").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        try:
            parsed = json.loads(text[start:end + 1]) if start >= 0 and end > start else fallback
        except json.JSONDecodeError:
            parsed = fallback
    return parsed if isinstance(parsed, dict) else fallback


def parse_question_to_filters(question, api_key, model, client=None):
    prompt = """將使用者的景觀植栽問題解析為 JSON。只能回傳 JSON，不可補充說明。
欄位固定為 months(1-12整數陣列), ornamental_parts(只可花、果、葉), plant_types,
growth_forms, flower_colors, fruit_colors, leaf_colors, requires_year_round_interest,
requires_seasonal_change, requires_composition, exclude_needs_review, requested_count(5-20整數), user_intent_summary。
未明確提到的條件使用空陣列或 false。春=3,4,5；夏=6,7,8；秋=9,10,11；冬=12,1,2。
只可把資料表可驗證的花、果、葉、月份、顏色、植物型態與生長型態放進篩選欄位。
庭院、日照、耐旱、維護、毒性與生態等沒有對應欄位的需求不可當成篩選條件。"""
    response = (client or OpenAI(api_key=api_key)).responses.create(
        model=model,
        input=[{"role": "system", "content": prompt}, {"role": "user", "content": question}],
        timeout=30,
    )
    parsed = _parse_json(response.output_text, DEFAULT_FILTERS.copy())
    filters = DEFAULT_FILTERS.copy()
    for field in FILTER_LIST_FIELDS:
        value = parsed.get(field, [])
        filters[field] = value if isinstance(value, list) else []
    filters["months"] = sorted({int(month) for month in filters["months"] if str(month).isdigit() and 1 <= int(month) <= 12})
    filters["ornamental_parts"] = [part for part in filters["ornamental_parts"] if part in MONTH_FIELD_PREFIXES]
    for field in ("requires_year_round_interest", "requires_seasonal_change", "requires_composition", "exclude_needs_review"):
        filters[field] = normalize_boolean(parsed.get(field))
    try:
        filters["requested_count"] = min(20, max(5, int(parsed.get("requested_count", 8))))
    except (TypeError, ValueError):
        filters["requested_count"] = 8
    filters["user_intent_summary"] = as_text(parsed.get("user_intent_summary"))
    return filters


def merge_ai_and_manual_filters(ai_filters, manual_filters):
    merged = {**DEFAULT_FILTERS, **ai_filters}
    for field in FILTER_LIST_FIELDS:
        manual_value = manual_filters.get(field, [])
        if manual_value:
            merged[field] = manual_value
    if manual_filters.get("exclude_needs_review"):
        merged["exclude_needs_review"] = True
    if manual_filters.get("requested_count") is not None:
        merged["requested_count"] = manual_filters["requested_count"]
    return merged


__all__ = [
    "COLOR_ALIASES",
    "DEFAULT_FILTERS",
    "DESIGN_PALETTES",
    "DESIGN_STYLE_PROFILES",
    "FILTER_LIST_FIELDS",
    "PLAIN_LANGUAGE_TYPE_ALIASES",
    "SEASON_MONTHS",
    "UNSUPPORTED_TERM_LABELS",
    "extract_known_filters",
    "merge_ai_and_manual_filters",
    "merge_known_and_ai_filters",
    "parse_question_to_filters",
]
