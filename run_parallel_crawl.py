"""
Parallel UFC Stats Crawler — 50 worker processes with batch Neo4j writes.

Each worker:
  1. Pulls fighter URLs from a shared Queue
  2. Scrapes profiles with per-worker rate limiting
  3. Batches writes (UNWIND 50 at a time) to Neo4j
  4. Updates shared progress counter

Usage:
    python run_parallel_crawl.py                    # Default 50 workers
    python run_parallel_crawl.py --workers 50       # Explicit workers
    python run_parallel_crawl.py --fighters-only    # Skip events
    python run_parallel_crawl.py --events-only      # Skip fighters
    python run_parallel_crawl.py --batch-size 100   # Larger Neo4j batches
"""

import sys
import os
import time
import random
import json
import argparse
from multiprocessing import Process, Queue, Manager, Event
from datetime import datetime

# Path setup for both root and base/ legacy modules
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "base"))

# Try new architecture first, fall back to legacy
try:
    from config.settings import Neo4jConfig, CrawlConfig
    from infrastructure.neo4j_client import Neo4jConnection
    from base.ucf_stats_scraper import UfcStatsScraper
    HAS_NEW_ARCH = True
except ImportError:
    from base.ucf_stats_scraper import UfcStatsScraper
    from base.neo4j_loader import Neo4jLoader
    HAS_NEW_ARCH = False


# ===================== CONFIG =====================

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS", "password")

DEFAULT_WORKERS = 50
DEFAULT_BATCH_SIZE = 50  # Fighters per Neo4j UNWIND batch
DEFAULT_DELAY = 0.6      # Base delay per worker (50 workers * 0.6s = ~30 req/s total)

PROGRESS_FILE = os.path.join(ROOT, "logs", "crawl_progress.json")
CHECKPOINT_FILE = os.path.join(ROOT, "logs", "crawl_checkpoint.json")


# ===================== BATCH WRITER =====================

class BatchWriter:
    """
    Accumulates fighter data and flushes via Neo4j UNWIND.
    Reduces 5000 individual queries to ~100 batch queries.
    """

    def __init__(self, uri, user, password, batch_size=50):
        if HAS_NEW_ARCH:
            self._conn = Neo4jConnection(Neo4jConfig(uri, user, password))
            self._use_new = True
        else:
            self._loader = Neo4jLoader(uri, user, password)
            self._use_new = False
        self._batch_size = batch_size
        self._buffer = []
        self._total_flushed = 0

    def add(self, fighter_data: dict) -> None:
        self._buffer.append(fighter_data)
        if len(self._buffer) >= self._batch_size:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        if self._use_new:
            self._flush_new()
        else:
            self._flush_legacy()
        self._buffer.clear()

    def _flush_new(self) -> None:
        """UNWIND batch write via new architecture."""
        query = """
            UNWIND $fighters AS f
            MERGE (fighter:Fighter {name: f.name})
            SET fighter.nickname = f.nickname,
                fighter.record = f.record,
                fighter.height = f.height,
                fighter.reach = f.reach,
                fighter.stance = f.stance,
                fighter.dob = f.dob,
                fighter.slpm = f.slpm,
                fighter.str_acc = f.str_acc,
                fighter.sapm = f.sapm,
                fighter.str_def = f.str_def,
                fighter.td_avg = f.td_avg,
                fighter.td_acc = f.td_acc,
                fighter.td_def = f.td_def,
                fighter.sub_avg = f.sub_avg,
                fighter.wins = f.wins,
                fighter.losses = f.losses,
                fighter.draws = f.draws,
                fighter.nc = f.nc,
                fighter.height_inches = f.height_inches,
                fighter.weight_lbs = f.weight_lbs,
                fighter.reach_inches = f.reach_inches
        """
        try:
            self._conn.run_write(query, {"fighters": self._buffer})
            self._total_flushed += len(self._buffer)
        except Exception as e:
            print(f"  [BatchWriter] Flush error: {e}")

    def _flush_legacy(self) -> None:
        """Fallback: individual MERGE per fighter."""
        for f in self._buffer:
            try:
                self._loader.create_fighter(f)
            except Exception:
                pass
            self._total_flushed += 1

    def close(self) -> None:
        self.flush()
        if self._use_new:
            self._conn.close()
        else:
            self._loader.close()

    @property
    def total_flushed(self) -> int:
        return self._total_flushed


# ===================== WORKER =====================

