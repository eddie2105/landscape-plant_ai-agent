import argparse
import csv
import os
import re
from datetime import datetime, timedelta, timezone

import gspread
from dotenv import load_dotenv


TAIPEI_TZ = timezone(timedelta(hours=8))

FIELDNAMES = [
    "plant_id",
    "canonical_key",
    "preferred_source",
    "source_names",
    "source_count",
    "has_native_data",
    "has_tlpg_data",
    "native_plant_id",
    "tlpg_plant_id",
    "native_source_url",
    "tlpg_source_url",
    "chinese_name",
    "scientific_name",
    "scientific_name_normalized",
    "family",
    "plant_type",
    "growth_form",
    "category_name",
    "english_name",
    "japanese_name",
    "alias_names",
    "tree_height",
    "height_min_m",
    "height_max_m",
    "height_source",
    "height_conflict",
    "height_conflict_note",
    "native_tree_height",
    "native_height_min_m",
    "native_height_max_m",
    "tlpg_tree_height",
    "tlpg_height_min_m",
    "tlpg_height_max_m",
    "light_condition",
    "water_condition",
    "planting_environment",
    "region",
    "flowering_period",
    "flower_months",
    "fruiting_period",
    "fruit_months",
    "flower_color",
    "leaf_color",
    "leaf_habit",
    "ornamental_part",
    "ecological_use",
    "is_toxic",
    "cultivation",
    "maintenance_notes",
    "intro",
    "landscape_application",
    "knowledge",
    "image_url",
    "source_urls",
    "search_text",
    "data_completeness_score",
    "missing_core_fields",
    "updated_at",
]

SEARCH_FIELDS = [
    "chinese_name",
    "scientific_name",
    "family",
    "plant_type",
    "growth_form",
    "category_name",
    "english_name",
    "japanese_name",
    "alias_names",
    "tree_height",
    "light_condition",
    "water_condition",
    "planting_environment",
    "region",
    "flowering_period",
    "fruiting_period",
    "flower_color",
    "leaf_color",
    "leaf_habit",
    "ornamental_part",
    "ecological_use",
    "cultivation",
    "maintenance_notes",
    "intro",
    "landscape_application",
    "knowledge",
]


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_scientific_name(value):
    return clean_text(value).casefold()


def normalize_match_text(value):
    return clean_text(value).casefold()


def family_match_text(value):
    text = clean_text(value)
    text = re.sub(r"[A-Za-z().,&'\-]+", "", text)
    text = re.sub(r"\s+", "", text)
    return text.casefold()


def scientific_short_key(row):
    scientific = normalize_scientific_name(row.get("scientific_name"))
    words = re.findall(r"[a-z]+", scientific)
    if len(words) >= 2:
        return f"sci_short:{words[0]} {words[1]}"
    return ""


def first_value(*values):
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return ""


def join_unique(*values):
    parts = []
    for value in values:
        text = clean_text(value)
        if not text:
            continue
        for part in re.split(r"[,，、;；]+", text):
            part = clean_text(part)
            if part:
                parts.append(part)
    return ",".join(dict.fromkeys(parts))


def to_float(value):
    text = clean_text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def canonical_key(row):
    scientific = normalize_scientific_name(row.get("scientific_name"))
    if scientific:
        return f"sci:{scientific}"

    chinese_name = normalize_match_text(row.get("chinese_name"))
    family = normalize_match_text(row.get("family"))
    if chinese_name and family:
        return f"name_family:{chinese_name}|{family}"
    if chinese_name:
        return f"name:{chinese_name}"
    return ""


def name_family_key(row):
    chinese_name = normalize_match_text(row.get("chinese_name"))
    family = family_match_text(row.get("family"))
    if chinese_name and family:
        return f"name_family:{chinese_name}|{family}"
    return ""


def source_bool(value):
    return "TRUE" if value else "FALSE"


