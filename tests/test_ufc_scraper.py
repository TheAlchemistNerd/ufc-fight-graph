import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'base'))
from ufc_scraper import UfcScraper

def test_scrape_fighter_profile_leon_edwards():
    scraper = UfcScraper(use_selenium=False)
    # Using the real URL for a quick integration check, though mocking is preferred for CI
    leon_url = "http://ufcstats.com/fighter-details/f1fac969a1d70b08"
    data = scraper.scrape_fighter_profile(leon_url)
    
    assert data['name'] == "Leon Edwards"
    assert "nickname" in data
    assert len(data['fight_urls']) > 0
    assert len(data['fights']) > 0
    assert 'date' in data['fights'][0]

def test_scrape_fight_details():
    scraper = UfcScraper(use_selenium=False)
    # A specific fight URL
    fight_url = "http://ufcstats.com/fight-details/3c60884853766487"
    details = scraper.scrape_fight_details(fight_url)
    print(f"\nDEBUG Fight Details: {details}")
    
    assert details['event'] != ""
    assert details['date'] != ""
    assert len(details['fighters']) == 2
