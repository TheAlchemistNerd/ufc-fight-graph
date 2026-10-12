"""Incremental UFCStats crawl with committed checkpoints and fight enrichment."""

import argparse
import json
import logging
import string
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from config.settings import load_config
from data_access.loader import Neo4jLoader
from infrastructure.checkpoint import Checkpoint
from infrastructure.neo4j_client import Neo4jConnection
from infrastructure.ufcstats import UfcStatsScraper
from run_backfill import backfill
from run_backup import backup
from run_upload import DriveUploader

logger = logging.getLogger(__name__)


def crawl_stage(urls, stage, loader, checkpoint, *, workers=2, delay=1.0, limit=None):
    pending = [u for u in dict.fromkeys(urls) if not checkpoint.contains(stage, u)][:limit]
    local = threading.local()
    sessions = []
    stats = {"loaded": 0, "failed": 0, "skipped": 0}

    def fetch(url):
        if not hasattr(local, "scraper"):
            local.scraper = UfcStatsScraper(delay=delay)
            sessions.append(local.scraper)
        method = (
            local.scraper.scrape_event_details
            if stage == "events"
            else local.scraper.scrape_fighter_profile
        )
        return method(url)

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            tasks = {executor.submit(fetch, url): url for url in pending}
            try:
                for task in as_completed(tasks):
                    url = tasks[task]
                    try:
                        data = task.result()
                        if stage == "events":
                            if not data["fights"]:
                                stats["skipped"] += 1
                                continue
                            loader.create_event(data)
                            for fight in data["fights"]:
                                loader.create_fight(fight)
                        else:
                            loader.create_fighter(data)
                        checkpoint.mark(stage, url)
                        stats["loaded"] += 1
                    except Exception:
                        stats["failed"] += 1
                        logger.exception("Failed %s; retained for retry", url)
                    logger.info("%s: %s", stage, stats)
            except BaseException:
                for task in tasks:
                    task.cancel()
                raise
    finally:
        for scraper in sessions:
            scraper.close()
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--events-only", action="store_true")
    modes.add_argument("--fighters-only", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--delay", type=float, default=1.0, help="Minimum seconds between requests per worker"
    )
    parser.add_argument("--limit", type=int, help="Maximum new events/fighters per stage")
    parser.add_argument("--checkpoint", default="logs/crawl_checkpoint.json")
    parser.add_argument(
        "--reset", action="store_true", help="Rebuild checkpoint and recrawl; preserve graph data"
    )
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--env-file")
    parser.add_argument("--backup-dir", help="Export a portable graph ZIP when the crawl ends")
    parser.add_argument(
        "--upload-drive",
        action="store_true",
        help="Upload the successful crawl's backup directly with rclone",
    )
    parser.add_argument(
        "--skip-details", action="store_true", help="Import summaries; run run_backfill.py later"
    )
    args = parser.parse_args(argv)
    if args.upload_drive and not args.backup_dir:
        parser.error("--upload-drive requires --backup-dir")
    if args.workers < 1 or args.delay < 0 or (args.limit is not None and args.limit < 1):
        parser.error("workers/limit must be positive and delay must be nonnegative")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = load_config(args.env_file)
    uploader = DriveUploader.from_environment() if args.upload_drive else None
    if args.reset and not args.status:
        Path(args.checkpoint).unlink(missing_ok=True)
    checkpoint = Checkpoint(args.checkpoint, config)
    if args.status:
        print(
            json.dumps(
                {stage: len(checkpoint.data[stage]) for stage in ("events", "fighters")}, indent=2
            )
        )
        return 0
    results = {}
    with Neo4jConnection(config) as db, UfcStatsScraper(delay=args.delay) as scraper:
        db.setup_schema()
        loader = Neo4jLoader(db)
        options = dict(workers=args.workers, delay=args.delay, limit=args.limit)
        if not args.fighters_only:
            results["events"] = crawl_stage(
                scraper.scrape_all_events(), "events", loader, checkpoint, **options
            )
            if not args.skip_details:
                loader.repair_local_metadata()
                results["details"] = backfill(
                    loader, scraper, workers=args.workers, delay=args.delay
                )
        if not args.events_only:
            urls = [
                url
                for char in string.ascii_lowercase
                for url in scraper.scrape_alphabetical_list(char)
            ]
            results["fighters"] = crawl_stage(urls, "fighters", loader, checkpoint, **options)
        if args.backup_dir:
            archive = backup(db, args.backup_dir).resolve()
            print(f"Backup: {archive}")
            if uploader and not any(stage["failed"] for stage in results.values()):
                print("Drive upload: " + json.dumps(uploader.upload(archive)))
        print(json.dumps(results, indent=2))
    return 1 if any(stage["failed"] for stage in results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
