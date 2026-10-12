"""Offline regressions for UFCStats source layouts and request failures."""

from pathlib import Path
from unittest.mock import Mock

import pytest
import requests
from bs4 import BeautifulSoup

from infrastructure.ufcstats import ScrapeError, UfcStatsScraper

FIGHT_URL = "http://ufcstats.com/fight-details/3c60884853766487"
EVENT_URL = "http://ufcstats.com/event-details/8db1b36dde268ef6"


@pytest.fixture
def scraper(monkeypatch):
    with UfcStatsScraper(delay=0, retries=3) as client:
        monkeypatch.setattr(
            client.session, "request", Mock(side_effect=AssertionError("Unexpected HTTP"))
        )
        monkeypatch.setattr("infrastructure.ufcstats.time.sleep", Mock())
        yield client


@pytest.fixture
def fight_page():
    path = Path(__file__).with_name("fixtures") / "fight.html"
    return BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")


@pytest.mark.parametrize("layout", ["nested", "plain", "missing", "absent"])
def test_fight_referee_source_layouts(scraper, fight_page, monkeypatch, layout):
    label = next(
        n
        for n in fight_page.select(".b-fight-details__label")
        if n.get_text(strip=True) == "Referee:"
    )
    if layout == "absent":
        label.parent.decompose()
    elif layout != "nested":
        label.parent.find("span").replace_with("Keith Peterson" if layout == "plain" else "--")
    monkeypatch.setattr(scraper, "_get_soup", Mock(return_value=fight_page))
    fight = scraper.scrape_fight_details(FIGHT_URL, event_date="November 15, 2025")
    assert fight.get("referee") == ("Keith Peterson" if layout in {"nested", "plain"} else None)
    assert fight["fighters"] == ["Leon Edwards", "Carlos Prates"]
    assert (fight["f1_result"], fight["f2_result"]) == ("loss", "win")
    assert fight["event_url"] == EVENT_URL
    assert fight["date"] == "2025-11-15"
    assert (fight["method"], fight["round"], fight["time"]) == ("KO/TKO", "2", "1:28")
    assert fight["weight_class"] == "Welterweight"
    assert fight["is_title_fight"] is False


@pytest.mark.parametrize("status,expected", [("D", "draw"), ("NC", "nc")])
def test_fight_draw_and_no_contest(scraper, fight_page, monkeypatch, status, expected):
    for node in fight_page.select(".b-fight-details__person-status"):
        node.string = status
    monkeypatch.setattr(scraper, "_get_soup", Mock(return_value=fight_page))
    fight = scraper.scrape_fight_details(FIGHT_URL, event_date="2025-11-15")
    assert [fight["f1_result"], fight["f2_result"]] == [expected, expected]


def test_fight_missing_date_uses_event_page(scraper, fight_page, monkeypatch):
    monkeypatch.setattr(scraper, "_get_soup", Mock(return_value=fight_page))
    event = Mock(return_value={"date": "2025-11-15"})
    monkeypatch.setattr(scraper, "scrape_event_details", event)
    assert scraper.scrape_fight_details(FIGHT_URL)["date"] == "2025-11-15"
    event.assert_called_once_with(EVENT_URL)


@pytest.mark.parametrize(
    "selector", [".b-fight-details__person", ".b-fight-details__text-item_first"]
)
def test_incomplete_fight_is_rejected(scraper, fight_page, monkeypatch, selector):
    fight_page.select_one(selector).decompose()
    monkeypatch.setattr(scraper, "_get_soup", Mock(return_value=fight_page))
    with pytest.raises(ScrapeError):
        scraper.scrape_fight_details(FIGHT_URL, event_date="2025-11-15")


@pytest.mark.parametrize(
    "status,expected",
    [
        ("win", ["win", "loss"]),
        ("draw", ["draw", "draw"]),
        ("nc", ["nc", "nc"]),
    ],
)
def test_event_rows_supply_results_and_fight_metadata(scraper, monkeypatch, status, expected):
    page = BeautifulSoup(
        f"""
        <h2 class="b-content__title">UFC Test</h2>
        <li class="b-list__box-list-item"><i>Date:</i> November 15, 2025</li>
        <li class="b-list__box-list-item"><i>Location:</i> New York, New York, USA</li>
        <table><tr data-link="{FIGHT_URL}">
          <td><p>{status}</p></td>
          <td><p><a href="http://ufcstats.com/fighter-details/a">Fighter A</a></p>
              <p><a href="http://ufcstats.com/fighter-details/b">Fighter B</a></p></td>
          <td>0</td><td>0</td><td>0</td><td>0</td>
          <td>UFC Welterweight Title Bout</td><td><p>KO/TKO</p><p>Punch</p></td>
          <td><p>2</p></td><td><p>1:28</p></td>
        </tr></table>""",
        "lxml",
    )
    monkeypatch.setattr(scraper, "_get_soup", Mock(return_value=page))
    event = scraper.scrape_event_details(EVENT_URL)
    (fight,) = event["fights"]
    assert event["date"] == fight["date"] == "2025-11-15"
    assert event["location"] == "New York, New York, USA"
    assert fight["url"] == FIGHT_URL
    assert [fight["f1_result"], fight["f2_result"]] == expected
    assert fight["weight_class"] == "Welterweight"
    assert fight["method"] == "KO/TKO"


def test_fighter_profile_normalizes_source_statistics(scraper, monkeypatch):
    page = BeautifulSoup(
        """
        <h2 class="b-content__title"><span class="b-content__title-highlight">Leon Edwards</span>
        <span class="b-content__title-record">Record: 22-6-0 (1 NC)</span></h2>
        <p class="b-content__Nickname">Rocky</p>
        <li class="b-list__box-list-item"><i>HEIGHT:</i> 6' 2"</li>
        <li class="b-list__box-list-item"><i>DOB:</i> Aug 25, 1991</li>
        <li class="b-list__box-list-item"><i>Str. Acc.:</i> 54%</li>
        <li class="b-list__box-list-item"><i>REACH:</i> --</li>""",
        "lxml",
    )
    monkeypatch.setattr(scraper, "_get_soup", Mock(return_value=page))
    fighter = scraper.scrape_fighter_profile("http://ufcstats.com/fighter-details/a")
    assert fighter["name"] == "Leon Edwards"
    assert fighter["nickname"] == "Rocky"
    assert fighter["height_inches"] == 74
    assert fighter["dob"] == "1991-08-25"
    assert fighter["str_acc"] == 0.54
    assert fighter["nc"] == 1
    assert "reach_inches" not in fighter


def response(html):
    result = requests.Response()
    result.status_code = 200
    result._content = html.encode()
    return result


def test_transient_request_error_is_retried(scraper):
    scraper.session.request.side_effect = [
        requests.Timeout("temporary failure"),
        response('<h2 class="b-content__title">UFC Test</h2>'),
    ]
    assert scraper._get_soup(EVENT_URL).select_one(".b-content__title").get_text() == "UFC Test"
    assert scraper.session.request.call_count == 2


def test_unexpected_page_exhausts_retries(scraper):
    scraper.session.request.side_effect = None
    scraper.session.request.return_value = response("<html>Service temporarily unavailable</html>")
    with pytest.raises(ScrapeError, match="unexpected page"):
        scraper._get_soup(EVENT_URL)
    assert scraper.session.request.call_count == 3


def test_foreign_source_host_is_rejected_before_http(scraper):
    with pytest.raises(ScrapeError, match="Unexpected source host"):
        scraper._get_soup("https://example.com/fight-details/a")
    scraper.session.request.assert_not_called()