def height_values(native, tlpg):
    native_tree_height = clean_text(native.get("tree_height")) if native else ""
    native_min = clean_text(native.get("height_min_m")) if native else ""
    native_max = clean_text(native.get("height_max_m")) if native else ""
    tlpg_tree_height = clean_text(tlpg.get("tree_height")) if tlpg else ""
    tlpg_min = clean_text(tlpg.get("height_min_m")) if tlpg else ""
    tlpg_max = clean_text(tlpg.get("height_max_m")) if tlpg else ""

    if native_tree_height or native_min or native_max:
        tree_height = native_tree_height
        height_min = native_min
        height_max = native_max
        height_source = "native_tree"
    elif tlpg_tree_height or tlpg_min or tlpg_max:
        tree_height = tlpg_tree_height
        height_min = tlpg_min
        height_max = tlpg_max
        height_source = "tlpg"
    else:
        tree_height = ""
        height_min = ""
        height_max = ""
        height_source = ""

    native_max_value = to_float(native_max)
    tlpg_max_value = to_float(tlpg_max)
    conflict = False
    conflict_note = ""
    if native_max_value is not None and tlpg_max_value is not None:
        diff = abs(native_max_value - tlpg_max_value)
        baseline = min(native_max_value, tlpg_max_value)
        ratio = diff / baseline if baseline else 0
        conflict = diff > 5 or ratio > 0.5
        if conflict:
            conflict_note = (
                f"native: {native_tree_height or native_max}; "
                f"tlpg: {tlpg_tree_height or tlpg_max}"
            )

    return {
        "tree_height": tree_height,
        "height_min_m": height_min,
        "height_max_m": height_max,
        "height_source": height_source,
        "height_conflict": source_bool(conflict),
        "height_conflict_note": conflict_note,
        "native_tree_height": native_tree_height,
        "native_height_min_m": native_min,
        "native_height_max_m": native_max,
        "tlpg_tree_height": tlpg_tree_height,
        "tlpg_height_min_m": tlpg_min,
        "tlpg_height_max_m": tlpg_max,
    }


def build_search_text(row):
    parts = []
    for field in SEARCH_FIELDS:
        value = clean_text(row.get(field))
        if value:
            parts.append(value)
    return " ".join(dict.fromkeys(parts))


def completeness_score(row):
    checks = [
        bool(row.get("chinese_name")),
        bool(row.get("scientific_name")),
        bool(row.get("family")),
        bool(row.get("plant_type") or row.get("growth_form")),
        bool(row.get("flowering_period") or row.get("flower_months")),
        bool(row.get("fruiting_period") or row.get("fruit_months")),
        bool(row.get("tree_height") or row.get("height_max_m")),
        bool(row.get("light_condition") or row.get("water_condition")),
        bool(row.get("intro") or row.get("landscape_application")),
        row.get("has_native_data") == "TRUE" and row.get("has_tlpg_data") == "TRUE",
    ]
    return str(sum(10 for check in checks if check))


def missing_core_fields(row):
    missing = []
    for field in ("chinese_name", "scientific_name", "family", "plant_type"):
        if not clean_text(row.get(field)):
            missing.append(field)
    return ",".join(missing)


