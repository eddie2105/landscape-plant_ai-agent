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
            {"plant_id": "tree", "chinese_name": "焦點樹", "scientific_name": "Tree", "plant_type": "喬木", "growth_form": "喬木", "use_tags": "觀花", "native_status": "待確認", "needs_review": False},
            {"plant_id": "ground", "chinese_name": "前景花", "scientific_name": "Ground", "plant_type": "地被", "growth_form": "地被", "use_tags": "觀花", "native_status": "待確認", "flower_mar": True, "needs_review": False},
            {"plant_id": "shrub", "chinese_name": "白花灌木", "scientific_name": "Shrub", "plant_type": "灌木", "growth_form": "灌木", "flower_color": "白色", "use_tags": "觀花", "native_status": "待確認", "flower_mar": True, "needs_review": False},
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
        self.assertEqual([3, 4, 5, 6, 7, 8], parsed["required_months"])
        self.assertIn("cherry", selected["plant_id"].tolist())
        self.assertIn("3月花", selected.loc[selected["plant_id"] == "cherry", "seasonal_evidence"].iloc[0])

    def test_display_roles_do_not_change_the_selected_plants(self):
        parsed, result = self.query("春天有櫻花、夏天有變化")
        selected = intent.select_intent_recommendations(result["candidates"], parsed, 4)
        roles = app.build_intent_display_roles(selected, parsed)
        self.assertEqual(set(selected["plant_id"]), set(roles))
        self.assertEqual("主題植物／季節焦點候選", roles["cherry"]["role"])

    def test_herb_and_focal_tree_use_separate_candidate_pools(self):
        parsed, result = self.query("我想要一個香草庭院，搭配一棵作為視覺焦點的喬木。")
        selected = intent.select_intent_recommendations(result["candidates"], parsed, 4)
        self.assertEqual({"香草植栽", "視覺焦點喬木"}, {item["key"] for item in parsed["role_requests"]})
        self.assertIn("herb", selected["plant_id"].tolist())
        self.assertIn("tree", selected["plant_id"].tolist())

    def test_unavailable_safety_and_size_conditions_are_disclosed(self):
        edible, _ = self.query("我想做可以採收煮菜的食用花園，不要有毒植物。")
        small, small_result = self.query("我只有小庭院，希望低維護、不要長得太大的植物。")
        self.assertTrue(any("毒性" in item for item in edible["unavailable_conditions"]))
        self.assertTrue(any("植株高度" in item for item in small["unavailable_conditions"]))
        self.assertTrue(small_result["candidates"].empty)
        self.assertTrue(small_result["data_shortage"])

    def test_shrub_and_evergreen_query_uses_only_verifiable_conditions(self):
        parsed, result = self.query("請找白花、常綠、適合做中層量體的灌木。")
        self.assertEqual(["灌木"], parsed["plant_types"])
        self.assertIn("shrub", result["candidates"]["plant_id"].tolist())
        self.assertTrue(any("常綠" in item for item in result["unavailable_conditions"]))

    def test_unmentioned_cherry_is_not_inferred_from_pink_spring_flowers(self):
        parsed, _ = self.query("我想要春天有粉紅花、夏天仍有花果葉變化的庭院。")
        self.assertEqual([], parsed["theme_concepts"])
        self.assertEqual("粉紅色", parsed["flower_colors"][0])
        self.assertEqual([3, 4, 5, 6, 7, 8], parsed["required_months"])

    def test_main_tree_and_foreground_flower_are_separate_roles(self):
        parsed, result = self.query("我想做一個有主景樹、前景有低矮開花植物的現代庭院。")
        selected = intent.select_intent_recommendations(result["candidates"], parsed, 4)
        self.assertIn("tree", selected["plant_id"].tolist())
        self.assertIn("ground", selected["plant_id"].tolist())

    def test_two_directions_keep_their_primary_candidates_distinct(self):
        parsed, result = self.query("請提供兩套不同風格的庭院植栽方向：一套偏觀花，一套偏觀葉，且不要重複主題植物。")
        selected = intent.select_intent_recommendations(result["candidates"], parsed, 4)
        self.assertEqual({"觀花方向", "觀葉方向"}, {item["key"] for item in parsed["role_requests"]})
        self.assertGreaterEqual(len(selected), 2)
        self.assertEqual(len(selected), selected["plant_id"].nunique())


if __name__ == "__main__":
    unittest.main()
