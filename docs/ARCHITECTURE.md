# Architecture & Module Organization

## Clean Architecture Layers

```
ufc-fight-graph/
├── config/                          # Configuration only - no logic
│   ├── __init__.py
│   └── settings.py                 # Dataclasses: Neo4jConfig, ScraperConfig, DaskConfig
│
├── domain/                          # Pure domain entities - zero dependencies
│   ├── __init__.py
│   └── models.py                   # Fighter, Fight, Event, Scorecard, value objects
│
├── infrastructure/                  # External I/O - depends on domain only
│   ├── __init__.py
│   ├── neo4j_client.py            # Neo4jDriver: connection lifecycle, schema setup
│   └── dask_engine.py             # DaskComputeEngine: delayed tasks, cluster management
│
├── data_access/                     # Data repositories - depends on infra + domain
│   ├── __init__.py
│   └── repositories.py            # OverviewRepo, NetworkCentralityRepo, JudgeRepo
│                                  #   All Neo4j Cypher lives here - zero UI code
│
├── web/                             # UI layer - depends on data_access + charts
│   ├── __init__.py
│   ├── app.py                     # Streamlit pages: thin UI, no Cypher, no logic
│   └── charts.py                  # Pure functions: DataFrame -> Plotly figure
│
├── tests/                           # Test suites
├── base/                            # Legacy code (original scraper, old loader)
└── run_dashboard.py                 # Entry point: python run_dashboard.py
```

## Dependency Rules (Strict)

```
config ← domain ← infrastructure ← data_access ← web
   ↑        ↑           ↑               ↑          ↑
   └────────┴───────────┴───────────────┴──────────┘
           Nothing depends on upper layers
```

| Layer | Can Import | Cannot Import |
|-------|-----------|---------------|
| `config` | Nothing | Everything |
| `domain` | `config` | `infrastructure`, `data_access`, `web` |
| `infrastructure` | `config`, `domain` | `data_access`, `web` |
| `data_access` | `config`, `domain`, `infrastructure` | `web` |
| `web` | Everything above | Nothing (no one depends on it) |

## Bounded Contexts

### 1. Configuration Context
- **Responsibility**: Application settings, credentials, feature flags
- **Boundary**: Pure dataclasses, no behavior
- **Owned by**: DevOps / deployment config

### 2. Domain Context
- **Responsibility**: Business entities, value objects, domain rules
- **Boundary**: No I/O, no frameworks, no external deps
- **Owned by**: Domain experts / data analysts

### 3. Infrastructure Context
- **Responsibility**: External system communication (Neo4j, Dask, HTTP)
- **Boundary**: Connection management, protocol handling
- **Owned by**: Platform engineering

### 4. Data Access Context
- **Responsibility**: Query execution, data mapping, repository pattern
- **Boundary**: All Cypher lives here, returns DataFrames
- **Owned by**: Data engineers

### 5. Web Context
- **Responsibility**: User interface, visualization, interaction
- **Boundary**: Streamlit pages, chart rendering
- **Owned by**: Frontend / data visualization

## Dask Integration

### What Dask Does
- **Heavy computation**: Centrality calculations on 5,000+ fighters
- **Aggregations**: Network density, judge consistency across large datasets
- **ML pipelines**: Feature engineering for fight prediction models

### What Dask Does NOT Do
- Replace GitHub Actions (CI/CD orchestration)
- Replace Cloud Run (HTTP service hosting)
- Replace Neo4j (graph storage and querying)

### When to Use Dask
| Scenario | Use Dask? | Why |
|----------|-----------|-----|
| Querying 100 fighters from Neo4j | No | Single query is fast enough |
| Computing eigenvector centrality on 5,000 fighters | Yes | Multiple passes over large graph |
| Building ML features for 10,000 fights | Yes | Parallel feature engineering |
| Weekly incremental crawl | No | I/O bound, not compute bound |
| Serving dashboard | No | That's Streamlit/Cloud Run |

## GitHub Actions vs Cloud Run vs Dask

| Tool | Purpose | Lifetime | Cost |
|------|---------|----------|------|
| **GitHub Actions** | Scheduled crawls, tests, deployments | Minutes-hours per run | Free 2,000 min/mo |
| **Cloud Run** | Host Streamlit dashboard publicly | Always-on HTTP service | ~$5/mo for light usage |
| **Dask** | Heavy compute on big data | Lives while cluster is up | Cost of machines it runs on |

## Running the Dashboard

```bash
# Local development
python run_dashboard.py

# Opens at http://127.0.0.1:8501
```

## Adding New Features

### New Analytics Page
1. Add Cypher query to appropriate repo in `data_access/repositories.py`
2. Add chart function to `web/charts.py` (if needed)
3. Add page function to `web/app.py`
4. Add to `PAGES` dict and sidebar

### New Repository
1. Create class in `data_access/repositories.py` extending `BaseRepo`
2. Add to `get_repos()` in `web/app.py`

### New Domain Entity
1. Add dataclass to `domain/models.py`
2. No dependencies needed - pure domain logic
