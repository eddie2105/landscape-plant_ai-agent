import unittest

import pandas as pd

from matrix_question_app.matrix_query import (
    DEFAULT_FILTERS, FINAL_REMINDER, apply_filters, build_ai_context, build_seasonal_matrix,
    extract_known_filters, find_relaxed_candidates, generate_grounded_answer,
    generate_design_proposal, invalid_answer_plant_ids, merge_ai_and_manual_filters, normalize_boolean, normalize_matrix_data,
    normalize_multivalue_text, PLANTING_DESIGN_FRAMEWORK, score_candidates, select_recommendations, validate_design_proposal,
)


class MatrixQueryTests(unittest.TestCase):
    def setUp(self):
        self.df = normalize_matrix_data(pd.DataFrame([
            {"plant_id": "001", "chinese_name": "紫花灌木", "plant_type": "灌木", "growth_form": "灌木", "flower_color": "紫色，白色", "ornamental_part": "花", "flower_mar": "TRUE", "fruit_mar": "FALSE", "leaf_mar": 1, "confidence": "high", "needs_review": "FALSE"},
            {"plant_id": "002", "chinese_name": "秋果喬木", "plant_type": "喬木", "growth_form": "喬木", "fruit_color": "紅色", "ornamental_part": "果", "flower_mar": "FALSE", "fruit_mar": "TRUE", "leaf_mar": 0, "confidence": "low", "needs_review": "TRUE"},
        ]))

    def test_boolean_normalization(self):
        self.assertTrue(normalize_boolean("TRUE")); self.assertTrue(normalize_boolean(1)); self.assertFalse(normalize_boolean("false"))

    def test_multivalue_text_normalizes_separators_and_color_suffix(self):
        self.assertEqual(["紫", "白"], normalize_multivalue_text("紫色、白色"))

    def test_pink_color_alias_matches_matrix_pink_red_spelling(self):
        pink_df = normalize_matrix_data(pd.DataFrame([
            {"plant_id": "003", "chinese_name": "粉花植物", "flower_color": "粉紅色", "confidence": "high", "needs_review": "FALSE"}
        ]))
        result = apply_filters(pink_df, {**DEFAULT_FILTERS, "flower_colors": ["粉色"]})
        self.assertEqual(["003"], result["plant_id"].tolist())

    def test_flower_color_does_not_require_a_separate_ornamental_part_label(self):
        color_only_df = normalize_matrix_data(pd.DataFrame([
            {"plant_id": "004", "chinese_name": "粉花植物", "flower_color": "粉紅色", "ornamental_part": "", "confidence": "high", "needs_review": "FALSE"}
        ]))
        result = apply_filters(color_only_df, {**DEFAULT_FILTERS, "ornamental_parts": ["花"], "flower_colors": ["粉色"]})
        self.assertEqual(["004"], result["plant_id"].tolist())

    def test_march_flower_filter_uses_flower_mar(self):
        result = apply_filters(self.df, {**DEFAULT_FILTERS, "months": [3], "ornamental_parts": ["花"]})
        self.assertEqual(["001"], result["plant_id"].tolist())

    def test_multiple_parts_match_any_selected_part_in_month(self):
        result = apply_filters(self.df, {**DEFAULT_FILTERS, "months": [3], "ornamental_parts": ["花", "果"]})
        self.assertEqual(["001", "002"], result["plant_id"].tolist())

    def test_empty_filters_returns_all_rows(self):
        self.assertEqual(2, len(apply_filters(self.df, DEFAULT_FILTERS)))

    def test_needs_review_exclusion(self):
        result = apply_filters(self.df, {**DEFAULT_FILTERS, "exclude_needs_review": True})
        self.assertEqual(["001"], result["plant_id"].tolist())

    def test_manual_filter_takes_precedence(self):
        merged = merge_ai_and_manual_filters({**DEFAULT_FILTERS, "plant_types": ["喬木"]}, {"plant_types": ["灌木"], "exclude_needs_review": False, "requested_count": 8})
        self.assertEqual(["灌木"], merged["plant_types"])

    def test_context_is_limited_to_max_rows(self):
        context = build_ai_context(pd.concat([self.df] * 15, ignore_index=True), DEFAULT_FILTERS, max_rows=20)
        self.assertEqual(20, context.count('"plant_id"'))

    def test_matrix_contains_flower_fruit_leaf_symbols(self):
        matrix = build_seasonal_matrix(self.df.head(1))
        self.assertEqual("花＋葉", matrix.loc[0, "3月"])

    def test_score_penalizes_review_rows(self):
        result = score_candidates(self.df, {**DEFAULT_FILTERS, "months": [3], "ornamental_parts": ["花", "果"]})
        self.assertEqual("001", result.iloc[0]["plant_id"])

    def test_answer_plant_ids_must_belong_to_candidates(self):
        self.assertEqual([], invalid_answer_plant_ids("推薦 plant_id：001", self.df))
        self.assertEqual(["999"], invalid_answer_plant_ids("推薦 plant_id: 999", self.df))

    def test_grounded_answer_prompt_keeps_legacy_three_section_contract(self):
        class FakeResponse:
            output_text = "ok"

        class FakeResponses:
            def __init__(self):
                self.kwargs = None

            def create(self, **kwargs):
                self.kwargs = kwargs
                return FakeResponse()

        class FakeClient:
            def __init__(self):
                self.responses = FakeResponses()

        client = FakeClient()
        generate_grounded_answer("推薦植物", DEFAULT_FILTERS, "{}", "sk-test", "gpt-test", client=client)
        prompt = client.responses.kwargs["input"][0]["content"]
        self.assertIn("一、查詢結論與推薦植栽", prompt)
        self.assertIn("二、判斷依據", prompt)
        self.assertIn("三、資料品質與設計提醒", prompt)
        self.assertIn(FINAL_REMINDER, prompt)
        self.assertIn("不得使用外部知識", prompt)
        self.assertIn("低層植栽", prompt)
        self.assertIn("中層植栽", prompt)
        self.assertIn("高層植栽", prompt)
        self.assertIn("景觀分層推定", prompt)
        self.assertIn("The Planting Design Handbook", prompt)
        self.assertIn("vegetation layers", prompt)
        self.assertIn("designed plant communities", prompt)
        self.assertIn("不可捏造書中原文、頁碼、案例", prompt)

    def test_plain_language_keeps_supported_pink_filter_and_marks_garden_unverified(self):
        options = {"plant_types": ["喬木", "灌木"], "flower_colors": ["粉紅", "紫"]}
        filters = extract_known_filters("我想要有粉色花的庭院", options)
        self.assertEqual(["粉紅"], filters["flower_colors"])
        self.assertEqual(["花"], filters["ornamental_parts"])
        self.assertEqual(["庭院適應性"], filters["unverified_terms"])

    def test_relaxed_candidates_offer_a_near_match(self):
        filters = {**DEFAULT_FILTERS, "flower_colors": ["不存在的顏色"]}
        result, relaxed_field = find_relaxed_candidates(self.df, filters)
        self.assertFalse(result.empty)
        self.assertEqual("花色", relaxed_field)

    def test_garden_question_enables_composition_mode(self):
        options = {"plant_types": ["喬木", "灌木"], "flower_colors": []}
        filters = extract_known_filters("我想做夏天的庭院", options)
        self.assertEqual([6, 7, 8], filters["months"])
        self.assertTrue(filters["requires_composition"])

    def test_composition_selection_keeps_multiple_landscape_layers(self):
        candidates = pd.DataFrame([
            {"plant_id": "001", "chinese_name": "樹", "plant_type": "喬木", "growth_form": "喬木", "match_score": 10},
            {"plant_id": "002", "chinese_name": "灌木", "plant_type": "灌木", "growth_form": "灌木", "match_score": 9},
            {"plant_id": "003", "chinese_name": "地被", "plant_type": "地被", "growth_form": "地被", "match_score": 8},
        ])
        selected = select_recommendations(candidates, {**DEFAULT_FILTERS, "requires_composition": True, "requested_count": 3})
        self.assertEqual(["001", "002", "003"], selected["plant_id"].tolist())

    def test_champagne_palette_uses_flower_fruit_or_leaf_color(self):
        palette_df = normalize_matrix_data(pd.DataFrame([
            {"plant_id": "001", "chinese_name": "白花", "flower_color": "乳白色", "confidence": "high", "needs_review": "FALSE"},
            {"plant_id": "002", "chinese_name": "黃果", "fruit_color": "金黃色", "confidence": "high", "needs_review": "FALSE"},
            {"plant_id": "003", "chinese_name": "綠葉", "leaf_color": "綠色", "confidence": "high", "needs_review": "FALSE"},
        ]))
        options = {"plant_types": [], "flower_colors": ["乳白", "白", "黃", "金黃"]}
        filters = extract_known_filters("我想要有香檳色感覺的庭院植栽", options)
        result = apply_filters(palette_df, filters)
        self.assertEqual("香檳色", filters["design_palette_name"])
        self.assertTrue(filters["requires_composition"])
        self.assertEqual(["001", "002"], result["plant_id"].tolist())

    def test_palette_composition_reserves_roles_for_flower_fruit_and_leaf(self):
        candidates = pd.DataFrame([
            {"plant_id": "001", "chinese_name": "白花樹", "plant_type": "喬木", "growth_form": "喬木", "flower_color": "白色", "match_score": 10},
            {"plant_id": "002", "chinese_name": "黃果灌木", "plant_type": "灌木", "growth_form": "灌木", "fruit_color": "金黃色", "match_score": 9},
            {"plant_id": "003", "chinese_name": "淡葉地被", "plant_type": "地被", "growth_form": "地被", "leaf_color": "乳白色", "match_score": 8},
        ])
        selected = select_recommendations(candidates, {**DEFAULT_FILTERS, "requires_composition": True, "requested_count": 8, "design_palette_colors": ["乳白", "白", "黃", "金黃"]})
        self.assertEqual(["001", "002", "003"], selected["plant_id"].tolist())

    def test_classic_style_translates_to_palette_and_composition(self):
        options = {"plant_types": [], "flower_colors": []}
        filters = extract_known_filters("我想要古典感的庭院植栽", options)
        self.assertEqual("古典感", filters["design_palette_name"])
        self.assertTrue(filters["requires_composition"])
        self.assertIn("紫", filters["design_palette_colors"])

    def test_design_proposal_uses_only_candidate_ids_and_roles(self):
        candidates = pd.DataFrame([
            {"plant_id": "001", "chinese_name": "候選一"},
            {"plant_id": "002", "chinese_name": "候選二"},
        ])
        proposal = {
            "summary": "一個提案。",
            "plant_ids": ["002", "999", "001"],
            "roles": [
                {"plant_id": "002", "role": "主景", "rationale": "作為畫面的焦點。"},
                {"plant_id": "999", "role": "虛構", "rationale": "不應出現。"},
            ],
            "data_limit": "庭院條件需另行確認。",
        }
        result = validate_design_proposal(proposal, candidates, candidates, 8)
        self.assertEqual(["002", "001"], result["selected"]["plant_id"].tolist())
        self.assertEqual("主景", result["roles"]["002"]["role"])
        self.assertNotIn("999", result["roles"])

    def test_design_prompt_requires_named_plants_in_the_legacy_answer_shape(self):
        class FakeResponse:
            output_text = "{}"

        class FakeResponses:
            def __init__(self):
                self.kwargs = None

            def create(self, **kwargs):
                self.kwargs = kwargs
                return FakeResponse()

        class FakeClient:
            def __init__(self):
                self.responses = FakeResponses()

        client = FakeClient()
        generate_design_proposal("溫暖庭院", DEFAULT_FILTERS, "{}", "sk-test", "gpt-test", client=client)
        prompt = client.responses.kwargs["input"][0]["content"]
        self.assertIn("景觀提案不得只有氣氛描述", prompt)
        self.assertIn("一、查詢結論與推薦植栽", prompt)
        self.assertIn("低層植栽、中層植栽、高層植栽、其他型態", prompt)
        self.assertIn("中文名｜scientific_name｜plant_id", prompt)
        self.assertIn("植栽設計選種大要", prompt)
        self.assertIn("景觀植栽設計", prompt)
        self.assertIn(PLANTING_DESIGN_FRAMEWORK, prompt)


if __name__ == "__main__":
    unittest.main()
