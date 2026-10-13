"""User-facing archive filters, exports and empty database behavior."""

from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from web.catalogue import csv_bytes, fight_table, fighter_fights, filter_fights, prepare_fights
from web.charts import opponent_graph


@pytest.fixture
def fights():
    def bout(url, date, method, title=False):
        return {
            "fight_url": url,
            "date": date,
            "event": "UFC Test",
            "event_url": None,
            "location": "London",
            "method": method,
            "round": "3",
            "time": "5:00",
            "time_format": None,
            "finish_details": None,
            "title_fight": title,
            "fighters": [
                {"name": "Same Name", "url": "first", "result": "win"},
                {"name": "Same Name", "url": "second", "result": "loss"},
            ],
            "divisions": ["Lightweight", "Tournament"],
            "referee": "A. Referee",
            "judges": [],
        }

    return prepare_fights(
        pd.DataFrame(
            [
                bout("a", "2024-01-01", "KO/TKO"),
                bout("b", "2025-01-01", "Decision - Unanimous", True),
                bout("c", None, None),
            ]
        )
    )


def test_filters_combine_and_search_is_literal(fights):
    filtered = filter_fights(
        fights,
        query="a. referee",
        years=(2025, 2025),
        divisions=["Lightweight"],
        outcomes=["Decision"],
        title_only=True,
    )
    assert filtered.fight_url.tolist() == ["b"]
    assert filter_fights(fights, query=".*").empty
    assert len(filter_fights(fights)) == 3  # Unknown dates remain visible with no date filter.
    assert filter_fights(fights, years=(2024, 2024)).fight_url.tolist() == ["a"]


def test_fighter_identity_and_export_rows_are_preserved(fights):
    assert len(fighter_fights(fights, "first")) == 3
    assert fighter_fights(fights, "missing").empty
    table = fight_table(fights)
    assert len(table) == 3 and table.Source.nunique() == 3
    assert table.iloc[0]["Date"] == "2025-01-01"
    assert table.iloc[0]["Matchup"] == "Same Name vs. Same Name"


def test_csv_exports_escape_spreadsheet_formulas_and_preserve_numbers():
    content = csv_bytes(
        pd.DataFrame({"Name": ["=SUM(1)", " @test", "Normal"], "Fights": [0, 2, 3]})
    ).decode("utf-8-sig")
    assert "'=SUM(1),0" in content and "' @test,2" in content
    assert "Normal,3" in content


def test_opponent_network_uses_urls_and_counts_rematches(fights):
    figure = opponent_graph(fights, "first", "Same Name")
    assert list(figure.data[1].customdata) == [3]
    assert list(figure.data[1].text) == ["Same Name"]


@pytest.mark.parametrize(
    "page",
    [
        "Overview",
        "Fight archive",
        "Fighter explorer",
        "Tale of the tape",
        "Referee desk",
        "Judge scorecards",
        "Geographic insights",
    ],
)
def test_new_pages_explain_empty_graph(monkeypatch, page):
    from web.app import NAVIGATION

    db = SimpleNamespace(test_connection=lambda: (True, 0), run_query=Mock(return_value=[]))
    monkeypatch.setattr("web.app.get_connection", lambda: db)
    app = AppTest.from_string("from web.app import main\nmain()", default_timeout=20).run()
    section = next(section for section, pages in NAVIGATION.items() if page in pages)
    app.sidebar.selectbox[0].set_value(section).run()
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception and not app.error
    assert app.info


def test_country_map_aggregates_aliases_and_retains_unmapped_locations():
    from web.charts import event_map
    from web.geography import country_totals, prepare_locations

    locations = prepare_locations(
        pd.DataFrame(
            [
                {"location": "Las Vegas, Nevada, USA", "events": 3, "total_fights": 30},
                {"location": "New York, United States", "events": 2, "total_fights": 20},
                {"location": "London, England", "events": 1, "total_fights": 12},
                {"location": "Unknown city", "events": 1, "total_fights": 9},
            ]
        )
    )
    totals = country_totals(locations)
    assert totals.events.sum() == 7
    usa = totals.set_index("iso3").loc["USA"]
    assert (usa.events, usa.total_fights, usa.locations) == (5, 50, 2)
    figure = event_map(totals, "total_fights")
    assert dict(zip(figure.data[0].locations, figure.data[0].z)) == {"USA": 50, "GBR": 12}
    assert totals[totals.iso3.isna()].events.sum() == 1


def test_geography_country_filter_keeps_all_locations_in_table(monkeypatch):
    from data_access.repositories import GeographyRepo

    locations = pd.DataFrame(
        [{"location": f"City {i}, USA", "events": 1, "total_fights": 10} for i in range(18)]
        + [{"location": "London, United Kingdom", "events": 2, "total_fights": 24}]
    )
    monkeypatch.setattr(GeographyRepo, "get_events_by_location", lambda _: locations)
    monkeypatch.setattr(
        GeographyRepo,
        "get_fight_outcomes_by_location",
        lambda _: pd.DataFrame(
            [
                {
                    "location": "London, United Kingdom",
                    "result": "Decision - Unanimous",
                    "count": 24,
                },
                {"location": "City 0, USA", "result": "KO/TKO", "count": 10},
            ]
        ),
    )
    app = AppTest.from_string(
        "from web.app import page_geographic\n"
        "from data_access.repositories import GeographyRepo\n"
        "page_geographic({'geography': GeographyRepo(None)})"
    ).run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 19
    app.selectbox[0].set_value("United Kingdom").run()
    assert app.dataframe[0].value["Events"].tolist() == [2]
    assert app.dataframe[0].value["Fights"].tolist() == [24]
    app.radio[0].set_value("Fights").run()
    assert not app.exception