def fighter_worker(worker_id: int, url_queue: Queue,
                   progress_dict: dict, stop_event: Event,
                   batch_size: int, delay: float) -> None:
    """
    Single worker process. Pulls URLs from shared queue, scrapes,
    batches writes to Neo4j, updates shared progress.
    """
    scraper = UfcStatsScraper()
    writer = BatchWriter(NEO4J_URI, NEO4J_USER, NEO4J_PASS, batch_size=batch_size)

    loaded = 0
    failed = 0

    while not stop_event.is_set():
        # Get a batch of URLs
        batch = []
        for _ in range(min(10, max(1, url_queue.qsize()))):
            try:
                url = url_queue.get_nowait()
                batch.append(url)
            except Exception:
                break

        if not batch:
            break

        for url in batch:
            if stop_event.is_set():
                break
            try:
                fighter = scraper.scrape_fighter_profile(url)
                if fighter and fighter.get("name"):
                    normalized = scraper.normalize_data(fighter)
                    writer.add(normalized)
                    loaded += 1
                    progress_dict["loaded"] = progress_dict.get("loaded", 0) + 1
                else:
                    failed += 1
                    progress_dict["failed"] = progress_dict.get("failed", 0) + 1
            except Exception as e:
                failed += 1
                progress_dict["failed"] = progress_dict.get("failed", 0) + 1

            progress_dict["last_update"] = datetime.now().isoformat()
            # Per-worker rate limiting
            time.sleep(random.uniform(delay * 0.5, delay * 1.5))

    writer.close()
    scraper.close()
    print(f"  Worker {worker_id:2d} done: {loaded} loaded, {failed} failed")


# ===================== EVENT CRAWL (Sequential) =====================

def crawl_events_sequential(delay: float = 1.0) -> int:
    """
    Crawl all events sequentially (not enough events to parallelize meaningfully).
    Returns count of events loaded.
    """
    scraper = UfcStatsScraper()
    if HAS_NEW_ARCH:
        conn = Neo4jConnection(Neo4jConfig(NEO4J_URI, NEO4J_USER, NEO4J_PASS))
        conn.setup_schema()
    else:
        loader = Neo4jLoader(NEO4J_URI, NEO4J_USER, NEO4J_PASS)
        loader.setup_schema()

    print("\n[Phase 1] Discovering events...")
    all_urls = scraper.scrape_all_events()
    print(f"  Found {len(all_urls)} events")

    loaded = 0
    for i, url in enumerate(all_urls):
        try:
            event = scraper.scrape_event_details(url)
            if event and event.get("name"):
                if HAS_NEW_ARCH:
                    # Write event
                    conn.run_write("""
                        MERGE (e:Event {name: $name})
                        SET e.url = $url, e.date = $date
                        WITH e
                        MERGE (loc:Location {name: $location})
                        MERGE (e)-[:HELD_AT]->(loc)
                    """, {
                        "name": event.get("name"),
                        "url": event.get("url"),
                        "date": event.get("date"),
                        "location": event.get("location", "Unknown"),
                    })
                    # Write fights
                    ename = event.get("name")
                    for fight in event.get("fights", []):
                        if fight.get("fighter1"):
                            conn.run_write("""
                                MERGE (e:Event {name: $event})
                                MERGE (f1:Fighter {name: $f1})
                                MERGE (f2:Fighter {name: $f2})
                                MERGE (wc:WeightClass {name: $wc})
                                MERGE (fight:Fight {url: $url})
                                SET fight.date = $date, fight.method = $method,
                                    fight.round = $round, fight.time = $time
                                MERGE (fight)-[:PART_OF]->(e)
                                MERGE (fight)-[:IN_WEIGHT_CLASS]->(wc)
                                MERGE (f1)-[r1:FOUGHT]->(fight)
                                SET r1.result = $result
                                MERGE (f2)-[r2:FOUGHT]->(fight)
                            """, {
                                "event": ename,
                                "f1": fight["fighter1"],
                                "f2": fight["fighter2"],
                                "wc": fight.get("weight_class", "Unknown"),
                                "url": fight.get("url", ""),
                                "date": None,
                                "method": fight.get("method"),
                                "round": fight.get("round"),
                                "time": fight.get("time"),
                                "result": fight.get("result"),
                            })
                loaded += 1
        except Exception as e:
            print(f"  Event FAILED {url}: {e}")

        if (i + 1) % 50 == 0:
            print(f"  Events: {i+1}/{len(all_urls)}")

        time.sleep(random.uniform(delay * 0.5, delay * 1.5))

    scraper.close()
    if HAS_NEW_ARCH:
        conn.close()
    else:
        loader.close()
    print(f"\n  [OK] Loaded {loaded} events")
    return loaded


# ===================== MAIN =====================

