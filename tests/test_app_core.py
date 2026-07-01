import unittest

import pandas as pd

from app import (
    REQUIRED_ENV_VARS,
    SYSTEM_PROMPT,
    ask_ai,
    build_context,
    build_seasonal_matrix,
    find_missing_settings,
    find_related_plants,
    find_related_plants_by_ids,
    hide_internal_id_columns,
    parse_ai_json,
)


class AppCoreTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
