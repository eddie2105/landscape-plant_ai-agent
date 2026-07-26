import json
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# When Streamlit executes this file directly, its folder is first on sys.path.
# Put the project root first so ``app`` resolves to the preserved legacy app.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if not sys.path or sys.path[0] != str(PROJECT_ROOT):
    if str(PROJECT_ROOT) in sys.path:
        sys.path.remove(str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT))

from 景觀植物AI系統.AI回答.context import build_ai_context
from 景觀植物AI系統.AI回答.generator import (
    generate_design_proposal,
    generate_grounded_answer,
    invalid_answer_plant_ids,
    validate_design_proposal,
)
from 景觀植物AI系統.介面.charts import build_coverage_analysis, build_seasonal_matrix
from 景觀植物AI系統.推薦.scoring import score_candidates, select_recommendations
from 景觀植物AI系統.查詢.filters import (
    DEFAULT_FILTERS,
    extract_known_filters,
    merge_ai_and_manual_filters,
    merge_known_and_ai_filters,
    parse_question_to_filters,
)
from 景觀植物AI系統.查詢.search import apply_filters, find_relaxed_candidates
from 景觀植物AI系統.資料.matrix_loader import load_matrix as _load_matrix
from 景觀植物AI系統.資料.normalizer import build_filter_options
from 景觀植物AI系統.設定.settings import (
    disable_dead_local_proxy,
    load_matrix_settings as _load_matrix_settings,
)


QUERY_LOGIC_VERSION = "2026-07-17-unified-answer-v8"
EXAMPLE_QUESTIONS = [
    "我想找春天開粉紅花的灌木。",
    "秋天有果實的樹有哪些？",
    "我想找四季都有變化的植物。",
    "幫我規劃一組夏天有變化的庭院植物。",
]


def load_matrix_settings():
    return _load_matrix_settings()


def load_matrix():
    return _load_matrix()


def render_filters(options):
    with st.sidebar:
        st.header("輔助篩選")
        if st.button("清除全部條件", use_container_width=True):
            for key in list(st.session_state):
                if key.startswith("filter_"):
                    del st.session_state[key]
            st.rerun()
        months = st.multiselect("月份", range(1, 13), format_func=lambda value: f"{value}月", key="filter_months")
        parts = st.multiselect("觀賞重點", ["花", "果", "葉"], key="filter_parts")
        plant_types = st.multiselect("植物型態", options["plant_types"], key="filter_plant_types")
        growth_forms = st.multiselect("生長型態", options["growth_forms"], key="filter_growth_forms")
        flower_colors = st.multiselect("花色", options["flower_colors"], key="filter_flower_colors")
        fruit_colors = st.multiselect("果色", options["fruit_colors"], key="filter_fruit_colors")
        leaf_colors = st.multiselect("葉色", options["leaf_colors"], key="filter_leaf_colors")
        confidence = st.multiselect("資料信心", ["high", "medium", "low"], key="filter_confidence")
        exclude_review = st.checkbox("排除需要人工複查的資料", key="filter_exclude_review")
        requested_count = st.slider("推薦數量", 5, 20, 8, key="filter_requested_count")
        response_mode = st.radio("回答方式", ["查資料", "景觀提案"], key="filter_response_mode")
    return {
        "months": months, "ornamental_parts": parts, "plant_types": plant_types,
        "growth_forms": growth_forms, "flower_colors": flower_colors,
        "fruit_colors": fruit_colors, "leaf_colors": leaf_colors,
        "confidence": confidence, "exclude_needs_review": exclude_review,
        "requested_count": requested_count, "response_mode": response_mode,
    }


def render_plant_cards(df, roles=None):
    roles = roles or {}
    for _, row in df.iterrows():
        with st.expander(f"{row['chinese_name']} | {row['scientific_name']} | {row['plant_id']}", expanded=False):
            st.write(f"**型態：** {row['plant_type']}　**生長型態：** {row['growth_form']}")
            st.write(f"**花／果／葉色：** {row['flower_color'] or '-'}／{row['fruit_color'] or '-'}／{row['leaf_color'] or '-'}")
            st.write(f"**符合原因：** {row['match_reasons']}　**匹配分數：** {row['match_score']}")
            st.write(f"**資料信心：** {row['confidence'] or '未標示'}")
            role = roles.get(row["plant_id"])
            if role:
                st.write(f"**景觀角色：** {role['role'] or '景觀搭配植物'}")
                if role["rationale"]:
                    st.write(f"**提案想法：** {role['rationale']}")
            if row["needs_review"]:
                st.warning("此筆資料需要人工複查。")


