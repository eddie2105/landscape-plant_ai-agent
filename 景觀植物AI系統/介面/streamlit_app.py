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
    generate_design_interpretation,
    generate_grounded_answer,
    invalid_answer_plant_ids,
)
from 景觀植物AI系統.介面.charts import build_coverage_analysis, build_seasonal_matrix
from 景觀植物AI系統.推薦.scoring import score_candidates, select_recommendations
from 景觀植物AI系統.推薦.composition import build_composition
from 景觀植物AI系統.查詢.filters import (
    DEFAULT_FILTERS,
    extract_known_filters,
    merge_ai_and_manual_filters,
    merge_known_and_ai_filters,
    parse_question_to_filters,
    suggest_plant_search_terms,
    new_default_filters,
)
from 景觀植物AI系統.查詢.search import apply_filters, find_relaxed_candidates
from 景觀植物AI系統.資料.matrix_loader import load_matrix as _load_matrix
from 景觀植物AI系統.資料.normalizer import build_filter_options
from 景觀植物AI系統.設定.settings import (
    disable_dead_local_proxy,
    load_matrix_settings as _load_matrix_settings,
)


QUERY_LOGIC_VERSION = "2026-08-28-traceable-season-and-name-v7"
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
    return {
        "months": months, "ornamental_parts": parts, "plant_types": plant_types,
        "growth_forms": growth_forms, "flower_colors": flower_colors,
        "fruit_colors": fruit_colors, "leaf_colors": leaf_colors,
        "confidence": confidence, "exclude_needs_review": exclude_review,
        "requested_count": requested_count,
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
                "固定層次": role.get("layer") or "依型態待確認",
                "固定角色": role.get("role") or "景觀搭配候選",
                "選入的資料依據": role.get("selection_evidence", "資料表僅可確認型態"),
                "植物": row["chinese_name"],
                "型態": row["plant_type"],
                "實際命中月份與部位": role.get("seasonal_evidence", {}).get("text", "未指定季節條件"),
                "季節覆蓋": role.get("seasonal_evidence", {}).get("coverage", "未指定季節條件"),
                "資料可確認的色彩": "；".join(color_evidence) or "色彩資料未提供",
                "資料狀態": f"{role.get('confidence') or '未標示'}／{'需要人工複查' if role.get('needs_review') else '未標示需複查'}",
                "與其他植栽的協作": role.get("collaboration", "系統尚未建立協作說明"),
            }
        )
    return pd.DataFrame(rows)


