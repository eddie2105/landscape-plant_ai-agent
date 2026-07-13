import argparse
import csv
import os
import re
from datetime import datetime, timedelta, timezone

import gspread
from dotenv import load_dotenv


DEAD_LOCAL_PROXY = "127.0.0.1:9"
PROXY_ENV_VARS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
]
TAIPEI_TZ = timezone(timedelta(hours=8))

MONTHS = [
    ("jan", 1),
    ("feb", 2),
    ("mar", 3),
    ("apr", 4),
    ("may", 5),
    ("jun", 6),
    ("jul", 7),
    ("aug", 8),
    ("sep", 9),
    ("oct", 10),
    ("nov", 11),
    ("dec", 12),
]

IDENTITY_FIELDNAMES = [
    "plant_id",
    "chinese_name",
    "scientific_name",
    "plant_type",
    "growth_form",
]

DETAIL_FIELDNAMES = [
    "flower_color",
    "fruit_color",
    "leaf_color",
    "ornamental_part",
    "flowering_period",
    "flower_months",
    "fruiting_period",
    "fruit_months",
    "season_notes",
    "matrix_source",
    "confidence",
    "needs_review",
    "updated_at",
]

FIELDNAMES = (
    IDENTITY_FIELDNAMES
    + [f"flower_{key}" for key, _ in MONTHS]
    + [f"fruit_{key}" for key, _ in MONTHS]
    + [f"leaf_{key}" for key, _ in MONTHS]
    + DETAIL_FIELDNAMES
)

SEASON_MONTHS = {
    "\u6625": {2, 3, 4},
    "\u590f": {5, 6, 7},
    "\u79cb": {8, 9, 10},
    "\u51ac": {11, 12, 1},
}

LEAF_KEYWORDS = [
    "\u8449",
    "\u8449\u8272",
    "\u89c0\u8449",
    "\u5f69\u8449",
    "\u7d05\u8449",
    "\u9ec3\u8449",
    "\u6591\u8449",
    "\u65b0\u8449",
    "\u5e38\u7da0",
]


def disable_dead_local_proxy():
    for name in PROXY_ENV_VARS:
        value = os.environ.get(name, "")
        if DEAD_LOCAL_PROXY in value:
            os.environ.pop(name, None)


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def source_bool(value):
    return "TRUE" if value else "FALSE"


def month_range(start, end):
    months = []
    current = start
    while True:
        months.append(current)
        if current == end:
            break
        current = 1 if current == 12 else current + 1
    return months


def add_month(months, value):
    if 1 <= value <= 12:
        months.add(value)


def parse_months(value):
    text = clean_text(value)
    if not text:
        return set()

    months = set()
    normalized = (
        text.replace("\uff5e", "~")
        .replace("\u2013", "~")
        .replace("\u2014", "~")
        .replace("-", "~")
        .replace("\u81f3", "~")
        .replace("\u5230", "~")
    )

    for season, season_months in SEASON_MONTHS.items():
        if season in normalized:
            months.update(season_months)

    for start, end in re.findall(r"(\d{1,2})\s*(?:~)\s*(\d{1,2})", normalized):
        start_month = int(start)
        end_month = int(end)
        if 1 <= start_month <= 12 and 1 <= end_month <= 12:
            months.update(month_range(start_month, end_month))

    range_masked = re.sub(r"\d{1,2}\s*~\s*\d{1,2}", " ", normalized)
    for number in re.findall(r"\d{1,2}", range_masked):
        add_month(months, int(number))

    return months


def month_flags(months, prefix):
    return {
        f"{prefix}_{key}": source_bool(number in months)
        for key, number in MONTHS
    }


def infer_leaf_months(row):
    text = " ".join(
        clean_text(row.get(field))
        for field in ("leaf_color", "leaf_habit", "ornamental_part", "landscape_application", "knowledge")
    )
    if not text:
        return set(), False

    has_leaf_signal = any(keyword in text for keyword in LEAF_KEYWORDS)
    if not has_leaf_signal:
        return set(), False

    return {number for _, number in MONTHS}, True


def confidence_for(flower_months, fruit_months, leaf_months, source_names):
    if "flower_months" in source_names or "fruit_months" in source_names:
        return "high"
    if flower_months or fruit_months:
        return "medium"
    if leaf_months:
        return "low"
    return "low"


