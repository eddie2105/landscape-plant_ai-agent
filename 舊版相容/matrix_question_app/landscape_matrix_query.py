"""Compatibility entry point for the old Streamlit UI module path.

New code should import from ``景觀植物AI系統/介面/streamlit_app.py``.
"""

from importlib import import_module


_streamlit_app = import_module(
    "\u666f\u89c0\u690d\u7269AI\u7cfb\u7d71.\u4ecb\u9762.streamlit_app"
)

load_matrix_settings = _streamlit_app.load_matrix_settings
load_matrix = _streamlit_app.load_matrix
render_filters = _streamlit_app.render_filters
render_plant_cards = _streamlit_app.render_plant_cards
build_proposal_overview = _streamlit_app.build_proposal_overview
describe_applied_filters = _streamlit_app.describe_applied_filters
render_results = _streamlit_app.render_results
render_app = _streamlit_app.render_app


__all__ = [
    "load_matrix_settings",
    "load_matrix",
    "render_filters",
    "render_plant_cards",
    "build_proposal_overview",
    "describe_applied_filters",
    "render_results",
    "render_app",
]


if __name__ == "__main__":
    render_app()