def build_proposal_overview(df, roles):
    rows = []
    for _, row in df.iterrows():
        role = roles.get(row["plant_id"], {})
        color_evidence = []
        for label, column in (("花", "flower_color"), ("果", "fruit_color"), ("葉", "leaf_color")):
            value = str(row.get(column, "") or "").strip()
            if value:
                color_evidence.append(f"{label}：{value}")
        rows.append(
            {
                "景觀角色": role.get("role") or "景觀搭配植物",
                "植物": row["chinese_name"],
                "型態": row["plant_type"],
                "資料可確認的色彩": "；".join(color_evidence) or "色彩資料未提供",
            }
        )
    return pd.DataFrame(rows)


def describe_applied_filters(filters):
    descriptions = []
    if filters.get("months"):
        descriptions.append("月份：" + "、".join(f"{month}月" for month in filters["months"]))
    if filters.get("ornamental_parts"):
        descriptions.append("觀賞重點：" + "、".join(filters["ornamental_parts"]))
    labels = {"plant_types": "植物型態", "growth_forms": "生長型態", "flower_colors": "花色", "fruit_colors": "果色", "leaf_colors": "葉色"}
    for field, label in labels.items():
        if filters.get(field):
            descriptions.append(f"{label}：" + "、".join(filters[field]))
    if filters.get("requires_year_round_interest"):
        descriptions.append("全年觀賞性")
    if filters.get("requires_seasonal_change"):
        descriptions.append("季節變化")
    if filters.get("requires_composition"):
        descriptions.append("景觀組合模式")
    if filters.get("design_palette_name"):
        descriptions.append(
            f"設計色調：{filters['design_palette_name']}（{'、'.join(filters['design_palette_colors'])}）"
        )
    return "；".join(descriptions) or "沒有指定資料條件，顯示所有植物資料。"


def render_results(result):
    candidates = result["candidates"]
    selected = result["selected"]
    coverage = build_coverage_analysis(selected)
    st.subheader("景觀提案" if result.get("design_proposal") else "AI 查詢結論")
    if result.get("answer"):
        st.markdown(result["answer"])
    else:
        st.info("AI 暫時無法使用，以下仍保留 Python 篩選與排序結果。")
    if result.get("design_proposal"):
        st.subheader("本次搭配植栽")
        if selected.empty:
            st.warning("目前沒有可用於搭配的候選植物。")
        else:
            st.dataframe(
                build_proposal_overview(selected, result.get("roles") or {}),
                hide_index=True,
                use_container_width=True,
            )
    st.subheader("本次查詢依據")
    st.write(describe_applied_filters(result["filters"]))
    if result["filters"].get("unverified_terms"):
        st.info("目前資料無法確認：" + "、".join(result["filters"]["unverified_terms"]) + "。以下結果仍依可驗證條件提供。")
    if result.get("approximation_note"):
        st.info(result["approximation_note"])
    if result["filters"].get("requires_composition"):
        st.info("景觀組合模式會優先讓高、中、低層與不同花果葉角色共同出現；這是季節視覺搭配，不代表已驗證基地適應性。")
    with st.expander("研究與資料細節", expanded=False):
        st.json(result["filters"], expanded=False)
    metrics = st.columns(5)
    metrics[0].metric("篩選前", result["total"])
    metrics[1].metric("篩選後", len(candidates))
    metrics[2].metric("推薦數", len(selected))
    metrics[3].metric("high", int((selected["confidence"] == "high").sum()))
    metrics[4].metric("待複查", int(selected["needs_review"].sum()))
    st.subheader("推薦植物")
    if selected.empty:
        st.warning("目前沒有完全符合的資料。可放寬月份、顏色或植物型態後再試。")
    else:
        render_plant_cards(selected, result.get("roles"))
        st.subheader("12 個月季節矩陣")
        st.caption("花、果、葉為資料表中的實際月份標記；- 代表該月無資料。")
        st.dataframe(build_seasonal_matrix(selected), hide_index=True, use_container_width=True)
        st.subheader("月份覆蓋分析")
        chart_data = coverage.melt("月份", var_name="觀賞特徵", value_name="植物數")
        st.altair_chart(alt.Chart(chart_data).mark_line(point=True).encode(x="月份:N", y="植物數:Q", color="觀賞特徵:N", tooltip=["月份", "觀賞特徵", "植物數"]).properties(height=280), use_container_width=True)
        weak = coverage.loc[coverage["任一觀賞特徵"] == 0, "月份"].tolist()
        st.info(f"整體觀賞性沒有覆蓋的月份：{'、'.join(weak) if weak else '無'}")
    review_count = int(selected["needs_review"].sum()) if not selected.empty else 0
    if review_count:
        st.warning(f"資料品質提醒：本次推薦有 {review_count} 筆需要人工複查；請將月份資訊視為待驗證資料。")
    if result.get("data_limit"):
        st.info("資料限制：" + result["data_limit"])