def build_row(row, updated_at):
    flower_months = parse_months(row.get("flower_months"))
    fruit_months = parse_months(row.get("fruit_months"))
    source_names = []

    if flower_months:
        source_names.append("flower_months")
    else:
        flower_months = parse_months(row.get("flowering_period"))
        if flower_months:
            source_names.append("flowering_period")

    if fruit_months:
        source_names.append("fruit_months")
    else:
        fruit_months = parse_months(row.get("fruiting_period"))
        if fruit_months:
            source_names.append("fruiting_period")

    leaf_months, leaf_needs_review = infer_leaf_months(row)
    if leaf_months:
        source_names.append("leaf_inference")

    needs_review = (
        leaf_needs_review
        or not source_names
        or ("flowering_period" in source_names and not clean_text(row.get("flower_months")))
        or ("fruiting_period" in source_names and not clean_text(row.get("fruit_months")))
    )

    output = {
        "plant_id": clean_text(row.get("plant_id")),
        "chinese_name": clean_text(row.get("chinese_name")),
        "scientific_name": clean_text(row.get("scientific_name")),
        "plant_type": clean_text(row.get("plant_type")),
        "growth_form": clean_text(row.get("growth_form")),
        "flower_color": clean_text(row.get("flower_color")),
        "fruit_color": clean_text(row.get("fruit_color")),
        "leaf_color": clean_text(row.get("leaf_color")),
        "ornamental_part": clean_text(row.get("ornamental_part")),
        "flowering_period": clean_text(row.get("flowering_period")),
        "flower_months": clean_text(row.get("flower_months")),
        "fruiting_period": clean_text(row.get("fruiting_period")),
        "fruit_months": clean_text(row.get("fruit_months")),
        "season_notes": build_season_notes(row, flower_months, fruit_months, leaf_months),
        "matrix_source": ",".join(source_names),
        "confidence": confidence_for(flower_months, fruit_months, leaf_months, source_names),
        "needs_review": source_bool(needs_review),
        "updated_at": updated_at,
    }
    output.update(month_flags(flower_months, "flower"))
    output.update(month_flags(fruit_months, "fruit"))
    output.update(month_flags(leaf_months, "leaf"))
    return output


def build_season_notes(row, flower_months, fruit_months, leaf_months):
    notes = []
    if flower_months:
        notes.append(f"flower: {format_months(flower_months)}")
    if fruit_months:
        notes.append(f"fruit: {format_months(fruit_months)}")
    if leaf_months:
        notes.append("leaf: inferred year-round ornamental foliage")

    for field in ("flowering_period", "fruiting_period", "ornamental_part"):
        value = clean_text(row.get(field))
        if value:
            notes.append(f"{field}: {value}")

    return "; ".join(notes)


def format_months(months):
    return ",".join(str(month) for month in sorted(months))


def read_csv_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def read_sheet_rows():
    service_account_file = os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"]
    spreadsheet_id = os.environ["PLANTS_MERGED_SPREADSHEET_ID"]
    worksheet_name = os.environ["PLANTS_MERGED_WORKSHEET_NAME"]
    client = gspread.service_account(filename=service_account_file)
    worksheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    return worksheet.get_all_records(numericise_ignore=["all"])


def write_sheet_rows(rows):
    service_account_file = os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"]
    spreadsheet_id = os.getenv(
        "DISPLAY_MATRIX_MERGED_SPREADSHEET_ID",
        os.environ["PLANTS_MERGED_SPREADSHEET_ID"],
    )
    worksheet_name = os.getenv(
        "DISPLAY_MATRIX_MERGED_WORKSHEET_NAME",
        "display_matrix_merged",
    )
    client = gspread.service_account(filename=service_account_file)
    spreadsheet = client.open_by_key(spreadsheet_id)
    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=worksheet_name,
            rows=max(len(rows) + 1, 1000),
            cols=len(FIELDNAMES),
        )

    values = [FIELDNAMES] + [[row.get(field, "") for field in FIELDNAMES] for row in rows]
    worksheet.clear()
    worksheet.update(values=values, range_name="A1")
    return worksheet_name


def write_csv_rows(rows, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def build_matrix_rows(plant_rows):
    updated_at = datetime.now(TAIPEI_TZ).isoformat(timespec="seconds")
    rows = []
    for row in plant_rows:
        if clean_text(row.get("plant_id")):
            rows.append(build_row(row, updated_at))
    return rows


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build display_matrix_merged preview CSV from plants_merged rows."
    )
    parser.add_argument(
        "--input-csv",
        help="Read plants_merged rows from a local CSV instead of Google Sheets.",
    )
    parser.add_argument(
        "--output-csv",
        default="data/display_matrix_merged_preview.csv",
        help="Write display matrix preview rows to this local CSV.",
    )
    parser.add_argument(
        "--write-sheet",
        action="store_true",
        help="Replace the configured display_matrix_merged worksheet with matrix rows.",
    )
    return parser.parse_args()


def main():
    load_dotenv()
    disable_dead_local_proxy()
    args = parse_args()
    plant_rows = read_csv_rows(args.input_csv) if args.input_csv else read_sheet_rows()
    matrix_rows = build_matrix_rows(plant_rows)
    write_csv_rows(matrix_rows, args.output_csv)
    review_count = sum(1 for row in matrix_rows if row.get("needs_review") == "TRUE")
    print(f"Wrote {len(matrix_rows)} display matrix rows to {args.output_csv}")
    print(f"Rows marked needs_review: {review_count}")

    if args.write_sheet:
        worksheet_name = write_sheet_rows(matrix_rows)
        print(f"Wrote {len(matrix_rows)} rows to Google Sheet worksheet {worksheet_name}")


if __name__ == "__main__":
    main()
