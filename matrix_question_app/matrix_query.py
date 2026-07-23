"""Pure query and AI helpers for the merged seasonal plant matrix."""

import json
import re
from collections.abc import Iterable

import pandas as pd
from openai import OpenAI


MONTH_KEYS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
MONTH_LABELS = {index: f"{index}月" for index in range(1, 13)}
MONTH_FIELD_PREFIXES = {"花": "flower", "果": "fruit", "葉": "leaf"}
FILTER_LIST_FIELDS = (
    "months", "ornamental_parts", "plant_types", "growth_forms", "flower_colors",
    "fruit_colors", "leaf_colors", "confidence",
)
DEFAULT_FILTERS = {
    "months": [], "ornamental_parts": [], "plant_types": [], "growth_forms": [],
    "flower_colors": [], "fruit_colors": [], "leaf_colors": [], "confidence": [],
    "requires_year_round_interest": False, "requires_seasonal_change": False,
    "exclude_needs_review": False, "requested_count": 8, "user_intent_summary": "",
    "requires_composition": False,
    "design_palette_name": "", "design_palette_colors": [],
}
SCORE_WEIGHTS = {
    "flower_month": 2, "fruit_month": 2, "leaf_month": 1, "plant_type": 3,
    "growth_form": 2, "flower_color": 3, "fruit_color": 2, "leaf_color": 2,
    "high_confidence": 2, "medium_confidence": 1, "palette_color": 3, "needs_review": -2,
}
FINAL_REMINDER = "實際配置仍需依基地日照、土壤、排水、維護條件與設計風格確認。"
COLOR_ALIASES = {
    "粉": "粉紅",
    "粉紅": "粉紅",
    "橙": "橘",
    "橘": "橘",
}
SEASON_MONTHS = {
    "春": [3, 4, 5], "春天": [3, 4, 5],
    "夏": [6, 7, 8], "夏天": [6, 7, 8],
    "秋": [9, 10, 11], "秋天": [9, 10, 11],
    "冬": [12, 1, 2], "冬天": [12, 1, 2],
}
PLAIN_LANGUAGE_TYPE_ALIASES = {
    "樹": "喬木", "大樹": "喬木", "小樹": "喬木",
    "灌木": "灌木", "矮樹": "灌木", "地被": "地被",
    "草花": "花壇", "花草": "花壇", "香草": "香草/蔬菜",
    "藤": "藤本", "爬藤": "藤本",
}
UNSUPPORTED_TERM_LABELS = {
    "庭院": "庭院適應性", "陽台": "陽台適應性", "校園": "校園適應性",
    "公園": "公園適應性", "半日照": "日照條件", "全日照": "日照條件",
    "耐陰": "日照條件", "耐旱": "耐旱性", "好照顧": "維護需求",
    "低維護": "維護需求", "寵物": "寵物安全性", "毒": "毒性", "生態": "生態功能",
}
DESIGN_PALETTES = {
    "香檳色": ["乳白", "白", "黃", "金黃"],
}
DESIGN_STYLE_PROFILES = {
    "香檳色": {
        "keywords": ("香檳",),
        "colors": ["乳白", "白", "黃", "金黃"],
        "description": "以乳白、白、淡黃、金黃色形成柔和暖白色調",
    },
    "古典感": {
        "keywords": ("古典", "典雅"),
        "colors": ["乳白", "白", "紫", "淡紫", "綠"],
        "description": "以白、乳白、紫、淡紫與綠色建立沉穩典雅的層次",
    },
    "溫暖感": {
        "keywords": ("溫暖", "暖色"),
        "colors": ["黃", "金黃", "橘", "紅", "粉紅"],
        "description": "以黃、金黃、橘、紅與粉紅建立溫暖明亮的色彩焦點",
    },
}


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
    }


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


def _row_matches_values(value, choices):
    normalized = set(normalize_multivalue_text(value))
    requested = {
        item
        for choice in choices
        for item in normalize_multivalue_text(choice)
    }
    return bool(normalized.intersection(requested))


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


