import unittest

import pandas as pd

from app import (
    REQUIRED_ENV_VARS,
    build_context,
    build_seasonal_matrix,
    find_missing_settings,
    find_related_plants,
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
