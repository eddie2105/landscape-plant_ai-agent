import unittest


class ChinesePackageStructureTests(unittest.TestCase):
    def test_public_entrypoint_imports_render_app(self):
        from 景觀植物AI系統.介面.streamlit_app import render_app

        self.assertTrue(callable(render_app))

    def test_settings_and_data_modules_expose_expected_helpers(self):
        from 景觀植物AI系統.設定.settings import load_matrix_settings
        from 景觀植物AI系統.資料.matrix_loader import load_matrix
        from 景觀植物AI系統.資料.normalizer import build_filter_options

        self.assertTrue(callable(load_matrix_settings))
        self.assertTrue(callable(load_matrix))
        self.assertTrue(callable(build_filter_options))

    def test_query_recommendation_and_ai_modules_expose_expected_helpers(self):
        from 景觀植物AI系統.AI回答.context import build_ai_context
        from 景觀植物AI系統.AI回答.generator import generate_grounded_answer
        from 景觀植物AI系統.推薦.scoring import score_candidates
        from 景觀植物AI系統.查詢.filters import extract_known_filters
        from 景觀植物AI系統.查詢.search import apply_filters

        self.assertTrue(callable(build_ai_context))
        self.assertTrue(callable(generate_grounded_answer))
        self.assertTrue(callable(score_candidates))
        self.assertTrue(callable(extract_known_filters))
        self.assertTrue(callable(apply_filters))


if __name__ == "__main__":
    unittest.main()
