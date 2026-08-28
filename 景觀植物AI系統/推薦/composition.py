"""Deterministic landscape-composition helpers.

This module turns ranked, traceable plant candidates into a small planting
composition before an AI writes the proposal.  It only makes design-role
inferences from the fields already present in the matrix; it never invents
site suitability, mature size, quantities, or planting distances.
"""

import pandas as pd

from ..資料.normalizer import as_text, normalize_boolean
from ..查詢.schema import MONTH_FIELD_PREFIXES, MONTH_KEYS


ROLE_SPECS = (
    ("骨架／背景候選", "高層", "作為背景或重複配置", "建立初步空間骨架與視覺背景"),
    ("中層量體候選", "中層", "以塊狀或群植方式配置", "形成初步中段量體，銜接背景與前景"),
    ("前景／收邊候選", "低層", "以前景帶狀或成片方式配置", "形成初步前景、收邊或地表覆蓋"),
)
SUPPORTING_ROLE = "季節銜接候選"
SEASONAL_ROLE = "季節花果葉焦點候選"


def landscape_layer(row):
    """Infer a design layer from recorded plant/growth type, not plant height."""
    text = f"{as_text(row.get('plant_type'))} {as_text(row.get('growth_form'))}"
    if "喬木" in text:
        return "高層"
    if "灌木" in text:
        return "中層"
    if any(word in text for word in ("地被", "草本", "花壇", "香草")):
        return "低層"
    return "其他型態"


def _matches_requested_season(row, filters):
    months = filters.get("months", [])
    if not months:
        return False
    parts = filters.get("ornamental_parts") or list(MONTH_FIELD_PREFIXES)
    for month in months:
        key = MONTH_KEYS[month - 1]
        if any(normalize_boolean(row.get(f"{MONTH_FIELD_PREFIXES[part]}_{key}")) for part in parts):
            return True
    return False


def _seasonal_evidence(row, filters):
    """Return exact, recorded month evidence for this row and request."""
    requested_months = filters.get("months", [])
    requested_parts = filters.get("ornamental_parts") or list(MONTH_FIELD_PREFIXES)
    by_part = {}
    for part in requested_parts:
        prefix = MONTH_FIELD_PREFIXES[part]
        active = [month for month, key in enumerate(MONTH_KEYS, start=1) if normalize_boolean(row.get(f"{prefix}_{key}"))]
        matched = [month for month in active if not requested_months or month in requested_months]
        if matched:
            by_part[part] = matched
    matched_months = sorted({month for months in by_part.values() for month in months})
    if not requested_months:
        coverage = "未指定季節條件"
    elif set(requested_months).issubset(matched_months):
        coverage = "指定月份完整覆蓋"
    elif matched_months:
        coverage = "指定月份部分覆蓋"
    else:
        coverage = "指定月份無可確認紀錄"
    evidence_text = "；".join(f"{part}：{'、'.join(f'{month}月' for month in months)}" for part, months in by_part.items()) or "無可確認的指定季節紀錄"
    return {"by_part": by_part, "matched_months": matched_months, "coverage": coverage, "text": evidence_text}


def _composition_seasonal_coverage(rows, filters):
    """Describe coverage by the selected *group*, never by assumption."""
    requested_months = sorted(set(filters.get("months", [])))
    if not requested_months:
        return {
            "requested_months": [], "covered_months": [], "uncovered_months": [],
            "is_complete": None, "status": "未指定月份，不判定季節覆蓋。",
        }
    covered_months = sorted({
        month
        for row in rows
        for month in _seasonal_evidence(row, filters)["matched_months"]
    })
    uncovered_months = [month for month in requested_months if month not in covered_months]
    complete = not uncovered_months
    return {
        "requested_months": requested_months,
        "covered_months": covered_months,
        "uncovered_months": uncovered_months,
        "is_complete": complete,
        "status": "整組植物共同完整覆蓋指定月份" if complete else "整組植物僅部分覆蓋指定月份",
    }


