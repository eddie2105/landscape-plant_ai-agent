import argparse
import os

import gspread
from dotenv import load_dotenv


DEFAULT_TABS = [
    ("tlpg_raw", 1000, 24),
    ("tlpg_clean", 1000, 32),
    ("plants_merged", 1500, 48),
]


def parse_tab(value):
    parts = value.split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("tabs must use title:rows:cols")
    title, rows, cols = parts
    return title, int(rows), int(cols)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create missing worksheets in the configured planting spreadsheet."
    )
    parser.add_argument(
        "--spreadsheet-id",
        default=None,
        help="Spreadsheet id. Defaults to TREES_RAW_SPREADSHEET_ID or PLANTS_SPREADSHEET_ID.",
    )
    parser.add_argument(
        "--tab",
        action="append",
        type=parse_tab,
        help="Worksheet spec as title:rows:cols. Can be repeated.",
    )
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()

    spreadsheet_id = (
        args.spreadsheet_id
        or os.getenv("TREES_RAW_SPREADSHEET_ID")
        or os.getenv("PLANTS_SPREADSHEET_ID")
    )
    if not spreadsheet_id:
        raise RuntimeError("Missing spreadsheet id")

    service_account_file = os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"]
    client = gspread.service_account(filename=service_account_file)
    spreadsheet = client.open_by_key(spreadsheet_id)
    existing = {worksheet.title: worksheet for worksheet in spreadsheet.worksheets()}

    print("spreadsheet_title:", spreadsheet.title)
    print("before:", list(existing))

    tabs = args.tab or DEFAULT_TABS
    created = []
    for title, rows, cols in tabs:
        worksheet = existing.get(title)
        if worksheet is None:
            worksheet = spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)
            existing[title] = worksheet
            created.append(title)
        print(
            f"{title}: gid={worksheet.id}, rows={worksheet.row_count}, cols={worksheet.col_count}"
        )

    print("created:", created)


if __name__ == "__main__":
    main()
