"""Map UFCStats event locations to ISO country codes without runtime geocoding."""

# Countries and territories currently present in the source archive.
COUNTRY_CODES = {
    "Argentina": "ARG",
    "Australia": "AUS",
    "Azerbaijan": "AZE",
    "Brazil": "BRA",
    "Canada": "CAN",
    "Chile": "CHL",
    "China": "CHN",
    "Croatia": "HRV",
    "Czech Republic": "CZE",
    "Denmark": "DNK",
    "France": "FRA",
    "Germany": "DEU",
    "Ireland": "IRL",
    "Japan": "JPN",
    "Mexico": "MEX",
    "Netherlands": "NLD",
    "New Zealand": "NZL",
    "Philippines": "PHL",
    "Poland": "POL",
    "Puerto Rico": "PRI",
    "Qatar": "QAT",
    "Russia": "RUS",
    "Saudi Arabia": "SAU",
    "Serbia": "SRB",
    "Singapore": "SGP",
    "South Korea": "KOR",
    "Sweden": "SWE",
    "United States": "USA",
    "United Arab Emirates": "ARE",
    "United Kingdom": "GBR",
    "Uruguay": "URY",
}
COUNTRY_ALIASES = {
    "USA": "United States",
    "UK": "United Kingdom",
    "England": "United Kingdom",
    "Scotland": "United Kingdom",
    "Wales": "United Kingdom",
    "Northern Ireland": "United Kingdom",
    "UAE": "United Arab Emirates",
    "Czechia": "Czech Republic",
}


def prepare_locations(frame):
    frame = frame.copy()
    frame["country"] = (
        frame["location"]
        .fillna("")
        .str.rsplit(",", n=1)
        .str[-1]
        .str.strip()
        .replace(COUNTRY_ALIASES)
        .replace("", "Unknown")
    )
    frame["iso3"] = frame["country"].map(COUNTRY_CODES)
    return frame


def country_totals(locations):
    """Retain unmapped locations in tables while keeping the map's totals explicit."""
    return (
        locations.groupby(["country", "iso3"], dropna=False)
        .agg(
            events=("events", "sum"),
            total_fights=("total_fights", "sum"),
            locations=("location", "size"),
        )
        .reset_index()
        .sort_values("events", ascending=False)
    )
