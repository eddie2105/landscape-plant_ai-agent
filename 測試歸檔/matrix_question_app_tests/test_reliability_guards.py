"""Regression tests for the query-to-composition reliability guards."""

import unittest
from importlib import import_module

import pandas as pd

_filters = import_module("景觀植物AI系統.查詢.filters")
_normalizer = import_module("景觀植物AI系統.資料.normalizer")
_schema = import_module("景觀植物AI系統.查詢.schema")
_search = import_module("景觀植物AI系統.查詢.search")
_composition = import_module("景觀植物AI系統.推薦.composition")
_charts = import_module("景觀植物AI系統.介面.charts")


class ReliabilityGuardTests(unittest.TestCase):
    def test_query_filter_factory_does_not_leak_list_values(self):
        options = {"plant_names": [], "plant_types": ["喬木"], "flower_colors": []}
        first = _filters.extract_known_filters("夏天開花", options)
        second = _filters.extract_known_filters("夏天", options)

        self.assertEqual(["花"], first["ornamental_parts"])
        self.assertEqual([], second["ornamental_parts"])
        self.assertEqual([], _schema.DEFAULT_FILTERS["ornamental_parts"])

    def test_mixed_season_cherry_question_keeps_theme_and_composition_seasons_separate(self):
        options = {"plant_names": [], "plant_types": ["喬木"], "flower_colors": []}
        filters = _filters.extract_known_filters("夏天的庭院，和春天想要有櫻花在裡面", options)

        self.assertEqual([6, 7, 8], filters["months"])
        self.assertEqual([3, 4, 5], filters["theme_months"])
        self.assertEqual(["櫻花", "Prunus"], filters["plant_name_terms"])

    def test_theme_without_its_own_season_does_not_inherit_summer_filter(self):
        options = {"plant_names": [], "plant_types": ["喬木"], "flower_colors": []}
        filters = _filters.extract_known_filters("幫我規劃一組夏天有變化的庭院植物，然後要有櫻花", options)
        plants = _normalizer.normalize_matrix_data(pd.DataFrame([
            {"plant_id": "cherry", "chinese_name": "山櫻花", "scientific_name": "Prunus campanulata", "ornamental_part": "花", "flower_mar": True, "needs_review": False},
            {"plant_id": "summer", "chinese_name": "夏季植物", "flower_jul": True, "needs_review": False},
        ]))
        named_filters = {**filters, "months": filters["theme_months"]}

        named = _search.apply_filters(plants, named_filters)

        self.assertEqual([6, 7, 8], filters["months"])
        self.assertEqual([], filters["theme_months"])
        self.assertTrue(filters["requires_seasonal_change"])
        self.assertTrue(filters["theme_plant_requirements"][0]["required"])
        self.assertEqual(["cherry"], named["plant_id"].tolist())

    def test_named_tree_does_not_inherit_companion_shrub_type(self):
        options = {
            "plant_names": ["鳳凰木"],
            "plant_types": ["喬木", "灌木"],
            "flower_colors": [],
        }
        filters = _filters.extract_known_filters("春天有開花的灌木，然後搭配一棵鳳凰木", options)
        requirement = filters["theme_plant_requirements"][0]

        self.assertEqual([3, 4, 5], filters["months"])
        self.assertEqual(["花"], filters["ornamental_parts"])
        self.assertEqual(["灌木"], filters["plant_types"])
        self.assertEqual([], requirement["months"])
        self.assertEqual([], requirement["ornamental_parts"])
        self.assertEqual([], requirement["plant_types"])

    def test_explicit_theme_modifiers_stay_attached_to_theme(self):
        options = {
            "plant_names": ["鳳凰木"],
            "plant_types": ["喬木", "灌木"],
            "flower_colors": [],
        }
        filters = _filters.extract_known_filters("春天開花的灌木鳳凰木庭院", options)
        requirement = filters["theme_plant_requirements"][0]

        self.assertEqual([3, 4, 5], requirement["months"])
        self.assertEqual(["花"], requirement["ornamental_parts"])
        self.assertEqual(["灌木"], requirement["plant_types"])

    def test_multiple_named_themes_are_kept_as_separate_requirements(self):
        options = {
            "plant_names": [],
            "plant_types": ["喬木", "灌木"],
            "flower_colors": [],
        }
        filters = _filters.extract_known_filters("夏天的庭院，另外想要櫻花和松樹", options)
        requirements = filters["theme_plant_requirements"]

        self.assertEqual(2, len(requirements))
        self.assertEqual(["櫻花", "松樹"], [item["phrase"] for item in requirements])
        self.assertTrue(all(item["max_required"] == 1 for item in requirements))
        self.assertTrue(all(item["months"] == [] for item in requirements))

    def test_explicit_name_from_user_wins_over_ai_parser_name(self):
        known = _schema.new_default_filters()
        known["plant_name_terms"] = ["梅花", "Armeniaca mume"]
        ai = _schema.new_default_filters()
        ai["plant_name_terms"] = ["其他植物"]

        merged = _filters.merge_known_and_ai_filters(ai, known)
        self.assertEqual(known["plant_name_terms"], merged["plant_name_terms"])

    def test_full_month_coverage_is_completed_by_the_group(self):
        plants = _normalizer.normalize_matrix_data(pd.DataFrame([
            {"plant_id": "jun", "chinese_name": "六月喬木", "plant_type": "喬木", "growth_form": "喬木", "flower_jun": True, "confidence": "high", "needs_review": False},
            {"plant_id": "jul", "chinese_name": "七月灌木", "plant_type": "灌木", "growth_form": "灌木", "flower_jul": True, "confidence": "high", "needs_review": False},
            {"plant_id": "aug", "chinese_name": "八月草本", "plant_type": "草本", "growth_form": "草本", "flower_aug": True, "confidence": "high", "needs_review": False},
        ]))
        filters = _schema.new_default_filters()
        filters.update({
            "months": [6, 7, 8], "ornamental_parts": ["花"],
            "requires_full_month_coverage": True, "requires_composition": True,
            "requested_count": 3,
        })

        candidates = _search.apply_filters(plants, filters)
        proposal = _composition.build_composition(candidates, filters)

        self.assertEqual({"jun", "jul", "aug"}, set(candidates["plant_id"]))
        self.assertTrue(proposal["seasonal_coverage"]["is_complete"])
        self.assertEqual([], proposal["seasonal_coverage"]["uncovered_months"])

    def test_heatmap_data_has_12_months_and_deduplicates_plant_ids(self):
        plants = _normalizer.normalize_matrix_data(pd.DataFrame([
            {"plant_id": "one", "flower_mar": True, "fruit_mar": True, "needs_review": True},
            {"plant_id": "one", "flower_mar": True, "needs_review": True},
            {"plant_id": "two", "leaf_apr": True, "needs_review": False},
        ]))

        chart = _charts.build_coverage_analysis(
            plants, requested_months=[3, 4], requested_parts=["花"]
        )

        self.assertEqual(12, len(chart))
        march = chart.loc[chart["月份"] == "3月"].iloc[0]
        april = chart.loc[chart["月份"] == "4月"].iloc[0]
        january = chart.loc[chart["月份"] == "1月"].iloc[0]
        self.assertEqual(1, march["花"])
        self.assertEqual(1, march["果"])
        self.assertEqual(1, march["花_需複查"])
        self.assertEqual(1, april["葉"])
        self.assertEqual("是", march["查詢指定月份"])
        self.assertEqual("否", january["查詢指定月份"])
        self.assertEqual(0, january["花"])
        self.assertEqual(0, january["果"])
        self.assertEqual(0, january["葉"])


if __name__ == "__main__":
    unittest.main()
