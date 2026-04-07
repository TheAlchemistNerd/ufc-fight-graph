import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class UfcScraper:
    def __init__(self, use_selenium=False):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.use_selenium = use_selenium
        self.driver = None
        if use_selenium:
            self._init_driver()

    def _init_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)

    def _get_soup(self, url):
        if self.use_selenium:
            self.driver.get(url)
            # Wait a bit for JS to load if needed
            time.sleep(2)
            return BeautifulSoup(self.driver.page_source, 'lxml')
        else:
            response = requests.get(url, headers=self.headers)
            return BeautifulSoup(response.content, 'lxml')

    def scrape_fighter_profile(self, fighter_url):
        print(f"Scraping fighter profile: {fighter_url}")
        soup = self._get_soup(fighter_url)

        fighter_data = {}

        # Name and Record
        title_block = soup.find('h2', class_='b-content__title')
        if title_block:
            fighter_data['name'] = title_block.find('span', class_='b-content__title-highlight').text.strip()
            fighter_data['record'] = title_block.find('span', class_='b-content__title-record').text.strip()

        # Nickname
        nickname_block = soup.find('p', class_='b-content__Nickname')
        fighter_data['nickname'] = nickname_block.text.strip() if nickname_block else ""

        # Bio Info
        bio_list = soup.find('ul', class_='b-list__box-list')
        if bio_list:
            items = bio_list.find_all('li')
            for item in items:
                text = item.text.strip()
                if "Height:" in text: fighter_data['height'] = text.replace("Height:", "").strip()
                if "Weight:" in text: fighter_data['weight'] = text.replace("Weight:", "").strip()
                if "Reach:" in text: fighter_data['reach'] = text.replace("Reach:", "").strip()
                if "STANCE:" in text: fighter_data['stance'] = text.replace("STANCE:", "").strip()
                if "DOB:" in text: fighter_data['dob'] = text.replace("DOB:", "").strip()

        # Career Statistics
        stats_boxes = soup.find_all('div', class_='b-list__info-box-left')
        for box in stats_boxes:
            stat_items = box.find_all('li')
            for stat in stat_items:
                text = stat.text.strip()
                if ":" in text:
                    key, val = text.split(":", 1)
                    fighter_data[key.strip().lower()] = val.strip()

        # Fight URLs and basic data
        fight_table = soup.find('table', class_='b-fight-details__table')
        fight_urls = []
        fights = []
        if fight_table:
            rows = fight_table.find_all('tr', class_='js-fight-details-click')
            for row in rows:
                if 'data-link' in row.attrs:
                    url = row['data-link']
                    fight_urls.append(url)

                    cols = row.find_all('td')
                    if len(cols) >= 10:
                        res_p = cols[0].find('p')
                        result = res_p.text.strip() if res_p else "N/A"

                        opp_a = cols[1].find_all('p')[1].find('a') if len(cols[1].find_all('p')) > 1 else None
                        opponent = opp_a.text.strip() if opp_a else "N/A"

                        event_p = cols[6].find_all('p')[0]
                        event_name = event_p.find('a').text.strip() if event_p.find('a') else event_p.text.strip()
                        date = cols[6].find_all('p')[1].text.strip()

                        method = cols[7].find_all('p')[0].text.strip()
                        round_val = cols[8].find('p').text.strip()
                        time_val = cols[9].find('p').text.strip()

                        fights.append({
                            'url': url,
                            'result': result,
                            'opponent': opponent,
                            'event': event_name,
                            'date': date,
                            'method': method,
                            'round': round_val,
                            'time': time_val
                        })

        fighter_data['fight_urls'] = fight_urls
        fighter_data['fights'] = fights
        return fighter_data

    def scrape_fight_details(self, fight_url):
        print(f"Scraping fight details: {fight_url}")
        soup = self._get_soup(fight_url)

        # Meta info
        title_h2 = soup.find('h2', class_='b-content__title')
        event_name = title_h2.find('a').text.strip() if title_h2 and title_h2.find('a') else ""

        date_val = ""
        info_items = soup.find_all('li', class_='b-list__box-list-item')
        for item in info_items:
            if "Date:" in item.text:
                date_val = item.text.replace("Date:", "").strip()
                break

        # If date is still empty, try to get it from the event page
        if not date_val:
            title_h2 = soup.find('h2', class_='b-content__title')
            if title_h2 and title_h2.find('a'):
                event_url = title_h2.find('a')['href']
                print(f"Date missing on fight page, following event link: {event_url}")
                event_soup = self._get_soup(event_url)
                event_info = event_soup.find_all('li', class_='b-list__box-list-item')
                for item in event_info:
                    if "Date:" in item.text:
                        date_val = item.text.replace("Date:", "").strip()
                        break

        fighter_links = soup.find_all('a', class_='b-fight-details__person-link')
        fighters = [f.text.strip() for f in fighter_links][:2] # Take first 2 to avoid potential duplicates in lower tables

        fight_details = {
            'url': fight_url,
            'event': event_name,
            'date': date_val,
            'fighters': fighters,
            'rounds': []
        }

        # Detailed tables (Totals and Significant Strikes)
        # These are usually in sections with class 'b-fight-details__section'
        # We want the round-by-round breakdown which is usually hidden or at the bottom

        round_sections = soup.find_all('tr', class_='b-fight-details__table-row')
        # This is getting complex because the table structure uses rows to represent rounds
        # Let's look for the tables that have 'Per Round' headers

        round_tables = soup.find_all('table', class_='b-fight-details__table')
        # Usually:
        # Table 0: Total (Overall)
        # Table 1: Sig Str (Overall)
        # Table 2...N: Per Round Tables

        # To keep it simple for this POC, let's extract the Overall Totals first
        if len(round_tables) >= 2:
            totals_table = round_tables[0]
            sig_str_table = round_tables[1]

            # Parsing logic for a standard UFC stats table
            def parse_table(table):
                rows = table.find_all('tr')[1:] # skip header
                data = []
                for row in rows:
                    cols = row.find_all('td')
                    col_texts = [c.text.strip() for c in cols]
                    data.append(col_texts)
                return data

            fight_details['overall_totals'] = parse_table(totals_table)
            fight_details['overall_sig_str'] = parse_table(sig_str_table)

        return fight_details

    def scrape_alphabetical_list(self, char):
        url = f"http://ufcstats.com/statistics/fighters?char={char}&page=all"
        print(f"Scraping fighter list for char: {char}")
        soup = self._get_soup(url)

        fighter_urls = []
        table = soup.find('table', class_='b-statistics__table')
        if table:
            rows = table.find_all('tr', class_='b-statistics__table-row')[1:] # skip header
            for row in rows:
                cols = row.find_all('td')
                if cols:
                    link = cols[0].find('a')
                    if link and 'href' in link.attrs:
                        fighter_urls.append(link['href'])

        return fighter_urls

    def normalize_data(self, data):
        normalized = data.copy()

        # Height: 6' 2" -> 74 (inches)
        if 'height' in data and data['height'] != "--":
            match = re.search(r"(\d+)'\s*(\d+)\"", data['height'])
            if match:
                inches = int(match.group(1)) * 12 + int(match.group(2))
                normalized['height_inches'] = inches

        # Weight: 170 lbs. -> 170 (int)
        if 'weight' in data and data['weight'] != "--":
            match = re.search(r"(\d+)", data['weight'])
            if match:
                normalized['weight_lbs'] = int(match.group(1))

        # Reach: 74" -> 74 (int)
        if 'reach' in data and data['reach'] != "--":
            match = re.search(r"(\d+)", data['reach'])
            if match:
                normalized['reach_inches'] = int(match.group(1))

        # Record: Record: 22-6-0 (1 NC) -> wins: 22, losses: 6, draws: 0, nc: 1
        if 'record' in data:
            match = re.search(r"(\d+)-(\d+)-(\d+)(?:\s*\((.*)\))?", data['record'])
            if match:
                normalized['wins'] = int(match.group(1))
                normalized['losses'] = int(match.group(2))
                normalized['draws'] = int(match.group(3))
                nc_part = match.group(4)
                if nc_part and "NC" in nc_part:
                    nc_match = re.search(r"(\d+)", nc_part)
                    normalized['nc'] = int(nc_match.group(1)) if nc_match else 0
                else:
                    normalized['nc'] = 0

        # Percentages: 54% -> 0.54
        for key in ['str. acc.', 'str. def', 'td acc.', 'td def.']:
            if key in data and "%" in data[key]:
                normalized[key.replace(".", "").replace(" ", "_")] = float(data[key].replace("%", "")) / 100.0

        return normalized

    def close(self):
        if self.driver:
            self.driver.quit()

if __name__ == "__main__":
    scraper = UfcScraper(use_selenium=False)
    # Leon Edwards
    leon_url = "http://ufcstats.com/fighter-details/f1fac969a1d70b08"
    leon_data = scraper.scrape_fighter_profile(leon_url)
    print("\nLeon Edwards Bio Data:")
    for k, v in leon_data.items():
        if k != 'fight_urls':
            print(f"{k}: {v}")

    print(f"\nFound {len(leon_data['fight_urls'])} fights.")

    # Scrape 1 sample fight
    if leon_data['fight_urls']:
        sample_fight = scraper.scrape_fight_details(leon_data['fight_urls'][0])
        print("\nSample Fight Metadata:")
        print(f"Event: {sample_fight['event']}")
        print(f"Date: {sample_fight['date']}")
        print(f"Fighters: {sample_fight['fighters']}")

    scraper.close()