def _choose_month_coverage_rows(remaining, selected_rows, roles, filters, requested_count):
    """Use remaining slots to fill months missing from the selected group."""
    if not filters.get("requires_full_month_coverage") or not filters.get("months"):
        return remaining
    while len(selected_rows) < requested_count:
        coverage = _composition_seasonal_coverage(selected_rows, filters)
        missing = set(coverage["uncovered_months"])
        if not missing:
            break
        best_row, best_gain = None, 0
        for _, row in remaining.iterrows():
            gain = len(missing.intersection(_seasonal_evidence(row, filters)["matched_months"]))
            if gain > best_gain:
                best_row, best_gain = row, gain
        if best_row is None:
            break
        selected_rows.append(best_row)
        roles[as_text(best_row.get("plant_id"))] = _role_data(
            best_row,
            "季節銜接候選",
            "依缺少月份作群植或重複配置",
            "補足整體組合尚未覆蓋的指定月份，讓季相由不同植物共同接續。",
            filters,
        )
        remaining = remaining.drop(index=best_row.name)
    return remaining


def _role_for_remaining(row, filters):
    layer = landscape_layer(row)
    evidence = _seasonal_evidence(row, filters)
    if layer == "其他型態":
        text = f"{as_text(row.get('plant_type'))} {as_text(row.get('growth_form'))}"
        return ("藤本垂直綠化候選" if "藤本" in text else "其他型態候選", "依基地條件作垂直或特殊型態配置", "作為非高、中、低層的條件式搭配")
    if layer == "高層":
        return ("高層季節表現候選", "在背景中重複或局部點置", "延續高層季節節奏")
    if layer == "中層":
        return ("中層花果過渡候選", "以塊狀或群植方式配置", "銜接中層量體與季節表現")
    if evidence["by_part"]:
        return ("前景季節草本候選", "以前景帶狀或成片方式配置", "提供近距離的季節觀賞")
    return ("前景地表覆蓋候選", "以前景帶狀或成片方式配置", "補足地表與前景層次")


def _role_data(row, role, pattern, purpose, filters):
    plant_id = as_text(row.get("plant_id"))
    evidence = as_text(row.get("match_reasons")) or "依候選資料的植物型態與季節資訊選入"
    seasonal_evidence = _seasonal_evidence(row, filters)
    selection_evidence = []
    if filters.get("months") and seasonal_evidence["by_part"]:
        selection_evidence.append(seasonal_evidence["text"])
    else:
        for label, column in (("花色", "flower_color"), ("果色", "fruit_color"), ("葉色", "leaf_color")):
            value = as_text(row.get(column))
            if value:
                selection_evidence.append(f"{label}：{value}")
        ornamental = as_text(row.get("ornamental_part"))
        if ornamental:
            selection_evidence.append(f"觀賞部位：{ornamental}")
    if not selection_evidence:
        selection_evidence.append("資料表僅可確認植物型態／生長型態")
    return {
        "plant_id": plant_id,
        "role": role,
        "rationale": f"{purpose}；{evidence}。",
        "planting_pattern": pattern,
        "purpose": purpose,
        "layer": landscape_layer(row),
        "seasonal_evidence": seasonal_evidence,
        "selection_evidence": "；".join(selection_evidence),
        "confidence": as_text(row.get("confidence")),
        "needs_review": normalize_boolean(row.get("needs_review")),
    }


def _design_concept(filters):
    months = filters.get("months", [])
    palette = as_text(filters.get("design_palette_name"))
    season_text = f"{''.join(f'{month}月' for month in months)}的季節表現" if months else "可確認的季節表現"
    palette_text = f"，以{palette}作為色彩方向" if palette else ""
    return f"以{season_text}建立主題{palette_text}，先形成層次骨架，再以量體、前景與季節焦點完成配置。"


def _is_water_feature(row):
    text = f"{as_text(row.get('plant_type'))} {as_text(row.get('growth_form'))}"
    return "水生" in text or "濕生" in text


def _join_names(rows, layer):
    names = [as_text(row.get("chinese_name")) for row in rows if landscape_layer(row) == layer]
    return "、".join(filter(None, names)) or "目前未選入此層植物"


