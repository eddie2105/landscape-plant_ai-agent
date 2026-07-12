import argparse
import csv
import os
import re
import time
from datetime import datetime, timezone, timedelta
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import gspread
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from dotenv import load_dotenv


BASE_URL = "https://nativetree.forest.gov.tw"
TREE_LIST_URL = f"{BASE_URL}/Tree"
TAIPEI_TZ = timezone(timedelta(hours=8))

FIELDNAMES = [
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

LABEL_TO_FIELD = {
    "植物名稱": "chinese_name",
    "學名": "scientific_name",
    "科別": "family",
    "海拔": "altitude",
    "全球分布": "global_distribution",
    "環境類型": "environment_type",
    "臺灣分布": "taiwan_distribution",
    "地區": "region",
    "栽植場域": "planting_environment",
    "生長型": "growth_form",
    "樹高": "tree_height",
    "冠幅": "crown_shape",
    "日照": "light_condition",
    "水分": "water_condition",
    "適植類型": "planting_type",
    "觀賞部位": "ornamental_part",
    "生態應用": "ecological_use",
    "是否有毒": "is_toxic",
    "繁殖法": "propagation",
    "生長速度": "growth_rate",
}

INLINE_LABEL_TO_FIELD = {
    "葉序": "leaf_arrangement",
    "葉色": "leaf_color",
    "葉候": "leaf_habit",
    "質地": "leaf_texture",
    "花型": "flower_type",
    "花序": "inflorescence",
    "花色": "flower_color",
    "花期": "flowering_period",
    "果型": "fruit_type",
    "大小": "fruit_size",
    "熟果色": "fruit_color",
    "果期": "fruiting_period",
}


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attrs = dict(attrs)
        href = attrs.get("href")
        if href:
            self.links.append(href)


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(unescape(text))


def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def fetch(session, url, verify_ssl=True):
    response = session.get(url, timeout=30, verify=verify_ssl)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def extract_tree_links(html):
    parser = LinkParser()
    parser.feed(html)

    urls = []
    seen = set()
    for href in parser.links:
        url = urljoin(BASE_URL, href)
        parsed = urlparse(url)
        match = re.search(r"/Tree/Info/([0-9a-f]{32})$", parsed.path)
        if not match:
            continue
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def extract_text_parts(html):
    parser = TextParser()
    parser.feed(html)
    return [clean_text(part) for part in parser.parts if clean_text(part)]


def value_after_label(parts, label):
    for index, part in enumerate(parts):
        if part == label and index + 1 < len(parts):
            return parts[index + 1]
        if part.startswith(f"{label} "):
            return part[len(label) :].strip()
    return ""


def inline_value(text, label):
    pattern = rf"{re.escape(label)}\s*[:：]\s*([^\n;；]*)"
    match = re.search(pattern, text)
    return clean_text(match.group(1)) if match else ""


def normalize_is_toxic(value):
    value = clean_text(value)
    if value == "否":
        return "FALSE"
    if value == "是":
        return "TRUE"
    return value or "UNKNOWN"


def extract_photo_source(parts):
    for index, part in enumerate(parts):
        if "照片來源" in part:
            source = part.split("照片來源", 1)[-1]
            source = source.replace("：", "").replace(":", "").strip()
            if source:
                return source
            if index + 1 < len(parts):
                return parts[index + 1]
    return ""


def extract_maintenance_notes(parts):
    try:
        start = parts.index("養護注意事項") + 1
    except ValueError:
        return ""

    stop_markers = ("分布在臺灣的哪裡", "觀測紀錄次數", "資料來源", "其他相似樹種")
    notes = []
    for part in parts[start:]:
        if any(marker in part for marker in stop_markers):
            break
        notes.append(part)
    return clean_text(" ".join(notes))


def parse_tree_detail(html, source_url, scraped_at):
    parts = extract_text_parts(html)
    text = "\n".join(parts)
    record = {field: "" for field in FIELDNAMES}
    record["plant_id"] = source_url.rstrip("/").split("/")[-1]
    record["source_url"] = source_url
    record["scraped_at"] = scraped_at
    record["photo_source"] = extract_photo_source(parts)
    record["maintenance_notes"] = extract_maintenance_notes(parts)

    for label, field in LABEL_TO_FIELD.items():
        record[field] = value_after_label(parts, label)

    for label, field in INLINE_LABEL_TO_FIELD.items():
        record[field] = inline_value(text, label)

    record["is_toxic"] = normalize_is_toxic(record["is_toxic"])
    record["raw_name_line"] = clean_text(
        f"{record['chinese_name']} {record['scientific_name']}"
    )

    notes = []
    required_fields = ["chinese_name", "scientific_name", "family"]
    missing = [field for field in required_fields if not record[field]]
    if missing:
        notes.append(f"missing required fields: {', '.join(missing)}")
    record["data_quality_notes"] = "; ".join(notes)

    return record


def scrape_trees(limit=None, delay_seconds=0.75, verify_ssl=True):
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 compatible; landscape-plant-ai-agent/1.0; "
                "+https://nativetree.forest.gov.tw/Tree"
            )
        }
    )

    if not verify_ssl:
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

    list_html = fetch(session, TREE_LIST_URL, verify_ssl=verify_ssl)
    links = extract_tree_links(list_html)
    if limit:
        links = links[:limit]

    scraped_at = datetime.now(TAIPEI_TZ).isoformat(timespec="seconds")
    rows = []
    for index, url in enumerate(links, start=1):
        print(f"[{index}/{len(links)}] scraping {url}")
        detail_html = fetch(session, url, verify_ssl=verify_ssl)
        rows.append(parse_tree_detail(detail_html, url, scraped_at))
        if index < len(links):
            time.sleep(delay_seconds)
    return rows


