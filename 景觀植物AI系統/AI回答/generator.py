"""Grounded answer and design proposal helpers."""

import json
import re

from openai import OpenAI

from ..資料.normalizer import as_text
from ..查詢.filters import _parse_json
from ..查詢.schema import FINAL_REMINDER, PLANTING_DESIGN_FRAMEWORK


def generate_grounded_answer(question, applied_filters, candidate_context, api_key, model, client=None):
    prompt = f"""你是一位景觀植栽知識助理。
你只能根據提供的候選植物資料回答，不得使用外部知識，也不得捏造候選資料中不存在的資訊。

{PLANTING_DESIGN_FRAMEWORK}

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


def generate_design_proposal(question, applied_filters, candidate_context, api_key, model, composition=None, client=None):
    # ``selected`` is a DataFrame used by the UI and cannot be JSON-encoded for
    # the Responses API.  The model only needs the locked design metadata; its
    # candidate facts are already supplied separately in ``candidate_context``.
    composition_prompt_data = {
        key: value
        for key, value in (composition or {}).items()
        if key != "selected"
    }
    prompt = f"""你是景觀植栽設計提案助理。你可以對候選植物的搭配方式提出創意建議，
但不得捏造植物的耐性、高度、基地適應性、生態功能或未提供的顏色與季節資料。
你只能從候選資料中的 plant_id 選植物。花、果、葉、月份、信心程度與複查狀態的事實必須來自候選資料。

{PLANTING_DESIGN_FRAMEWORK}

景觀提案不得只有氣氛描述。系統已先依園林規則建立「最終配置方案」；其中的 plant_id 就是本次提案唯一可用的植物清單。你必須逐一保留全部 plant_id 及其既定角色與順序，不得新增、刪除、替換或自行改選任何植物。
每一株必須有中文名、學名、plant_id、系統既定的景觀角色，以及候選資料中的花／果／葉色或季節依據。
不得宣稱香氣、生態功能、庭院適應性、成株高度、株距、日照、耐旱或資料表未列的植物特性。不得自行總結「全部無 needs_review」；資料品質由系統顯示。
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
  "plant_ids": ["必須與系統建立的配置方案 plant_id 完全相同，且順序相同"],
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
            {"role": "user", "content": f"使用者需求：{question}\n設計與篩選條件：{json.dumps(applied_filters, ensure_ascii=False)}\n系統建立的配置方案：{json.dumps(composition_prompt_data, ensure_ascii=False)}\n可用候選植物：{candidate_context}"},
        ],
        timeout=45,
    )
    return _parse_json(response.output_text, {})


def generate_design_interpretation(question, composition, api_key, model, client=None):
    """Write only a cautious design reading; Python renders all plant facts."""
    prompt_data = {key: value for key, value in (composition or {}).items() if key != "selected"}
    prompt = """你是景觀植栽設計助理。請以台灣繁體中文撰寫設計解讀，且不要自行加上「設計解讀」標題，
只說明系統已確定的角色如何形成視覺層次、主從關係、群植或帶狀配置的方向。
必須先用一段話說明整體主從關係，再以「各植物協作」小節逐一列出系統固定配置中的每一株中文名、固定角色、selection_evidence 欄的資料依據，以及 collaboration 欄提供的協作方式。植物名稱、角色、資料依據與協作方式不可遺漏、替換或改寫成其他植物事實。
不得加入學名、plant_id、月份、花果葉顏色、信心程度或 needs_review；這些事實由系統表格固定呈現。
不得新增任何植物事實，也不得宣稱適合庭院、可靠、完整、全期覆蓋、已確立、耐旱、日照、香氣、生態功能、株距或成株尺度。
不可把使用者的季節需求說成每株植物都已涵蓋該期間；各植物實際月份以系統表格為準。不可把依型態推定的高、中、低層或主從關係說成資料表已證實的事實。
若有缺層或資料限制，請以「候選資料仍需現地確認」的保守方式說明。只輸出 Markdown 文字，不要 JSON。"""
    response = (client or OpenAI(api_key=api_key)).responses.create(
        model=model,
        input=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"使用者需求：{question}\n系統固定配置：{json.dumps(prompt_data, ensure_ascii=False)}"},
        ],
        timeout=45,
    )
    return as_text(response.output_text)


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


def answer_uses_exact_composition(answer, selected_df, all_candidate_df):
    """Ensure an AI proposal lists all and only the program-selected plants."""
    expected_ids = {as_text(value) for value in selected_df.get("plant_id", [])}
    all_ids = {as_text(value) for value in all_candidate_df.get("plant_id", [])}
    text = as_text(answer)
    mentioned_ids = {plant_id for plant_id in all_ids if plant_id and plant_id in text}
    return bool(expected_ids) and mentioned_ids == expected_ids


__all__ = [
    "FINAL_REMINDER",
    "PLANTING_DESIGN_FRAMEWORK",
    "generate_design_proposal",
    "generate_design_interpretation",
    "generate_grounded_answer",
    "answer_uses_exact_composition",
    "invalid_answer_plant_ids",
    "validate_design_proposal",
]
