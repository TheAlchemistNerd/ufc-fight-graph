# Data operations

## Native Windows Neo4j

The Windows launcher uses Neo4j Community 5.26.32 with Java 21. The installation
defaults to `$env:LOCALAPPDATA\Programs\Neo4j\neo4j-community-5.26.32`; persistent
configuration, data and logs live under `$env:LOCALAPPDATA\UFCFightGraph\neo4j`.

```powershell
powershell -File tools/start_neo4j.ps1
powershell -File tools/start_neo4j.ps1 -Console
```

Use the first command for a hidden background process, or `-Console` for foreground
logs. `-Neo4jHome` and `-StateRoot` select different installation and state paths.
Set the matching credentials in `.env`; the dashboard and crawler connect to
`bolt://localhost:7687`. Neo4j Browser is at `http://localhost:7474`.

## Fresh import and resume

Start Neo4j, configure `.env`, then run `python run_crawl.py`. Progress is saved in
`logs/crawl_checkpoint.json`. A failed scrape or write is never marked complete.
An event is checkpointed only after all its fight summaries commit. Partial events
are safe to retry because writes use `MERGE`. Detail enrichment resumes from the
graph's version markers independently of event checkpoints.

The older crawler's list-shaped checkpoints could include unprocessed URLs. The
new crawler rejects those files; use `--reset` to rebuild them. Use a separate
checkpoint per database. Following a database rebuild or restore, use `--reset`.

Fighters are keyed by their UFCStats URLs. Older databases using the `fighter_name`
uniqueness constraint need a backup and a fresh database rebuild; name-based nodes
may already combine distinct athletes. The crawler detects that legacy constraint
before writing data.

## Referees and historical repairs

```sh
python run_backfill.py --dry-run
python run_backfill.py --limit 50
python run_backfill.py
python run_backfill.py --refresh
```

Dry runs only read coverage and select eligible fights. Normal backfills first
normalize parseable legacy dates, fill missing fight dates from events, and connect
stored referee names when links are absent. They then fetch version-old fight
pages or unresolved referee assignments. This repairs results, methods, rounds,
times, dates, weight classes, title flags, referees and published judge totals.

An absent referee on a validated page is recorded as unavailable and skipped on
ordinary reruns. `--refresh` checks all fight pages again. HTTP and write failures
retain retry eligibility and produce a nonzero exit code. `--limit` counts selected
fights, including failures. Progress logs report every 25 selected fights.

## Backup and restore

```sh
python run_backup.py --output-dir backups
python run_crawl.py --backup-dir backups
python run_backup.py --env-file restore.env --restore backups/ufc-graph-TIMESTAMP.zip
```

Each portable ZIP contains `graph.json` (nodes, relationships and properties)
and `manifest.json` (counts, format version and SHA-256). Connection credentials
are excluded. Restore supports the seven node labels and six relationship types
in the [project schema](ARCHITECTURE.md#graph-schema).

Upload the ZIP to a Google Drive backup folder as a regular file, preserving its
format. Keep the timestamp in its filename and verify the uploaded file's size.
Create a snapshot after initial recovery and another after the full crawl finishes.
For recovery on another machine, download the ZIP, configure an empty Neo4j
database and run the restore command above. Drive uploads are a separate step;
`run_backup.py` creates a local file.

Export while writes are paused for a stable snapshot. Restoration verifies the
checksum and endpoints, requires an empty database, installs uniqueness constraints
and writes all graph data in one transaction. Format v2 preserves Neo4j temporal
types and existing ISO date strings; legacy v1 archives retain their ISO strings.
Checkpoint files are deliberately
excluded: they describe a particular database's successful crawl history.

For a native Neo4j store backup, stop Community Edition and run
`neo4j-admin database dump neo4j --to-path=BACKUP_DIRECTORY` from the installation's
`bin` directory. Use the same persistent configuration as the running database.
The portable export is also readable without Neo4j.
