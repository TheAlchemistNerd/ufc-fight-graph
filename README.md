# UFC Stats Scraper & Neo4j Graph Database

A comprehensive scraping and analytics pipeline for UFC fight data. Crawls [ufcstats.com](http://ufcstats.com) for fighters, events, fights, referees, and locations, then loads everything into a Neo4j graph database for deep network analysis.

## Overview

This project builds a knowledge graph of the entire UFC history, enabling queries like:
- **Transitive wins**: Find all fighters who beat someone who beat Fighter X
- **Common opponents**: Discover shared opponents between any two fighters
- **Referee patterns**: Which referees officiate the most title fights?
- **Geographic analysis**: Which cities host the most events?
- **Fighter similarity**: Cluster fighters by striking/grappling profiles

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  UfcStatsScraper    │────>│   Neo4jLoader       │────>│    Neo4j Graph   │
│                     │     │                     │     │                  │
│  - Fighter profiles │     │  - Fighter nodes    │     │  - Fighter       │
│  - Event details    │     │  - Fight nodes      │     │  - Fight         │
│  - Fight stats      │     │  - Event nodes      │     │  - Event         │
│  - Alphabetical     │     │  - WeightClass      │     │  - WeightClass   │
│    crawler          │     │  - Referee          │     │  - Referee       │
│  - Event crawler    │     │  - Location         │     │  - Location      │
└─────────────────────┘     └─────────────────────┘     └──────────────────┘
```

## Project Structure

```
ufc_stats_scrapper/
├── data_access/                  # Data Access Layer (NEW: modular)
│   ├── __init__.py
│   └── repositories.py           # Neo4jClient + 7 domain repositories
│                                 #   OverviewRepo, FighterRepo, RefereeRepo,
│                                 #   GeographyRepo, WeightClassRepo, NetworkRepo,
│                                 #   EvolutionRepo
│
├── visualizations/               # Visualization Layer (NEW: modular)
│   ├── __init__.py
│   └── charts.py                 # Pure Plotly chart generators
│                                 #   horizontal_bar, vertical_bar, grouped_bar,
│                                 #   line_chart, scatter_chart, two_panel_chart
│
├── dashboard/                    # UI Layer (NEW: thin Streamlit app)
│   ├── __init__.py
│   └── app.py                    # Only renders charts from repos + charts modules
│                                 #   Zero Cypher queries, zero data manipulation
│
├── ufc_scraper.py                # Original POC scraper (Leon Edwards proof of concept)
├── ucf_stats_scraper.py          # Full production scraper (fighters, events, fights, referees)
├── neo4j_loader.py               # Neo4j loader with full schema (6 node types, relationships)
├── incremental_crawl.py          # Production incremental crawler with checkpointing
├── analytics.py                  # Standalone analytics query runner (Cypher reference)
├── main.py                       # CLI entry point for running crawls
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container definition for cloud deployment
├── PLAN.md                       # Project plan and task tracking
├── DISTRIBUTION.md               # Distribution strategy, cloud setup, analytics insights
├── README.md                     # This file
└── tests/
    ├── test_ufc_scraper.py       # Integration tests for original scraper
    └── test_normalization.py     # Unit tests for data normalization
```

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│  dashboard/app.py         ← UI: Streamlit pages only        │
│       calls              ↓                                   │
│  data_access/repositories.py  ← Data: Neo4Client + queries   │
│       returns            ↓                                   │
│  visualizations/charts.py     ← Viz: DataFrame -> Plotly     │
│       renders            ↓                                   │
│  Streamlit page                                      │
└─────────────────────────────────────────────────────────────┘
```

Each layer has a single responsibility:
- **data_access/** — All Cypher queries live here. UI code never writes SQL/Cypher.
- **visualizations/** — Pure functions: `DataFrame -> plotly.graph_objects.Figure`. No database, no UI imports.
- **dashboard/** — Thin UI: selects widgets, calls repos, renders charts. No data logic.

## Neo4j Schema

### Nodes

| Label | Key Property | Description |
|-------|-------------|-------------|
| `Fighter` | `name` (unique) | Fighter bio, record, normalized physical stats, career averages |
| `Fight` | `url` (unique) | Individual fight with method, round, time, finish details |
| `Event` | `name` (unique) | UFC event with date and location |
| `WeightClass` | `name` (unique) | Weight division (e.g., "Welterweight", "Lightweight") |
| `Referee` | `name` (unique) | Fight official (e.g., "Herb Dean", "Keith Peterson") |
| `Location` | `name` (unique) | City/venue where events are held |

### Relationships

```
(:Fighter)-[:FOUGHT {result}]->(:Fight)
(:Fight)-[:PART_OF]->(:Event)
(:Fight)-[:IN_WEIGHT_CLASS]->(:WeightClass)
(:Fight)-[:OFFICIATED_BY]->(:Referee)
(:Event)-[:HELD_AT]->(:Location)
```

### Fighter Properties

| Property | Type | Source |
|----------|------|--------|
| `name` | string | Fighter profile header |
| `nickname` | string | Fighter profile |
| `record` | string | e.g., "22-6-0 (1 NC)" |
| `wins`, `losses`, `draws`, `nc` | int | Parsed from record |
| `height`, `weight`, `reach` | string | Raw values |
| `height_inches`, `weight_lbs`, `reach_inches` | int | Normalized |
| `stance` | string | Orthodox, Southpaw, Switch |
| `dob` | string | Date of birth |
| `slpm` | float | Significant landed per minute |
| `str_acc` | float | Striking accuracy (0.0-1.0) |
| `sapm` | float | Significant absorbed per minute |
| `str_def` | float | Striking defense (0.0-1.0) |
| `td_avg` | float | Takedown average |
| `td_acc` | float | Takedown accuracy (0.0-1.0) |
| `td_def` | float | Takedown defense (0.0-1.0) |
| `sub_avg` | float | Submission average |

## Prerequisites

- **Python 3.11+**
- **Docker** (for Neo4j)
- **Internet access** (to scrape ufcstats.com)

## Quick Start

### 1. Start Neo4j

```bash
docker run -d --name ufc-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

Wait ~30 seconds for Neo4j to start. Verify at http://localhost:7474.

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Crawler

```bash
# Full crawl (all events + all fighters + enriched fight sample)
python main.py

# Events only (fast - ~15-30 min)
python main.py --events-only

# Fighters only (~2-4 hours depending on rate limiting)
python main.py --fighters-only

# Test run (5 events, fighters A-B)
python main.py --test

# Custom sample fight enrichment count
python main.py --sample-fights 50
```

### Launch the Dashboard

```bash
streamlit run dashboard/app.py
```

Opens at http://localhost:8501. Seven pages: Overview, Fighter Explorer, Referee Analysis, Geographic Insights, Network Analysis, Weight Class Breakdown, Fighter Evolution.

The dashboard is fully modular: add a repo method in `data_access/repositories.py`, a chart function in `visualizations/charts.py`, and a page function in `dashboard/app.py`.

## Production Incremental Strategy

For ongoing production use, `incremental_crawl.py` ensures daily runs only process **new** data without re-scraping everything:

1. **`MERGE` semantics** — All Neo4j queries use `MERGE` not `CREATE`. Re-running on existing data is a no-op (just updates).
2. **Checkpoint file** (`crawl_checkpoint.json`) — Tracks every processed URL. On re-run, it skips already-seen URLs and only fetches new ones.

```bash
# First run — loads everything, saves checkpoint
python incremental_crawl.py

# Days later — only processes NEW events/fighters since last run
python incremental_crawl.py

# Re-scrape events only (e.g., if stats were updated)
python incremental_crawl.py --reset-events --events-only

# Check progress
python incremental_crawl.py --status
```

This means a production daily run takes **minutes** (just new events that happened), not hours.

## Docker Deployment

Build the container:

```bash
docker build -t ufc-scraper .
```

Run with Neo4j connection:

```bash
docker run --network host ufc-scraper python main.py --events-only
```

For Google Cloud Run, the scraper can be triggered via Cloud Scheduler + Pub/Sub. See `PLAN.md` for scaling strategy.

## Graph Analytics Queries

Once the data is loaded, run these Cypher queries in the Neo4j Browser (http://localhost:7474):

### 1. Fighter Win/Loss Record
```cypher
MATCH (f:Fighter {name: "Leon Edwards"})-[r:FOUGHT]->(fight)
RETURN f.name,
       count(CASE WHEN r.result = "win" THEN 1 END) AS wins,
       count(CASE WHEN r.result <> "win" AND r.result <> "" THEN 1 END) AS losses
```

### 2. Common Opponents Between Two Fighters
```cypher
MATCH (a:Fighter {name: "Leon Edwards"})-[:FOUGHT]->(fight1)<-[:FOUGHT]-(o:Fighter),
      (b:Fighter {name: "Georges St-Pierre"})-[:FOUGHT]->(fight2)<-[:FOUGHT]-(o)
RETURN DISTINCT o.name AS common_opponent
```

### 3. Most Prolific Referees
```cypher
MATCH (ref:Referee)<-[:OFFICIATED_BY]-(fight)
RETURN ref.name, count(fight) AS fights_officiated
ORDER BY fights_officiated DESC
LIMIT 10
```

### 4. Events by Location
```cypher
MATCH (e:Event)-[:HELD_AT]->(loc:Location)
RETURN loc.name, count(e) AS events_held
ORDER BY events_held DESC
LIMIT 10
```

### 5. Weight Class Activity
```cypher
MATCH (fight)-[:IN_WEIGHT_CLASS]->(wc:WeightClass)
RETURN wc.name, count(fight) AS total_fights
ORDER BY total_fights DESC
```

### 6. Transitive Wins (Fighters Who Beat Someone Who Beat X)
```cypher
MATCH (target:Fighter {name: "Leon Edwards"})<-[:FOUGHT]-(fight1)<-[:FOUGHT {result: "win"}]-(beaten_by_me:Fighter),
      (beaten_by_me)-[:FOUGHT {result: "win"}]->(fight2)<-[:FOUGHT]-(i_beat_them:Fighter)
WHERE i_beat_them <> target
RETURN DISTINCT i_beat_them.name, beaten_by_me.name AS via
LIMIT 20
```

### 7. Fighter Network Centrality (PageRank-style)
```cypher
MATCH (f:Fighter)-[r:FOUGHT]->(fight)
WITH f, count(r) AS degree
RETURN f.name, degree
ORDER BY degree DESC
LIMIT 20
```

## Data Sources

All data is scraped from **ufcstats.com**:
- **Fighters**: `/statistics/fighters?char=[a-z]&page=all` (~5,000+ fighters)
- **Events**: `/statistics/events/completed?page=all` (~768 events)
- **Fight details**: Per-fight pages with referee, time format, per-round stats
- **Event details**: Location, date, full fight cards with weight classes

## Rate Limiting & Ethics

The scraper includes:
- Random delays between requests (configurable, default 1-3 seconds)
- Automatic retry logic (3 attempts per URL)
- Session reuse for connection efficiency
- No aggressive parallel scraping (sequential by design)

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_ufc_scraper.py -v
python -m pytest tests/test_normalization.py -v
```

## License

This project is for educational and research purposes. UFCStats.com data belongs to their respective owners.
