import unittest
from importlib import import_module

import pandas as pd


intent = import_module("景觀植物AI系統.查詢.intent")
normalizer = import_module("景觀植物AI系統.資料.normalizer")
app = import_module("景觀植物AI系統.介面.streamlit_app")


class ControlledIntentTests(unittest.TestCase):
    def setUp(self):
        self.df = normalizer.normalize_matrix_data(pd.DataFrame([
            {"plant_id": "herb", "chinese_name": "香草", "scientific_name": "Herba", "use_tags": "香草,芳香,食用", "native_status": "待確認", "flower_mar": True, "needs_review": False},
            {"plant_id": "fragrant", "chinese_name": "芳香", "scientific_name": "Aroma", "use_tags": "芳香", "native_status": "台灣原生", "flower_mar": True, "needs_review": False},
            {"plant_id": "edible", "chinese_name": "食用", "scientific_name": "Edible", "use_tags": "食用", "native_status": "台灣原生", "leaf_jul": True, "needs_review": False},
            {"plant_id": "cherry", "chinese_name": "山櫻花", "scientific_name": "Prunus campanulata", "use_tags": "觀花", "native_status": "台灣原生", "flower_mar": True, "needs_review": False},
            {"plant_id": "summer", "chinese_name": "夏季", "scientific_name": "Summer", "use_tags": "觀葉", "native_status": "待確認", "leaf_jun": True, "fruit_jul": True, "flower_aug": True, "needs_review": False},
        ]))

    def query(self, text):
        parsed = intent.normalize_design_intent({}, text)
        return parsed, intent.filter_by_design_intent(self.df, parsed)

    def test_herb_requires_exact_tag(self):
        parsed, result = self.query("幫我規劃香草花園")
        self.assertEqual("herb_garden", parsed["primary_intent"])
        self.assertEqual(["herb"], result["candidates"]["plant_id"].tolist())

    def test_fragrant_cannot_replace_herb(self):
        _, result = self.query("香草植物")
        self.assertNotIn("fragrant", result["candidates"]["plant_id"].tolist())

    def test_edible_requires_exact_tag(self):
        _, result = self.query("可以採來煮菜")
        self.assertTrue(all("食用" in intent.split_use_tags(value) for value in result["candidates"]["use_tags"]))

    def test_native_herb_reports_shortage(self):
        _, result = self.query("台灣原生香草花園")
        self.assertTrue(result["candidates"].empty)
        self.assertTrue(result["data_shortage"])

    def test_cherry_and_summer_has_month_evidence(self):
        parsed, result = self.query("春天有櫻花、夏天有變化")
        selected = intent.select_intent_recommendations(result["candidates"], parsed, 4)
        self.assertEqual([3, 6, 7, 8], parsed["required_months"])
        self.assertIn("cherry", selected["plant_id"].tolist())
        self.assertIn("3月花", selected.loc[selected["plant_id"] == "cherry", "seasonal_evidence"].iloc[0])

    def test_display_roles_do_not_change_the_selected_plants(self):
        parsed, result = self.query("春天有櫻花、夏天有變化")
        selected = intent.select_intent_recommendations(result["candidates"], parsed, 4)
        roles = app.build_intent_display_roles(selected, parsed)
        self.assertEqual(set(selected["plant_id"]), set(roles))
        self.assertEqual("主題植物／季節焦點候選", roles["cherry"]["role"])


if __name__ == "__main__":
    unittest.main()
