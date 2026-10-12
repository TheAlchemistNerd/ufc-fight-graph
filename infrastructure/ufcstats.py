"""Requests-based UFCStats scraper with validated pages and bounded retries."""

import hashlib
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from domain.normalization import iso_date, normalize_fighter, result_pair, text, weight_class


class ScrapeError(RuntimeError):
    pass


def content(node):
    return text(node.get_text(" ", strip=True)) if node else None


class UfcStatsScraper:
    base_url = "http://ufcstats.com"

    def __init__(self, delay=1.0, retries=3):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Mozilla/5.0 (compatible; UFCFightGraph/1.0)"
        self.delay = delay
        self.retries = retries
        self._last_request = 0.0

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _request(self, method, url, **kwargs):
        if urlparse(url).hostname not in {"ufcstats.com", "www.ufcstats.com"}:
            raise ScrapeError(f"Unexpected source host: {url}")
        time.sleep(max(0, self.delay - (time.monotonic() - self._last_request)))
        self._last_request = time.monotonic()
        response = self.session.request(method, url, timeout=30, **kwargs)
        response.raise_for_status()
        return response

    def _verify_browser(self, html):
        # Parse the site's known SHA-256 challenge without executing remote JS.
        nonce = re.search(r'var nonce="([0-9a-f]{1,128})"', html)
        difficulty = re.search(r"target=new Array\((\d+)\+1\)\.join\('0'\)", html)
        if not nonce or not difficulty or not 1 <= int(difficulty[1]) <= 4:
            raise ScrapeError("Unrecognized UFCStats browser verification page")
        target = "0" * int(difficulty[1])
        for n in range(1_000_000):
            if hashlib.sha256(f"{nonce[1]}:{n}".encode()).hexdigest().startswith(target):
                self._request("POST", self.base_url + "/__c", data={"nonce": nonce[1], "n": n})
                return
        raise ScrapeError("UFCStats browser verification exceeded work limit")

    def _get_soup(self, url):
        error = None
        for attempt in range(self.retries):
            try:
                response = self._request("GET", url)
                if "Checking your browser" in response.text:
                    self._verify_browser(response.text)
                    response = self._request("GET", url)
                soup = BeautifulSoup(response.content, "lxml")
                if not soup.select_one(".b-content__title"):
                    raise ScrapeError(f"UFCStats returned an unexpected page for {url}")
                return soup
            except (requests.RequestException, ScrapeError) as exc:
                error = exc
                if attempt + 1 < self.retries:
                    time.sleep(attempt + 1)
        raise ScrapeError(f"Could not scrape {url}: {error}") from error

    def scrape_alphabetical_list(self, char):
        soup = self._get_soup(f"{self.base_url}/statistics/fighters?char={char}&page=all")
        return list(dict.fromkeys(a["href"] for a in soup.select('a[href*="/fighter-details/"]')))

    def scrape_all_events(self):
        soup = self._get_soup(f"{self.base_url}/statistics/events/completed?page=all")
        return list(dict.fromkeys(a["href"] for a in soup.select('a[href*="/event-details/"]')))

    def scrape_fighter_profile(self, url):
        soup = self._get_soup(url)
        data = {
            "url": url,
            "name": content(soup.select_one(".b-content__title-highlight")),
            "record": content(soup.select_one(".b-content__title-record")),
            "nickname": content(soup.select_one(".b-content__Nickname")),
        }
        if not data["name"]:
            raise ScrapeError(f"Fighter name missing: {url}")
        for item in soup.select("li.b-list__box-list-item"):
            value = content(item)
            if value and ":" in value:
                key, value = value.split(":", 1)
                data[key.lower().strip()] = text(value)
        return normalize_fighter(data)

    def scrape_event_details(self, url):
        soup = self._get_soup(url)
        data = {"url": url, "name": content(soup.select_one(".b-content__title")), "fights": []}
        for item in soup.select("li.b-list__box-list-item"):
            value = content(item)
            if value and ":" in value:
                key, value = value.split(":", 1)
                data[key.lower().strip()] = text(value)
        data["date"] = iso_date(data.get("date"))
        for row in soup.select("tr[data-link]"):
            cols = row.find_all("td")
            fighters = row.select('a[href*="/fighter-details/"]')
            if len(cols) < 10 or len(fighters) != 2:
                continue
            outcomes = result_pair([content(p) for p in cols[0].select("p")] or [content(cols[0])])
            if not outcomes[0]:
                continue
            data["fights"].append(
                {
                    "url": row["data-link"],
                    "event": data["name"],
                    "event_url": url,
                    "date": data["date"],
                    "fighters": [content(f) for f in fighters],
                    "fighter_urls": [f["href"] for f in fighters],
                    "f1_result": outcomes[0],
                    "f2_result": outcomes[1],
                    "weight_class": weight_class(content(cols[6])),
                    "method": content(cols[7].find("p") or cols[7]),
                    "round": content(cols[8]),
                    "time": content(cols[9]),
                }
            )
        if not data["name"] or not data["date"]:
            raise ScrapeError(f"Incomplete event metadata: {url}")
        return data

    def scrape_fight_details(self, url, event_date=None):
        soup = self._get_soup(url)
        event = soup.select_one('.b-content__title a[href*="/event-details/"]')
        people = soup.select(".b-fight-details__person")
        if not event or len(people) != 2:
            raise ScrapeError(f"Incomplete fight page: {url}")
        fighters = [p.select_one(".b-fight-details__person-link") for p in people]
        outcomes = result_pair(
            [content(p.select_one(".b-fight-details__person-status")) for p in people]
        )
        if not all(content(f) for f in fighters) or not all(outcomes):
            raise ScrapeError(f"Completed fight participants missing: {url}")
        title_node = soup.select_one(".b-fight-details__fight-title")
        title = content(title_node)
        data = {
            "url": url,
            "event": content(event),
            "event_url": urljoin(url, event["href"]),
            "date": iso_date(event_date),
            "fighters": [content(f) for f in fighters],
            "fighter_urls": [f.get("href") for f in fighters],
            "f1_result": outcomes[0],
            "f2_result": outcomes[1],
            "weight_class": weight_class(title),
            "judges": [],
        }
        if title:
            data["is_title_fight"] = "title" in title.lower() or bool(
                title_node.select('img[src*="belt.png"]')
            )
        labels = {
            "Method": "method",
            "Round": "round",
            "Time": "time",
            "Time format": "time_format",
            "Referee": "referee",
        }
        for label in soup.select(".b-fight-details__label"):
            key = (content(label) or "").rstrip(":")
            if key in labels:
                value = content(label.parent)
                data[labels[key]] = text(value.split(":", 1)[-1])
            elif key == "Details":
                detail = content(label.find_parent("p"))
                data["finish_details"] = text(detail.split(":", 1)[-1]) if detail else None
        for item in soup.select(".b-fight-details__text-item"):
            if item.select_one(".b-fight-details__label"):
                continue
            name = content(item.find("span"))
            score = re.search(r"(\d+)\s*-\s*(\d+)", content(item) or "")
            if name and score:
                data["judges"].append({"name": name, "score": f"{score[1]} - {score[2]}"})
        if not data.get("method") or not data.get("round") or not data.get("time"):
            raise ScrapeError(f"Fight result metadata missing: {url}")
        if not data["date"]:
            data["date"] = self.scrape_event_details(data["event_url"])["date"]
        return data
