"""Source normalization; missing values stay missing."""

import re
from datetime import datetime


def text(value):
    value = " ".join(str(value).split()) if value is not None else ""
    return None if value.lower() in {"", "--", "---", "n/a", "unknown", "none"} else value


def iso_date(value):
    value = text(value)
    if value:
        for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                continue
    return None


def result(value):
    return {
        "w": "win",
        "win": "win",
        "l": "loss",
        "loss": "loss",
        "d": "draw",
        "draw": "draw",
        "nc": "nc",
        "n/c": "nc",
        "no contest": "nc",
    }.get((text(value) or "").lower())


def result_pair(values):
    values = [result(v) for v in values]
    values = [v for v in values if v]
    if len(values) >= 2:
        return values[:2]
    if values:
        return [values[0], {"win": "loss", "loss": "win", "draw": "draw", "nc": "nc"}[values[0]]]
    return [None, None]


def weight_class(value):
    value = text(value)
    if value:
        value = re.sub(r"^(?:UFC\s+)?(?:Interim\s+)?", "", value)
        return re.sub(r"\s+(?:Title\s+)?Bout$", "", value).strip()
    return None


def normalize_fighter(data):
    normalized = dict(data)
    for key in ("height", "weight", "reach"):
        raw = text(data.get(key))
        if not raw:
            continue
        match = (
            re.search(r"(\d+)'\s*(\d+)", raw)
            if key == "height"
            else re.search(r"\d+(?:\.\d+)?", raw)
        )
        if match:
            normalized[
                {"height": "height_inches", "weight": "weight_lbs", "reach": "reach_inches"}[key]
            ] = int(match[1]) * 12 + int(match[2]) if key == "height" else float(match[0])
    match = re.search(r"(\d+)-(\d+)-(\d+)(?:\s*\((\d+)\s*NC\))?", data.get("record") or "")
    if match:
        normalized.update(
            zip(("wins", "losses", "draws", "nc"), (int(v or 0) for v in match.groups()))
        )
    for key, value in data.items():
        canonical = key.lower().replace(".", "").replace(" ", "_")
        if canonical in {
            "slpm",
            "sapm",
            "str_acc",
            "str_def",
            "td_avg",
            "td_acc",
            "td_def",
            "sub_avg",
        }:
            raw = text(value)
            try:
                normalized[canonical] = (
                    float(raw.rstrip("%")) / (100 if raw.endswith("%") else 1) if raw else None
                )
            except ValueError:
                normalized[canonical] = None
    normalized["dob"] = iso_date(data.get("dob"))
    return normalized
