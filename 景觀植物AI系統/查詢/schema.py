"""Shared query schema, constants, and vocabulary."""


MONTH_KEYS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
MONTH_LABELS = {index: f"{index}月" for index in range(1, 13)}
MONTH_FIELD_PREFIXES = {"花": "flower", "果": "fruit", "葉": "leaf"}
FILTER_LIST_FIELDS = (
    "months", "ornamental_parts", "plant_types", "growth_forms", "flower_colors",
    "fruit_colors", "leaf_colors", "confidence",
)
DEFAULT_FILTERS = {
    "months": [], "ornamental_parts": [], "plant_types": [], "growth_forms": [],
    "flower_colors": [], "fruit_colors": [], "leaf_colors": [], "confidence": [],
    "requires_year_round_interest": False, "requires_seasonal_change": False,
    "exclude_needs_review": False, "requested_count": 8, "user_intent_summary": "",
    "requires_composition": False,
    "design_palette_name": "", "design_palette_colors": [],
}
SCORE_WEIGHTS = {
    "flower_month": 2, "fruit_month": 2, "leaf_month": 1, "plant_type": 3,
    "growth_form": 2, "flower_color": 3, "fruit_color": 2, "leaf_color": 2,
    "high_confidence": 2, "medium_confidence": 1, "palette_color": 3, "needs_review": -2,
}
FINAL_REMINDER = "實際配置仍需依基地日照、土壤、排水、維護條件與設計風格確認。"
PLANTING_DESIGN_FRAMEWORK = """植栽設計判斷框架：
- 設計判斷可參考 Nick Robinson《The Planting Design Handbook》的方向：植物不是單株清單，而是由結構性角色、裝飾性角色、vegetation layers 與 designed plant communities 組成的空間系統。
- 設計判斷可參考潘富俊《植栽設計選種大要》的方向：台灣景觀選種要重視公園、道路、綠地、住宅、庭園等在地使用情境，避免只用歐美溫帶經驗或只看花色。
- 設計判斷可參考《景觀植栽設計》的方向：喬木、灌木、草本、地被、藤本各有基本功能，推薦時要說明植物在空間中的用途與層次。
- 回答設計型問題時，不要只列植物名單；必須把候選植物組成有上層、中層、下層與季節節奏的植栽方案。
- 優先建立植被層次：高層喬木形成骨架、遮蔭或背景；中層灌木形成量體、視線控制與銜接；低層草本、地被或低矮植物提供邊界、季節色彩與地表覆蓋。
- 每一種推薦植物都要說明設計角色，例如骨架植物、背景植物、焦點植物、季節花色植物、觀葉植物、地被、邊界植物或色彩銜接植物。
- 不要只依花色推薦；必須同時考慮候選資料中可驗證的型態、層次、花果葉月份、葉色、果實、資料可信度與 needs_review。
- 以上書籍只作為設計判斷框架，不可捏造書中原文、頁碼、案例，也不可補充候選資料沒有提供的植物事實。"""
COLOR_ALIASES = {
    "粉": "粉紅",
    "粉紅": "粉紅",
    "橙": "橘",
    "橘": "橘",
}
SEASON_MONTHS = {
    "春": [3, 4, 5], "春天": [3, 4, 5],
    "夏": [6, 7, 8], "夏天": [6, 7, 8],
    "秋": [9, 10, 11], "秋天": [9, 10, 11],
    "冬": [12, 1, 2], "冬天": [12, 1, 2],
}
PLAIN_LANGUAGE_TYPE_ALIASES = {
    "樹": "喬木", "大樹": "喬木", "小樹": "喬木",
    "灌木": "灌木", "矮樹": "灌木", "地被": "地被",
    "草花": "花壇", "花草": "花壇", "香草": "香草/蔬菜",
    "藤": "藤本", "爬藤": "藤本",
}
UNSUPPORTED_TERM_LABELS = {
    "庭院": "庭院適應性", "陽台": "陽台適應性", "校園": "校園適應性",
    "公園": "公園適應性", "半日照": "日照條件", "全日照": "日照條件",
    "耐陰": "日照條件", "耐旱": "耐旱性", "好照顧": "維護需求",
    "低維護": "維護需求", "寵物": "寵物安全性", "毒": "毒性", "生態": "生態功能",
}
DESIGN_PALETTES = {
    "香檳色": ["乳白", "白", "黃", "金黃"],
}
DESIGN_STYLE_PROFILES = {
    "香檳色": {
        "keywords": ("香檳",),
        "colors": ["乳白", "白", "黃", "金黃"],
        "description": "以乳白、白、淡黃、金黃色形成柔和暖白色調",
    },
    "古典感": {
        "keywords": ("古典", "典雅"),
        "colors": ["乳白", "白", "紫", "淡紫", "綠"],
        "description": "以白、乳白、紫、淡紫與綠色建立沉穩典雅的層次",
    },
    "溫暖感": {
        "keywords": ("溫暖", "暖色"),
        "colors": ["黃", "金黃", "橘", "紅", "粉紅"],
        "description": "以黃、金黃、橘、紅與粉紅建立溫暖明亮的色彩焦點",
    },
}

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
]