def write_csv(rows, output_path):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def write_google_sheet(rows, spreadsheet_id, worksheet_name, service_account_file):
    client = gspread.service_account(filename=service_account_file)
    worksheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    values = [FIELDNAMES] + [[row.get(field, "") for field in FIELDNAMES] for row in rows]
    worksheet.clear()
    worksheet.update(values=values, range_name="A1")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape native tree data and optionally sync it to Google Sheets."
    )
    parser.add_argument("--limit", type=int, help="Scrape only the first N tree records.")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.75,
        help="Seconds to wait between detail-page requests.",
    )
    parser.add_argument(
        "--output",
        default="data/native_trees.csv",
        help="CSV output path.",
    )
    parser.add_argument(
        "--write-sheet",
        action="store_true",
        help="Replace the configured Google Sheet worksheet with scraped rows.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Skip SSL certificate verification for sites that fail local verification.",
    )
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()
    rows = scrape_trees(
        limit=args.limit,
        delay_seconds=args.delay,
        verify_ssl=not args.insecure,
    )
    write_csv(rows, args.output)
    print(f"Wrote {len(rows)} rows to {args.output}")

    if args.write_sheet:
        spreadsheet_id = os.getenv("TREES_RAW_SPREADSHEET_ID") or os.getenv(
            "PLANTS_SPREADSHEET_ID"
        )
        worksheet_name = os.getenv("TREES_RAW_WORKSHEET_NAME") or os.getenv(
            "PLANTS_WORKSHEET_NAME"
        )
        service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        if not spreadsheet_id or not worksheet_name or not service_account_file:
            raise RuntimeError(
                "Missing one of: TREES_RAW_SPREADSHEET_ID, "
                "TREES_RAW_WORKSHEET_NAME, GOOGLE_SERVICE_ACCOUNT_FILE"
            )
        write_google_sheet(rows, spreadsheet_id, worksheet_name, service_account_file)
        print(f"Wrote {len(rows)} rows to Google Sheet worksheet {worksheet_name}")


if __name__ == "__main__":
    main()
