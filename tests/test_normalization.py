import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'base'))
from ufc_scraper import UfcScraper

def test_normalize_data():
    scraper = UfcScraper()
    raw_data = {
        'height': "6' 2\"",
        'weight': "170 lbs.",
        'reach': "74\"",
        'record': "Record: 22-6-0 (1 NC)",
        'str. acc.': "54%",
        'td def.': "63%"
    }
    normalized = scraper.normalize_data(raw_data)
    
    assert normalized['height_inches'] == 74
    assert normalized['weight_lbs'] == 170
    assert normalized['reach_inches'] == 74
    assert normalized['wins'] == 22
    assert normalized['losses'] == 6
    assert normalized['draws'] == 0
    assert normalized['nc'] == 1
    assert normalized['str_acc'] == 0.54
    assert normalized['td_def'] == 0.63
