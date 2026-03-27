import urllib.request
import csv
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

class SchoolListParser(HTMLParser):
    def __init__(self, is_primary):
        super().__init__()
        self.is_primary = is_primary
        self.in_table = False
        self.in_tbody = False
        self.in_tr = False
        self.in_td = False
        self.in_a = False
        self.current_td_index = -1 
        self.current_row = []
        self.current_cell_data = ""
        self.schools = []
        self.current_href = ""
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "table" and attrs_dict.get("width") == "100%" and attrs_dict.get("cellspacing") == "0":
            self.in_table = True
        elif self.in_table and tag == "tbody":
            self.in_tbody = True
        elif self.in_tbody and tag == "tr":
            self.in_tr = True
            self.current_row = []
            self.current_td_index = -1
            self.current_href = ""
        elif self.in_tr and (tag == "td" or tag == "th"):
            self.in_td = True
            self.current_td_index += 1
            self.current_cell_data = ""
            if attrs_dict.get("colspan") == "6":
                self.in_td = False
                
        elif self.in_td and tag == "a":
            self.in_a = True
            href = attrs_dict.get("href", "")
            if "sch_detail.php" in href:
                self.current_href = href
        elif self.in_td and tag == "br":
            self.current_cell_data += "\n"

    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table = False
            self.in_tbody = False
        elif tag == "tbody":
            self.in_tbody = False
        elif tag == "tr" and self.in_tr:
            self.in_tr = False
            if len(self.current_row) >= 5 and self.current_row[1].strip() and "School Name" not in self.current_row[1]:
                self.process_row()
        elif tag == "td" or tag == "th":
            if self.in_td:
                self.current_row.append(self.current_cell_data.strip())
            self.in_td = False
            self.in_a = False
        elif tag == "a":
            self.in_a = False
            
    def handle_data(self, data):
        if self.in_td:
            self.current_cell_data += data

    def process_row(self):
        name_cell = self.current_row[1].strip()
        names = name_cell.split('\n')
        name_eng = names[0].strip() if len(names) > 0 else name_cell
        name_chi = names[-1].strip() if len(names) > 1 else ""
        
        if self.is_primary:
            if len(self.current_row) > 4:
                school_type = self.current_row[4].strip()
                self.schools.append({
                    "Name (English)": name_eng,
                    "Name (Chinese)": name_chi,
                    "School Type": school_type,
                    "Link": self.current_href
                })
        else:
            if len(self.current_row) > 4:
                district = self.current_row[3].strip()
                school_type = self.current_row[4].strip()
                self.schools.append({
                    "Name (English)": name_eng,
                    "Name (Chinese)": name_chi,
                    "District": district,
                    "School Type": school_type,
                    "Link": self.current_href
                })

DISTRICTS = {
    1: "Central & Western", 2: "Eastern", 3: "Islands", 4: "Southern",
    5: "Wan Chai", 6: "Kowloon City", 7: "Kwun Tong", 8: "Sai Kung",
    9: "Sham Shui Po", 10: "Wong Tai Sin", 11: "Yau Tsim Mong", 12: "North",
    13: "Sha Tin", 14: "Tai Po", 15: "Kwai Tsing", 16: "Tsuen Wan",
    17: "Tuen Mun", 18: "Yuen Long"
}

