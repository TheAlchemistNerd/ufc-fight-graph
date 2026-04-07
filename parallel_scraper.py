"""
Parallel UFC Stats Crawler — Multiprocessing pipeline simulating Cloud Run workers.

Each worker process:
  1. Pulls a batch of fighter URLs from the shared queue
  2. Scrapes the fighter profile with rate limiting
  3. Normalizes and writes to Neo4j via MERGE
  4. Updates a shared progress counter

This mirrors Cloud Run's parallel worker pattern where each instance
pulls from a Pub/Sub task queue independently.

Usage:
    python parallel_scraper.py                  # Full parallel crawl
    python parallel_scraper.py --workers 20     # Use 20 parallel workers
    python parallel_scraper.py --fighters-only  # Skip events
    python parallel_scraper.py --events-only    # Skip fighters
    python parallel_scraper.py --batch-size 50  # URLs per worker batch
"""

import sys
import os
import time
import random
import json
import argparse
from multiprocessing import Process, Queue, Manager, Value
from datetime import datetime

# Add parent and base dirs to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "base"))

from ucf_stats_scraper import UfcStatsScraper
from neo4j_loader import Neo4jLoader


# ===================== CONFIGURATION =====================

DEFAULT_WORKERS = 10
DEFAULT_BATCH_SIZE = 30
DEFAULT_DELAY = 1.0  # seconds between requests per worker

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "password"

PROGRESS_FILE = "parallel_progress.json"


# ===================== WORKER FUNCTION =====================

def fighter_worker(worker_id, url_queue, progress_dict, stop_event, batch_size, delay):
    """
    Worker process: pulls fighter URLs from queue, scrapes, normalizes, loads to Neo4j.
    Mirrors a Cloud Run instance pulling from Pub/Sub.
    """
    scraper = UfcStatsScraper()
    loader = Neo4jLoader(NEO4J_URI, NEO4J_USER, NEO4J_PASS)

    loaded = 0
    failed = 0

    while not url_queue.empty():
        batch = []
        for _ in range(min(batch_size, url_queue.qsize())):
            try:
                url = url_queue.get_nowait()
                batch.append(url)
            except Exception:
                break

        for url in batch:
            try:
                fighter = scraper.scrape_fighter_profile(url)
                if fighter and fighter.get("name"):
                    normalized = scraper.normalize_data(fighter)
                    loader.create_fighter(normalized)
                    loaded += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"  Worker {worker_id} FAILED {url.split('/')[-1]}: {e}")
                failed += 1

            # Update shared progress
            progress_dict["loaded"] = progress_dict.get("loaded", 0) + (1 if fighter and fighter.get("name") else 0)
            progress_dict["failed"] = progress_dict.get("failed", 0) + (0 if fighter and fighter.get("name") else 1)
            progress_dict["last_update"] = datetime.now().isoformat()

            # Rate limiting per worker
            time.sleep(random.uniform(delay * 0.5, delay * 1.5))

    print(f"  Worker {worker_id} done: {loaded} loaded, {failed} failed")
    scraper.close()
    loader.close()


def event_worker(worker_id, event_urls, progress_dict, delay):
    """Worker process for event crawling."""
    scraper = UfcStatsScraper()
    loader = Neo4jLoader(NEO4J_URI, NEO4J_USER, NEO4J_PASS)

    loaded = 0
    for i, url in enumerate(event_urls):
        try:
            event = scraper.scrape_event_details(url)
            if event and event.get("name"):
                loader.create_event(event)
                event_name = event.get("name")
                for fight in event.get("fights", []):
                    if fight.get("fighter1"):
                        loader.create_fight_from_event(fight["fighter1"], fight, event_name)
                    if fight.get("fighter2"):
                        loader.create_fight_from_event(fight["fighter2"], fight, event_name)
                loaded += 1
        except Exception as e:
            print(f"  Event worker FAILED {url}: {e}")

        progress_dict["events_loaded"] = loaded
        progress_dict["last_update"] = datetime.now().isoformat()
        time.sleep(random.uniform(delay * 0.5, delay * 1.5))

    print(f"  Event worker done: {loaded} events loaded")
    scraper.close()
    loader.close()


# ===================== MAIN ORCHESTRATOR =====================

