"""Controlled intent parsing: AI returns intent JSON; Python selects plants."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd
from openai import OpenAI

from ..資料.normalizer import as_text, normalize_boolean, normalize_multivalue_text
from .filters import _parse_json
from .schema import MONTH_KEYS


INTENTS = {"herb_garden", "fragrant_garden", "edible_garden", "pollinator_garden", "native_garden", "seasonal_garden", "general"}
TAGS = {"香草", "芳香", "食用", "藥用", "觀花", "觀葉", "觀果", "誘蝶", "遮蔭", "收邊", "地被", "垂直綠化"}
COLOR_ALIASES = {
    "白": "白色", "白花": "白色", "white": "白色",
    "粉紅": "粉紅色", "粉紅花": "粉紅色", "pink": "粉紅色",
    "紅": "紅色", "red": "紅色", "黃": "黃色", "yellow": "黃色",
    "紫": "紫色", "purple": "紫色",
}
THEMES = {
    "cherry_blossom": {"scientific": ("prunus",), "names": ("山櫻花", "櫻花", "緋寒櫻"), "months": (3, 4, 5), "label": "櫻花主題"},
    "royal_poinciana": {"scientific": ("delonix regia",), "names": ("鳳凰木",), "months": (), "label": "鳳凰木主題"},
    "pine": {"scientific": ("pinus", "podocarpus"), "names": ("黑松", "臺灣五葉松", "台灣五葉松", "臺灣二葉松", "台灣二葉松", "小葉羅漢松", "大葉羅漢松"), "months": (), "label": "松樹主題"},
    "plum_blossom": {"scientific": ("armeniaca mume", "prunus mume"), "names": ("梅花", "梅樹"), "months": (12, 1, 2), "label": "梅樹主題"},
}


def new_design_intent():
    return {
        "primary_intent": "general", "required_tags": [], "preferred_tags": [], "native_only": False,
        "required_months": [], "flower_colors": [], "plant_types": [],
        "constraints": {"maintenance_level": None, "space_scale": None},
        "theme_concepts": [], "unavailable_conditions": [], "reasoning_summary": "",
        # These are deterministic, internal planning instructions.  They are
        # never supplied by the model as plant facts.
        "role_requests": [], "required_flower_months": [],
    }


def split_use_tags(value):
    """The schema declares a half-width comma as the only tag separator."""
    return [item.strip() for item in as_text(value).split(",") if item.strip()]


def _unique(values):
    return list(dict.fromkeys(value for value in values if value))


def _months(values):
    output = []
    for value in values if isinstance(values, list) else []:
        try:
            month = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= month <= 12 and month not in output:
            output.append(month)
    return sorted(output)


def _apply_keyword_guards(intent, question):
    text = as_text(question)
    required, preferred = set(intent["required_tags"]), set(intent["preferred_tags"])
    if any(word in text for word in ("香草花園", "香草植物", "香草")):
        intent["primary_intent"] = "herb_garden"; required.add("香草"); preferred.update(("芳香", "食用"))
    elif any(word in text for word in ("有香味", "芳香庭園", "香氛花園")):
        intent["primary_intent"] = "fragrant_garden"; required.add("芳香")
    elif any(word in text for word in ("食用花園", "料理花園", "可以採來煮菜", "可採摘")):
        intent["primary_intent"] = "edible_garden"; required.add("食用")
    elif "藥草" in text:
        required.add("藥用")
    elif any(word in text for word in ("蝴蝶", "蜜蜂", "生態花園", "蜜源")):
        intent["primary_intent"] = "pollinator_garden"; required.add("誘蝶")
    if any(word in text for word in ("台灣原生", "本土植物", "原生種")):
        intent["native_only"] = True
        if intent["primary_intent"] == "general": intent["primary_intent"] = "native_garden"
    if "低維護" in text: intent["constraints"]["maintenance_level"] = "低"
    if "小庭院" in text: intent["constraints"]["space_scale"] = "小庭院"
    concept_words = (("cherry_blossom", ("櫻花", "山櫻花")), ("royal_poinciana", ("鳳凰木",)), ("pine", ("松樹", "羅漢松")), ("plum_blossom", ("梅樹", "梅花")))
    # A theme is a hard fact only when the user actually named it.  Do not
    # preserve a theme that the model inferred from an unrelated flower query.
    intent["theme_concepts"] = []
    for concept, words in concept_words:
        if any(word in text for word in words): intent["theme_concepts"] = _unique(intent["theme_concepts"] + [concept])
    if ("春天" in text or "春季" in text) and ("夏天" in text or "夏季" in text):
        intent["primary_intent"] = "seasonal_garden"; intent["required_months"] = _unique(intent["required_months"] + [3, 4, 5, 6, 7, 8])
    elif "春天" in text or "春季" in text:
        intent["required_months"] = _unique(intent["required_months"] + [3, 4, 5])
    elif "夏天" in text or "夏季" in text:
        intent["required_months"] = _unique(intent["required_months"] + [6, 7, 8])
    if ("粉紅" in text or "粉色" in text) and ("春天" in text or "春季" in text):
        intent["flower_colors"] = ["粉紅色"]
        intent["required_flower_months"] = [3, 4, 5]
    if "白花" in text:
        intent["flower_colors"] = ["白色"]
    # Plant types are controlled vocabulary.  Decorative phrases such as
    # "中層量體" must never be passed through as if they were data values.
    if "灌木" in text: intent["plant_types"] = ["灌木"]
    elif "喬木" in text and not ("搭配" in text or "焦點" in text): intent["plant_types"] = ["喬木"]
    if "常綠" in text:
        intent["unavailable_conditions"] = _unique(intent["unavailable_conditions"] + ["常綠：此條件尚未有可靠資料驗證"])
    if any(word in text for word in ("不要有毒", "無毒", "不含毒")):
        intent["unavailable_conditions"] = _unique(intent["unavailable_conditions"] + ["毒性：目前資料表未載入可靠的毒性欄位，無法驗證"])
    if any(word in text for word in ("不要長得太大", "不要太大", "高度限制")):
        intent["unavailable_conditions"] = _unique(intent["unavailable_conditions"] + ["植株高度：目前資料表未載入可靠的高度欄位，無法驗證"])

    # A single plant cannot be required to be both the herb layer and the
    # focal tree.  These pools are independently filtered and then combined.
    if "香草" in text and "喬木" in text and any(word in text for word in ("搭配", "焦點", "主景")):
        intent["plant_types"] = []
        intent["role_requests"] = [
            {"key": "香草植栽", "label": "香草植栽候選", "required_tags": ["香草"], "plant_types": [], "requires_flower": False},
            {"key": "視覺焦點喬木", "label": "視覺焦點喬木候選", "required_tags": [], "plant_types": ["喬木"], "requires_flower": False},
        ]
    elif any(word in text for word in ("主景樹", "視覺焦點的樹")) and any(word in text for word in ("前景", "低矮開花")):
        intent["plant_types"] = []
        intent["role_requests"] = [
            {"key": "主景樹", "label": "主景喬木候選", "required_tags": [], "plant_types": ["喬木"], "requires_flower": False},
            {"key": "前景開花植物", "label": "前景低層開花候選", "required_tags": [], "plant_types": ["地被", "香草/蔬菜"], "requires_flower": True},
        ]
    elif "兩套" in text and "觀花" in text and "觀葉" in text:
        intent["role_requests"] = [
            {"key": "觀花方向", "label": "觀花庭院方向", "required_tags": ["觀花"], "plant_types": [], "requires_flower": False},
            {"key": "觀葉方向", "label": "觀葉庭院方向", "required_tags": ["觀葉"], "plant_types": [], "requires_flower": False},
        ]
    intent["required_tags"] = [tag for tag in ("香草", "芳香", "食用", "藥用", "誘蝶") if tag in required]
    intent["preferred_tags"] = [tag for tag in ("芳香", "食用", "觀花", "觀葉", "觀果", "誘蝶") if tag in preferred and tag not in required]
    intent["required_months"] = sorted(set(intent["required_months"]))
    return intent


def normalize_design_intent(raw, question=""):
    raw = raw if isinstance(raw, dict) else {}
    intent = new_design_intent()
    intent["primary_intent"] = raw.get("primary_intent") if raw.get("primary_intent") in INTENTS else "general"
    for key in ("required_tags", "preferred_tags"):
        intent[key] = _unique(tag for tag in raw.get(key, []) if tag in TAGS) if isinstance(raw.get(key), list) else []
    intent["native_only"] = normalize_boolean(raw.get("native_only"))
    intent["required_months"] = _months(raw.get("required_months", []))
    raw_colors = raw.get("flower_colors", []) if isinstance(raw.get("flower_colors"), list) else []
    intent["flower_colors"] = _unique(COLOR_ALIASES.get(as_text(value).casefold(), as_text(value)) for value in raw_colors if as_text(value))
    allowed_types = {"喬木", "小喬木", "灌木", "地被", "草本", "香草/蔬菜", "藤本", "水生/濕生"}
    intent["plant_types"] = _unique(as_text(value) for value in raw.get("plant_types", []) if as_text(value) in allowed_types) if isinstance(raw.get("plant_types"), list) else []
    constraints = raw.get("constraints") if isinstance(raw.get("constraints"), dict) else {}
    intent["constraints"] = {
        "maintenance_level": as_text(constraints.get("maintenance_level")) if as_text(constraints.get("maintenance_level")) in {"低", "中", "高"} else None,
        "space_scale": as_text(constraints.get("space_scale")) if as_text(constraints.get("space_scale")) in {"小庭院", "中庭", "公園／大型開放空間"} else None,
    }
    intent["theme_concepts"] = _unique(item for item in raw.get("theme_concepts", []) if item in THEMES) if isinstance(raw.get("theme_concepts"), list) else []
    intent["unavailable_conditions"] = _unique(as_text(value) for value in raw.get("unavailable_conditions", []) if as_text(value)) if isinstance(raw.get("unavailable_conditions"), list) else []
    intent["reasoning_summary"] = as_text(raw.get("reasoning_summary"))
    # Role plans and flower-month requirements are generated by deterministic
    # keyword guards, then preserved during the later filter/select passes.
    if isinstance(raw.get("required_flower_months"), list):
        intent["required_flower_months"] = _months(raw["required_flower_months"])
    if isinstance(raw.get("role_requests"), list):
        roles = []
        for role in raw["role_requests"]:
            if not isinstance(role, dict):
                continue
            key = as_text(role.get("key"))
            if not key:
                continue
            roles.append({
                "key": key,
                "label": as_text(role.get("label")) or key,
                "required_tags": [tag for tag in role.get("required_tags", []) if tag in TAGS] if isinstance(role.get("required_tags"), list) else [],
                "plant_types": [kind for kind in role.get("plant_types", []) if kind in {"喬木", "小喬木", "灌木", "地被", "草本", "香草/蔬菜", "藤本", "水生/濕生"}] if isinstance(role.get("plant_types"), list) else [],
                "requires_flower": normalize_boolean(role.get("requires_flower")),
            })
        intent["role_requests"] = roles
    return _apply_keyword_guards(intent, question) if question else intent


SYSTEM_PROMPT = """只輸出 JSON。不可輸出植物名稱、學名、plant_id、推薦或替代植物。
欄位只能為 primary_intent, required_tags, preferred_tags, native_only, required_months, flower_colors, plant_types, constraints, theme_concepts, unavailable_conditions, reasoning_summary。
primary_intent 可為 herb_garden, fragrant_garden, edible_garden, pollinator_garden, native_garden, seasonal_garden, general；theme_concepts 僅能是 cherry_blossom, royal_poinciana, pine, plum_blossom。
香草花園／香草／香草植物：herb_garden、required_tags=[香草]、preferred_tags=[芳香,食用]；芳香、食用或藥用不能單獨算香草，名稱有草不可推論香草。
有香味的庭院／芳香庭園／香氛花園：fragrant_garden、required_tags=[芳香]。食用花園／料理花園／可以採來煮菜／可採摘：edible_garden、required_tags=[食用]。藥草：required_tags=[藥用]，提醒傳統用途資料非醫療建議。蝴蝶／蜜蜂／生態花園／蜜源：pollinator_garden、required_tags=[誘蝶]。
台灣原生／本土植物／原生種：native_only=true，待確認不可當原生。春天有櫻花、夏天有變化：seasonal_garden、required_months 至少含 3,6,7,8，theme_concepts 含 cherry_blossom；不可只因名稱含櫻主張花期。小庭院、低維護可解析 constraints，資料不能驗證時放 unavailable_conditions。"""


def parse_design_intent(question, api_key, model, client=None):
    response = (client or OpenAI(api_key=api_key)).responses.create(model=model, input=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": as_text(question)}], timeout=30)
    return normalize_design_intent(_parse_json(response.output_text, {}), question)


def _season_evidence(row, months):
    result = []
    for month in months:
        found = [label for label, prefix in (("花", "flower"), ("果", "fruit"), ("葉", "leaf")) if normalize_boolean(row.get(f"{prefix}_{MONTH_KEYS[month - 1]}"))]
        if found: result.append(f"{month}月{'＋'.join(found)}")
    return "、".join(result)


def _theme_match(row, concept):
    spec = THEMES[concept]
    scientific = as_text(row.get("scientific_name")).casefold()
    name = as_text(row.get("chinese_name"))
    if not (any(term in scientific for term in spec["scientific"]) or name in spec["names"]): return False
    return not spec["months"] or any(normalize_boolean(row.get(f"flower_{MONTH_KEYS[month - 1]}")) for month in spec["months"])


def _has_any_flower(row):
    return any(normalize_boolean(row.get(f"flower_{month}")) for month in MONTH_KEYS)


def _normalized_colors(value):
    return {
        COLOR_ALIASES.get(as_text(item).casefold(), as_text(item))
        for item in normalize_multivalue_text(value)
        if as_text(item)
    }


def _base_mask(df, intent, unavailable):
    mask = pd.Series(True, index=df.index)
    if intent["native_only"]:
        mask &= df.get("native_status", pd.Series("", index=df.index)).map(as_text).eq("台灣原生")
    if intent["flower_colors"]:
        wanted = set(intent["flower_colors"])
        mask &= df.get("flower_color", pd.Series("", index=df.index)).map(lambda value: bool(wanted.intersection(_normalized_colors(value))))
    if intent["required_flower_months"]:
        mask &= df.apply(lambda row: any(normalize_boolean(row.get(f"flower_{MONTH_KEYS[month - 1]}")) for month in intent["required_flower_months"]), axis=1)
    for key, field, label in (("maintenance_level", "maintenance_level", "低維護"), ("space_scale", "suitable_space_scale", "小庭院")):
        if not intent["constraints"].get(key):
            continue
        available = set(df.get(field, pd.Series(dtype=str)).map(as_text)).difference({"", "待確認"})
        if available:
            mask &= df[field].map(as_text).eq(intent["constraints"][key])
        else:
            unavailable.append(f"{label}：此條件尚未有可靠資料驗證")
    return mask


def _tag_and_type_mask(frame, required_tags, plant_types, requires_flower=False):
    mask = pd.Series(True, index=frame.index)
    if required_tags:
        required = set(required_tags)
        mask &= frame.get("use_tags", pd.Series("", index=frame.index)).map(lambda value: required.issubset(set(split_use_tags(value))))
    if plant_types:
        mask &= frame.get("plant_type", pd.Series("", index=frame.index)).map(as_text).isin(plant_types)
    if requires_flower:
        mask &= frame.apply(_has_any_flower, axis=1)
    return mask


def filter_by_design_intent(df, intent):
    intent = normalize_design_intent(intent)
    unavailable = list(intent["unavailable_conditions"])
    base = df.loc[_base_mask(df, intent, unavailable)].copy()
    role_requests = intent["role_requests"]
    if role_requests:
        pools = []
        for role in role_requests:
            pool = base.loc[_tag_and_type_mask(base, role["required_tags"], role["plant_types"], role["requires_flower"])].copy()
            if not pool.empty:
                pool["requested_roles"] = role["key"]
                pools.append(pool)
        if not pools:
            return {"candidates": base.iloc[0:0].copy(), "unavailable_conditions": _unique(unavailable), "data_shortage": "沒有可驗證的角色候選植物；系統不以無關植物補足。"}
        candidates = pd.concat(pools, ignore_index=True)
        candidates["requested_roles"] = candidates.groupby("plant_id")["requested_roles"].transform(lambda values: "、".join(dict.fromkeys(values)))
        base = candidates.drop_duplicates("plant_id", keep="first")
    else:
        base = base.loc[_tag_and_type_mask(base, intent["required_tags"], intent["plant_types"])].copy()
    if base.empty:
        criteria = "、".join((["台灣原生"] if intent["native_only"] else []) + intent["required_tags"] + intent["plant_types"])
        return {"candidates": base, "unavailable_conditions": _unique(unavailable), "data_shortage": f"沒有植物同時符合必要條件（{criteria or '目前可驗證條件'}）；系統不以一般植物替代。"}
    only_unverifiable_constraints = (not role_requests and not intent["required_tags"] and not intent["flower_colors"] and not intent["plant_types"] and not intent["required_months"] and not intent["theme_concepts"] and bool(intent["constraints"]["maintenance_level"] or intent["constraints"]["space_scale"]))
    if only_unverifiable_constraints and unavailable:
        return {"candidates": base.iloc[0:0].copy(), "unavailable_conditions": _unique(unavailable), "data_shortage": "此需求僅包含目前無法可靠驗證的基地尺度或維護條件，因此不推薦未經驗證的植物。"}
    themes = []
    for concept in intent["theme_concepts"]:
        found = base.loc[base.apply(lambda row: _theme_match(row, concept), axis=1)].copy()
        if found.empty:
            return {"candidates": base.iloc[0:0].copy(), "unavailable_conditions": _unique(unavailable), "data_shortage": f"找不到可驗證的{THEMES[concept]['label']}候選植物；系統不以其他植物替代。"}
        found["matched_theme_concept"] = concept; themes.append(found)
    candidates = base.copy()
    candidates["seasonal_evidence"] = candidates.apply(lambda row: _season_evidence(row, intent["required_months"]), axis=1)
    if intent["required_months"]: candidates = candidates[candidates["seasonal_evidence"].ne("")]
    if themes: candidates = pd.concat(themes + [candidates], ignore_index=True).drop_duplicates("plant_id", keep="first")
    candidates["seasonal_evidence"] = candidates.apply(lambda row: _season_evidence(row, intent["required_months"]), axis=1)
    candidates["matched_required_tags"] = candidates["use_tags"].map(lambda value: "、".join(tag for tag in intent["required_tags"] if tag in split_use_tags(value)))
    candidates["matched_preferred_tags"] = candidates["use_tags"].map(lambda value: "、".join(tag for tag in intent["preferred_tags"] if tag in split_use_tags(value)))
    return {"candidates": candidates, "unavailable_conditions": _unique(unavailable), "data_shortage": ""}


def select_intent_recommendations(candidates, intent, requested_count=8):
    if candidates.empty: return candidates
    intent = normalize_design_intent(intent)
    scored = candidates.copy()
    scored["intent_score"] = scored.apply(lambda row: len(set(split_use_tags(row.get("use_tags"))).intersection(intent["preferred_tags"])) * 4 + len(as_text(row.get("seasonal_evidence")).split("、")) * 2 + (5 if as_text(row.get("matched_theme_concept")) else 0) - (2 if normalize_boolean(row.get("needs_review")) else 0), axis=1)
    scored = scored.sort_values(["intent_score", "chinese_name"], ascending=[False, True])
    selected, ids, covered = [], set(), set()
    # Guarantee one result for every explicit role pool first.  This prevents
    # a focal-tree request from being silently swallowed by a herb filter.
    for role in intent.get("role_requests", []):
        key = role["key"]
        for _, row in scored[scored.get("requested_roles", pd.Series("", index=scored.index)).map(lambda value: key in as_text(value).split("、"))].iterrows():
            if row["plant_id"] not in ids:
                selected.append(row); ids.add(row["plant_id"])
                break
    for _, row in scored.iterrows():
        evidence = {int(item.split("月", 1)[0]) for item in as_text(row.get("seasonal_evidence")).split("、") if "月" in item}
        if as_text(row.get("matched_theme_concept")) or evidence.difference(covered):
            if row["plant_id"] not in ids and len(selected) < requested_count:
                selected.append(row); ids.add(row["plant_id"]); covered.update(evidence)
    for _, row in scored.iterrows():
        if len(selected) >= requested_count: break
        if row["plant_id"] not in ids: selected.append(row); ids.add(row["plant_id"])
    return pd.DataFrame(selected, columns=scored.columns)


def intent_month_coverage(selected, intent):
    requested = set(normalize_design_intent(intent)["required_months"]); covered = set()
    for value in selected.get("seasonal_evidence", pd.Series(dtype=str)):
        for item in as_text(value).split("、"):
            if "月" in item: covered.add(int(item.split("月", 1)[0]))
    return {"covered_months": sorted(covered.intersection(requested)), "uncovered_months": sorted(requested.difference(covered))}


def describe_design_intent(intent):
    return {"主要意圖": intent["primary_intent"], "必要用途標籤": "、".join(intent["required_tags"]) or "無", "偏好用途標籤": "、".join(intent["preferred_tags"]) or "無", "限定台灣原生": "是" if intent["native_only"] else "否", "季相月份": "、".join(f"{month}月" for month in intent["required_months"]) or "未指定", "主題代碼": "、".join(intent["theme_concepts"]) or "無"}


__all__ = ["describe_design_intent", "filter_by_design_intent", "intent_month_coverage", "new_design_intent", "normalize_design_intent", "parse_design_intent", "select_intent_recommendations", "split_use_tags"]