def merge_pair(native, tlpg, merged_id, key, updated_at):
    has_native = native is not None
    has_tlpg = tlpg is not None
    source_names = []
    if has_native:
        source_names.append("native_tree")
    if has_tlpg:
        source_names.append("tlpg")

    preferred_source = "native_tree" if has_native else "tlpg"
    height = height_values(native, tlpg)

    row = {
        "plant_id": f"merged_{merged_id:04d}",
        "canonical_key": key,
        "preferred_source": preferred_source,
        "source_names": ",".join(source_names),
        "source_count": str(len(source_names)),
        "has_native_data": source_bool(has_native),
        "has_tlpg_data": source_bool(has_tlpg),
        "native_plant_id": clean_text(native.get("plant_id")) if native else "",
        "tlpg_plant_id": clean_text(tlpg.get("plant_id")) if tlpg else "",
        "native_source_url": clean_text(native.get("source_url")) if native else "",
        "tlpg_source_url": clean_text(tlpg.get("source_url")) if tlpg else "",
        "chinese_name": first_value(
            native.get("chinese_name") if native else "",
            tlpg.get("chinese_name") if tlpg else "",
        ),
        "scientific_name": first_value(
            native.get("scientific_name") if native else "",
            tlpg.get("scientific_name") if tlpg else "",
        ),
        "family": first_value(
            native.get("family") if native else "",
            tlpg.get("family") if tlpg else "",
        ),
        "plant_type": first_value(
            native.get("plant_type") if native else "",
            tlpg.get("plant_type") if tlpg else "",
        ),
        "growth_form": first_value(
            native.get("growth_form") if native else "",
            tlpg.get("growth_form") if tlpg else "",
        ),
        "category_name": clean_text(tlpg.get("category_name")) if tlpg else "",
        "english_name": clean_text(tlpg.get("english_name")) if tlpg else "",
        "japanese_name": clean_text(tlpg.get("japanese_name")) if tlpg else "",
        "alias_names": clean_text(tlpg.get("alias_names")) if tlpg else "",
        "light_condition": first_value(
            native.get("light_condition") if native else "",
            tlpg.get("light_condition") if tlpg else "",
        ),
        "water_condition": first_value(
            native.get("water_condition") if native else "",
            tlpg.get("water_condition") if tlpg else "",
        ),
        "planting_environment": first_value(
            native.get("planting_environment") if native else "",
            tlpg.get("planting_environment") if tlpg else "",
        ),
        "region": clean_text(native.get("region")) if native else "",
        "flowering_period": first_value(
            native.get("flowering_period") if native else "",
            tlpg.get("flowering_period") if tlpg else "",
        ),
        "flower_months": first_value(
            native.get("flower_months") if native else "",
            tlpg.get("flower_months") if tlpg else "",
        ),
        "fruiting_period": first_value(
            native.get("fruiting_period") if native else "",
            tlpg.get("fruiting_period") if tlpg else "",
        ),
        "fruit_months": first_value(
            native.get("fruit_months") if native else "",
            tlpg.get("fruit_months") if tlpg else "",
        ),
        "flower_color": join_unique(
            native.get("flower_color") if native else "",
            tlpg.get("flower_color") if tlpg else "",
        ),
        "leaf_color": clean_text(native.get("leaf_color")) if native else "",
        "leaf_habit": clean_text(native.get("leaf_habit")) if native else "",
        "ornamental_part": join_unique(
            native.get("ornamental_part") if native else "",
            tlpg.get("ornamental_part") if tlpg else "",
        ),
        "ecological_use": first_value(
            native.get("ecological_use") if native else "",
            tlpg.get("ecological_use") if tlpg else "",
        ),
        "is_toxic": clean_text(native.get("is_toxic")) if native else "UNKNOWN",
        "cultivation": clean_text(tlpg.get("cultivation")) if tlpg else "",
        "maintenance_notes": clean_text(native.get("maintenance_notes")) if native else "",
        "intro": clean_text(tlpg.get("intro")) if tlpg else "",
        "landscape_application": clean_text(tlpg.get("landscape_application")) if tlpg else "",
        "knowledge": clean_text(tlpg.get("knowledge")) if tlpg else "",
        "image_url": clean_text(tlpg.get("image_url")) if tlpg else "",
        "source_urls": join_unique(
            native.get("source_url") if native else "",
            tlpg.get("source_url") if tlpg else "",
        ),
        "updated_at": updated_at,
    }
    row.update(height)
    row["scientific_name_normalized"] = normalize_scientific_name(
        row.get("scientific_name")
    )
    row["search_text"] = build_search_text(row)
    row["data_completeness_score"] = completeness_score(row)
    row["missing_core_fields"] = missing_core_fields(row)
    return row


def read_csv_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def read_sheet_rows(spreadsheet_id, worksheet_name, service_account_file):
    client = gspread.service_account(filename=service_account_file)
    worksheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    return worksheet.get_all_records(numericise_ignore=["all"])


