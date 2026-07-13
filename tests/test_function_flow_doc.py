from pathlib import Path
import unittest


class FunctionFlowDocTests(unittest.TestCase):
    def test_interactive_doc_contains_required_sections_and_functions(self):
        html = Path("docs/function-flow.html").read_text(encoding="utf-8")

        required_text = [
            "互動式 DEF 流程圖",
            'id="flow-map"',
            'id="function-detail"',
            "functionData",
            "render_app",
            "ask_ai",
            "parse_ai_json",
            "build_coverage_analysis",
            "run_checks",
            "check_google_sheets",
            "test_app_core.py",
            "test_connection_checks.py",
        ]

        for text in required_text:
            with self.subTest(text=text):
                self.assertIn(text, html)

    def test_interactive_doc_uses_mind_map_layout(self):
        html = Path("docs/function-flow.html").read_text(encoding="utf-8")

        required_text = [
            'class="mind-map"',
            'class="mind-center"',
            'class="mind-branches"',
            "心智圖",
            "重點提示",
        ]

        for text in required_text:
            with self.subTest(text=text):
                self.assertIn(text, html)

    def test_interactive_doc_maps_app_py_from_top_to_bottom(self):
        html = Path("docs/function-flow.html").read_text(encoding="utf-8")

        required_text = [
            "brain-network",
            "leaf-node",
            "source_imports",
            "proxy_bootstrap",
            "env_contract",
            "prompt_contract",
            "ui_constants",
            "main_guard",
            "import json",
            "DEAD_LOCAL_PROXY",
            "SYSTEM_PROMPT",
            "DASHBOARD_CSS",
            "if __name__",
        ]

        for text in required_text:
            with self.subTest(text=text):
                self.assertIn(text, html)

    def test_interactive_doc_shows_line_ranges_for_clickable_nodes(self):
        html = Path("docs/function-flow.html").read_text(encoding="utf-8")

        required_text = [
            "Source lines",
            "item.lines",
            'lines: "app.py:1-10"',
            'lines: "app.py:24-33"',
            'lines: "app.py:342-374"',
            'lines: "app.py:376-394"',
            'lines: "app.py:606-787"',
            'lines: "connection_checks.py:84-94"',
        ]

        for text in required_text:
            with self.subTest(text=text):
                self.assertIn(text, html)

    def test_doc_explains_app_py_in_source_order_from_first_line(self):
        html = Path("docs/function-flow.html").read_text(encoding="utf-8")

        required_text = [
            'id="app-sequential-walkthrough"',
            'data-source-order="app-py-1-to-end"',
            "line-1-10",
            "line-24-33",
            "line-62",
            "line-64-111",
            "line-132-273",
            "line-606-787",
            "line-789-790",
            'id="bottom-brain-map"',
            "brain-spoke",
            "render_app center",
        ]

        for text in required_text:
            with self.subTest(text=text):
                self.assertIn(text, html)

    def test_doc_uses_split_source_reader_with_fixed_detailed_explanation(self):
        html = Path("docs/function-flow.html").read_text(encoding="utf-8")

        required_text = [
            "source-reader-layout",
            "source-reader-left",
            "source-reader-right",
            "sticky-explanation",
            "fixed-explanation",
            "position: fixed",
            "overflow-y: auto",
            "item.inputs",
            "item.outputs",
            "item.callers",
            "item.calls",
            "item.tests",
        ]

        for text in required_text:
            with self.subTest(text=text):
                self.assertIn(text, html)


if __name__ == "__main__":
    unittest.main()