def generate_grounded_answer(question, applied_filters, candidate_context, api_key, model, client=None):
    prompt = f"""你是一位景觀植栽知識助理。
你只能根據提供的候選植物資料回答，不得使用外部知識，也不得捏造候選資料中不存在的資訊。

嚴格規則：
- 所有植物名稱、學名、plant_id、型態、花果葉月份、顏色、信心程度與複查狀態，都必須來自候選資料。
- 不得自行推測或補充耐陰性、耐旱性、毒性、維護性、生態功能、適用基地或植栽高度。
- 若資料不足，必須明確寫出「目前資料表不足以判斷」，並指出缺少的資料類型。
- 每一株推薦植物都必須使用候選資料中的中文名或學名，並在同一行附上 plant_id；plant_id 必須逐字保留，不得改寫。
- needs_review 為 true 的植物，必須在該植物下方標示「此筆資料需要人工複查」。
- 使用台灣繁體中文。
- 最終回答必須在最後附上這句提醒：{FINAL_REMINDER}
- 不可推薦候選資料以外的植物；若候選資料為空，不可虛構近似選項。
- 實際條件中的 unverified_terms 是使用者有提到、但資料表無法驗證的需求；不得因此說沒有植物。應先依其他可驗證條件推薦，並在資料提醒中說明該需求需另行確認。
- 若 requires_composition 為 true，這代表使用者想看景觀搭配，而非資料表已證實適合該基地。不同植物可分別負責花、果或葉的夏季視覺角色，不可要求每一株同時具有花、果、葉。優先用高、中、低層各至少一株形成組合，並用資料中實際的月份與觀賞部位說明分工。
- 實際條件中的 design_palette_name 與 design_palette_colors 是設計色感翻譯。例如香檳色代表乳白、白、淡黃、金黃。這些色彩可出現在花、果或葉任一部位；不得說資料原本標示「香檳色」。要說「以乳白、白、淡黃、金黃色系構成香檳色感」。

回答必須使用以下固定三段式 Markdown 格式，並保留換行：

一、查詢結論與推薦植栽
第一句先用日常語言簡短說明找到幾種植物、主要符合什麼條件；避免資料庫或技術術語。
無論使用者是否明確要求搭配，都必須依下列景觀分層輸出：

低層植栽（優先放 plant_type 或 growth_form 為地被、花壇、草本、香草/蔬菜者）：
1. 中文名｜scientific_name｜plant_id：實際 plant_id

中層植栽（優先放 plant_type 或 growth_form 為灌木者）：
1. 中文名｜scientific_name｜plant_id：實際 plant_id

高層植栽（優先放 plant_type 或 growth_form 為喬木或小喬木者）：
1. 中文名｜scientific_name｜plant_id：實際 plant_id

藤本、水生/濕生或無法依上述規則歸類者，放在「其他型態」；不得強行歸入高、中、低層。
每株格式為：
1. 中文名｜scientific_name｜plant_id：實際 plant_id
某分層沒有候選植物時，寫「目前候選資料未找到合適選項」。
必須在本節最後加上一句：「以上為依植物型態／生長型態進行的景觀分層推定，並非實際株高資料。」

二、判斷依據
只根據候選資料說明符合的植物型態、生長型態、花／果／葉色、月份、觀賞部位與季節資料；不可把景觀分層推定描述成實際高度。

三、資料品質與設計提醒
說明資料信心程度、needs_review 狀態與資料限制。
{FINAL_REMINDER}"""
    response = (client or OpenAI(api_key=api_key)).responses.create(
        model=model,
        input=[{"role": "system", "content": prompt}, {"role": "user", "content": f"問題：{question}\n實際條件：{json.dumps(applied_filters, ensure_ascii=False)}\n候選資料：{candidate_context}"}],
        timeout=45,
    )
    return as_text(response.output_text)


