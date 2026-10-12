# Code and history audit

Reviewed the two commits preceding this cleanup: `9f0862c` (initial import) and
`518bd76` (architecture refactor). The latter added a new dashboard and crawler
while retaining their predecessors. Commit descriptions alone overstated the
degree of consolidation and the analytics implemented.

| Evidence in the prior revision | Cleanup |
|---|---|
| `parallel_scraper.py` and `tools/parallel_scraper.py` have identical Git blobs; `run_parallel_crawl.py` adds another crawl path. | One `run_crawl.py` coordinates the shared scraper and graph writer. |
| Both `dashboard/app.py` and `web/app.py` implement the dashboard, with separate chart modules. | Retain `web/` and the `run_dashboard.py` entry point. |
| No application module imports `domain/models.py` or `infrastructure/dask_engine.py`; Dask is absent from requirements. | Remove unused abstractions and retain normalization used by ingestion. |
| The multiprocessing crawler checkpoints `set(unique_urls)` before all work finishes and catches batch-write failures. | Checkpoint individual committed records; surface failures and retry unfinished work. |
| Fighter nodes are merged by name, combining distinct athletes who share a name. | Use UFCStats URLs as identity and disambiguate dashboard selections. |
| Its event path writes a null fight date and only one participant's result, and skips fight-detail pages. The old detail scraper already had referee extraction. | Enrich every eligible fight with both outcomes, date, title status, referee and published judge totals; expose a resumable backfill. |
| Container startup points to a missing root `main.py` and installs Chrome for an HTTP-based application. | Build only runtime modules and start the Streamlit entry point. |
| Scheduled CI can create and discard a temporary Neo4j database; its CSV exports omit graph relationships and officials. | Require a persistent target and export the project graph in a restorable ZIP. |
| Most lint steps use `continue-on-error`; parser tests call the live website and analytics tests supply mocked result tables. | Enforce Ruff; test parsing offline and graph writes/queries against a disposable Neo4j instance. |
| Documentation includes overlapping plans, pricing estimates, marketing copy and unimplemented research claims; diagnostic text files are committed. | Keep setup, schema, recovery, CI and metric definitions; remove obsolete documents and diagnostic litter. |

The retained application is an HTTP scraper, Neo4j graph and Streamlit dashboard.
Network influence and bridge rankings use documented heuristics. The current
schema stores fight metadata and fighter career averages; it does not store
per-round statistics or betting odds. See [metric definitions](NETWORK_RESEARCH.md)
and [architecture](ARCHITECTURE.md).

## Verification

Run the commands in the [README](../README.md#development) for offline tests and
lint. [Integration tests](CI_CD_SETUP.md) exercise the database separately. A fresh
import should be checked with `python run_backfill.py --dry-run`; its coverage
counts distinguish recorded referees, source-unavailable officials and detail
pages already checked. Validate backup restoration in a separate empty database
before relying on a recovery copy.

The old implementation and removed research material remain available through
`git show 518bd76:PATH`; there is no separate archive of duplicate source files.