def describe_applied_filters(filters):
    descriptions = []
    if filters.get("months"):
        descriptions.append("月份：" + "、".join(f"{month}月" for month in filters["months"]))
    if filters.get("theme_months"):
        descriptions.append("指定主題植物月份：" + "、".join(f"{month}月" for month in filters["theme_months"]))
    if filters.get("ornamental_parts"):
        descriptions.append("觀賞重點：" + "、".join(filters["ornamental_parts"]))
    labels = {"plant_name_terms": "指定植物名稱", "plant_types": "植物型態", "growth_forms": "生長型態", "flower_colors": "花色", "fruit_colors": "果色", "leaf_colors": "葉色"}
    for field, label in labels.items():
        if filters.get(field):
            descriptions.append(f"{label}：" + "、".join(filters[field]))
    if filters.get("requires_year_round_interest"):
        descriptions.append("全年觀賞性")
    if filters.get("requires_seasonal_change"):
        descriptions.append("季節變化")
    if filters.get("requires_full_month_coverage"):
        descriptions.append("指定月份完整覆蓋")
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
    requested_months = result["filters"].get("months", [])
    requested_parts = result["filters"].get("ornamental_parts") or ["花", "果", "葉"]
    coverage = build_coverage_analysis(
        selected,
        requested_months=requested_months,
        requested_parts=requested_parts,
    )
    st.subheader("植栽建議與景觀提案")
    if result.get("answer"):
        if result.get("has_composition"):
            st.caption("設計解讀（植物事實、分層與資料品質以下方系統表格為準）")
        st.markdown(result["answer"])
    else:
        st.info("AI 暫時無法使用，以下仍保留 Python 篩選與排序結果。")
    if result.get("has_composition"):
        st.subheader("本次搭配植栽")
        if selected.empty:
            st.warning("目前沒有可用於搭配的候選植物。")
        else:
            st.dataframe(
                build_proposal_overview(selected, result.get("roles") or {}),
                hide_index=True,
                use_container_width=True,
            )
        quality = (result.get("composition") or {}).get("quality", {})
        seasonal_coverage = (result.get("composition") or {}).get("seasonal_coverage", {})
        if result["filters"].get("requires_full_month_coverage"):
            covered = "、".join(f"{month}月" for month in seasonal_coverage.get("covered_months", [])) or "無"
            missing = "、".join(f"{month}月" for month in seasonal_coverage.get("uncovered_months", [])) or "無"
            message = f"整組季節覆蓋：已確認 {covered}；未覆蓋 {missing}。"
            (st.success if seasonal_coverage.get("is_complete") else st.warning)(message)
        if quality.get("all_need_review"):
            st.error("資料品質限制：本次配置的植物全數需要人工複查；本結果僅可用於設計初選，不可直接作為定案依據。")
        elif quality.get("needs_review"):
            st.warning(f"資料品質提醒：本次配置有 {quality['needs_review']} 筆需要人工複查；請先複核相關資料再定案。")
    st.subheader("本次查詢依據")
    st.write(describe_applied_filters(result["filters"]))
    theme_requirements = result["filters"].get("theme_plant_requirements", [])
    if theme_requirements:
        composition_months = result["filters"].get("months", [])
        composition_text = "、".join(f"{month}月" for month in composition_months) or "未指定月份"
        theme_descriptions = []
        for requirement in theme_requirements:
            theme_name = requirement.get("phrase") or "、".join(requirement.get("terms", []))
            theme_months = requirement.get("months", [])
            if theme_months:
                theme_text = "、".join(f"{month}月" for month in theme_months)
                theme_descriptions.append(f"「{theme_name}」依 {theme_text} 與同子句條件查核")
            else:
                theme_descriptions.append(f"「{theme_name}」未被要求符合整體月份，依自身資料查核")
        st.info(f"系統理解：整體配置以 {composition_text} 為條件；" + "；".join(theme_descriptions) + "，並保留於提案。")
    if result["filters"].get("unverified_terms"):
        st.info("目前資料無法確認：" + "、".join(result["filters"]["unverified_terms"]) + "。以下結果仍依可驗證條件提供。")
    if result.get("approximation_note"):
        st.info(result["approximation_note"])
    if result.get("hard_filter_no_match"):
        st.error(
            "找不到符合指定植物名稱的資料，因此沒有自動改用其他植物或建立替代配置。"
            "若要看非指定植物的替代候選，請在問題中明確表示「可以看替代植物」。"
        )
    suggestion = result.get("keyword_suggestion")
    if suggestion:
        terms = suggestion.get("terms", [])
        st.info(
            "AI 找到可對應資料表的搜尋詞："
            + "、".join(terms)
            + f"（可找到 {suggestion.get('match_count', 0)} 筆）。系統尚未替換你的原始指定植物。"
        )
        if suggestion.get("interpretation"):
            st.caption("AI 關鍵字解讀：" + suggestion["interpretation"])
        if st.button("採用這組搜尋詞，重新生成提案", key="confirm_keyword_suggestion"):
            st.session_state["confirmed_keyword_question"] = result.get("question", "")
            st.session_state["confirmed_keyword_terms"] = terms
            st.session_state.pop("matrix_result", None)
            st.success("已採用搜尋詞；請按「生成植栽建議」重新查詢。")
    if result.get("ai_keyword_interpretation"):
        st.info("AI 關鍵字辨識：" + result["ai_keyword_interpretation"] + "；系統僅採用資料表實際命中的植物。")
    if result["filters"].get("requires_composition"):
        st.info("本案的高、中、低層與協作角色，是依植物型態建立的初步設計推定；實際株高、基地適應性與施工配置尚未驗證。")
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
        st.subheader("12個月季相分布熱圖")
        st.caption("色彩深淺代表本次選入植物中，具有該月份花、果或葉紀錄的不重複植物數。此數值不是植栽株數、花量或實際配置面積；同一植物可能同時具有多種觀賞特徵。")
        chart_data = coverage.melt(
            id_vars=["月份序號", "月份", "查詢指定月份"],
            value_vars=["花", "果", "葉"],
            var_name="觀賞特徵",
            value_name="植物數",
        )
        review_data = coverage.melt(
            id_vars=["月份"],
            value_vars=["花_需複查", "果_需複查", "葉_需複查"],
            value_name="需複查植物數",
        )
        review_data["觀賞特徵"] = review_data["variable"].str.replace("_需複查", "", regex=False)
        chart_data = chart_data.merge(
            review_data[["月份", "觀賞特徵", "需複查植物數"]],
            on=["月份", "觀賞特徵"],
            how="left",
        )
        maximum = max(1, int(chart_data["植物數"].max()))
        heatmap = alt.Chart(chart_data).mark_rect(stroke="#d1d5db", strokeWidth=1).encode(
            x=alt.X("月份:O", title="月份", sort=[f"{month}月" for month in range(1, 13)]),
            y=alt.Y("觀賞特徵:N", title="觀賞特徵", sort=["花", "果", "葉"]),
            color=alt.Color(
                "植物數:Q",
                title="不重複植物數",
                scale=alt.Scale(domain=[0, maximum], range=["#e5e7eb", "#14532d"]),
            ),
            tooltip=["月份", "觀賞特徵", "植物數", "需複查植物數", "查詢指定月份"],
        )
        labels = alt.Chart(chart_data).mark_text(fontSize=14, fontWeight="bold").encode(
            x=alt.X("月份:O", sort=[f"{month}月" for month in range(1, 13)]),
            y=alt.Y("觀賞特徵:N", sort=["花", "果", "葉"]),
            text=alt.Text("植物數:Q", format="d"),
            color=alt.condition(alt.datum["植物數"] > maximum / 2, alt.value("white"), alt.value("#1f2937")),
        )
        st.altair_chart((heatmap + labels).properties(height=180), use_container_width=True)

        st.markdown("#### 資料洞察")
        weak = coverage.loc[coverage["指定觀賞特徵植物數"] == 0, "月份"].tolist()
        if weak:
            st.info(f"沒有指定觀賞特徵紀錄的月份：{'、'.join(weak)}")
        else:
            st.success("本次選入植物在12個月皆有至少一項季相紀錄。")
        peak_count = int(coverage["指定觀賞特徵植物數"].max())
        peak_months = coverage.loc[coverage["指定觀賞特徵植物數"] == peak_count, "月份"].tolist()
        st.info(f"依查詢觀賞重點，不重複植物紀錄數最高的月份：{'、'.join(peak_months)}（{peak_count} 種）。")
        review_base = coverage["指定觀賞特徵植物數"]
        review_ratio = coverage["指定觀賞特徵需複查數"].div(review_base.where(review_base > 0)).fillna(0)
        high_review = coverage.loc[review_ratio >= 0.5, "月份"].tolist()
        if high_review:
            st.warning(f"需要人工複查資料占比較高（至少 50%）的月份：{'、'.join(high_review)}。")
        elif review_ratio.max() > 0:
            highest_review = coverage.loc[review_ratio == review_ratio.max(), "月份"].tolist()
            st.info(f"需要人工複查資料比例最高的月份：{'、'.join(highest_review)}（{review_ratio.max():.0%}）。")
        else:
            st.info("本次12個月的季相紀錄中，沒有需要人工複查的資料。")
    review_count = int(selected["needs_review"].sum()) if not selected.empty else 0
    if review_count:
        st.warning(f"資料品質提醒：本次推薦有 {review_count} 筆需要人工複查；請將月份資訊視為待驗證資料。")
    if result.get("data_limit"):
        st.info("資料限制：" + result["data_limit"])