def fetch_html(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urllib.request.urlopen(req)
    return response.read().decode('utf-8')

def generate_oid():
    return os.urandom(12).hex()

def deduplicate(schools):
    seen = set()
    unique_schools = []
    for s in schools:
        if s["Name (English)"] not in seen:
            seen.add(s["Name (English)"])
            s["_id"] = {"$oid": generate_oid()}
            unique_schools.append(s)
    return unique_schools

def fetch_school_details(school, base_url):
    link = school.get("Link")
    school["Address"] = ""
    school["Phone"] = ""
    school["Email"] = ""
    school["Country"] = "Hong Kong"
    
    if not link:
        return school
        
    url = f"{base_url}/{link}"
    try:
        html = fetch_html(url)
        
        addr_match = re.search(r'<td[^>]*>Address:\s*</td>\s*<td[^>]*>(.*?)</td>', html, re.IGNORECASE | re.DOTALL)
        if addr_match:
            school["Address"] = addr_match.group(1).strip()
            
        phone_match = re.search(r'<td[^>]*>Phone:&nbsp;&nbsp;</td>\s*<td[^>]*>(.*?)</td>', html, re.IGNORECASE | re.DOTALL)
        if phone_match:
            school["Phone"] = phone_match.group(1).strip()
            
        email_match = re.search(r'<td[^>]*>Email:&nbsp;&nbsp;</td>\s*<td[^>]*><a[^>]*>(.*?)</a></td>', html, re.IGNORECASE | re.DOTALL)
        if email_match:
            school["Email"] = email_match.group(1).strip()
    except Exception as e:
        print(f"Error fetching details for {school['Name (English)']}: {e}")
        
    return school

def scrape_primary():
    all_schools = []
    print("Scraping Primary Schools...")
    for district_id, district_name in DISTRICTS.items():
        print(f"  Fetching district: {district_name}")
        url = f"https://www.chsc.hk/psp2025/sch_list.php?district_id={district_id}&lang_id=1&frmMode=pagebreak"
        try:
            html = fetch_html(url)
            parser = SchoolListParser(is_primary=True)
            parser.feed(html)
            
            for school in parser.schools:
                school["District"] = district_name
                school["Level"] = "Primary"
                all_schools.append(school)
        except Exception as e:
            print(f"Error fetching {district_name}: {e}")
            
    all_schools = deduplicate(all_schools)
    
    print("  Fetching primary school details...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        all_schools = list(executor.map(lambda s: fetch_school_details(s, "https://www.chsc.hk/psp2025"), all_schools))
        
    if all_schools:
        keys = ["_id", "District", "Name (English)", "Name (Chinese)", "School Type", "Level", "Address", "Phone", "Email", "Country", "Link"]
        with open("primary_schools.csv", "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_schools)
        print(f"Saved {len(all_schools)} unique primary schools to primary_schools.csv (Excel compatible)")
    return all_schools

def scrape_secondary():
    all_schools = []
    print("Scraping Secondary Schools...")
    for district_id, district_name in DISTRICTS.items():
        print(f"  Fetching district: {district_name}")
        url = f"https://www.chsc.hk/ssp2025/sch_list.php?district_id={district_id}&lang_id=1&frmMode=pagebreak"
        try:
            html = fetch_html(url)
            parser = SchoolListParser(is_primary=False)
            parser.feed(html)
            
            for school in parser.schools:
                if not school.get("District"):
                    school["District"] = district_name
                school["Level"] = "Secondary"
                all_schools.append(school)
        except Exception as e:
            print(f"Error fetching {district_name}: {e}")
            
    all_schools = deduplicate(all_schools)
    
    print("  Fetching secondary school details...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        all_schools = list(executor.map(lambda s: fetch_school_details(s, "https://www.chsc.hk/ssp2025"), all_schools))
        
    if all_schools:
        keys = ["_id", "District", "Name (English)", "Name (Chinese)", "School Type", "Level", "Address", "Phone", "Email", "Country", "Link"]
        with open("secondary_schools.csv", "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_schools)
        print(f"Saved {len(all_schools)} unique secondary schools to secondary_schools.csv (Excel compatible)")
    return all_schools

if __name__ == "__main__":
    primary = scrape_primary()
    secondary = scrape_secondary()
    

    combined = primary + secondary

    formatted_schools = []
    for s in combined:
        formatted_schools.append({
            "_id": s["_id"],
            "nameEng": s["Name (English)"],
            "nameChi": s["Name (Chinese)"],
            "district": s["District"],
            "schoolType": s["School Type"],
            "level": s["Level"],
            "address": s["Address"],
            "phone": s["Phone"],
            "email": s["Email"],
            "country": s["Country"]
        })
        
    with open("schools.json", "w", encoding="utf-8") as f:
        json.dump(formatted_schools, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(formatted_schools)} combined schools to schools.json in MongoDB format")

    print("Scraping completed!")
