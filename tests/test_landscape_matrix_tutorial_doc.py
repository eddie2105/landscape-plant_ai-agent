from pathlib import Path
import unittest


class LandscapeMatrixTutorialDocTests(unittest.TestCase):
    def test_tutorial_has_interactive_reader_and_fixed_detail_panel(self):
        html = Path("docs/landscape-matrix-query-tutorial.html").read_text(encoding="utf-8")
        for text in (
            'id="source-order"',
            'id="function-detail"',
            "position:fixed",
            'id="bottom-brain-map"',
            "data-function=\"render_app\"",
            "const data =",
        ):
            with self.subTest(text=text):
                self.assertIn(text, html)

    def test_tutorial_covers_new_entry_ui_core_and_tests(self):
        html = Path("docs/landscape-matrix-query-tutorial.html").read_text(encoding="utf-8")
        for text in (
            "landscape_matrix_query.py:1-7",
            "matrix_question_app/landscape_matrix_query.py:213-293",
            "matrix_query.py:519-563",
            "matrix_question_app/tests/test_matrix_query.py:1-206",
            "Source lines",
            "在幹嘛",
            "誰呼叫它",
            "它呼叫誰／連到哪裡",
            "測試對應",
        ):
            with self.subTest(text=text):
                self.assertIn(text, html)


if __name__ == "__main__":
    unittest.main()
