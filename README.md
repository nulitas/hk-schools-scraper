# HK Schools Scraper

A Python script to scrape and extract comprehensive data of Primary and Secondary schools in Hong Kong, directly from the official Committee on Home-School Co-operation (CHSC) website.

## Features

- Scrapes profiles for both **Primary** (PSP 2025) and **Secondary** (SSP 2025) schools.
- Extracts detailed data for each school:
  - English and Chinese Names
  - District
  - School Type (e.g., Gov't, Aided, DSS)
  - Address
  - Phone Number
  - Email Address
- Uses multi-threading (`ThreadPoolExecutor`) to quickly fetch detail pages concurrently.
- Generates unique MongoDB-compatible ObjectIds (`_id`) for easy database insertion.
- Automatically handles data deduplication.

## Output Files

Running the script generates three files:
1. `primary_schools.csv` - Excel-compatible CSV file containing all primary schools.
2. `secondary_schools.csv` - Excel-compatible CSV file containing all secondary schools.
3. `schools.json` - A single JSON file combining both primary and secondary schools, formatted to be easily imported into a MongoDB database.

## Prerequisites

This script is built using only Python's standard libraries. No external dependencies (like `requests` or `BeautifulSoup`) are required!

- Python 3.6 or higher

## Usage

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/hk-schools-scraper.git
   cd hk-schools-scraper
   ```

2. Run the script:
   ```bash
   python scrape_schools.py
   ```

3. Wait for the scraping to finish. Progress will be displayed in the console. The output files will be created in the same directory.

## Disclaimer

This project is intended for educational purposes only. Please be mindful of the server load when scraping and respect the source website's terms of service and `robots.txt`.