def generate_design_proposal(question, applied_filters, candidate_context, api_key, model, client=None):
    prompt = f"""你是景觀植栽設計提案助理。你可以對候選植物的搭配方式提出創意建議，
但不得捏造植物的耐性、高度、基地適應性、生態功能或未提供的顏色與季節資料。
你只能從候選資料中的 plant_id 選植物。花、果、葉、月份、信心程度與複查狀態的事實必須來自候選資料。

景觀提案不得只有氣氛描述。你必須選出 6-8 株植物；候選不足時列出全部候選。
每一株必須有中文名、學名、plant_id、景觀角色，以及候選資料中的花／果／葉色或季節依據。
若 design_palette_name 有值，這是系統的設計色調翻譯；不得說資料原本標示該色調名稱。
若 unverified_terms 有值，這些需求沒有可驗證欄位；不得因此說沒有候選植物，需在資料提醒中說明。

answer 必須使用以下固定三段式 Markdown，並保留換行：

一、查詢結論與推薦植栽
第一句用日常語言說明找到幾株植物、整體搭配概念與主要可確認條件。
必須依低層植栽、中層植栽、高層植栽、其他型態列出選定植物；每株格式為：
1. 中文名｜scientific_name｜plant_id：實際 plant_id｜景觀角色：角色名稱
每一層沒有候選時，寫「目前候選資料未找到合適選項」。
必須在本節最後加上一句：「以上為依植物型態／生長型態進行的景觀分層推定，並非實際株高資料。」

二、判斷依據
只根據候選資料，逐一說明每個景觀角色所使用的植物型態、花／果／葉色、月份或觀賞部位。

三、資料品質與設計提醒
說明資料信心程度、needs_review 狀態與資料限制。
最後必須附上：{FINAL_REMINDER}

只能輸出下列 JSON，不要加任何說明：
{{
  "answer": "完整的固定三段式 Markdown 回答，必須直接列出每株植物名稱與 plant_id",
  "plant_ids": ["只能是候選資料內的 plant_id，6-8 筆；候選不足時可少於 6 筆"],
  "roles": [
    {{"plant_id": "候選 plant_id", "role": "主景/中層量體/前景/色彩焦點/背景等", "rationale": "只描述設計上的搭配角色，不宣稱未提供的植物事實"}}
  ],
  "data_limit": "簡短說明資料無法確認的基地條件；若無則空字串"
}}
"""
    response = (client or OpenAI(api_key=api_key)).responses.create(
        model=model,
        input=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"使用者需求：{question}\n設計與篩選條件：{json.dumps(applied_filters, ensure_ascii=False)}\n最多可用的候選植物：{candidate_context}"},
        ],
        timeout=45,
    )
    return _parse_json(response.output_text, {})


def validate_design_proposal(proposal, candidate_df, fallback_df, requested_count):
    known_ids = {as_text(value) for value in candidate_df.get("plant_id", [])}
    requested_ids = proposal.get("plant_ids", []) if isinstance(proposal, dict) else []
    valid_ids = []
    for plant_id in requested_ids:
        plant_id = as_text(plant_id)
        if plant_id in known_ids and plant_id not in valid_ids:
            valid_ids.append(plant_id)
        if len(valid_ids) >= min(12, requested_count):
            break
    selected = candidate_df[candidate_df["plant_id"].isin(valid_ids)].copy()
    if valid_ids:
        selected["_proposal_order"] = selected["plant_id"].map({plant_id: index for index, plant_id in enumerate(valid_ids)})
        selected = selected.sort_values("_proposal_order").drop(columns="_proposal_order")
    if selected.empty:
        selected = fallback_df.head(requested_count).copy()

    roles = {}
    for item in proposal.get("roles", []) if isinstance(proposal, dict) else []:
        if not isinstance(item, dict):
            continue
        plant_id = as_text(item.get("plant_id"))
        if plant_id in set(selected["plant_id"]):
            roles[plant_id] = {"role": as_text(item.get("role")), "rationale": as_text(item.get("rationale"))}
    return {
        "selected": selected,
        "answer": as_text(proposal.get("answer") or proposal.get("summary")) if isinstance(proposal, dict) else "",
        "roles": roles,
        "data_limit": as_text(proposal.get("data_limit")) if isinstance(proposal, dict) else "",
    }


def invalid_answer_plant_ids(answer, candidate_df):
    """Return any explicitly labelled plant ids that cannot be traced to candidates."""
    known_ids = {as_text(value) for value in candidate_df.get("plant_id", [])}
    mentioned = re.findall(r"plant_id\s*[：:]?\s*([A-Za-z0-9_-]+)", as_text(answer), flags=re.IGNORECASE)
    return sorted({plant_id for plant_id in mentioned if plant_id not in known_ids})


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