def _add_collaboration_guidance(selected_rows, roles):
    """Add traceable design relationships after the final plant list is fixed."""
    high_names = _join_names(selected_rows, "高層")
    middle_names = _join_names(selected_rows, "中層")
    low_names = _join_names(selected_rows, "低層")
    other_names = _join_names(selected_rows, "其他型態")
    for row in selected_rows:
        plant_id = as_text(row.get("plant_id"))
        item = roles[plant_id]
        layer = item["layer"]
        if item["role"].startswith("主題植物"):
            text = f"作為主題焦點，與中層的「{middle_names}」形成前後景銜接，並由低層的「{low_names}」延伸至觀賞前景。"
        elif layer == "高層":
            text = f"與主題高層共同形成背景節奏；前方以「{middle_names}」銜接量體，底部由「{low_names}」完成前景過渡。"
        elif layer == "中層":
            text = f"配置在高層「{high_names}」之前形成量體，並與低層「{low_names}」以塊狀或群植方式銜接。"
        elif layer == "低層":
            text = f"配置於觀賞前景，以帶狀或成片方式承接中層「{middle_names}」，讓視線由地表過渡至高層「{high_names}」。"
        else:
            text = f"作為其他型態候選，需依基地條件安排；可與「{high_names}」、「{middle_names}」及「{low_names}」形成垂直或特殊位置的補充關係。"
        item["collaboration"] = text


