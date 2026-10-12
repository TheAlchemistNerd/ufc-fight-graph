import pytest

from domain.normalization import iso_date, normalize_fighter, result_pair, text, weight_class


def test_normalize_fighter_measurements_record_and_percentages():
    raw = {
        "height": "6' 2\"",
        "weight": "170 lbs.",
        "reach": '74"',
        "record": "Record: 22-6-0 (1 NC)",
        "str. acc.": "54%",
        "td def.": "63%",
        "slpm": "2.51",
        "dob": "Aug 25, 1991",
    }
    fighter = normalize_fighter(raw)
    assert [fighter[k] for k in ("height_inches", "weight_lbs", "reach_inches")] == [74, 170, 74]
    assert [fighter[k] for k in ("wins", "losses", "draws", "nc")] == [22, 6, 0, 1]
    assert fighter["str_acc"] == 0.54
    assert fighter["td_def"] == 0.63
    assert fighter["slpm"] == 2.51
    assert fighter["dob"] == "1991-08-25"
    assert "height_inches" not in raw


def test_missing_fighter_data_stays_missing_and_zero_is_preserved():
    fighter = normalize_fighter(
        {
            "height": "--",
            "reach": None,
            "weight": "unknown",
            "record": None,
            "str. acc.": "--",
            "td def.": "invalid",
            "slpm": "0.00",
            "dob": "not a date",
        }
    )
    assert not {"height_inches", "weight_lbs", "reach_inches", "wins"} & fighter.keys()
    assert fighter["str_acc"] is fighter["td_def"] is fighter["dob"] is None
    assert fighter["slpm"] == 0


@pytest.mark.parametrize("value", [None, "", "  -- ", "---", "N/A", "Unknown", "none"])
def test_missing_text(value):
    assert text(value) is None


def test_text_collapses_whitespace_and_preserves_zero():
    assert text(" Keith\n  Peterson ") == "Keith Peterson"
    assert text(0) == "0"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("November 15, 2025", "2025-11-15"),
        ("Nov 15, 2025", "2025-11-15"),
        ("2025-11-15", "2025-11-15"),
        ("February 30, 2025", None),
        ("--", None),
    ],
)
def test_iso_dates(value, expected):
    assert iso_date(value) == expected


@pytest.mark.parametrize(
    "values,expected",
    [
        (["W", "L"], ["win", "loss"]),
        (["L", "W"], ["loss", "win"]),
        (["win"], ["win", "loss"]),
        (["loss"], ["loss", "win"]),
        (["D"], ["draw", "draw"]),
        (["D", "D"], ["draw", "draw"]),
        (["NC"], ["nc", "nc"]),
        (["N/C", "no contest"], ["nc", "nc"]),
        (["--", None], [None, None]),
        ([], [None, None]),
    ],
)
def test_result_pairs(values, expected):
    assert result_pair(values) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("UFC Welterweight Title Bout", "Welterweight"),
        ("UFC Interim Lightweight Title Bout", "Lightweight"),
        ("Women's Strawweight Bout", "Women's Strawweight"),
        ("Open Weight Bout", "Open Weight"),
        ("Welterweight", "Welterweight"),
        (None, None),
    ],
)
def test_weight_class(value, expected):
    assert weight_class(value) == expected
