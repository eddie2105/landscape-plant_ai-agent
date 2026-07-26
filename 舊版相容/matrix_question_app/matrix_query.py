"""Compatibility exports for the old matrix query module path.

New code should import from the Chinese package under ``景觀植物AI系統``.
"""

from importlib import import_module


_context = import_module(
    "\u666f\u89c0\u690d\u7269AI\u7cfb\u7d71.AI\u56de\u7b54.context"
)
_generator = import_module(
    "\u666f\u89c0\u690d\u7269AI\u7cfb\u7d71.AI\u56de\u7b54.generator"
)
_charts = import_module("\u666f\u89c0\u690d\u7269AI\u7cfb\u7d71.\u4ecb\u9762.charts")
_scoring = import_module("\u666f\u89c0\u690d\u7269AI\u7cfb\u7d71.\u63a8\u85a6.scoring")
_normalizer = import_module("\u666f\u89c0\u690d\u7269AI\u7cfb\u7d71.\u8cc7\u6599.normalizer")
_filters = import_module("\u666f\u89c0\u690d\u7269AI\u7cfb\u7d71.\u67e5\u8a62.filters")
_schema = import_module("\u666f\u89c0\u690d\u7269AI\u7cfb\u7d71.\u67e5\u8a62.schema")
_search = import_module("\u666f\u89c0\u690d\u7269AI\u7cfb\u7d71.\u67e5\u8a62.search")


MONTH_KEYS = _schema.MONTH_KEYS
MONTH_LABELS = _schema.MONTH_LABELS
MONTH_FIELD_PREFIXES = _schema.MONTH_FIELD_PREFIXES
FILTER_LIST_FIELDS = _schema.FILTER_LIST_FIELDS
DEFAULT_FILTERS = _schema.DEFAULT_FILTERS
SCORE_WEIGHTS = _schema.SCORE_WEIGHTS
FINAL_REMINDER = _schema.FINAL_REMINDER
PLANTING_DESIGN_FRAMEWORK = _schema.PLANTING_DESIGN_FRAMEWORK
COLOR_ALIASES = _schema.COLOR_ALIASES
SEASON_MONTHS = _schema.SEASON_MONTHS
PLAIN_LANGUAGE_TYPE_ALIASES = _schema.PLAIN_LANGUAGE_TYPE_ALIASES
UNSUPPORTED_TERM_LABELS = _schema.UNSUPPORTED_TERM_LABELS
DESIGN_PALETTES = _schema.DESIGN_PALETTES
DESIGN_STYLE_PROFILES = _schema.DESIGN_STYLE_PROFILES

as_text = _normalizer.as_text
normalize_boolean = _normalizer.normalize_boolean
normalize_multivalue_text = _normalizer.normalize_multivalue_text
normalize_matrix_data = _normalizer.normalize_matrix_data
extract_filter_options = _normalizer.extract_filter_options
build_filter_options = _normalizer.build_filter_options

_months_from_question = _filters._months_from_question
extract_known_filters = _filters.extract_known_filters
merge_known_and_ai_filters = _filters.merge_known_and_ai_filters
_parse_json = _filters._parse_json
parse_question_to_filters = _filters.parse_question_to_filters
merge_ai_and_manual_filters = _filters.merge_ai_and_manual_filters

apply_filters = _search.apply_filters
find_relaxed_candidates = _search.find_relaxed_candidates

score_candidates = _scoring.score_candidates
select_recommendations = _scoring.select_recommendations

format_months = _context.format_months
build_ai_context = _context.build_ai_context

generate_grounded_answer = _generator.generate_grounded_answer
generate_design_proposal = _generator.generate_design_proposal
validate_design_proposal = _generator.validate_design_proposal
invalid_answer_plant_ids = _generator.invalid_answer_plant_ids

build_seasonal_matrix = _charts.build_seasonal_matrix
build_coverage_analysis = _charts.build_coverage_analysis


__all__ = [
    "MONTH_KEYS",
    "MONTH_LABELS",
    "MONTH_FIELD_PREFIXES",
    "FILTER_LIST_FIELDS",
    "DEFAULT_FILTERS",
    "SCORE_WEIGHTS",
    "FINAL_REMINDER",
    "PLANTING_DESIGN_FRAMEWORK",
    "COLOR_ALIASES",
    "SEASON_MONTHS",
    "PLAIN_LANGUAGE_TYPE_ALIASES",
    "UNSUPPORTED_TERM_LABELS",
    "DESIGN_PALETTES",
    "DESIGN_STYLE_PROFILES",
    "as_text",
    "normalize_boolean",
    "normalize_multivalue_text",
    "normalize_matrix_data",
    "extract_filter_options",
    "build_filter_options",
    "_months_from_question",
    "extract_known_filters",
    "merge_known_and_ai_filters",
    "_parse_json",
    "parse_question_to_filters",
    "merge_ai_and_manual_filters",
    "apply_filters",
    "find_relaxed_candidates",
    "score_candidates",
    "select_recommendations",
    "format_months",
    "build_ai_context",
    "generate_grounded_answer",
    "generate_design_proposal",
    "validate_design_proposal",
    "invalid_answer_plant_ids",
    "build_seasonal_matrix",
    "build_coverage_analysis",
]

