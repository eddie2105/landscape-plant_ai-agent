import argparse
import csv
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import gspread
import requests
from dotenv import load_dotenv


BASE_URL = "https://tlpg.hsiliu.org.tw"
CATEGORY_IDS = range(1, 10)
TAIPEI_TZ = timezone(timedelta(hours=8))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

CATEGORY_FALLBACKS = {
    1: ("觀花喬木", "Flower arbor"),
    2: ("觀葉喬木", "Leaf arbor"),
    3: ("觀果喬木", "Fruit tree"),
    4: ("觀賞灌木", "Ornamental shrub"),
    5: ("蔓藤植物", "Climbing Plant"),
    6: ("地被植物", "Groundcover"),
    7: ("花壇植物", "Bedflower"),
    8: ("蔬菜與香藥草", "Vegetable and Herb"),
    9: ("水生與濕生植物", "Aquatic and hygrophytes"),
}

FIELDNAMES = [
    "tlpg_id",
    "category_id",
    "category_name",
    "category_english_name",
    "chinese_name",
    "family",
    "scientific_name",
    "english_name",
    "japanese_name",
    "alias_names",
    "intro",
    "cultivation",
    "landscape_application",
    "knowledge",
    "image_url",
    "image_alt",
    "source_url",
    "scraped_at",
    "raw_title_line",
    "data_quality_notes",
]

SECTION_TO_FIELD = {
    "簡介": "intro",
    "栽培": "cultivation",
    "應用": "landscape_application",
    "知識": "knowledge",
}

FOOTER_MARKERS = (
    "農業部農田水利署瑠公管理處",
    "財團法人台北市錫瑠環境綠化基金會",
    "COPYRIGHT",
    "累積拜訪人數",
    "jQuery(document).ready",
)

LABEL_PREFIXES = ("學名：", "英名：", "日名：", "別名：")


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
        text = clean_text(data)
        if text:
            self.parts.append(unescape(text))


class ImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag != "img":
            return
        attrs = dict(attrs)
        self.images.append(
            {
                "src": attrs.get("src", ""),
                "alt": attrs.get("alt", ""),
            }
        )


