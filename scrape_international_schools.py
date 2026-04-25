import urllib.request
import csv
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

BASE_URL = "https://internationalschools.edb.gov.hk"
MAX_ID = 119         
MAX_WORKERS = 8      
DELAY_BETWEEN_BATCHES = 0.5  

def fetch_html(url: str):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"HTTP {e.code} fetching {url}")
        return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def generate_oid() -> str:
    return os.urandom(12).hex()


def normalize_level(stage: str) -> str:
    stage = stage.strip()
    normalized = re.sub(r"\s+cum\s+", ", ", stage, flags=re.IGNORECASE)
    return normalized

class InternationalSchoolDetailParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_h1 = False
        self._in_address_div = False
        self._in_age_li = False
        self._in_age_span = False
        self._in_email_li = False
        self._in_email_span = False
        self._in_row_div = False
        self._in_title_div = False
        self._in_value_div = False
        self._current_title = ""
        self._current_value = ""
        self._row_depth = 0  

        self.name_eng = ""
        self.address = ""
        self.raw_age_span = ""   
        self.raw_email_span = ""   
        self.school_type = ""
        self.educational_stage = "" 
        self.district = ""

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)

        if tag == "h1":
            self._in_h1 = True
            return

        if tag == "div" and "address" in attrs_d.get("class", ""):
            self._in_address_div = True
            return

        if tag == "li" and "age" in attrs_d.get("class", ""):
            self._in_age_li = True
            return
        if self._in_age_li and tag == "span":
            self._in_age_span = True
            return

        if tag == "li" and "email" in attrs_d.get("class", ""):
            self._in_email_li = True
            return
        if self._in_email_li and tag == "span":
            self._in_email_span = True
            return

        if tag == "div" and "row" in attrs_d.get("class", "").split():
            self._in_row_div = True
            self._current_title = ""
            self._current_value = ""
            self._row_depth = 0
            return

        if self._in_row_div and tag == "div":
            classes = attrs_d.get("class", "")
            self._row_depth += 1
            if "title" in classes.split():
                self._in_title_div = True
            elif self._row_depth > 0 and not ("title" in classes.split()):
                if self._current_title and not self._in_title_div:
                    self._in_value_div = True
            return

    def handle_endtag(self, tag):
        if tag == "h1":
            self._in_h1 = False
        elif tag == "div":
            if self._in_address_div:
                self._in_address_div = False
            elif self._in_value_div:
                self._in_value_div = False
                self._store_row()
            elif self._in_title_div:
                self._in_title_div = False
            elif self._in_row_div:
                self._in_row_div = False
                self._row_depth = 0
        elif tag == "li":
            if self._in_age_li:
                self._in_age_li = False
                self._in_age_span = False
            elif self._in_email_li:
                self._in_email_li = False
                self._in_email_span = False
        elif tag == "span":
            if self._in_age_span:
                self._in_age_span = False
            elif self._in_email_span:
                self._in_email_span = False

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return

        if self._in_h1:
            self.name_eng += text
        elif self._in_address_div:
            self.address += text
        elif self._in_age_span:
            self.raw_age_span += text
        elif self._in_email_span:
            self.raw_email_span += text
        elif self._in_title_div:
            self._current_title += text
        elif self._in_value_div:
            self._current_value += text

    def _store_row(self):
        title = self._current_title.strip()
        value = self._current_value.strip()
        if not title or not value:
            return
        tl = title.lower()
        if "school type" in tl:
            self.school_type = value
        elif "educational stage" in tl:
            self.educational_stage = value
        elif "district" in tl:
            self.district = value

    def get_email(self) -> str:
        if "|" in self.raw_email_span:
            return self.raw_email_span.split("|")[0].strip()
        if ";" in self.raw_email_span:
            return self.raw_email_span.split(";")[0].strip()
        if "@" in self.raw_email_span:
            return self.raw_email_span.strip()
        return ""

    def get_phone(self) -> str:
        if "|" in self.raw_email_span:
            raw_phone = self.raw_email_span.split("|", 1)[1].strip()
            phone = re.split(r"[,(]", raw_phone)[0].strip()
            return phone
        return ""

    def get_level(self) -> str:

        stage = self.educational_stage or self._parse_age_span_stage()
        return normalize_level(stage)

    def _parse_age_span_stage(self) -> str:

        if "•" in self.raw_age_span:
            return self.raw_age_span.split("•", 1)[1].strip()
        return ""


def scrape_school(school_id: int):

    url = f"{BASE_URL}/en/schools/{school_id}.html"
    html = fetch_html(url)
    if html is None:
        return None

    parser = InternationalSchoolDetailParser()
    try:
        parser.feed(html)
    except Exception as e:
        print(f"  Parse error for ID {school_id}: {e}")
        return None

    name = parser.name_eng.strip()
    if not name:

        return None

    school = {
        "_id": {"$oid": generate_oid()},
        "nameEng": name,
        "nameChi": "",         
        "district": parser.district.strip() or "",
        "schoolType": parser.school_type.strip() or "International School",
        "level": parser.get_level(),
        "address": parser.address.strip(),
        "phone": parser.get_phone(),
        "email": parser.get_email(),
        "country": "Hong Kong",
    }
    return school


def scrape_international_schools() -> list:
    ids_to_probe = list(range(1, MAX_ID + 1))
    schools = []

    print(f"Probing {len(ids_to_probe)} school IDs (1 to {MAX_ID})...")

    def fetch_and_parse(school_id: int):
        result = scrape_school(school_id)
        if result:
            print(f"  [OK] ID {school_id:3d} -> {result['nameEng']}")
        else:
            print(f"  [--] ID {school_id:3d}  (no data)")
        return result

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(fetch_and_parse, ids_to_probe))

    schools = [r for r in results if r is not None]
    print(f"\nFound {len(schools)} international schools.")
    return schools


def save_results(schools: list[dict]) -> None:
    if not schools:
        print("No schools to save.")
        return

    json_path = "international_schools.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(schools, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(schools)} schools to {json_path}")

    csv_path = "international_schools.csv"
    keys = ["_id", "nameEng", "nameChi", "district", "schoolType", "level",
            "address", "phone", "email", "country"]

    flat_schools = []
    for s in schools:
        row = dict(s)
        row["_id"] = s["_id"]["$oid"]
        flat_schools.append(row)

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(flat_schools)
    print(f"Saved {len(schools)} schools to {csv_path} (Excel compatible)")


if __name__ == "__main__":
    schools = scrape_international_schools()
    save_results(schools)
    print("\nDone!")
