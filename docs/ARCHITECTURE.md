# Architecture

| Location | Responsibility |
|---|---|
| `config/settings.py` | Environment and optional `.env` configuration |
| `domain/normalization.py` | Dates, names, results, weight classes and fighter measurements |
| `infrastructure/ufcstats.py` | HTTP sessions, request pacing, page validation and parsing |
| `infrastructure/neo4j_client.py` | Neo4j driver, transactions and uniqueness constraints |
| `infrastructure/checkpoint.py` | Atomic, database-scoped crawl checkpoints |
| `data_access/loader.py` | Graph writes, coverage, backfill selection and local repairs |
| `data_access/repositories.py` | Dashboard read queries |
| `web/` | Streamlit pages and Plotly charts |
| `run_crawl.py`, `run_backfill.py`, `run_backup.py` | Command-line workflows |

The project uses one scraper, one writer and one dashboard. HTTP workers own their
sessions. The coordinator writes data and checkpoints only after a commit. Write
and query failures propagate; the dashboard reports query failures explicitly.

## Graph schema

Unique keys: `Fighter.url`, `Event.name`, `Fight.url`, `WeightClass.name`,
`Referee.name`, `Judge.name`, `Location.name`.

```text
(Fighter)-[:FOUGHT {result}]->(Fight)-[:PART_OF]->(Event)-[:HELD_AT]->(Location)
                               |--[:IN_WEIGHT_CLASS]->(WeightClass)
                               |--[:OFFICIATED_BY]->(Referee)
                               `--[:SCORED_BY {score}]->(Judge)
```

Results are `win`, `loss`, `draw` or `nc`. Missing results stay unset. Dates are ISO
`YYYY-MM-DD`; percentages are fractions and measurements use inches/pounds.
`is_title_fight` comes from the fight page. Referee names retain source spelling
with whitespace normalized. No inferred personal details are added.

`Fight.details_version` and `details_checked_at` record successful enrichment.
`referee_status=unavailable` means a valid fight page did not publish an official.
Sparse updates preserve populated properties. A newly observed referee replaces
stale referee links for that fight.

Fighters use UFCStats URLs as identity, so distinct people with the same name retain
separate profiles and fight histories. Dashboard selectors disambiguate duplicate
names with their source IDs. Events use names as their unique keys and retain URLs
for provenance. A legacy `fighter_name` constraint requires a backup and a fresh
database rebuild before using this schema.
Per-round strike tables, betting odds and gym affiliations are outside the persisted
schema. The dashboard uses fighter career averages and fight-level metadata.
