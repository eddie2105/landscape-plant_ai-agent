# Interactive Function Flow Design

## Goal

Create a browser-readable HTML guide that explains how `app.py`, `connection_checks.py`, and `tests/` connect in the landscape plant AI agent project.

## Scope

The guide will cover:

- Main Streamlit application functions in `app.py`.
- Connection smoke-check functions in `connection_checks.py`.
- Unit tests in `tests/test_app_core.py` and `tests/test_connection_checks.py`.

## User Experience

The page will be a standalone static HTML file at `docs/function-flow.html`. It will open directly in a browser without a local server or package install.

The layout will use:

- A left-side interactive flow map with clickable function nodes.
- A right-side detail panel showing what the selected `def` does, inputs, outputs, callers, callees, and related tests.
- A lower test coverage section explaining which tests protect which behaviors.
- A complete function index for quick scanning.

## Content Model

Each function entry will include:

- Function name.
- Source file.
- Plain-language purpose in Traditional Chinese.
- Inputs and outputs.
- Caller and callee relationships.
- Related unit tests when present.

## Interaction

Clicking a flow-map node updates the detail panel. Function index rows use the same behavior. The first selected node is `render_app()`.

## Constraints

- No external JavaScript or CSS dependencies.
- No generated images or network assets.
- Keep the visual style readable and suitable for explaining code in a presentation.
