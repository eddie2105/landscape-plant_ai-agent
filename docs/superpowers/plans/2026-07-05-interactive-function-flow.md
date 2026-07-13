# Interactive Function Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone interactive HTML guide explaining the project function flow and test coverage.

**Architecture:** Add one static HTML file under `docs/` with embedded CSS and JavaScript. Add one unit test that verifies the documentation file exists and contains the required interactive data and coverage sections.

**Tech Stack:** HTML, CSS, vanilla JavaScript, Python `unittest`.

---

### Task 1: Documentation Contract Test

**Files:**
- Create: `tests/test_function_flow_doc.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
import unittest


class FunctionFlowDocTests(unittest.TestCase):
    def test_interactive_doc_contains_required_sections_and_functions(self):
        html = Path("docs/function-flow.html").read_text(encoding="utf-8")

        required_text = [
            "互動式 DEF 流程圖",
            "id=\"flow-map\"",
            "id=\"function-detail\"",
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_function_flow_doc`

Expected: FAIL because `docs/function-flow.html` does not exist.

### Task 2: Static Interactive HTML

**Files:**
- Create: `docs/function-flow.html`
- Test: `tests/test_function_flow_doc.py`

- [ ] **Step 1: Create the standalone HTML**

Include:

- Embedded CSS for the two-column layout.
- Flow-map buttons with `data-function` attributes.
- A `functionData` object containing function explanations.
- JavaScript that updates `#function-detail`.
- Test coverage section for `tests/test_app_core.py` and `tests/test_connection_checks.py`.

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m unittest tests.test_function_flow_doc`

Expected: PASS.

- [ ] **Step 3: Run the full test suite**

Run: `python -m unittest discover`

Expected: PASS.
