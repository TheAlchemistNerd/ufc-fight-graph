"""
Full UFC Stats Scraper - Crawls all fighters, fights, events, referees, locations, weight classes.
Extended version of the original ufc_scraper.py proof of concept.
"""

import requests
from bs4 import BeautifulSoup
import time
import random
import re

class UfcStatsScraper:
    """Comprehensive scraper for all UFC Stats data."""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = requests.Session()

    def _get_soup(self, url, retries=3, delay=1):
        """Get page content with retry logic and rate limiting."""
        for attempt in range(retries):
            try:
                response = self.session.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()
                return BeautifulSoup(response.content, 'lxml')
            except Exception as e:
                print(f"  Attempt {attempt+1} failed for {url}: {e}")
                if attempt < retries - 1:
                    time.sleep(delay * (attempt + 1))
        return None

    def _parse_fight_table(self, table):
        """Parse a standard UFC stats fight table."""
        rows = table.find_all('tr')[1:]  # skip header
        data = []
        for row in rows:
            cols = row.find_all('td')
            col_texts = [c.text.strip() for c in cols]
            if any(col_texts):
                data.append(col_texts)
        return data

    # ===================== FIGHTER SCRAPING =====================

    def scrape_fighter_profile(self, fighter_url):
        """Scrape a fighter's complete profile including fight history."""
        print(f"  Scraping fighter profile: {fighter_url}")
        soup = self._get_soup(fighter_url)
        if not soup:
            return None

        fighter_data = {}

        # Name and Record
        title_block = soup.find('h2', class_='b-content__title')
        if title_block:
            name_span = title_block.find('span', class_='b-content__title-highlight')
            fighter_data['name'] = name_span.text.strip() if name_span else ""
            record_span = title_block.find('span', class_='b-content__title-record')
            fighter_data['record'] = record_span.text.strip() if record_span else ""

        # Nickname
        nickname_block = soup.find('p', class_='b-content__Nickname')
        fighter_data['nickname'] = nickname_block.text.strip() if nickname_block else ""

        # Bio Info (Height, Weight, Reach, Stance, DOB)
        bio_list = soup.find('ul', class_='b-list__box-list')
        if bio_list:
            items = bio_list.find_all('li')
            for item in items:
                text = item.text.strip()
                if "Height:" in text:
                    fighter_data['height'] = text.replace("Height:", "").strip()
                elif "Weight:" in text:
                    fighter_data['weight'] = text.replace("Weight:", "").strip()
                elif "Reach:" in text:
                    fighter_data['reach'] = text.replace("Reach:", "").strip()
                elif "STANCE:" in text:
                    fighter_data['stance'] = text.replace("STANCE:", "").strip()
                elif "DOB:" in text:
                    fighter_data['dob'] = text.replace("DOB:", "").strip()

        # Career Statistics (SLpM, Str Acc, SApM, Str Def, TD Avg, TD Acc, TD Def, Sub Avg)
        stats_boxes = soup.find_all('div', class_='b-list__info-box-left')
        for box in stats_boxes:
            stat_items = box.find_all('li')
            for stat in stat_items:
                text = stat.text.strip()
                if ":" in text:
                    key, val = text.split(":", 1)
                    fighter_data[key.strip().lower()] = val.strip()

        # Fight history from the table
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

    def scrape_alphabetical_list(self, char):
        """Get all fighter URLs for a given starting letter."""
        url = f"http://ufcstats.com/statistics/fighters?char={char}&page=all"
        print(f"Scraping fighter list for char: {char}")
        soup = self._get_soup(url)

        fighter_urls = []
        table = soup.find('table', class_='b-statistics__table')
        if table:
            rows = table.find_all('tr', class_='b-statistics__table-row')[1:]  # skip header
            for row in rows:
                cols = row.find_all('td')
                if cols:
                    link = cols[0].find('a')
                    if link and 'href' in link.attrs:
                        fighter_urls.append(link['href'])

        return fighter_urls

    def scrape_all_fighters(self, chars=None, delay_range=(1, 3)):
        """Crawl all fighters alphabetically. chars=None means a-z."""
        if chars is None:
            chars = [chr(c) for c in range(ord('a'), ord('z') + 1)]

        all_fighters = []
        for char in chars:
            urls = self.scrape_alphabetical_list(char)
            all_fighters.extend(urls)
            print(f"  Found {len(urls)} fighters starting with '{char}'")
            time.sleep(random.uniform(*delay_range))

        return all_fighters

    # ===================== FIGHT DETAILS SCRAPING =====================

    def scrape_fight_details(self, fight_url):
        """Scrape detailed fight data including referee, weight class, finish details."""
        print(f"  Scraping fight details: {fight_url}")
        soup = self._get_soup(fight_url)
        if not soup:
            return None

        # Meta info
        title_h2 = soup.find('h2', class_='b-content__title')
        event_name = title_h2.find('a').text.strip() if title_h2 and title_h2.find('a') else ""
        event_url = title_h2.find('a')['href'] if title_h2 and title_h2.find('a') else ""

        date_val = ""
        info_items = soup.find_all('li', class_='b-list__box-list-item')
        for item in info_items:
            if "Date:" in item.text:
                date_val = item.text.replace("Date:", "").strip()
                break

        # If date is empty, try event page
        if not date_val and event_url:
            event_soup = self._get_soup(event_url)
            if event_soup:
                event_info = event_soup.find_all('li', class_='b-list__box-list-item')
                for item in event_info:
                    if "Date:" in item.text:
                        date_val = item.text.replace("Date:", "").strip()
                        break

        fighter_links = soup.find_all('a', class_='b-fight-details__person-link')
        fighters = [f.text.strip() for f in fighter_links][:2]

        fight_details = {
            'url': fight_url,
            'event': event_name,
            'event_url': event_url,
            'date': date_val,
            'fighters': fighters,
            'referee': None,
            'weight_class': None,
            'time_format': None,
            'finish_details': None,
            'rounds': []
        }

        # Extract referee, weight class, time format, finish details
        # Structure: <i class="b-fight-details__text-item"><i class="b-fight-details__label">Referee:</i> <span>Herb Dean</span></i>
        info_items = soup.find_all(['i', 'i'], class_=lambda x: x and ('b-fight-details__text-item' in x or 'b-fight-details__text-item_first' in x))
        for item in info_items:
            label = item.find('i', class_='b-fight-details__label')
            if not label:
                continue
            label_text = label.text.strip()
            
            if label_text == "Referee:":
                span = item.find('span')
                if span:
                    fight_details['referee'] = span.text.strip()
            
            elif label_text == "Time format:":
                full_text = item.text.strip()
                fight_details['time_format'] = full_text.replace("Time format:", "").strip()
            
            elif label_text == "Details:":
                # Get the text after the label (may be in an <i> or <span> sibling)
                siblings = item.find_all(['i', 'span'])
                for sib in siblings:
                    if sib.get('class') != ['b-fight-details__label']:
                        text = sib.text.strip()
                        if text:
                            fight_details['finish_details'] = text
                            break
                # Fallback: get all remaining text
                if not fight_details.get('finish_details'):
                    full_text = item.text.strip()
                    if "Details:" in full_text:
                        fight_details['finish_details'] = full_text.split("Details:")[-1].strip()

        # Parse fight statistics tables
        round_tables = soup.find_all('table', class_='b-fight-details__table')
        if len(round_tables) >= 2:
            totals_table = round_tables[0]
            sig_str_table = round_tables[1]
            fight_details['overall_totals'] = self._parse_fight_table(totals_table)
            fight_details['overall_sig_str'] = self._parse_fight_table(sig_str_table)

            # Per-round tables
            for table in round_tables[2:]:
                subheading = table.find('tr', class_='b-fight-details__table-subheading')
                if subheading and ("Round" in subheading.text or "per round" in subheading.text.lower()):
                    round_data = self._parse_fight_table(table)
                    if round_data:
                        fight_details['rounds'].append(round_data)

        return fight_details

    # ===================== EVENT SCRAPING =====================

    def scrape_event_details(self, event_url):
        """Scrape an event page for location, date, and full fight card."""
        print(f"  Scraping event details: {event_url}")
        soup = self._get_soup(event_url)
        if not soup:
            return None

        event_data = {'url': event_url}

        # Event name
        title_h2 = soup.find('h2', class_='b-content__title')
        if title_h2:
            event_data['name'] = title_h2.text.strip()

        # Date and Location
        info_items = soup.find_all('li', class_='b-list__box-list-item')
        for item in info_items:
            text = item.text.strip()
            if "Date:" in text:
                event_data['date'] = text.replace("Date:", "").strip()
            elif "Location:" in text:
                event_data['location'] = text.replace("Location:", "").strip()

        # Fight card
        fight_table = soup.find('table', class_='b-fight-details__table')
        fights = []
        if fight_table:
            rows = fight_table.find_all('tr')[1:]  # skip header
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 10:
                    result = cols[0].text.strip()

                    # Fighter names in one cell, separated by <br>
                    fighter_cell = cols[1]
                    fighter_names = fighter_cell.get_text(separator='\n').strip().split('\n')
                    fighter_names = [name.strip() for name in fighter_names if name.strip()]
                    f1_name = fighter_names[0] if len(fighter_names) > 0 else ""
                    f2_name = fighter_names[1] if len(fighter_names) > 1 else ""

                    weight_class = cols[6].text.strip()
                    method = cols[7].text.strip()
                    round_val = cols[8].text.strip()
                    time_val = cols[9].text.strip()
                    fight_url = row.get('data-link', '')

                    fights.append({
                        'url': fight_url,
                        'fighter1': f1_name,
                        'fighter2': f2_name,
                        'result': result,
                        'weight_class': weight_class,
                        'method': method,
                        'round': round_val,
                        'time': time_val
                    })

        event_data['fights'] = fights
        return event_data

    def scrape_all_events(self):
        """Scrape the events page to get all event URLs."""
        url = "http://ufcstats.com/statistics/events/completed?page=all"
        print("Scraping all completed events...")
        soup = self._get_soup(url)

        event_urls = []
        table = soup.find('table', class_='b-statistics__table-events')
        if table:
            rows = table.find_all('tr', class_='b-statistics__table-row')
            for row in rows:
                link = row.find('a', class_='b-link')
                if link and 'href' in link.attrs:
                    event_urls.append(link['href'])

        return event_urls

    # ===================== NORMALIZATION =====================

    def normalize_data(self, data):
        """Normalize raw fighter data: units, record parsing, percentages."""
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

        # Record: 22-6-0 (1 NC) -> wins: 22, losses: 6, draws: 0, nc: 1
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
        """Close the requests session."""
        self.session.close()


if __name__ == "__main__":
    scraper = UfcStatsScraper()

    # Test: scrape all events
    print("\n=== SCRAPING ALL EVENTS ===")
    event_urls = scraper.scrape_all_events()
    print(f"\nFound {len(event_urls)} events.")

    # Test: scrape one event
    if event_urls:
        event = scraper.scrape_event_details(event_urls[0])
        print(f"\nEvent: {event.get('name')}")
        print(f"Date: {event.get('date')}")
        print(f"Location: {event.get('location')}")
        print(f"Fights: {len(event.get('fights', []))}")
        if event.get('fights'):
            f = event['fights'][0]
            print(f"  Main event: {f['fighter1']} vs {f['fighter2']} ({f['weight_class']})")

    # Test: scrape one fight with full details
    print("\n=== SCRAPING FIGHT DETAILS ===")
    if event_urls and event.get('fights'):
        fight_url = event['fights'][0]['url']
        if fight_url:
            fight = scraper.scrape_fight_details(fight_url)
            print(f"  Referee: {fight.get('referee')}")
            print(f"  Weight Class: {fight.get('weight_class')}")
            print(f"  Time Format: {fight.get('time_format')}")
            print(f"  Finish: {fight.get('finish_details')}")