def save_progress(progress_dict):
    """Save progress to JSON file."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(dict(progress_dict), f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Parallel UFC Stats Crawler")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help=f"Number of parallel workers (default {DEFAULT_WORKERS})")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help=f"URLs per worker batch (default {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help=f"Base delay between requests (default {DEFAULT_DELAY}s)")
    parser.add_argument("--events-only", action="store_true", help="Only crawl events")
    parser.add_argument("--fighters-only", action="store_true", help="Only crawl fighters")
    parser.add_argument("--reset", action="store_true", help="Reset progress and re-crawl")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  PARALLEL UFC STATS CRAWLER")
    print(f"  Workers: {args.workers} | Batch size: {args.batch_size} | Delay: {args.delay}s")
    print(f"{'='*60}\n")

    # Initialize scraper to discover URLs
    scraper = UfcStatsScraper()
    loader = Neo4jLoader(NEO4J_URI, NEO4J_USER, NEO4J_PASS)
    loader.setup_schema()

    # Shared state (multiprocessing-safe)
    manager = Manager()
    url_queue = Queue()
    progress_dict = manager.dict({
        "loaded": 0,
        "failed": 0,
        "events_loaded": 0,
        "started": datetime.now().isoformat(),
        "last_update": None,
    })

    # ---- Phase 1: Events ----
    if not args.fighters_only:
        print("\n[Phase 1] Discovering events...")
        event_urls = scraper.scrape_all_events()
        print(f"  Found {len(event_urls)} events")

        # Load events sequentially (not enough to parallelize meaningfully)
        print("\n[Phase 1] Crawling events...")
        for i, url in enumerate(event_urls):
            try:
                event = scraper.scrape_event_details(url)
                if event and event.get("name"):
                    loader.create_event(event)
                    event_name = event.get("name")
                    for fight in event.get("fights", []):
                        if fight.get("fighter1"):
                            loader.create_fight_from_event(fight["fighter1"], fight, event_name)
                        if fight.get("fighter2"):
                            loader.create_fight_from_event(fight["fighter2"], fight, event_name)
                    progress_dict["events_loaded"] = i + 1
            except Exception as e:
                print(f"  Event FAILED {url}: {e}")
            progress_dict["last_update"] = datetime.now().isoformat()
            time.sleep(random.uniform(args.delay * 0.5, args.delay * 1.5))
        print(f"\n  [OK] Loaded {progress_dict.get('events_loaded', 0)} events")

    # ---- Phase 2: Fighters (Parallel) ----
    if not args.events_only:
        print(f"\n[Phase 2] Discovering fighters (a-z)...")
        all_fighter_urls = []
        chars = [chr(c) for c in range(ord("a"), ord("z") + 1)]
        for char in chars:
            urls = scraper.scrape_alphabetical_list(char)
            all_fighter_urls.extend(urls)
            time.sleep(random.uniform(0.3, 0.8))
        print(f"  Found {len(all_fighter_urls)} fighters total")

        # Deduplicate
        unique_urls = list(dict.fromkeys(all_fighter_urls))
        print(f"  Unique fighters: {len(unique_urls)}")

        # Fill queue
        for url in unique_urls:
            url_queue.put(url)

        # Launch parallel workers
        print(f"\n[Phase 2] Launching {args.workers} parallel workers...")
        start_time = time.time()

        workers = []
        for i in range(args.workers):
            p = Process(
                target=fighter_worker,
                args=(i, url_queue, progress_dict, None, args.batch_size, args.delay)
            )
            p.start()
            workers.append(p)

        # Monitor progress
        total = len(unique_urls)
        while any(p.is_alive() for p in workers):
            loaded = progress_dict.get("loaded", 0)
            failed = progress_dict.get("failed", 0)
            remaining = total - loaded - failed
            elapsed = time.time() - start_time
            rate = loaded / elapsed if elapsed > 0 else 0
            eta = remaining / rate if rate > 0 else 0

            print(f"\r  Progress: {loaded}/{total} loaded ({failed} failed) | "
                  f"Rate: {rate:.1f}/s | ETA: {eta/60:.0f}m", end="", flush=True)

            save_progress(progress_dict)
            time.sleep(5)

        # Wait for all workers to finish
        for p in workers:
            p.join()

        elapsed = time.time() - start_time
        print(f"\n\n  [OK] Loaded {progress_dict.get('loaded', 0)} fighters in {elapsed/60:.1f}m")
        print(f"  Rate: {progress_dict.get('loaded', 0) / elapsed:.1f} fighters/sec")

    # ---- Summary ----
    print(f"\n{'='*60}")
    print(f"  CRAWL COMPLETE")
    print(f"{'='*60}")
    print(f"  Events loaded:  {progress_dict.get('events_loaded', 0)}")
    print(f"  Fighters loaded: {progress_dict.get('loaded', 0)}")
    print(f"  Fighters failed: {progress_dict.get('failed', 0)}")
    print(f"  Duration:        {(time.time() - start_time)/60:.1f}m")

    scraper.close()
    loader.close()

    # Final Neo4j summary
    loader2 = Neo4jLoader(NEO4J_URI, NEO4J_USER, NEO4J_PASS)
    with loader2.driver.session() as s:
        for label in ["Fighter", "Event", "Fight", "WeightClass", "Location", "Referee"]:
            r = s.run(f"MATCH (n:{label}) RETURN count(n)").single()
            print(f"  Neo4j {label}: {r[0]}")
    loader2.close()


if __name__ == "__main__":
    main()
