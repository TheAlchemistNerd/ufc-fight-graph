"""Backfill fight officials and result metadata from existing fight URLs."""

import argparse
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.settings import load_config
from data_access.loader import Neo4jLoader
from infrastructure.neo4j_client import Neo4jConnection
from infrastructure.ufcstats import UfcStatsScraper

logger = logging.getLogger(__name__)


def backfill(loader, scraper, *, limit=None, refresh=False, dry_run=False, workers=1, delay=1.0):
    if workers < 1 or delay < 0:
        raise ValueError("workers must be positive and delay must be nonnegative")
    stats = {"selected": 0, "updated": 0, "missing_referee": 0, "failed": 0}
    after = ""
    local = threading.local()
    sessions = []

    def fetch(row):
        if workers == 1:
            worker_scraper = scraper
        else:
            if not hasattr(local, "scraper"):
                local.scraper = UfcStatsScraper(delay=delay)
                sessions.append(local.scraper)
            worker_scraper = local.scraper
        return worker_scraper.scrape_fight_details(row["url"], event_date=row["date"])

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            while limit is None or stats["selected"] < limit:
                batch_size = min(100, limit - stats["selected"]) if limit is not None else 100
                rows = loader.backfill_candidates(after, batch_size, refresh)
                if not rows:
                    break
                # Completion order can differ from URL order; advance only after the batch.
                after = rows[-1]["url"]
                if dry_run:
                    stats["selected"] += len(rows)
                    continue
                tasks = {executor.submit(fetch, row): row for row in rows}
                try:
                    for task in as_completed(tasks):
                        row = tasks[task]
                        stats["selected"] += 1
                        try:
                            data = task.result()
                            # Commit on this thread before recording success. A failed write
                            # never marks the fight checked, so restarting retries it.
                            loader.create_fight(data, enriched=True)
                            stats["updated"] += 1
                            stats["missing_referee"] += not bool(data.get("referee"))
                        except Exception:
                            stats["failed"] += 1
                            logger.exception(
                                "Backfill failed for %s; it remains eligible for retry", row["url"]
                            )
                        if stats["selected"] % 25 == 0:
                            logger.info("Backfill progress: %s", stats)
                except BaseException:
                    for task in tasks:
                        task.cancel()
                    raise
    finally:
        for session in sessions:
            session.close()
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file")
    parser.add_argument(
        "--limit", type=int, help="Maximum fights; omitted means all eligible fights"
    )
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--refresh", action="store_true", help="Recheck even previously enriched fights"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report coverage and candidate count without HTTP or writes",
    )
    args = parser.parse_args(argv)
    if args.workers < 1 or args.delay < 0 or (args.limit is not None and args.limit < 1):
        parser.error("workers/limit must be positive and delay must be nonnegative")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    with (
        Neo4jConnection(load_config(args.env_file)) as db,
        UfcStatsScraper(delay=args.delay) as scraper,
    ):
        loader = Neo4jLoader(db)
        before = loader.coverage()
        if not args.dry_run:
            db.setup_schema()
            loader.repair_local_metadata()
        stats = backfill(
            loader,
            scraper,
            limit=args.limit,
            refresh=args.refresh,
            dry_run=args.dry_run,
            workers=args.workers,
            delay=args.delay,
        )
        print(
            json.dumps({"before": before, "backfill": stats, "after": loader.coverage()}, indent=2)
        )
        return 1 if stats["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
