# CI and container setup

- **Tests:** offline parser/checkpoint tests plus Neo4j integration tests on Python
  3.11–3.13, with a fresh Neo4j 5.26 service for each job.
- **Lint:** Ruff import/error checks and formatting; failures block the workflow.
- **Build Dashboard Image:** builds the Streamlit image and checks imports on
  relevant pull requests, main-branch pushes and manual runs. Pushes and manual
  runs publish to `ghcr.io/OWNER/REPOSITORY/ufc-dashboard:latest` (lowercase path).
  Hosting the dashboard requires running that image.
- **Incremental UFC Crawl:** Sunday 03:00 UTC and manual runs; uses Aura, keeps a cache
  fallback, syncs its database-scoped checkpoint to Google Drive, uploads a verified
  ZIP after successful crawls, and retains the ZIP plus upload receipt as a 30-day artifact.

Set repository secrets `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASS` and optional
`NEO4J_DATABASE` for the crawler. The database must be reachable from the runner.
A Windows localhost installation is reachable by a local run, not GitHub-hosted
runners. The workflow requires configured credentials rather than importing data
into an ephemeral container that disappears after the job.

To enable Drive sync, add the complete rclone configuration file as the repository
Actions secret `RCLONE_CONFIG_CONTENT`. Its remote section must be named
`[ufc-backups]`. Add the Drive destination folder ID as the repository Actions
variable `UFC_DRIVE_FOLDER_ID`. The workflow writes the secret to a temporary file
with owner-only permissions, restores the checkpoint for the configured Aura
database from `crawl-state/`, and uploads checkpoint progress after each run,
including runs that fail after saving work. A successful crawl also exports a
checksum-validated graph ZIP to the Drive folder; the artifact remains available
as a second copy. If Drive settings are absent, the crawler continues with its
Actions cache and artifact behavior.

Manual crawl modes: `incremental`, `events-only`, `fighters-only`, `backfill`,
`full-reset`. A reset refreshes records/checkpoints and preserves the existing graph.

For local integration tests, create a disposable Neo4j instance on a separate port
and set `TEST_NEO4J_URI`, `TEST_NEO4J_USER` (default `neo4j`) and `TEST_NEO4J_PASS`.
The integration suite requires an empty database and owns its fixture data.

```powershell
$env:TEST_NEO4J_URI = 'bolt://localhost:17687'
$env:TEST_NEO4J_PASS = 'test-password'
python -m pytest -m integration
```

Container run: `docker run --env-file .env -p 8501:8501 IMAGE`. Use a database address
reachable from the container (for example `bolt://host.docker.internal:7687` on
Docker Desktop), rather than the container's own localhost.
