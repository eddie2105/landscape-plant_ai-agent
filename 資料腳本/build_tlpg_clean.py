import argparse
import csv
import os
import re
from datetime import datetime, timedelta, timezone

import gspread
from dotenv import load_dotenv


TAIPEI_TZ = timezone(timedelta(hours=8))

CLEAN_FIELDNAMES = [
    "tlpg_id",
    "plant_id",
    "source_name",
    "source_url",
    "category_id",
    "category_name",
    "category_english_name",
    "chinese_name",
    "scientific_name",
    "scientific_name_normalized",
    "family",
    "plant_type",
    "growth_form",
    "tree_height",
    "height_min_m",
    "height_max_m",
    "light_condition",
    "water_condition",
    "planting_environment",
    "ecological_use",
    "english_name",
    "japanese_name",
    "alias_names",
    "aliases_normalized",
    "intro",
    "cultivation",
    "landscape_application",
    "knowledge",
    "flowering_period",
    "flower_months",
    "fruiting_period",
    "fruit_months",
    "flower_color",
    "ornamental_part",
    "image_url",
    "image_alt",
    "search_text",
    "updated_at",
    "data_quality_notes",
]

SEARCH_FIELDS = [
    "chinese_name",
    "scientific_name",
    "family",
    "plant_type",
    "growth_form",
    "tree_height",
    "light_condition",
    "water_condition",
    "planting_environment",
    "ecological_use",
    "english_name",
    "japanese_name",
    "alias_names",
    "category_name",
    "intro",
    "cultivation",
    "landscape_application",
    "knowledge",
    "flowering_period",
    "fruiting_period",
    "flower_color",
    "ornamental_part",
]

CATEGORY_TO_PLANT_TYPE = {
    "觀花喬木": "喬木",
    "觀葉喬木": "喬木",
    "觀果喬木": "喬木",
    "觀賞灌木": "灌木",
    "蔓藤植物": "藤本",
    "地被植物": "地被",
    "花壇植物": "花壇",
    "蔬菜與香藥草": "香草/蔬菜",
    "水生與濕生植物": "水生/濕生",
}

CATEGORY_TO_GROWTH_FORM = {
    "觀花喬木": "喬木",
    "觀葉喬木": "喬木",
    "觀果喬木": "喬木",
    "觀賞灌木": "灌木",
    "蔓藤植物": "藤本",
    "地被植物": "地被",
    "花壇植物": "草本",
    "蔬菜與香藥草": "草本",
    "水生與濕生植物": "水生/濕生",
}

CATEGORY_TO_ORNAMENTAL_PART = {
    "觀花喬木": "花",
    "觀葉喬木": "葉",
    "觀果喬木": "果",
}

FLOWER_COLORS = [
    "白色",
    "乳白色",
    "黃色",
    "金黃色",
    "橙色",
    "橘色",
    "紅色",
    "粉紅色",
    "桃紅色",
    "紫色",
    "淡紫色",
    "藍色",
    "綠色",
]

PLANTING_ENVIRONMENT_KEYWORDS = {
    "行道樹": "行道樹",
    "公園": "公園",
    "校園": "校園",
    "庭園": "庭園",
    "庭院": "庭園",
    "綠籬": "綠籬",
    "盆栽": "盆栽",
    "花壇": "花壇",
    "地被": "地被",
    "水池": "水池",
    "濕地": "濕地",
    "屋頂": "屋頂",
    "牆面": "牆面",
    "棚架": "棚架",
}


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_scientific_name(value):
    text = clean_text(value).casefold()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_aliases(value):
    text = clean_text(value)
    if not text:
        return ""
    aliases = re.split(r"[、,，;；/／]+", text)
    aliases = [clean_text(alias) for alias in aliases if clean_text(alias)]
    return ",".join(dict.fromkeys(aliases))


def parse_number(value):
    if value is None or value == "":
        return ""
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)


def parse_height_range(tree_height):
    numbers = re.findall(r"\d+(?:\.\d+)?", clean_text(tree_height))
    if not numbers:
        return "", ""

    values = [float(number) for number in numbers]
    if len(values) == 1:
        return "", parse_number(values[0])
    return parse_number(min(values)), parse_number(max(values))