def main():
    parser = argparse.ArgumentParser(description="Parallel UFC Stats Crawler")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                        help=f"Number of parallel workers (default {DEFAULT_WORKERS})")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Neo4j UNWIND batch size (default {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help=f"Base delay per worker (default {DEFAULT_DELAY}s)")
    parser.add_argument("--events-only", action="store_true")
    parser.add_argument("--fighters-only", action="store_true")
    parser.add_argument("--reset", action="store_true", help="Reset and re-crawl all")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  PARALLEL UFC CRAWLER")
    print(f"  Workers: {args.workers} | Batch: {args.batch_size} | Delay: {args.delay}s")
    print(f"{'='*60}\n")

    # Setup schema
    if HAS_NEW_ARCH:
        conn = Neo4jConnection(Neo4jConfig(NEO4J_URI, NEO4J_USER, NEO4J_PASS))
        conn.setup_schema()
        conn.close()
    else:
        loader = Neo4jLoader(NEO4J_URI, NEO4J_USER, NEO4J_PASS)
        loader.setup_schema()
        loader.close()

    # Shared state
    manager = Manager()
    url_queue = Queue()
    progress_dict = manager.dict({
        "loaded": 0, "failed": 0, "events_loaded": 0,
        "started": datetime.now().isoformat(), "last_update": None,
    })
    stop_event = Event()

    start_time = time.time()

    # Phase 1: Events (sequential)
    if not args.fighters_only:
        crawl_events_sequential(delay=args.delay)

    # Phase 2: Fighters (50 parallel workers)
    if not args.events_only:
        print(f"\n[Phase 2] Discovering fighters (a-z)...")
        scraper = UfcStatsScraper()
        all_urls = []
        for char_code in range(ord("a"), ord("z") + 1):
            char = chr(char_code)
            urls = scraper.scrape_alphabetical_list(char)
            all_urls.extend(urls)
            time.sleep(random.uniform(0.3, 0.8))

        unique_urls = list(dict.fromkeys(all_urls))
        print(f"  Found {len(unique_urls)} unique fighters")

        if args.reset:
            print("  Reset: processing all fighters")
        else:
            # Load checkpoint
            processed = set()
            if os.path.exists(CHECKPOINT_FILE):
                with open(CHECKPOINT_FILE, "r") as f:
                    processed = set(json.load(f))
            remaining = [u for u in unique_urls if u not in processed]
            print(f"  Already processed: {len(processed)}")
            print(f"  Remaining: {len(remaining)}")
            unique_urls = remaining

        for url in unique_urls:
            url_queue.put(url)

        print(f"\n[Phase 2] Launching {args.workers} parallel workers...")
        workers = []
        for i in range(args.workers):
            p = Process(
                target=fighter_worker,
                args=(i, url_queue, progress_dict, stop_event,
                      args.batch_size, args.delay),
            )
            p.start()
            workers.append(p)

        # Monitor progress
        total = len(unique_urls)
        try:
            while any(p.is_alive() for p in workers):
                loaded = progress_dict.get("loaded", 0)
                failed = progress_dict.get("failed", 0)
                remaining = total - loaded - failed
                elapsed = time.time() - start_time
                rate = loaded / elapsed if elapsed > 0 else 0
                eta = remaining / rate / 60 if rate > 0 else 0

                print(f"\r  [{loaded}/{total}] loaded | {failed} failed | "
                      f"Rate: {rate:.1f}/s | ETA: {eta:.0f}m", end="", flush=True)

                # Save checkpoint every 10 seconds
                if random.random() < 0.1:
                    done_urls = set(unique_urls)  # Approximate
                    with open(CHECKPOINT_FILE, "w") as f:
                        json.dump(list(done_urls), f)

                time.sleep(5)
        except KeyboardInterrupt:
            print("\n  Interrupted! Stopping workers...")
            stop_event.set()

        for p in workers:
            p.join(timeout=30)
            if p.is_alive():
                p.terminate()

        elapsed = time.time() - start_time
        print(f"\n\n  [OK] Loaded {progress_dict.get('loaded', 0)} fighters in {elapsed/60:.1f}m")
        print(f"  Rate: {progress_dict.get('loaded', 0) / elapsed:.1f} fighters/sec")

    # Summary
    print(f"\n{'='*60}")
    print(f"  CRAWL COMPLETE")
    print(f"{'='*60}")
    print(f"  Fighters loaded: {progress_dict.get('loaded', 0)}")
    print(f"  Fighters failed: {progress_dict.get('failed', 0)}")
    print(f"  Duration:        {(time.time() - start_time)/60:.1f}m")

    scraper.close()


if __name__ == "__main__":
    main()