def build_composition(candidate_df, filters, required_plant_ids=None):
    """Build a traceable planting composition from already ranked candidates.

    The first available high, middle, and low layer plants receive structural
    roles. A remaining candidate with requested seasonal evidence receives a
    seasonal-focus role; the rest remain supporting plants in rank order.
    """
    requested_count = int(filters.get("requested_count", 8) or 8)
    requested_count = min(20, max(1, requested_count))
    empty = candidate_df.iloc[0:0].copy()
    if candidate_df.empty:
        return {
            "design_concept": "目前沒有可用候選植物，無法建立植栽配置。",
            "selected": empty,
            "roles": {},
            "unfilled_roles": [role for role, _, _, _ in ROLE_SPECS],
            "data_limit": "資料不足以建立植栽配置。",
        }

    remaining = candidate_df.drop_duplicates(subset="plant_id").copy()
    if not filters.get("requires_water_feature"):
        remaining = remaining.loc[~remaining.apply(_is_water_feature, axis=1)].copy()
    selected_rows, roles, unfilled_roles = [], {}, []
    theme_filters = {
        **filters,
        "months": filters.get("theme_months") or filters.get("months", []),
    }

    # A named plant is the non-negotiable theme plant.  It must appear in the
    # proposal, while other candidates can still complete the planting layers.
    for plant_id in required_plant_ids or []:
        named_rows = remaining[remaining["plant_id"].map(as_text) == as_text(plant_id)]
        if named_rows.empty or len(selected_rows) >= requested_count:
            continue
        row = named_rows.iloc[0]
        layer = landscape_layer(row)
        purpose = "保留使用者明確指定的植物作為方案主題"
        roles[as_text(row.get("plant_id"))] = _role_data(
            row,
            f"主題植物／{layer}季節焦點候選",
            "作為視覺焦點並與其他層次重複或群植配置",
            purpose,
            theme_filters,
        )
        selected_rows.append(row)
        remaining = remaining.drop(index=row.name)

    for role, target_layer, pattern, purpose in ROLE_SPECS:
        if any(landscape_layer(row) == target_layer for row in selected_rows):
            continue
        matches = remaining[remaining.apply(landscape_layer, axis=1) == target_layer]
        if matches.empty:
            unfilled_roles.append(role)
            continue
        row = matches.iloc[0]
        selected_rows.append(row)
        roles[as_text(row.get("plant_id"))] = _role_data(row, role, pattern, purpose, filters)
        remaining = remaining.drop(index=row.name)

    # Keep structural layers first, then use open slots to let several plants
    # jointly cover a requested season.
    remaining = _choose_month_coverage_rows(remaining, selected_rows, roles, filters, requested_count)

    seasonal_matches = remaining[remaining.apply(lambda row: _matches_requested_season(row, filters), axis=1)]
    if not seasonal_matches.empty and len(selected_rows) < requested_count:
        row = seasonal_matches.iloc[0]
        selected_rows.append(row)
        roles[as_text(row.get("plant_id"))] = _role_data(
            row, SEASONAL_ROLE, "作為視線可及處的點狀或小群植", "提供指定季節的可確認觀賞焦點", filters
        )
        remaining = remaining.drop(index=row.name)

    for _, row in remaining.iterrows():
        if len(selected_rows) >= requested_count:
            break
        selected_rows.append(row)
        role, pattern, purpose = _role_for_remaining(row, filters)
        roles[as_text(row.get("plant_id"))] = _role_data(row, role, pattern, purpose, filters)

    selected_ids = [as_text(row.get("plant_id")) for row in selected_rows]
    if not selected_ids:
        return {
            "design_concept": "候選植物皆屬水生／濕生型態，但使用者沒有提出水景需求，因此未建立配置。",
            "selected": empty,
            "roles": {},
            "unfilled_roles": [role for role, _, _, _ in ROLE_SPECS],
            "data_limit": "若基地有水景、水池或濕地，請在需求中明確提出後再納入水生／濕生植物。",
        }
    selected = candidate_df[candidate_df["plant_id"].map(as_text).isin(selected_ids)].copy()
    selected["_composition_order"] = selected["plant_id"].map({plant_id: index for index, plant_id in enumerate(selected_ids)})
    selected = selected.sort_values("_composition_order").drop(columns="_composition_order")
    ordered_rows = [selected.loc[selected["plant_id"].map(as_text) == plant_id].iloc[0] for plant_id in selected_ids]
    _add_collaboration_guidance(ordered_rows, roles)
    seasonal_coverage = _composition_seasonal_coverage(ordered_rows, filters)

    missing_text = "、".join(unfilled_roles)
    review_names = selected.loc[selected["needs_review"].map(normalize_boolean), "chinese_name"].map(as_text).tolist()
    data_limit = (
        "本配置的層次、角色與協作關係是依植物型態建立的初步設計推定；"
        "資料表僅可確認型態、生長型態、花果葉色、月份與資料信心；"
        "日照、土壤、排水、成株尺度、株距、數量與維護需求仍須現地確認。"
    )
    if review_names:
        data_limit += "需要人工複查的植物：" + "、".join(review_names) + "。"
    if missing_text:
        data_limit += f"候選資料未找到可擔任{missing_text}的植物，因此未強行補足。"
    if filters.get("requires_full_month_coverage") and not seasonal_coverage["is_complete"]:
        uncovered = "、".join(f"{month}月" for month in seasonal_coverage["uncovered_months"])
        data_limit += f"本次選入植物未能共同覆蓋：{uncovered}；不可宣稱完整季節表現。"
    quality = {
        "total": len(selected),
        "high_confidence": int((selected["confidence"].map(as_text).str.casefold() == "high").sum()),
        "needs_review": len(review_names),
        "all_need_review": bool(len(selected) and len(review_names) == len(selected)),
    }
    return {
        "design_concept": _design_concept(filters),
        "selected": selected,
        "roles": roles,
        "unfilled_roles": unfilled_roles,
        "data_limit": data_limit,
        "quality": quality,
        "seasonal_coverage": seasonal_coverage,
        "items": [
            {
                "chinese_name": as_text(row.get("chinese_name")),
                "plant_id": as_text(row.get("plant_id")),
                "layer": roles[as_text(row.get("plant_id"))]["layer"],
                "role": roles[as_text(row.get("plant_id"))]["role"],
                "collaboration": roles[as_text(row.get("plant_id"))]["collaboration"],
                "selection_evidence": roles[as_text(row.get("plant_id"))]["selection_evidence"],
            }
            for row in ordered_rows
        ],
    }


__all__ = ["ROLE_SPECS", "build_composition", "landscape_layer"]