def extract_tree_height(text):
    text = clean_text(text)
    patterns = [
        r"(高(?:可達|約|達)?\s*\d+(?:\.\d+)?\s*(?:[-~～至到]\s*\d+(?:\.\d+)?)?\s*公尺)",
        r"(樹高(?:約|可達|達)?\s*\d+(?:\.\d+)?\s*(?:[-~～至到]\s*\d+(?:\.\d+)?)?\s*公尺)",
        r"(株高(?:約|可達|達)?\s*\d+(?:\.\d+)?\s*(?:[-~～至到]\s*\d+(?:\.\d+)?)?\s*公尺)",
        r"(\d+(?:\.\d+)?\s*(?:[-~～至到]\s*\d+(?:\.\d+)?)?\s*公尺高)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return clean_text(match.group(1))
    return ""


def infer_growth_form(row, text):
    category_name = clean_text(row.get("category_name"))
    category_form = CATEGORY_TO_GROWTH_FORM.get(category_name)
    if category_form:
        return category_form

    patterns = [
        ("小喬木", "小喬木"),
        ("喬木", "喬木"),
        ("灌木", "灌木"),
        ("藤本", "藤本"),
        ("蔓藤", "藤本"),
        ("草本", "草本"),
        ("地被", "地被"),
        ("水生", "水生"),
        ("濕生", "濕生"),
    ]
    for keyword, value in patterns:
        if keyword in text:
            return value
    return ""


def infer_light_condition(text):
    text = clean_text(text)
    found = []
    if re.search(r"全日照|陽性|喜陽|陽光充足|日照充足", text):
        found.append("全日照")
    if re.search(r"半日照|半陰|半蔭", text):
        found.append("半日照")
    if re.search(r"耐陰|陰性|遮陰|蔭蔽", text):
        found.append("耐陰")
    return ",".join(dict.fromkeys(found))


def infer_water_condition(text):
    text = clean_text(text)
    found = []
    if re.search(r"耐旱|乾旱|排水良好|忌積水", text):
        found.append("耐旱/排水良好")
    if re.search(r"濕潤|潮濕|水濕|濕地|水邊|水生", text):
        found.append("濕潤")
    if re.search(r"耐水|耐淹|淹水", text):
        found.append("耐濕/耐淹")
    return ",".join(dict.fromkeys(found))


def infer_planting_environment(text):
    text = clean_text(text)
    values = []
    for keyword, value in PLANTING_ENVIRONMENT_KEYWORDS.items():
        if keyword in text:
            values.append(value)
    if "景觀樹" in text:
        values.append("景觀樹")
    return ",".join(dict.fromkeys(values))


def infer_ecological_use(text):
    text = clean_text(text)
    values = []
    if re.search(r"誘鳥|鳥類|鳥媒|鳥食", text):
        values.append("誘鳥")
    if re.search(r"蜜源|蝴蝶|蝶|蜂|昆蟲", text):
        values.append("蜜源/誘蝶")
    if re.search(r"固氮", text):
        values.append("固氮")
    if re.search(r"水土保持|護坡|防風|防砂", text):
        values.append("水土保持")
    return ",".join(dict.fromkeys(values))


def month_range(start, end):
    months = []
    current = start
    while True:
        months.append(current)
        if current == end:
            break
        current = 1 if current == 12 else current + 1
    return months


def parse_months(period):
    text = clean_text(period)
    if not text:
        return ""

    normalized = (
        text.replace("～", "~")
        .replace("-", "~")
        .replace("至", "~")
        .replace("到", "~")
        .replace("、", ",")
        .replace("，", ",")
    )

    months = []
    for start, end in re.findall(r"(\d{1,2})\s*(?:月)?\s*~\s*(\d{1,2})", normalized):
        start_month = int(start)
        end_month = int(end)
        if 1 <= start_month <= 12 and 1 <= end_month <= 12:
            months.extend(month_range(start_month, end_month))

    masked = re.sub(r"\d{1,2}\s*(?:月)?\s*~\s*\d{1,2}", " ", normalized)
    for number in re.findall(r"(\d{1,2})\s*月", masked):
        month = int(number)
        if 1 <= month <= 12:
            months.append(month)

    unique_months = []
    seen = set()
    for month in months:
        if month not in seen:
            seen.add(month)
            unique_months.append(month)
    return ",".join(str(month) for month in unique_months)


def extract_period(text, label_patterns):
    text = clean_text(text)
    for label in label_patterns:
        pattern = rf"{label}\s*(?:約|為|是)?\s*([0-9]{{1,2}}\s*(?:月)?\s*(?:[~～\-至到]\s*[0-9]{{1,2}}\s*)?月?)"
        match = re.search(pattern, text)
        if match:
            return clean_text(match.group(1))
    return ""


def extract_flower_color(text):
    text = clean_text(text)
    found = []
    for color in FLOWER_COLORS:
        if color in text:
            found.append(color)
    return ",".join(dict.fromkeys(found))


def infer_ornamental_part(row):
    category_name = clean_text(row.get("category_name"))
    parts = []
    category_part = CATEGORY_TO_ORNAMENTAL_PART.get(category_name)
    if category_part:
        parts.append(category_part)

    text = " ".join(
        clean_text(row.get(field))
        for field in ("intro", "landscape_application", "knowledge")
    )
    if re.search(r"觀賞\(花\)|觀花|賞花|花期|花色|開花", text):
        parts.append("花")
    if re.search(r"觀賞\(果\)|觀果|果期|果實|誘鳥", text):
        parts.append("果")
    if re.search(r"觀葉|葉色|葉形|彩葉|斑葉", text):
        parts.append("葉")
    return ",".join(dict.fromkeys(parts))


def build_search_text(row):
    parts = []
    for field in SEARCH_FIELDS:
        value = clean_text(row.get(field))
        if value:
            parts.append(value)
    return " ".join(dict.fromkeys(parts))


def clean_row(row, updated_at):
    text_for_periods = " ".join(
        clean_text(row.get(field))
        for field in ("intro", "landscape_application", "knowledge")
    )
    text_for_inference = " ".join(
        clean_text(row.get(field))
        for field in ("intro", "cultivation", "landscape_application", "knowledge")
    )
    flowering_period = extract_period(text_for_periods, ("花期", "開花期"))
    fruiting_period = extract_period(text_for_periods, ("果期", "結果期"))
    tree_height = extract_tree_height(text_for_inference)
    height_min, height_max = parse_height_range(tree_height)

    clean = {
        "tlpg_id": clean_text(row.get("tlpg_id")),
        "plant_id": f"tlpg_{clean_text(row.get('tlpg_id'))}",
        "source_name": "tlpg",
        "source_url": clean_text(row.get("source_url")),
        "category_id": clean_text(row.get("category_id")),
        "category_name": clean_text(row.get("category_name")),
        "category_english_name": clean_text(row.get("category_english_name")),
        "chinese_name": clean_text(row.get("chinese_name")),
        "scientific_name": clean_text(row.get("scientific_name")),
        "scientific_name_normalized": normalize_scientific_name(
            row.get("scientific_name")
        ),
        "family": clean_text(row.get("family")),
        "plant_type": CATEGORY_TO_PLANT_TYPE.get(clean_text(row.get("category_name")), ""),
        "growth_form": infer_growth_form(row, text_for_inference),
        "tree_height": tree_height,
        "height_min_m": height_min,
        "height_max_m": height_max,
        "light_condition": infer_light_condition(text_for_inference),
        "water_condition": infer_water_condition(text_for_inference),
        "planting_environment": infer_planting_environment(text_for_inference),
        "ecological_use": infer_ecological_use(text_for_inference),
        "english_name": clean_text(row.get("english_name")),
        "japanese_name": clean_text(row.get("japanese_name")),
        "alias_names": clean_text(row.get("alias_names")),
        "aliases_normalized": normalize_aliases(row.get("alias_names")),
        "intro": clean_text(row.get("intro")),
        "cultivation": clean_text(row.get("cultivation")),
        "landscape_application": clean_text(row.get("landscape_application")),
        "knowledge": clean_text(row.get("knowledge")),
        "flowering_period": flowering_period,
        "flower_months": parse_months(flowering_period),
        "fruiting_period": fruiting_period,
        "fruit_months": parse_months(fruiting_period),
        "flower_color": extract_flower_color(text_for_periods),
        "image_url": clean_text(row.get("image_url")),
        "image_alt": clean_text(row.get("image_alt")),
        "updated_at": updated_at,
    }
    clean["ornamental_part"] = infer_ornamental_part({**row, **clean})
    clean["search_text"] = build_search_text(clean)

    notes = []
    for field in ("tlpg_id", "chinese_name", "scientific_name", "family"):
        if not clean.get(field):
            notes.append(f"missing {field}")
    clean["data_quality_notes"] = "; ".join(notes)
    return clean


def clean_rows(raw_rows):
    updated_at = datetime.now(TAIPEI_TZ).isoformat(timespec="seconds")
    rows = []
    for row in raw_rows:
        if clean_text(row.get("tlpg_id")):
            rows.append(clean_row(row, updated_at))
    return rows


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def write_csv(rows, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CLEAN_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def read_raw_sheet():
    service_account_file = os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"]
    spreadsheet_id = os.environ["TLPG_RAW_SPREADSHEET_ID"]
    worksheet_name = os.environ["TLPG_RAW_WORKSHEET_NAME"]
    client = gspread.service_account(filename=service_account_file)
    worksheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    return worksheet.get_all_records(numericise_ignore=["all"])


def write_clean_sheet(rows):
    service_account_file = os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"]
    spreadsheet_id = os.environ["TLPG_CLEAN_SPREADSHEET_ID"]
    worksheet_name = os.environ["TLPG_CLEAN_WORKSHEET_NAME"]
    client = gspread.service_account(filename=service_account_file)
    worksheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    values = [CLEAN_FIELDNAMES] + [
        [row.get(field, "") for field in CLEAN_FIELDNAMES] for row in rows
    ]
    worksheet.clear()
    worksheet.update(values=values, range_name="A1")
    return worksheet_name


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build cleaned TLPG rows from tlpg_raw data."
    )
    parser.add_argument(
        "--input-csv",
        help="Read TLPG raw rows from a local CSV instead of Google Sheets.",
    )
    parser.add_argument(
        "--output-csv",
        default="data/tlpg_clean_preview.csv",
        help="Write cleaned rows to this local CSV for inspection.",
    )
    parser.add_argument(
        "--write-sheet",
        action="store_true",
        help="Replace the configured tlpg_clean worksheet with cleaned rows.",
    )
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()
    raw_rows = read_csv(args.input_csv) if args.input_csv else read_raw_sheet()
    rows = clean_rows(raw_rows)
    write_csv(rows, args.output_csv)
    print(f"Wrote {len(rows)} clean rows to {args.output_csv}")

    if args.write_sheet:
        worksheet_name = write_clean_sheet(rows)
        print(f"Wrote {len(rows)} clean rows to Google Sheet worksheet {worksheet_name}")


if __name__ == "__main__":
    main()