def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def fetch(session, url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def extract_links(html):
    parser = LinkParser()
    parser.feed(html)
    return parser.links


def extract_text_parts(html):
    parser = TextParser()
    parser.feed(html)
    return [part for part in parser.parts if part]


def extract_first_content_image(html, source_url):
    parser = ImageParser()
    parser.feed(html)
    for image in parser.images:
        src = clean_text(image.get("src"))
        alt = clean_text(image.get("alt"))
        if not src and not alt:
            continue
        if "facebook" in src.casefold():
            continue
        return urljoin(source_url, src) if src else "", alt
    return "", ""


def extract_category_label(parts):
    for part in parts:
        if any(marker in part for marker in ("植物名稱搜尋", "篩選條件", "開始搜尋")):
            continue
        if any(marker in part for marker in FOOTER_MARKERS):
            continue
        if part.startswith(("台灣景觀植物介紹", "搜尋植物", "聯絡我們")):
            continue
        if re.search(r"[A-Za-z]", part) and re.search(r"[\u4e00-\u9fff]", part):
            match = re.match(r"(.+?)\s+([A-Za-z].*)$", part)
            if match:
                return clean_text(match.group(1)), clean_text(match.group(2))
            return part, ""
    return "", ""


def category_url(category_id, start=None):
    url = f"{BASE_URL}/plant/category/{category_id}"
    if start:
        return f"{url}?start={start}"
    return url


def collect_category_pages(session, category_id, page_size=8, max_empty_pages=2):
    pages = []
    category_name = ""
    category_english_name = ""
    seen_links = set()
    empty_pages = 0
    start = 0

    while empty_pages < max_empty_pages:
        url = category_url(category_id, start=start)
        html = fetch(session, url)

        if not category_name:
            category_name, category_english_name = extract_category_label(
                extract_text_parts(html)
            )

        plant_links = extract_plant_links([(url, html)])
        new_links = [link for link in plant_links if link not in seen_links]
        if new_links:
            pages.append((url, html))
            seen_links.update(new_links)
            empty_pages = 0
        else:
            empty_pages += 1

        start += page_size

    if not category_name:
        category_name, category_english_name = CATEGORY_FALLBACKS.get(
            category_id, ("", "")
        )

    return pages, category_name, category_english_name


def extract_plant_links(category_pages):
    links = []
    seen = set()
    for _, html in category_pages:
        for href in extract_links(html):
            url = urljoin(BASE_URL, href)
            parsed = urlparse(url)
            match = re.search(r"/plant/view/(\d+)$", parsed.path)
            if not match:
                continue
            if url in seen:
                continue
            seen.add(url)
            links.append(url)
    return links


def value_after_prefix(parts, prefix):
    for index, part in enumerate(parts):
        if part.startswith(prefix):
            value = clean_text(part.split("：", 1)[-1])
            if value:
                return value
            if index + 1 >= len(parts):
                return ""
            next_part = parts[index + 1]
            if next_part in SECTION_TO_FIELD or next_part.startswith(LABEL_PREFIXES):
                return ""
            if any(marker in next_part for marker in FOOTER_MARKERS):
                return ""
            return clean_text(next_part)
    return ""


def section_text(parts, section_name):
    try:
        start = parts.index(section_name) + 1
    except ValueError:
        return ""

    stop_sections = set(SECTION_TO_FIELD)
    values = []
    for part in parts[start:]:
        if part in stop_sections:
            break
        if any(marker in part for marker in FOOTER_MARKERS):
            break
        values.append(part)
    return clean_text(" ".join(values))


def parse_detail(
    html,
    source_url,
    category_id,
    category_name,
    category_english_name,
    scraped_at,
):
    parts = extract_text_parts(html)
    image_url, image_alt = extract_first_content_image(html, source_url)
    record = {field: "" for field in FIELDNAMES}

    tlpg_id = source_url.rstrip("/").split("/")[-1]
    scientific_name = value_after_prefix(parts, "學名：")
    english_name = value_after_prefix(parts, "英名：")
    japanese_name = value_after_prefix(parts, "日名：")
    alias_names = value_after_prefix(parts, "別名：")

    scientific_index = next(
        (index for index, part in enumerate(parts) if part.startswith("學名：")),
        None,
    )
    if scientific_index is not None and scientific_index >= 2:
        chinese_name = parts[scientific_index - 2]
        family = parts[scientific_index - 1]
    else:
        chinese_name = ""
        family = ""

    record.update(
        {
            "tlpg_id": tlpg_id,
            "category_id": str(category_id),
            "category_name": category_name,
            "category_english_name": category_english_name,
            "chinese_name": chinese_name,
            "family": family,
            "scientific_name": scientific_name,
            "english_name": english_name,
            "japanese_name": japanese_name,
            "alias_names": alias_names,
            "image_url": image_url,
            "image_alt": image_alt,
            "source_url": source_url,
            "scraped_at": scraped_at,
            "raw_title_line": clean_text(f"{chinese_name} {scientific_name}"),
        }
    )

    for section_name, field in SECTION_TO_FIELD.items():
        record[field] = section_text(parts, section_name)

    notes = []
    for field in ("chinese_name", "scientific_name", "family"):
        if not record[field]:
            notes.append(f"missing {field}")
    record["data_quality_notes"] = "; ".join(notes)

    return record


def scrape_tlpg(limit=None, delay_seconds=0.75):
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 compatible; landscape-plant-ai-agent/1.0; "
                "+https://tlpg.hsiliu.org.tw/"
            )
        }
    )
    scraped_at = datetime.now(TAIPEI_TZ).isoformat(timespec="seconds")

    detail_jobs = []
    seen_detail_urls = set()
    for category_id in CATEGORY_IDS:
        print(f"Collecting category {category_id}")
        pages, category_name, category_english_name = collect_category_pages(
            session, category_id
        )
        plant_links = extract_plant_links(pages)
        print(
            f"Category {category_id} {category_name}: "
            f"{len(pages)} pages, {len(plant_links)} plant links"
        )
        for url in plant_links:
            if url in seen_detail_urls:
                continue
            seen_detail_urls.add(url)
            detail_jobs.append(
                (url, category_id, category_name, category_english_name)
            )
            if limit and len(detail_jobs) >= limit:
                break
        if limit and len(detail_jobs) >= limit:
            break

    rows = []
    for index, (url, category_id, category_name, category_english_name) in enumerate(
        detail_jobs, start=1
    ):
        print(f"[{index}/{len(detail_jobs)}] scraping {url}")
        html = fetch(session, url)
        rows.append(
            parse_detail(
                html,
                url,
                category_id,
                category_name,
                category_english_name,
                scraped_at,
            )
        )
        if index < len(detail_jobs):
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
        description="Scrape Taiwan Landscape Plant Guide data into tlpg_raw."
    )
    parser.add_argument("--limit", type=int, help="Scrape only the first N records.")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.75,
        help="Seconds to wait between detail-page requests.",
    )
    parser.add_argument(
        "--output",
        default="data/tlpg_raw.csv",
        help="CSV output path.",
    )
    parser.add_argument(
        "--write-sheet",
        action="store_true",
        help="Replace the configured tlpg_raw worksheet with scraped rows.",
    )
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()
    rows = scrape_tlpg(limit=args.limit, delay_seconds=args.delay)
    write_csv(rows, args.output)
    print(f"Wrote {len(rows)} rows to {args.output}")

    if args.write_sheet:
        spreadsheet_id = os.getenv("TLPG_RAW_SPREADSHEET_ID")
        worksheet_name = os.getenv("TLPG_RAW_WORKSHEET_NAME")
        service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        if not spreadsheet_id or not worksheet_name or not service_account_file:
            raise RuntimeError(
                "Missing one of: TLPG_RAW_SPREADSHEET_ID, "
                "TLPG_RAW_WORKSHEET_NAME, GOOGLE_SERVICE_ACCOUNT_FILE"
            )
        write_google_sheet(rows, spreadsheet_id, worksheet_name, service_account_file)
        print(f"Wrote {len(rows)} rows to Google Sheet worksheet {worksheet_name}")


if __name__ == "__main__":
    main()
