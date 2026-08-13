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
    ("骨架／背景", "高層", "作為背景或重複配置", "建立空間骨架與視覺背景"),
    ("中層量體", "中層", "以塊狀或群植方式配置", "形成中段量體，銜接背景與前景"),
    ("前景／收邊", "低層", "以前景帶狀或成片方式配置", "收邊、地表覆蓋或提供近距離觀賞"),
)
SUPPORTING_ROLE = "補充搭配"
SEASONAL_ROLE = "季節焦點"


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


def _role_data(row, role, pattern, purpose):
    plant_id = as_text(row.get("plant_id"))
    evidence = as_text(row.get("match_reasons")) or "依候選資料的植物型態與季節資訊選入"
    return {
        "plant_id": plant_id,
        "role": role,
        "rationale": f"{purpose}；{evidence}。",
        "planting_pattern": pattern,
        "purpose": purpose,
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


def build_composition(candidate_df, filters):
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

    for role, target_layer, pattern, purpose in ROLE_SPECS:
        matches = remaining[remaining.apply(landscape_layer, axis=1) == target_layer]
        if matches.empty:
            unfilled_roles.append(role)
            continue
        row = matches.iloc[0]
        selected_rows.append(row)
        roles[as_text(row.get("plant_id"))] = _role_data(row, role, pattern, purpose)
        remaining = remaining.drop(index=row.name)

    seasonal_matches = remaining[remaining.apply(lambda row: _matches_requested_season(row, filters), axis=1)]
    if not seasonal_matches.empty and len(selected_rows) < requested_count:
        row = seasonal_matches.iloc[0]
        selected_rows.append(row)
        roles[as_text(row.get("plant_id"))] = _role_data(
            row, SEASONAL_ROLE, "作為視線可及處的點狀或小群植", "提供指定季節的可確認觀賞焦點"
        )
        remaining = remaining.drop(index=row.name)

    for _, row in remaining.iterrows():
        if len(selected_rows) >= requested_count:
            break
        selected_rows.append(row)
        roles[as_text(row.get("plant_id"))] = _role_data(
            row, SUPPORTING_ROLE, "依相鄰植栽以群植、帶狀或重複方式配置", "補足層次、色彩或季節銜接"
        )

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

    missing_text = "、".join(unfilled_roles)
    review_names = selected.loc[selected["needs_review"].map(normalize_boolean), "chinese_name"].map(as_text).tolist()
    data_limit = (
        "本配置僅依資料表可確認的型態、生長型態、花果葉色、月份與資料信心建立；"
        "日照、土壤、排水、成株尺度、株距、數量與維護需求仍須現地確認。"
    )
    if review_names:
        data_limit += "需要人工複查的植物：" + "、".join(review_names) + "。"
    if missing_text:
        data_limit += f"候選資料未找到可擔任{missing_text}的植物，因此未強行補足。"
    return {
        "design_concept": _design_concept(filters),
        "selected": selected,
        "roles": roles,
        "unfilled_roles": unfilled_roles,
        "data_limit": data_limit,
    }


__all__ = ["ROLE_SPECS", "build_composition", "landscape_layer"]