def write_csv_rows(rows, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def write_sheet_rows(rows):
    service_account_file = os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"]
    spreadsheet_id = os.environ["PLANTS_MERGED_SPREADSHEET_ID"]
    worksheet_name = os.environ["PLANTS_MERGED_WORKSHEET_NAME"]
    client = gspread.service_account(filename=service_account_file)
    worksheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    values = [FIELDNAMES] + [[row.get(field, "") for field in FIELDNAMES] for row in rows]
    worksheet.clear()
    worksheet.update(values=values, range_name="A1")
    return worksheet_name


def load_inputs(args):
    if args.trees_csv:
        native_rows = read_csv_rows(args.trees_csv)
    else:
        native_rows = read_sheet_rows(
            os.environ["TREES_CLEAN_SPREADSHEET_ID"],
            os.environ["TREES_CLEAN_WORKSHEET_NAME"],
            os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"],
        )

    if args.tlpg_csv:
        tlpg_rows = read_csv_rows(args.tlpg_csv)
    else:
        tlpg_rows = read_sheet_rows(
            os.environ["TLPG_CLEAN_SPREADSHEET_ID"],
            os.environ["TLPG_CLEAN_WORKSHEET_NAME"],
            os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"],
        )

    return native_rows, tlpg_rows


def build_merged_rows(native_rows, tlpg_rows):
    updated_at = datetime.now(TAIPEI_TZ).isoformat(timespec="seconds")
    groups = []
    key_to_group = {}
    short_sci_to_group = {}
    name_family_to_group = {}

    def add_native(row):
        key = canonical_key(row)
        if not key:
            return
        group = {"key": key, "native": row, "tlpg": None}
        groups.append(group)
        key_to_group[key] = group
        short_key = scientific_short_key(row)
        if short_key:
            short_sci_to_group.setdefault(short_key, group)
        secondary_key = name_family_key(row)
        if secondary_key:
            name_family_to_group[secondary_key] = group

    def add_tlpg(row):
        key = canonical_key(row)
        short_key = scientific_short_key(row)
        secondary_key = name_family_key(row)
        group = key_to_group.get(key) if key else None
        if group is None and short_key:
            group = short_sci_to_group.get(short_key)
        if group is None and secondary_key:
            group = name_family_to_group.get(secondary_key)

        if group is None:
            final_key = key or secondary_key
            if not final_key:
                return
            group = {"key": final_key, "native": None, "tlpg": row}
            groups.append(group)
            key_to_group[final_key] = group
            if short_key:
                short_sci_to_group.setdefault(short_key, group)
        else:
            group["tlpg"] = row
            if short_key:
                short_sci_to_group.setdefault(short_key, group)
            if secondary_key:
                name_family_to_group.setdefault(secondary_key, group)

    for row in native_rows:
        add_native(row)
    for row in tlpg_rows:
        add_tlpg(row)

    merged = []
    for index, group in enumerate(groups, start=1):
        merged.append(
            merge_pair(
                group.get("native"),
                group.get("tlpg"),
                index,
                group["key"],
                updated_at,
            )
        )
    return merged


def parse_args():
    parser = argparse.ArgumentParser(
        description="Merge trees_clean and tlpg_clean into plants_merged."
    )
    parser.add_argument("--trees-csv", help="Read trees_clean rows from local CSV.")
    parser.add_argument("--tlpg-csv", help="Read tlpg_clean rows from local CSV.")
    parser.add_argument(
        "--output-csv",
        default="data/plants_merged_preview.csv",
        help="Write merged preview CSV here.",
    )
    parser.add_argument(
        "--write-sheet",
        action="store_true",
        help="Replace the configured plants_merged worksheet with merged rows.",
    )
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()
    native_rows, tlpg_rows = load_inputs(args)
    rows = build_merged_rows(native_rows, tlpg_rows)
    write_csv_rows(rows, args.output_csv)
    print(f"Wrote {len(rows)} merged rows to {args.output_csv}")

    if args.write_sheet:
        worksheet_name = write_sheet_rows(rows)
        print(f"Wrote {len(rows)} merged rows to Google Sheet worksheet {worksheet_name}")


if __name__ == "__main__":
    main()
