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
    PLANT_NAME_ALIASES,
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

    # Resolve named themes before generic type words.  For example, ``松樹``
    # is a theme name, not an instruction that every support plant must be a
    # tree; ``喬木``/``灌木`` remain explicit type constraints.
    for phrase, aliases in PLANT_NAME_ALIASES.items():
        if phrase in normalized_text:
            filters["plant_name_terms"].extend(aliases)
    for name in options.get("plant_names", []):
        if name in normalized_text and name not in filters["plant_name_terms"]:
            filters["plant_name_terms"].append(name)

    for phrase, plant_type in PLAIN_LANGUAGE_TYPE_ALIASES.items():
        if phrase == "樹" and filters["plant_name_terms"]:
            continue
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
    filters["requires_composition"] = any(word in normalized_text for word in ("庭院", "花園", "公園", "景觀", "搭配", "一組", "主題"))
    filters["requires_water_feature"] = any(word in normalized_text for word in ("水景", "水池", "池塘", "生態池", "濕地", "水生"))
    filters["requires_full_month_coverage"] = any(
        phrase in normalized_text
        for phrase in ("整個夏天", "整個夏季", "夏天都有", "夏季都有", "整個春天", "整個秋天", "整個冬天")
    )
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
    for field in ("requires_year_round_interest", "requires_seasonal_change", "requires_composition", "requires_water_feature", "requires_full_month_coverage"):
        if known_filters.get(field):
            merged[field] = True
    # A plant name is a hard constraint.  Never let the general-purpose AI
    # parser invent one; it must be found in the user's wording/known aliases,
    # or be separately verified by the keyword-lookup fallback.
    merged["plant_name_terms"] = known_filters.get("plant_name_terms", [])
    if known_filters.get("plant_name_terms") and not known_filters.get("plant_types"):
        # Do not let the general parser turn a name such as ``松樹`` into an
        # all-candidates-must-be-trees filter. Manual sidebar choices remain
        # applied later and can still intentionally constrain the type.
        merged["plant_types"] = []
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
growth_forms, flower_colors, fruit_colors, leaf_colors, plant_name_terms, requires_year_round_interest,
requires_seasonal_change, requires_composition, requires_full_month_coverage, exclude_needs_review, requested_count(5-20整數), user_intent_summary。
未明確提到的條件使用空陣列或 false。春=3,4,5；夏=6,7,8；秋=9,10,11；冬=12,1,2。
plant_name_terms 只放使用者明確點名的植物中文名、學名、屬名或常用名稱；它是不可自動放寬的硬條件。不可把植物名稱放進 plant_types。
只可把資料表可驗證的花、果、葉、月份、顏色、植物型態與生長型態放進其他篩選欄位。
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
    for field in ("requires_year_round_interest", "requires_seasonal_change", "requires_composition", "requires_water_feature", "requires_full_month_coverage", "exclude_needs_review"):
        filters[field] = normalize_boolean(parsed.get(field))
    try:
        filters["requested_count"] = min(20, max(5, int(parsed.get("requested_count", 8))))
    except (TypeError, ValueError):
        filters["requested_count"] = 8
    filters["user_intent_summary"] = as_text(parsed.get("user_intent_summary"))
    return filters


def suggest_plant_search_terms(question, api_key, model, client=None):
    """Let AI suggest *search tokens* only; Python must verify every match.

    This is deliberately separate from the filter parser: it never recommends
    a plant and is called only after an explicit-name search produced no rows.
    """
    prompt = """從使用者的植栽需求找出可能的「口語植物類別或名稱」搜尋詞。
只能回傳 JSON：{"terms": ["最多4個中文名、英文俗名或學名屬名片段"], "interpretation": "一句話說明理解"}。
這些詞只會被程式拿去比對既有植物資料的中文名與學名，並不代表你推薦任何植物。
若問題沒有明確植物名稱或類別，terms 回傳空陣列。不要輸出植物清單、型態、花色或其他欄位。"""
    response = (client or OpenAI(api_key=api_key)).responses.create(
        model=model,
        input=[{"role": "system", "content": prompt}, {"role": "user", "content": question}],
        timeout=20,
    )
    parsed = _parse_json(response.output_text, {})
    raw_terms = parsed.get("terms", []) if isinstance(parsed, dict) else []
    terms = []
    for term in raw_terms if isinstance(raw_terms, list) else []:
        term = as_text(term)
        if 1 < len(term) <= 50 and term not in terms:
            terms.append(term)
        if len(terms) == 4:
            break
    return {"terms": terms, "interpretation": as_text(parsed.get("interpretation")) if isinstance(parsed, dict) else ""}


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
    "suggest_plant_search_terms",
]
