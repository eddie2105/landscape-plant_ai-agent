import unittest

import pandas as pd

from app import (
    DASHBOARD_CSS,
    EXAMPLE_QUESTIONS,
    REQUIRED_ENV_VARS,
    SYSTEM_PROMPT,
    ask_ai,
    build_context,
    build_coverage_analysis,
    build_recommendation_summary,
    build_seasonal_matrix,
    dashboard_card,
    dashboard_section_title,
    find_missing_settings,
    find_related_plants,
    find_related_plants_by_ids,
    hide_internal_id_columns,
    metric_card,
    parse_ai_json,
)


class AppCoreTests(unittest.TestCase):
    def test_dashboard_css_uses_forest_palette_and_card_classes(self):
        self.assertIn("#2f3d38", DASHBOARD_CSS)
        self.assertIn("#51635b", DASHBOARD_CSS)
        self.assertIn("#b8c7b2", DASHBOARD_CSS)
        self.assertIn(".forest-header", DASHBOARD_CSS)
        self.assertIn(".forest-card", DASHBOARD_CSS)
        self.assertIn(".forest-metric", DASHBOARD_CSS)
        self.assertNotIn("images.unsplash.com", DASHBOARD_CSS)

    def test_dashboard_card_escapes_content_and_adds_title(self):
        html = dashboard_card("AI 回答", "<script>alert('x')</script>")
        self.assertIn("AI 回答", html)
        self.assertIn("&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("forest-card", html)

    def test_metric_card_escapes_value_and_label(self):
        html = metric_card("資料來源", "<Google Sheets>")
        self.assertIn("資料來源", html)
        self.assertIn("&lt;Google Sheets&gt;", html)
        self.assertIn("forest-metric", html)

    def test_dashboard_section_title_escapes_content(self):
        html = dashboard_section_title("<plants>")
        self.assertIn("&lt;plants&gt;", html)
        self.assertIn("forest-section-title", html)

    def test_example_questions_are_demo_ready(self):
        self.assertEqual(
            [
                "春季庭院低中高層植栽怎麼搭配？",
                "我想找全日照、紅花、花感強的灌木",
                "哪些植物適合做葉色觀賞？",
                "請推薦 3 到 5 月有花期的植栽組合",
            ],
            EXAMPLE_QUESTIONS,
        )

    def test_build_context_includes_plants_and_display_matrix_csv_sections(self):
        plants_df = pd.DataFrame([{"plant_id": "001", "chinese_name": "春不老"}])
        display_df = pd.DataFrame([{"plant_id": "001", "flower_jan": 1, "leaf_jan": 0}])

        context = build_context(plants_df, display_df)

        self.assertIn("以下是植栽基本資料 plants：", context)
        self.assertIn("以下是花期與葉色月份矩陣 display_matrix：", context)
        self.assertIn("001", context)
        self.assertIn("春不老", context)

    def test_find_missing_settings_returns_required_empty_values_in_required_order(self):
        settings = {
            "GOOGLE_SERVICE_ACCOUNT_FILE": "credentials/service-account.json",
            "PLANTS_SPREADSHEET_ID": "",
            "PLANTS_WORKSHEET_NAME": "Plants",
            "DISPLAY_MATRIX_SPREADSHEET_ID": None,
            "DISPLAY_MATRIX_WORKSHEET_NAME": "Display",
            "OPENAI_API_KEY": "",
            "UNRELATED_SETTING": "",
        }

        missing = find_missing_settings(settings)

        expected = [
            name
            for name in REQUIRED_ENV_VARS
            if name
            in {
                "PLANTS_SPREADSHEET_ID",
                "DISPLAY_MATRIX_SPREADSHEET_ID",
                "OPENAI_API_KEY",
            }
        ]
        self.assertEqual(expected, missing)

    def test_find_related_plants_matches_answer_text_against_chinese_and_scientific_names(self):
        plants_df = pd.DataFrame(
            [
                {
                    "plant_id": "001",
                    "chinese_name": "台灣欒樹",
                    "scientific_name": "Koelreuteria elegans",
                },
                {
                    "plant_id": "002",
                    "chinese_name": "九重葛",
                    "scientific_name": "Bougainvillea spectabilis",
                },
                {
                    "plant_id": "003",
                    "chinese_name": "樟樹",
                    "scientific_name": "Cinnamomum camphora",
                },
            ]
        )
        answer = "推薦台灣欒樹，也可以搭配 Bougainvillea spectabilis。"

        related = find_related_plants(answer, plants_df)

        self.assertEqual(["001", "002"], related["plant_id"].tolist())

    def test_find_related_plants_preserves_leading_zero_plant_id(self):
        plants_df = pd.DataFrame(
            [
                {
                    "plant_id": "001",
                    "chinese_name": "台灣欒樹",
                    "scientific_name": "Koelreuteria elegans",
                }
            ]
        )

        related = find_related_plants("Koelreuteria elegans 很適合。", plants_df)

        self.assertEqual(["001"], related["plant_id"].tolist())

    def test_parse_ai_json_extracts_answer_and_plant_ids_from_clean_json(self):
        result = parse_ai_json(
            '{"answer": "推薦台灣欒樹，因為它有季節表現。", "plant_ids": ["001"]}'
        )

        self.assertEqual("推薦台灣欒樹，因為它有季節表現。", result["answer"])
        self.assertEqual(["001"], result["plant_ids"])

    def test_parse_ai_json_tolerates_markdown_code_blocks_and_normalizes_ids(self):
        result = parse_ai_json(
            """```json
{
  "answer": "推薦九重葛。",
  "plant_ids": [1, "002", "", null]
}
```"""
        )

        self.assertEqual("推薦九重葛。", result["answer"])
        self.assertEqual(["1", "002"], result["plant_ids"])

    def test_parse_ai_json_falls_back_to_answer_text_when_json_is_invalid(self):
        result = parse_ai_json("推薦台灣欒樹，但格式不是 JSON。")

        self.assertEqual("推薦台灣欒樹，但格式不是 JSON。", result["answer"])
        self.assertEqual([], result["plant_ids"])

    def test_system_prompt_keeps_plant_ids_out_of_answer_text(self):
        self.assertIn("answer 不可出現 plant_id", SYSTEM_PROMPT)
        self.assertIn("只能放在 JSON 的 plant_ids 欄位", SYSTEM_PROMPT)

    def test_system_prompt_requires_three_section_answer_format(self):
        self.assertIn("一、推薦植栽", SYSTEM_PROMPT)
        self.assertIn("二、判斷依據", SYSTEM_PROMPT)
        self.assertIn("三、設計提醒", SYSTEM_PROMPT)

    def test_system_prompt_requires_planting_layer_recommendations(self):
        self.assertIn("低層植栽", SYSTEM_PROMPT)
        self.assertIn("中層植栽", SYSTEM_PROMPT)
        self.assertIn("高層植栽", SYSTEM_PROMPT)

    def test_find_related_plants_by_ids_matches_only_existing_sheet_ids(self):
        plants_df = pd.DataFrame(
            [
                {"plant_id": "001", "chinese_name": "台灣欒樹"},
                {"plant_id": "002", "chinese_name": "九重葛"},
                {"plant_id": "003", "chinese_name": "樟樹"},
            ]
        )

        related = find_related_plants_by_ids(["002", "999", "001"], plants_df)

        self.assertEqual(["001", "002"], related["plant_id"].tolist())

    def test_find_related_plants_by_ids_preserves_columns_when_empty(self):
        plants_df = pd.DataFrame(columns=["plant_id", "chinese_name"])

        related = find_related_plants_by_ids([], plants_df)

        self.assertEqual(["plant_id", "chinese_name"], related.columns.tolist())
        self.assertTrue(related.empty)

    def test_hide_internal_id_columns_removes_plant_id_from_display_tables(self):
        df = pd.DataFrame(
            [
                {
                    "plant_id": "001",
                    "chinese_name": "台灣欒樹",
                    "scientific_name": "Koelreuteria elegans",
                }
            ]
        )

        display_df = hide_internal_id_columns(df)

        self.assertEqual(["chinese_name", "scientific_name"], display_df.columns.tolist())

    def test_ask_ai_returns_parsed_json_result(self):
        class FakeResponse:
            output_text = '{"answer": "推薦台灣欒樹。", "plant_ids": ["001"]}'

        class FakeResponses:
            def create(self, **kwargs):
                return FakeResponse()

        class FakeClient:
            responses = FakeResponses()

        result = ask_ai(
            "請推薦植栽",
            "plants csv",
            "sk-test",
            "gpt-4.1-mini",
            client=FakeClient(),
        )

        self.assertEqual("推薦台灣欒樹。", result["answer"])
        self.assertEqual(["001"], result["plant_ids"])

    def test_build_seasonal_matrix_renders_symbols_and_keeps_plant_identity(self):
        plants_df = pd.DataFrame(
            [
                {
                    "plant_id": "001",
                    "chinese_name": "台灣欒樹",
                    "scientific_name": "Koelreuteria elegans",
                }
            ]
        )
        display_df = pd.DataFrame(
            [
                {
                    "plant_id": "001",
                    "flower_jan": True,
                    "leaf_jan": False,
                    "flower_feb": False,
                    "leaf_feb": True,
                    "flower_mar": True,
                    "leaf_mar": True,
                }
            ]
        )

        matrix = build_seasonal_matrix(plants_df, display_df)

        self.assertIn(0, matrix.index)
        self.assertEqual("001", matrix.loc[0, "plant_id"])
        self.assertEqual("台灣欒樹", matrix.loc[0, "植物名稱"])
        self.assertEqual("🌸", matrix.loc[0, "1月"])
        self.assertEqual("🍃", matrix.loc[0, "2月"])
        self.assertEqual("🌸🍃", matrix.loc[0, "3月"])

    def test_build_coverage_analysis_counts_monthly_flower_leaf_and_total(self):
        plants_df = pd.DataFrame(
            [
                {"plant_id": "001", "chinese_name": "台灣欒樹"},
                {"plant_id": "002", "chinese_name": "春不老"},
            ]
        )
        display_df = pd.DataFrame(
            [
                {
                    "plant_id": "001",
                    "flower_jan": True,
                    "leaf_jan": True,
                    "flower_feb": False,
                    "leaf_feb": True,
                },
                {
                    "plant_id": "002",
                    "flower_jan": True,
                    "leaf_jan": False,
                    "flower_feb": False,
                    "leaf_feb": False,
                },
                {
                    "plant_id": "999",
                    "flower_jan": True,
                    "leaf_jan": True,
                    "flower_feb": True,
                    "leaf_feb": True,
                },
            ]
        )

        analysis = build_coverage_analysis(plants_df, display_df)

        jan_rows = analysis[analysis["月份"] == "1月"].set_index("指標")
        feb_rows = analysis[analysis["月份"] == "2月"].set_index("指標")
        mar_rows = analysis[analysis["月份"] == "3月"].set_index("指標")

        self.assertEqual(2, jan_rows.loc["花期植物數", "植物數"])
        self.assertEqual(1, jan_rows.loc["葉色觀賞植物數", "植物數"])
        self.assertEqual(3, jan_rows.loc["花期＋葉色觀賞總數", "植物數"])
        self.assertEqual(0, feb_rows.loc["花期植物數", "植物數"])
        self.assertEqual(1, feb_rows.loc["葉色觀賞植物數", "植物數"])
        self.assertEqual(1, feb_rows.loc["花期＋葉色觀賞總數", "植物數"])
        self.assertEqual(0, mar_rows.loc["花期＋葉色觀賞總數", "植物數"])
        self.assertEqual(36, len(analysis))

    def test_build_recommendation_summary_counts_plant_types_and_peak_months(self):
        plants_df = pd.DataFrame(
            [
                {"plant_id": "001", "plant_type": "草本"},
                {"plant_id": "002", "plant_type": "灌木"},
                {"plant_id": "003", "plant_type": "灌木"},
                {"plant_id": "004", "plant_type": "喬木"},
            ]
        )
        coverage_df = pd.DataFrame(
            [
                {"月份": "1月", "月份順序": 1, "指標": "花期＋葉色觀賞總數", "植物數": 2},
                {"月份": "2月", "月份順序": 2, "指標": "花期＋葉色觀賞總數", "植物數": 5},
                {"月份": "3月", "月份順序": 3, "指標": "花期＋葉色觀賞總數", "植物數": 5},
                {"月份": "4月", "月份順序": 4, "指標": "花期植物數", "植物數": 6},
            ]
        )

        summary = dict(build_recommendation_summary(plants_df, coverage_df))

        self.assertEqual("4", summary["推薦植物數量"])
        self.assertEqual("1", summary["草本"])
        self.assertEqual("2", summary["灌木"])
        self.assertEqual("1", summary["喬木"])
        self.assertEqual("2月、3月", summary["主要觀賞月份"])
        self.assertEqual("Google Sheets", summary["資料來源"])

    def test_build_recommendation_summary_handles_missing_data(self):
        summary = dict(build_recommendation_summary(pd.DataFrame(), pd.DataFrame()))

        self.assertEqual("0", summary["推薦植物數量"])
        self.assertEqual("0", summary["草本"])
        self.assertEqual("0", summary["灌木"])
        self.assertEqual("0", summary["喬木"])
        self.assertEqual("無資料", summary["主要觀賞月份"])


if __name__ == "__main__":
    unittest.main()
