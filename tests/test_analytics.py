"""Small regressions for data boundaries, chart types and missing display values."""

from unittest.mock import Mock

import pandas as pd
import pytest

from data_access.repositories import BaseRepo, OverviewRepo
from web.app import fighter_choices, metric_value
from web.charts import horizontal_bar, line_chart, scatter_chart, vertical_bar


def test_database_errors_reach_the_page_error_handler():
    db = Mock()
    db.run_query.side_effect = RuntimeError("Database unavailable")
    with pytest.raises(RuntimeError, match="Database unavailable"):
        BaseRepo(db)._query("MATCH (n) RETURN n")


def test_event_dates_ignore_invalid_entries_and_aggregate_by_year():
    db = Mock()
    db.run_query.return_value = [
        {"date": value} for value in ["2025-01-02", "2025-10-02", "invalid", "2026-01-01"]
    ]
    frame = OverviewRepo(db).get_events_over_time()
    assert frame.to_dict("records") == [{"year": 2025, "events": 2}, {"year": 2026, "events": 1}]


@pytest.mark.parametrize("chart", [horizontal_bar, vertical_bar, line_chart, scatter_chart])
def test_empty_charts_explain_missing_data(chart):
    figure = chart(pd.DataFrame(), "x", "y")
    assert figure.layout.annotations[0].text == "No data available"


def test_categorical_colors_and_numeric_colors_use_the_correct_plotly_scales():
    frame = pd.DataFrame({"x": [1, 2], "y": [2, 3], "method": ["KO/TKO", "SUB"]})
    categories = scatter_chart(frame, "x", "y", color_col="method", color_scale="Set1")
    assert {trace.name for trace in categories.data} == {"KO/TKO", "SUB"}
    numeric = horizontal_bar(frame, "x", "method", "x", color_scale="Blues")
    assert numeric.layout.coloraxis.colorscale


@pytest.mark.parametrize(
    ("value", "suffix", "expected"),
    [
        (0, "", "0"),
        (0, "%", "0%"),
        (None, "%", "N/A"),
        (float("nan"), "", "N/A"),
    ],
)
def test_metrics_preserve_zero_and_hide_missing_values(value, suffix, expected):
    assert metric_value(value, suffix) == expected


def test_fighter_choices_disambiguate_names_and_bind_source_urls():
    repo = Mock()
    repo.get_fighter_options.return_value = [
        {"name": "Bruno Silva", "url": "http://ufcstats.com/fighter-details/first"},
        {"name": "Bruno Silva", "url": "http://ufcstats.com/fighter-details/second"},
    ]
    assert fighter_choices(repo) == {
        "http://ufcstats.com/fighter-details/first": "Bruno Silva (first)",
        "http://ufcstats.com/fighter-details/second": "Bruno Silva (second)",
    }
