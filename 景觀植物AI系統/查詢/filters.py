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
    new_default_filters,
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


def _requirement_clauses(text):
    """Split common natural-language joins without interpreting plant facts."""
    return [
        clause.strip()
        for clause in re.split(r"[，,。；;]|然後要有|另外想要|並且要有|且要有|包含|搭配|並有", text)
        if clause.strip()
    ]


def _theme_months_from_question(text, named_phrases=None):
    """Find months attached to a named plant in the same clause.

    For example, in ``夏天的庭院，春天想要有櫻花`` the summer months
    describe the composition while the spring months specifically qualify the
    cherry blossom theme.  This is intentionally deterministic and only uses
    known name aliases.
    """
    theme_months = set()
    clauses = _requirement_clauses(text)
    named_phrases = named_phrases or list(PLANT_NAME_ALIASES)
    for clause in clauses:
        if any(name in clause for name in named_phrases):
            theme_months.update(_months_from_question(clause))
    return sorted(theme_months)


def _find_named_terms(text, options):
    """Return the literal phrases found in the question and their search terms."""
    groups = []
    for phrase, aliases in PLANT_NAME_ALIASES.items():
        if phrase in text:
            groups.append({"phrase": phrase, "terms": list(dict.fromkeys(aliases))})
    for name in options.get("plant_names", []):
        if name in text and not any(group["phrase"] in name for group in groups):
            groups.append({"phrase": name, "terms": [name]})
    phrases = list(dict.fromkeys(group["phrase"] for group in groups))
    terms = list(dict.fromkeys(term for group in groups for term in group["terms"]))
    return phrases, terms, groups


def _without_named_phrases(text, phrases):
    cleaned = text
    for phrase in sorted(phrases, key=len, reverse=True):
        cleaned = cleaned.replace(phrase, "")
    return cleaned


def _extract_ornamental_parts(text, named_phrases=()):
    cleaned = _without_named_phrases(text, named_phrases)
    parts = []
    for part, words in (("花", ("花", "開花", "花期")), ("果", ("果", "果實", "結果")), ("葉", ("葉", "葉色", "觀葉"))):
        if any(word in cleaned for word in words):
            parts.append(part)
    return parts


def _extract_plant_types(text, options, named_phrases=()):
    cleaned = _without_named_phrases(text, named_phrases)
    for phrase, plant_type in PLAIN_LANGUAGE_TYPE_ALIASES.items():
        if phrase in cleaned and plant_type in options.get("plant_types", []):
            return [plant_type]
    return []


def _extract_flower_colors(text, options):
    colors = []
    for color in sorted(options.get("flower_colors", []), key=len, reverse=True):
        if not color or color not in text.replace("色", ""):
            continue
        if not any(color in matched_color for matched_color in colors):
            colors.append(color)
    return colors if "花" in text else []


def extract_known_filters(question, options):
    """Translate common everyday terms before asking the model for remaining intent."""
    text = as_text(question)
    normalized_text = text.replace("粉色", "粉紅色").replace("橙色", "橘色")
    filters = new_default_filters()
    named_phrases, named_terms, named_groups = _find_named_terms(normalized_text, options)
    clauses = _requirement_clauses(normalized_text)
    theme_clauses = [clause for clause in clauses if any(phrase in clause for phrase in named_phrases)]
    composition_clauses = [clause for clause in clauses if clause not in theme_clauses]
    # If the question contains only one clause, its modifiers reasonably apply
    # to both the overall planting and the named theme plant.  With multiple
    # clauses, each side retains only its own modifiers.
    composition_text = " ".join(composition_clauses) if composition_clauses else normalized_text
    theme_text = " ".join(theme_clauses)

    filters["months"] = _months_from_question(composition_text)
    filters["ornamental_parts"] = _extract_ornamental_parts(composition_text, named_phrases)
    filters["plant_types"] = _extract_plant_types(composition_text, options, named_phrases)
    filters["flower_colors"] = _extract_flower_colors(composition_text, options)
    filters["plant_name_terms"] = named_terms
    filters["theme_months"] = _months_from_question(theme_text) if named_terms else []
    if named_terms:
        for group in named_groups:
            group_clauses = [clause for clause in clauses if group["phrase"] in clause]
            group_text = " ".join(group_clauses)
            filters["theme_plant_requirements"].append({
                "phrase": group["phrase"],
                "terms": group["terms"],
                "months": _months_from_question(group_text),
                "ornamental_parts": _extract_ornamental_parts(group_text, [group["phrase"]]),
                "plant_types": _extract_plant_types(group_text, options, [group["phrase"]]),
                "growth_forms": [],
                "flower_colors": _extract_flower_colors(group_text, options),
                "fruit_colors": [],
                "leaf_colors": [],
                "required": True,
                "max_required": 2 if "主題" in group_text else 1,
                "role": "主題植物",
            })
    filters["requires_year_round_interest"] = any(word in normalized_text for word in ("四季", "全年", "整年"))
    filters["requires_seasonal_change"] = any(word in composition_text for word in ("季節變化", "四季變化", "有變化", "會變化"))
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
    merged = new_default_filters()
    merged.update(ai_filters)
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
    merged["theme_months"] = known_filters.get("theme_months", [])
    merged["theme_plant_requirements"] = known_filters.get("theme_plant_requirements", [])
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
    parsed = _parse_json(response.output_text, new_default_filters())
    filters = new_default_filters()
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
    merged = new_default_filters()
    merged.update(ai_filters)
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
    "new_default_filters",
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