def render_app():
    disable_dead_local_proxy()
    st.set_page_config(page_title="景觀植栽 AI 查詢", page_icon="🌿", layout="wide")
    st.title("景觀植栽 AI 查詢")
    st.caption("用自然語言描述植栽需求；系統會先查詢可追溯植物資料，再在需要時建立景觀配置。")
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
    if st.button("生成植栽建議", type="primary"):
        if not question.strip():
            st.warning("請先輸入問題。")
        else:
            confirmed_terms = []
            if st.session_state.get("confirmed_keyword_question") == question.strip():
                confirmed_terms = st.session_state.get("confirmed_keyword_terms", [])
            cache_key = json.dumps(
                {
                    "version": QUERY_LOGIC_VERSION,
                    "question": question.strip(),
                    "filters": manual_filters,
                    "confirmed_terms": confirmed_terms,
                },
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
                ai_filters = new_default_filters()
                st.info("AI 條件解析暫時不可用，已改以側欄條件進行查詢。")
            applied = merge_ai_and_manual_filters(merge_known_and_ai_filters(ai_filters, known_filters), manual_filters)
            # These terms are only applied after the user explicitly clicks
            # the confirmation control shown with an AI suggestion.
            if confirmed_terms:
                applied["plant_name_terms"] = confirmed_terms
            valid_options = {
                "plant_types": options["plant_types"],
                "growth_forms": options["growth_forms"],
                "flower_colors": options["flower_colors"],
                "fruit_colors": options["fruit_colors"],
                "leaf_colors": options["leaf_colors"],
            }
            for field, allowed in valid_options.items():
                applied[field] = [value for value in applied.get(field, []) if value in allowed]
            has_composition = bool(
                applied.get("design_palette_name")
                or applied.get("requires_composition")
            )
            if has_composition:
                applied["requires_composition"] = True
            theme_requirements = applied.get("theme_plant_requirements") or []
            named_filter_specs, named_frames, missing_theme_requirements = [], [], []
            if theme_requirements:
                for requirement in theme_requirements:
                    requirement_filters = {**applied}
                    for field in (
                        "months", "ornamental_parts", "plant_types", "growth_forms",
                        "flower_colors", "fruit_colors", "leaf_colors",
                    ):
                        requirement_filters[field] = requirement.get(field, [])
                    requirement_filters["plant_name_terms"] = requirement.get("terms", [])
                    named_filter_specs.append(requirement_filters)
                    requirement_matches = apply_filters(matrix_df, requirement_filters)
                    if requirement_matches.empty:
                        missing_theme_requirements.append(requirement)
                        continue
                    required_limit = max(1, int(requirement.get("max_required", 1)))
                    named_frames.append(score_candidates(requirement_matches, requirement_filters).head(required_limit))
                named_candidate_df = (
                    pd.concat(named_frames, ignore_index=True).drop_duplicates(subset="plant_id", keep="first")
                    if named_frames else matrix_df.iloc[0:0].copy()
                )
                named_filters = named_filter_specs[0]
            else:
                named_filters = {**applied}
                named_candidate_df = apply_filters(matrix_df, named_filters)
            named_theme_lookup = "主題" in question and not applied.get("plant_name_terms")
            hard_filter_no_match = bool(applied.get("plant_name_terms")) and (
                named_candidate_df.empty or bool(missing_theme_requirements)
            )
            # The general parser may flag an unfamiliar name in the user's
            # wording.  It only triggers a verified suggestion flow; it never
            # becomes a search constraint without confirmation.
            ai_name_request = bool(ai_filters.get("plant_name_terms")) and not applied.get("plant_name_terms")
            ai_keyword_interpretation = ""
            keyword_suggestion = None
            if (hard_filter_no_match or named_theme_lookup or ai_name_request) and settings.get("OPENAI_API_KEY"):
                try:
                    keyword_result = suggest_plant_search_terms(question, settings["OPENAI_API_KEY"], settings["OPENAI_MODEL"])
                    suggested_terms = keyword_result["terms"]
                    if suggested_terms:
                        suggested_filters = {**named_filters, "plant_name_terms": suggested_terms}
                        suggested_matches = apply_filters(matrix_df, suggested_filters)
                        if not suggested_matches.empty:
                            keyword_suggestion = {"terms": suggested_terms, "interpretation": keyword_result["interpretation"], "match_count": len(suggested_matches)}
                            # The verified matches remain a suggestion until the user confirms it.
                            hard_filter_no_match = True
                            ai_keyword_interpretation = keyword_result["interpretation"] or ("將需求理解為：" + "、".join(suggested_terms))
                        elif named_theme_lookup or ai_name_request:
                            hard_filter_no_match = True
                    elif named_theme_lookup or ai_name_request:
                        hard_filter_no_match = True
                except Exception:
                    if named_theme_lookup or ai_name_request:
                        hard_filter_no_match = True
            support_filters = {**applied, "plant_name_terms": []}
            candidates = score_candidates(
                apply_filters(matrix_df, support_filters) if applied.get("plant_name_terms") else named_candidate_df,
                support_filters,
            )
            # A named theme plant may intentionally belong to a different
            # season from the supporting composition (for example, spring
            # cherry blossom in a summer garden).  Keep its verified record in
            # the candidate pool so ``build_composition`` can preserve it.
            if applied.get("plant_name_terms") and not named_candidate_df.empty:
                named_scored = named_candidate_df if theme_requirements else score_candidates(named_candidate_df, named_filters)
                candidates = pd.concat([named_scored, candidates], ignore_index=True)
                candidates = candidates.drop_duplicates(subset="plant_id", keep="first")
            approximation_note = ""
            if candidates.empty and not hard_filter_no_match:
                relaxed_candidates, relaxed_field = find_relaxed_candidates(matrix_df, applied)
                if not relaxed_candidates.empty:
                    candidates = score_candidates(relaxed_candidates, applied)
                    approximation_note = f"找不到完全符合條件的資料，以下先放寬「{relaxed_field}」提供近似結果。"
            required_plant_ids = named_candidate_df["plant_id"].map(str).tolist() if applied.get("plant_name_terms") else []
            composition = (
                build_composition(candidates, applied, required_plant_ids=required_plant_ids)
                if has_composition and not hard_filter_no_match else None
            )
            selected = composition["selected"] if composition else select_recommendations(candidates, applied)
            answer = (
                "目前資料表找不到同時符合指定植物名稱與其他條件的植物，因此不以其他植物替代。"
                if hard_filter_no_match else ""
            )
            roles = composition["roles"] if composition else {}
            data_limit = composition["data_limit"] if composition else ""
            if settings.get("OPENAI_API_KEY") and not hard_filter_no_match:
                try:
                    with st.spinner("AI 正在根據候選資料整理回答..."):
                        context_rows = 55 if has_composition else 20
                        context_source = selected if has_composition else candidates
                        candidate_context = build_ai_context(context_source, applied, max_rows=context_rows)
                        if has_composition:
                            answer = generate_design_interpretation(question, composition, settings["OPENAI_API_KEY"], settings["OPENAI_MODEL"])
                        else:
                            answer = generate_grounded_answer(question, applied, candidate_context, settings["OPENAI_API_KEY"], settings["OPENAI_MODEL"])
                            invalid_ids = invalid_answer_plant_ids(answer, candidates)
                            if invalid_ids:
                                answer = "AI 回答出現無法回溯至候選資料的 plant_id，因此未採用文字回答；以下顯示 Python 篩選與排序結果。"
                except Exception:
                    st.info("AI 回答暫時不可用，已顯示可追溯的篩選結果。")
            st.session_state["matrix_result"] = {"cache_key": cache_key, "question": question.strip(), "total": len(matrix_df), "filters": applied, "candidates": candidates, "selected": selected, "answer": answer, "roles": roles, "data_limit": data_limit, "has_composition": has_composition and not hard_filter_no_match, "composition": composition, "approximation_note": approximation_note, "hard_filter_no_match": hard_filter_no_match, "ai_keyword_interpretation": ai_keyword_interpretation, "keyword_suggestion": keyword_suggestion}
    if "matrix_result" in st.session_state:
        render_results(st.session_state["matrix_result"])


if __name__ == "__main__":
    render_app()
