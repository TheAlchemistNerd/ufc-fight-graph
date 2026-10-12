"""Pure transformations shared by the fight archive, profiles and officials pages."""

import pandas as pd


def result_group(method):
    method = str(method or "").upper()
    if "KO" in method:
        return "KO / TKO"
    if "SUB" in method:
        return "Submission"
    if "DEC" in method:
        return "Decision"
    return "Other"


def prepare_fights(frame):
    frame = frame.copy()
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["year"] = frame["date"].dt.year
    frame["fighters"] = frame["fighters"].map(
        lambda entries: sorted(
            (entry for entry in entries if entry.get("url")),
            key=lambda entry: entry["url"],
        )
    )
    frame["bout"] = frame["fighters"].map(
        lambda entries: " vs. ".join(entry["name"] or "Unknown fighter" for entry in entries)
    )
    frame["division"] = frame["divisions"].map(lambda values: " / ".join(sorted(set(values))))
    frame["outcome"] = frame["method"].map(result_group)
    frame["winner"] = frame["fighters"].map(
        lambda entries: next(
            (entry["name"] for entry in entries if entry.get("result") == "win"),
            "Draw"
            if any(entry.get("result") == "draw" for entry in entries)
            else "No winner recorded",
        )
    )
    return frame.sort_values(["date", "event", "fight_url"], ascending=[False, True, True])


def filter_fights(frame, *, query="", years=None, divisions=(), outcomes=(), title_only=False):
    if frame.empty:
        return frame.copy()
    mask = pd.Series(True, index=frame.index)
    if query.strip():
        search = frame[["bout", "event", "referee", "location"]].fillna("").agg(" ".join, axis=1)
        mask &= search.str.contains(query.strip(), case=False, regex=False)
    if years:
        mask &= frame["year"].between(*years)
    if divisions:
        mask &= frame["divisions"].map(lambda values: bool(set(values) & set(divisions)))
    if outcomes:
        mask &= frame["outcome"].isin(outcomes)
    if title_only:
        mask &= frame["title_fight"].fillna(False)
    return frame.loc[mask].copy()


def fighter_fights(frame, fighter_url):
    if frame.empty:
        return frame.copy()
    return frame[
        frame["fighters"].map(lambda entries: any(f["url"] == fighter_url for f in entries))
    ]


def fight_table(frame):
    """A flat, readable table for the UI and CSV export; nested data stays in the detail view."""
    columns = {
        "date": "Date",
        "bout": "Matchup",
        "event": "Event",
        "division": "Division",
        "method": "Method",
        "winner": "Winner",
        "round": "Round",
        "time": "Time",
        "referee": "Referee",
        "title_fight": "Title fight",
        "fight_url": "Source",
    }
    result = frame.reindex(columns=columns).rename(columns=columns).copy()
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return result


def csv_bytes(frame):
    # Spreadsheet applications must treat scraped names as text, not formulas.
    safe = frame.map(
        lambda value: (
            "'" + value
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@"))
            else value
        )
    )
    return safe.to_csv(index=False).encode("utf-8-sig")