def render_app():
    disable_dead_local_proxy()
    st.set_page_config(page_title="景觀植栽 AI 查詢", page_icon="🌿", layout="wide")
    st.title("景觀植栽 AI 查詢")
    st.caption("用自然語言描述植栽需求，系統依季節矩陣與輔助篩選條件查詢適合植物。")
    try:
        matrix_df, source = load_matrix()
    except Exception as exc:
        st.error(str(exc)); return
    manual_filters = render_filters(build_filter_options(matrix_df))
    st.caption(f"資料來源：{source}｜共 {len(matrix_df)} 筆｜待複查 {int(matrix_df['needs_review'].sum())} 筆")
    for index, example in enumerate(EXAMPLE_QUESTIONS):
        if st.button(example, key=f"example_{index}"):
            st.session_state["question"] = example
    question = st.text_area("請描述你的植栽需求", placeholder="例如：想找 3 到 5 月有紫花的灌木。", height=130, key="question")
    if st.button("詢問 AI", type="primary"):
        if not question.strip():
            st.warning("請先輸入問題。")
        else:
            cache_key = json.dumps(
                {"version": QUERY_LOGIC_VERSION, "question": question.strip(), "filters": manual_filters},
                ensure_ascii=False,
                sort_keys=True,
            )
            cached = st.session_state.get("matrix_result")
            if cached and cached.get("cache_key") == cache_key:
                st.info("已顯示相同問題與篩選條件的既有結果。")
                render_results(cached)
                return
            settings = load_matrix_settings()
            options = build_filter_options(matrix_df)
            known_filters = extract_known_filters(question, options)
            try:
                with st.spinner("正在解析問題與整理資料..."):
                    ai_filters = parse_question_to_filters(question, settings["OPENAI_API_KEY"], settings["OPENAI_MODEL"])
            except Exception:
                ai_filters = DEFAULT_FILTERS.copy()
                st.info("AI 條件解析暫時不可用，已改以側欄條件進行查詢。")
            applied = merge_ai_and_manual_filters(merge_known_and_ai_filters(ai_filters, known_filters), manual_filters)
            applied["design_proposal_mode"] = (
                manual_filters["response_mode"] == "景觀提案"
                or bool(applied.get("design_palette_name"))
            )
            if applied["design_proposal_mode"]:
                applied["requires_composition"] = True
            candidates = score_candidates(apply_filters(matrix_df, applied), applied)
            approximation_note = ""
            if candidates.empty:
                relaxed_candidates, relaxed_field = find_relaxed_candidates(matrix_df, applied)
                if not relaxed_candidates.empty:
                    candidates = score_candidates(relaxed_candidates, applied)
                    approximation_note = f"找不到完全符合條件的資料，以下先放寬「{relaxed_field}」提供近似結果。"
            selected = select_recommendations(candidates, applied)
            answer = ""
            roles = {}
            data_limit = ""
            if settings.get("OPENAI_API_KEY"):
                try:
                    with st.spinner("AI 正在根據候選資料整理回答..."):
                        context_rows = 55 if applied["design_proposal_mode"] else 20
                        candidate_context = build_ai_context(candidates, applied, max_rows=context_rows)
                        if applied["design_proposal_mode"]:
                            proposal = generate_design_proposal(question, applied, candidate_context, settings["OPENAI_API_KEY"], settings["OPENAI_MODEL"])
                            proposal_result = validate_design_proposal(proposal, candidates.head(context_rows), selected, applied["requested_count"])
                            selected = proposal_result["selected"]
                            answer = proposal_result["answer"]
                            roles = proposal_result["roles"]
                            data_limit = proposal_result["data_limit"]
                        else:
                            answer = generate_grounded_answer(question, applied, candidate_context, settings["OPENAI_API_KEY"], settings["OPENAI_MODEL"])
                            invalid_ids = invalid_answer_plant_ids(answer, candidates)
                            if invalid_ids:
                                answer = "AI 回答出現無法回溯至候選資料的 plant_id，因此未採用文字回答；以下顯示 Python 篩選與排序結果。"
                except Exception:
                    st.info("AI 回答暫時不可用，已顯示可追溯的篩選結果。")
            st.session_state["matrix_result"] = {"cache_key": cache_key, "total": len(matrix_df), "filters": applied, "candidates": candidates, "selected": selected, "answer": answer, "roles": roles, "data_limit": data_limit, "design_proposal": applied["design_proposal_mode"], "approximation_note": approximation_note}
    if "matrix_result" in st.session_state:
        render_results(st.session_state["matrix_result"])


if __name__ == "__main__":
    render_app()
