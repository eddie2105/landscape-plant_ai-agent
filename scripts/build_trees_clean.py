import argparse
import csv
import os
import re
from datetime import datetime, timedelta, timezone

import gspread
from dotenv import load_dotenv


TAIPEI_TZ = timezone(timedelta(hours=8))

RAW_FIELDNAMES = [
    "plant_id",
    "chinese_name",
    "scientific_name",
    "family",
    "altitude",
    "global_distribution",
    "environment_type",
    "taiwan_distribution",
    "region",
    "planting_environment",
    "growth_form",
    "tree_height",
    "crown_shape",
    "leaf_arrangement",
    "leaf_color",
    "leaf_habit",
    "leaf_texture",
    "flower_type",
    "inflorescence",
    "flower_color",
    "flowering_period",
    "fruit_type",
    "fruit_size",
    "fruit_color",
    "fruiting_period",
    "light_condition",
    "water_condition",
    "planting_type",
    "ornamental_part",
    "ecological_use",
    "is_toxic",
    "propagation",
    "growth_rate",
    "maintenance_notes",
    "photo_source",
    "source_url",
    "scraped_at",
    "raw_name_line",
    "data_quality_notes",
]

CLEAN_FIELDNAMES = [
    "plant_id",
    "display_order",
    "chinese_name",
    "scientific_name",
    "family",
    "plant_type",
    "growth_form",
    "tree_height",
    "height_min_m",
    "height_max_m",
    "region",
    "planting_environment",
    "light_condition",
    "water_condition",
    "flower_color",
    "flowering_period",
    "flower_months",
    "fruit_color",
    "fruiting_period",
    "fruit_months",
    "leaf_color",
    "leaf_habit",
    "ornamental_part",
    "ecological_use",
    "is_toxic",
    "maintenance_notes",
    "search_text",
    "source_url",
    "updated_at",
]

SEARCH_FIELDS = [
    "chinese_name",
    "scientific_name",
    "family",
    "plant_type",
    "growth_form",
    "region",
    "planting_environment",
    "light_condition",
    "water_condition",
    "flower_color",
    "fruit_color",
    "leaf_color",
    "leaf_habit",
    "ornamental_part",
    "ecological_use",
    "maintenance_notes",
]


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


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
        return parse_number(values[0]), parse_number(values[0])

    return parse_number(min(values)), parse_number(max(values))


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
    for start, end in re.findall(r"(\d{1,2})\s*~\s*(\d{1,2})", normalized):
        start_month = int(start)
        end_month = int(end)
        if 1 <= start_month <= 12 and 1 <= end_month <= 12:
            months.extend(month_range(start_month, end_month))

    range_spans = list(re.finditer(r"\d{1,2}\s*~\s*\d{1,2}", normalized))
    masked = normalized
    for span in reversed(range_spans):
        masked = masked[: span.start()] + " " * (span.end() - span.start()) + masked[span.end() :]

    for number in re.findall(r"\d{1,2}", masked):
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


def normalize_bool(value):
    text = clean_text(value).casefold()
    if text in {"true", "1", "yes", "y", "是"}:
        return "TRUE"
    if text in {"false", "0", "no", "n", "否"}:
        return "FALSE"
    return "UNKNOWN"


def normalize_plant_type(growth_form):
    text = clean_text(growth_form)
    if not text:
        return ""
    if "喬木" in text:
        return "喬木"
    if "灌木" in text:
        return "灌木"
    if "藤" in text:
        return "藤本"
    if "草" in text:
        return "草本"
    return text


def build_search_text(row):
    parts = []
    for field in SEARCH_FIELDS:
        value = clean_text(row.get(field))
        if value:
            parts.append(value)
    return " ".join(dict.fromkeys(parts))


def clean_row(row, display_order, updated_at):
    height_min, height_max = parse_height_range(row.get("tree_height"))
    growth_form = clean_text(row.get("growth_form"))

    clean = {
        "plant_id": clean_text(row.get("plant_id")),
        "display_order": str(display_order),
        "chinese_name": clean_text(row.get("chinese_name")),
        "scientific_name": clean_text(row.get("scientific_name")),
        "family": clean_text(row.get("family")),
        "plant_type": normalize_plant_type(growth_form),
        "growth_form": growth_form,
        "tree_height": clean_text(row.get("tree_height")),
        "height_min_m": height_min,
        "height_max_m": height_max,
        "region": clean_text(row.get("region")),
        "planting_environment": clean_text(row.get("planting_environment")),
        "light_condition": clean_text(row.get("light_condition")),
        "water_condition": clean_text(row.get("water_condition")),
        "flower_color": clean_text(row.get("flower_color")),
        "flowering_period": clean_text(row.get("flowering_period")),
        "flower_months": parse_months(row.get("flowering_period")),
        "fruit_color": clean_text(row.get("fruit_color")),
        "fruiting_period": clean_text(row.get("fruiting_period")),
        "fruit_months": parse_months(row.get("fruiting_period")),
        "leaf_color": clean_text(row.get("leaf_color")),
        "leaf_habit": clean_text(row.get("leaf_habit")),
        "ornamental_part": clean_text(row.get("ornamental_part")),
        "ecological_use": clean_text(row.get("ecological_use")),
        "is_toxic": normalize_bool(row.get("is_toxic")),
        "maintenance_notes": clean_text(row.get("maintenance_notes")),
        "source_url": clean_text(row.get("source_url")),
        "updated_at": updated_at,
    }
    clean["search_text"] = build_search_text(clean)
    return clean


def clean_rows(raw_rows):
    updated_at = datetime.now(TAIPEI_TZ).isoformat(timespec="seconds")
    clean = []
    for index, row in enumerate(raw_rows, start=1):
        if not clean_text(row.get("plant_id")):
            continue
        clean.append(clean_row(row, index, updated_at))
    return clean


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
    spreadsheet_id = os.environ["TREES_RAW_SPREADSHEET_ID"]
    worksheet_name = os.environ["TREES_RAW_WORKSHEET_NAME"]
    client = gspread.service_account(filename=service_account_file)
    worksheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    return worksheet.get_all_records(numericise_ignore=["all"])


def write_clean_sheet(rows):
    service_account_file = os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"]
    spreadsheet_id = os.getenv("TREES_CLEAN_SPREADSHEET_ID") or os.environ["PLANTS_SPREADSHEET_ID"]
    worksheet_name = os.getenv("TREES_CLEAN_WORKSHEET_NAME") or os.environ["PLANTS_WORKSHEET_NAME"]
    client = gspread.service_account(filename=service_account_file)
    worksheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    values = [CLEAN_FIELDNAMES] + [[row.get(field, "") for field in CLEAN_FIELDNAMES] for row in rows]
    worksheet.clear()
    worksheet.update(values=values, range_name="A1")
    return worksheet_name


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build website-ready trees_clean rows from trees_raw data."
    )
    parser.add_argument(
        "--input-csv",
        help="Read raw tree rows from a local CSV instead of Google Sheets.",
    )
    parser.add_argument(
        "--output-csv",
        default="data/trees_clean_preview.csv",
        help="Write cleaned rows to this local CSV for inspection.",
    )
    parser.add_argument(
        "--write-sheet",
        action="store_true",
        help="Replace the configured trees_clean worksheet with cleaned rows.",
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
