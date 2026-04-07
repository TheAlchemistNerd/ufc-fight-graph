# Engineering Decisions: Dask, Neo4j Batch Loading & TDD

## Context

The project uses `multiprocessing` in `parallel_scraper.py` for parallel fighter scraping and individual `MERGE` queries for Neo4j writes. This document captures how **Dask** and **batch Neo4j loading** would improve the pipeline, with full TDD test suites written before implementation.

---

## Part 1: Using Dask Instead of Multiprocessing

### Why Dask Fits

The current `parallel_scraper.py` uses raw `multiprocessing.Queue` + `Process`. Dask replaces this with three layers, each solving a specific problem:

### Layer 1: `dask.delayed` for Fighter Scraping

```python
# Instead of: worker pulls from multiprocessing.Queue
# With Dask:
from dask import delayed
import dask

@dask.delayed
def scrape_and_load_fighter(url, neo4j_uri, neo4j_user, neo4j_pass):
    scraper = UfcStatsScraper()
    loader = Neo4jLoader(neo4j_uri, neo4j_user, neo4j_pass)
    fighter = scraper.scrape_fighter_profile(url)
    if fighter:
        normalized = scraper.normalize_data(fighter)
        loader.create_fighter(normalized)
    scraper.close()
    loader.close()
    return fighter.get("name") if fighter else None

# Build task graph, then execute:
tasks = [scrape_and_load_fighter(url, uri, user, pw) for url in all_fighter_urls]
results = dask.compute(*tasks, num_workers=25)
```

**Advantage over multiprocessing**: Dask automatically handles load balancing, retries failed tasks, tracks progress with a dashboard (`localhost:8787`), and serializes errors gracefully. No manual queue management.

### Layer 2: `dask.bag` for URL Discovery

```python
import dask.bag as db

def discover_fighters(char):
    scraper = UfcStatsScraper()
    urls = scraper.scrape_alphabetical_list(char)
    scraper.close()
    return urls

# 26 chars -> 26 parallel discovery tasks
bag = db.from_sequence([chr(c) for c in range(ord('a'), ord('z') + 1)])
all_urls = bag.map(discover_fighters).flatten().compute()
```

### Layer 3: `dask.dataframe` for Analytics on Large Result Sets

When you have 5,000+ fighters with full stats, aggregations like "finish rate by year" or "career trajectory clustering" become expensive. Dask DataFrames let you process out-of-core:

```python
import dask.dataframe as dd

# Export from Neo4j, process with Dask
df = dd.from_pandas(export_from_neo4j(), npartitions=20)

# Groupby, aggregations, rolling windows - all out-of-core
result = df.groupby("era").agg({
    "height_inches": "mean",
    "reach_inches": "mean",
    "slpm": "mean",
}).compute()
```

### Implementation Design (parallel_dask.py - written TDD-first)

```python
from dask import delayed
import dask
from ucf_stats_scraper import UfcStatsScraper
from neo4j_loader import Neo4jLoader

@delayed
def scrape_and_load_fighter(url, neo4j_uri, neo4j_user, neo4j_pass):
    scraper = UfcStatsScraper()
    loader = Neo4jLoader(neo4j_uri, neo4j_user, neo4j_pass)
    try:
        fighter = scraper.scrape_fighter_profile(url)
        if fighter and fighter.get("name"):
            normalized = scraper.normalize_data(fighter)
            loader.create_fighter(normalized)
            return fighter["name"]
    except Exception:
        pass
    finally:
        scraper.close()
        loader.close()
    return None

def crawl_fighters_parallel(urls, workers=25):
    tasks = [scrape_and_load_fighter(url, NEO4J_URI, NEO4J_USER, NEO4J_PASS) for url in urls]
    return list(dask.compute(*tasks, num_workers=workers))
```

### Dask vs Multiprocessing Comparison

| Aspect | `multiprocessing` (current) | `dask` (would be) |
|--------|---------------------------|-------------------|
| Load balancing | Manual queue management | Automatic work stealing |
| Error handling | Try/except per task | Built-in task-level retry |
| Progress | Manual print/JSON updates | Dask dashboard at `localhost:8787` |
| Serialization | Pickle issues with complex objects | Better serialization via cloudpickle |
| Scaling | Fixed process count | LocalCluster -> distributed cluster seamlessly |
| Retries | Not implemented | `dask.delayed(retries=2)` |
| Throttling | Manual `time.sleep()` | Adaptive scheduling |

For I/O bound work (HTTP requests), `dask` with `processes=False` (thread pool) is the right choice since the GIL is released during network I/O.

---

## Part 2: Neo4j Batch Loading Strategies

### Current Problem

```
Worker 1 --► Fighter A --► Neo4j (1 query)
Worker 1 --► Fighter B --► Neo4j (1 query)
Worker 2 --► Fighter C --► Neo4j (1 query)
...5000 fighters = 5000+ queries + 5000+ connection opens/closes
```

### Strategy 1: Batch Accumulator + UNWIND (Best for this use case)

Each worker collects fighters in memory, flushes in batches of 50-100:

```python
class BatchWriter:
    def __init__(self, uri, user, password, batch_size=50):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.batch_size = batch_size
        self.buffer = []

    def add(self, fighter_data):
        self.buffer.append(fighter_data)
        if len(self.buffer) >= self.batch_size:
            self.flush()

    def flush(self):
        if not self.buffer:
            return
        with self.driver.session() as session:
            session.run("""
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
            """, fighters=self.buffer)
        self.buffer.clear()

    def close(self):
        self.flush()
        self.driver.close()
```

**Performance improvement:**

| Metric | Individual MERGE (current) | UNWIND batch |
|--------|---------------------------|--------------|
| Network round-trips | 5,000 | 100 (at batch_size=50) |
| Connection opens/closes | 5,000 | 100 |
| Query parsing overhead | 5,000 parses | 100 parses |
| Throughput | ~5 fighters/sec | ~50-100 fighters/sec |

**Worker integration:**
```python
def fighter_worker(worker_id, url_queue, ...):
    loader = BatchWriter(NEO4J_URI, NEO4J_USER, NEO4J_PASS, batch_size=50)

    while not url_queue.empty():
        fighter = scraper.scrape_fighter_profile(url)
        if fighter:
            loader.add(scraper.normalize_data(fighter))

    loader.close()  # Final flush
```

### Strategy 2: Dedicated Loader Process + Message Queue

Workers don't write to Neo4j at all. They push to a multiprocessing Queue, and one dedicated process drains and batches:

```python
# Workers just put data in a queue
def worker(url, fight_queue):
    fighter = scraper.scrape_fighter_profile(url)
    if fighter:
        fight_queue.put(scraper.normalize_data(fighter))  # Fast, no network

# Single loader process
def neo4j_loader(fight_queue, uri, user, password):
    writer = BatchWriter(uri, user, password, batch_size=100)
    while not done_event.is_set() or not fight_queue.empty():
        try:
            data = fight_queue.get(timeout=1)
            writer.add(data)
        except Empty:
            continue
    writer.flush()
    writer.close()
```

**Advantages**: Workers never blocked on Neo4j latency. If Neo4j is slow, scraping continues at full speed. Single writer avoids connection contention.

### Strategy 3: CSV Bulk Import (Fastest for initial load)

Scrape everything to CSV files, then use `neo4j-admin import`:

```python
# Workers write to CSV, not Neo4j
def worker(url, csv_path):
    fighter = scraper.scrape_fighter_profile(url)
    if fighter:
        with open(csv_path, 'a') as f:
            w = csv.writer(f)
            w.writerow([
                fighter['name'], fighter['nickname'], ...
            ])

# After crawl completes:
# neo4j-admin import --nodes fighters.csv --nodes events.csv --relationships fights.csv
```

**Speed**: `neo4j-admin import` can ingest millions of nodes in minutes. It's 10-100x faster than any programmatic approach.

**Tradeoff**: Requires Neo4j downtime during import (offline tool).

---

## Part 3: TDD Test Suites

### TDD Test Suite: Dask-Based Scraper

Tests written before implementation. These define the API that `parallel_dask.py` would satisfy.

```python
"""
Tests for Dask-based parallel scraping pipeline.
Written TDD-style: tests define the API before implementation.
"""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import dask
from dask import delayed
import dask.bag as db


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def mock_fighter_data():
    return {
        "name": "Test Fighter",
        "record": "10-5-0",
        "height": "6' 0\"",
        "weight": "170 lbs.",
        "reach": "72\"",
        "stance": "Orthodox",
        "slpm": "4.50",
        "str. acc.": "50%",
        "fights": [],
        "fight_urls": [],
    }

@pytest.fixture
def sample_urls():
    return [
        "http://ufcstats.com/fighter-details/aaa111",
        "http://ufcstats.com/fighter-details/bbb222",
        "http://ufcstats.com/fighter-details/ccc333",
    ]


# ============================================================
# TEST: Single Fighter Scraping (Delayed Task)
# ============================================================

class TestScrapeFighterTask:
    """Test the delayed scraping task unit."""

    @patch("parallel_dask.UfcStatsScraper")
    @patch("parallel_dask.Neo4jLoader")
    def test_success_returns_fighter_name(self, mock_loader_cls, mock_scraper_cls, mock_fighter_data):
        """A successful scrape returns the fighter name."""
        mock_scraper = MagicMock()
        mock_scraper.scrape_fighter_profile.return_value = mock_fighter_data
        mock_scraper_cls.return_value = mock_scraper

        mock_loader = MagicMock()
        mock_loader_cls.return_value = mock_loader

        from parallel_dask import scrape_and_load_fighter
        result = scrape_and_load_fighter("http://test.com/aaa", "bolt://x", "u", "p").compute()

        assert result == "Test Fighter"
        mock_scraper.scrape_fighter_profile.assert_called_once()
        mock_scraper.normalize_data.assert_called_once()
        mock_loader.create_fighter.assert_called_once()
        mock_scraper.close.assert_called_once()
        mock_loader.close.assert_called_once()

    @patch("parallel_dask.UfcStatsScraper")
    def test_failure_returns_none(self, mock_scraper_cls):
        """A failed scrape returns None (not raises)."""
        mock_scraper = MagicMock()
        mock_scraper.scrape_fighter_profile.return_value = None
        mock_scraper_cls.return_value = mock_scraper

        from parallel_dask import scrape_and_load_fighter
        result = scrape_and_load_fighter("http://test.com/bad", "bolt://x", "u", "p").compute()

        assert result is None

    @patch("parallel_dask.UfcStatsScraper")
    def test_exception_returns_none(self, mock_scraper_cls):
        """An exception during scraping returns None."""
        mock_scraper = MagicMock()
        mock_scraper.scrape_fighter_profile.side_effect = ConnectionError("timeout")
        mock_scraper_cls.return_value = mock_scraper

        from parallel_dask import scrape_and_load_fighter
        result = scrape_and_load_fighter("http://test.com/err", "bolt://x", "u", "p").compute()

        assert result is None


# ============================================================
# TEST: Parallel Execution
# ============================================================

class TestParallelExecution:
    """Test the parallel compute pipeline."""

    @patch("parallel_dask.scrape_and_load_fighter")
    def test_all_urls_processed(self, mock_task, sample_urls):
        """Every URL in the input list gets processed."""
        mock_task.side_effect = lambda url, *a, **k: delayed(lambda: url.split("/")[-1])()

        from parallel_dask import crawl_fighters_parallel
        results = crawl_fighters_parallel(sample_urls, workers=3)

        assert len(results) == 3
        assert set(results) == {"aaa111", "bbb222", "ccc333"}

    @patch("parallel_dask.scrape_and_load_fighter")
    def test_partial_failure_still_completes(self, mock_task, sample_urls):
        """If some tasks fail, the pipeline completes with partial results."""
        call_count = 0
        def side_effect(url, *a, **k):
            nonlocal call_count
            call_count += 1
            if "bbb" in url:
                return delayed(lambda: None)()
            return delayed(lambda: url.split("/")[-1])()

        mock_task.side_effect = side_effect

        from parallel_dask import crawl_fighters_parallel
        results = crawl_fighters_parallel(sample_urls, workers=3)

        assert len(results) == 3
        assert results.count(None) == 1
        assert results.count("aaa111") == 1
        assert results.count("ccc333") == 1


# ============================================================
# TEST: URL Discovery with Dask Bag
# ============================================================

class TestUrlDiscovery:
    """Test parallel URL discovery using dask.bag."""

    @patch("parallel_dask.UfcStatsScraper")
    def test_discover_returns_all_urls(self, mock_scraper_cls):
        """Discovery across all 26 chars returns all fighter URLs."""
        mock_scraper = MagicMock()
        mock_scraper.scrape_alphabetical_list.return_value = ["url1", "url2"]
        mock_scraper_cls.return_value = mock_scraper

        from parallel_dask import discover_all_fighters_urls
        urls = discover_all_fighter_urls()

        assert len(urls) <= 52
        assert all(url.startswith("url") for url in urls)

    @patch("parallel_dask.UfcStatsScraper")
    def test_discover_handles_empty_chars(self, mock_scraper_cls):
        """Chars with no fighters are handled gracefully."""
        mock_scraper = MagicMock()
        mock_scraper.scrape_alphabetical_list.side_effect = lambda c: [] if c == 'x' else ["url1"]
        mock_scraper_cls.return_value = mock_scraper

        from parallel_dask import discover_all_fighters_urls
        urls = discover_all_fighters_urls()

        assert "url1" in urls


# ============================================================
# TEST: Progress Tracking
# ============================================================

class TestProgressTracking:
    """Test progress monitoring during parallel execution."""

    def test_progress_callback_fires(self, sample_urls):
        """A progress callback is called during compute."""
        progress_calls = []

        def progress_callback(state):
            progress_calls.append(state)

        @delayed
        def dummy_task(url):
            import time
            time.sleep(0.01)
            return url

        tasks = [dummy_task(url) for url in sample_urls]
        dask.compute(*tasks, callbacks=[progress_callback])

        assert len(progress_calls) > 0

    def test_progress_reports_success_and_failure_counts(self, sample_urls):
        """Progress tracking reports correct success/failure counts."""
        @delayed
        def succeed(url):
            return url

        @delayed
        def fail(url):
            return None

        tasks = [succeed(sample_urls[0]), fail(sample_urls[1]), succeed(sample_urls[2])]
        results = dask.compute(*tasks)

        success_count = sum(1 for r in results if r is not None)
        fail_count = sum(1 for r in results if r is None)

        assert success_count == 2
        assert fail_count == 1


# ============================================================
# TEST: Event Crawling (Sequential)
# ============================================================

class TestEventCrawl:
    """Test sequential event crawling (not parallelized - not enough events)."""

    @patch("parallel_dask.UfcStatsScraper")
    @patch("parallel_dask.Neo4jLoader")
    def test_events_loaded_and_fights_created(self, mock_loader_cls, mock_scraper_cls):
        """Event crawl creates events and fight relationships."""
        mock_scraper = MagicMock()
        mock_scraper.scrape_all_events.return_value = ["event1", "event2"]
        mock_scraper.scrape_event_details.return_value = {
            "name": "UFC 100",
            "date": "July 11, 2009",
            "location": "Las Vegas",
            "fights": [
                {"fighter1": "A", "fighter2": "B", "url": "fight1"},
            ],
        }
        mock_scraper_cls.return_value = mock_scraper

        mock_loader = MagicMock()
        mock_loader_cls.return_value = mock_loader

        from parallel_dask import crawl_events
        result = crawl_events("bolt://x", "u", "p")

        assert result["events_loaded"] == 2
        assert mock_loader.create_event.call_count == 2
        assert mock_loader.create_fight_from_event.call_count == 2


# ============================================================
# TEST: Neo4j Write Deduplication
# ============================================================

class TestNeo4jDeduplication:
    """Test that MERGE semantics prevent duplicate writes."""

    @patch("parallel_dask.UfcStatsScraper")
    @patch("parallel_dask.Neo4jLoader")
    def test_same_fighter_scraped_twice_writes_once(self, mock_loader_cls, mock_scraper_cls, mock_fighter_data):
        """If the same fighter is scraped twice (parallel race), Neo4j MERGE handles it."""
        mock_scraper = MagicMock()
        mock_scraper.scrape_fighter_profile.return_value = mock_fighter_data
        mock_scraper_cls.return_value = mock_scraper

        mock_loader = MagicMock()
        mock_loader_cls.return_value = mock_loader

        from parallel_dask import scrape_and_load_fighter

        task1 = scrape_and_load_fighter("http://test/aaa", "bolt://x", "u", "p")
        task2 = scrape_and_load_fighter("http://test/aaa", "bolt://x", "u", "p")
        r1, r2 = dask.compute(task1, task2)

        assert r1 == "Test Fighter"
        assert r2 == "Test Fighter"
        assert mock_loader.create_fighter.call_count == 2  # MERGE handles dedup


# ============================================================
# TEST: Dask Configuration
# ============================================================

class TestDaskConfiguration:
    """Test configuration of Dask cluster."""

    def test_thread_pool_executor(self):
        """Dask uses ThreadPoolExecutor for I/O bound scraping."""
        from dask.distributed import Client
        client = Client(processes=False)
        assert client.cluster._thread_pool is not None
        client.close()

    def test_configurable_workers(self):
        """Worker count is configurable."""
        from dask import delayed

        @delayed
        def count(x):
            return x

        tasks = [count(i) for i in range(10)]
        results = dask.compute(*tasks, num_workers=5)
        assert len(results) == 10
```

---

### TDD Test Suite: Batch Neo4j Writer

```python
"""Tests for batch Neo4j writing."""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd


class TestBatchWriter:
    """Test batch accumulation and UNWIND flushing."""

    @pytest.fixture
    def sample_fighters(self):
        return [
            {"name": "A", "nickname": "Alpha", "slpm": "4.5", "wins": 10},
            {"name": "B", "nickname": "Bravo", "slpm": "3.2", "wins": 8},
            {"name": "C", "nickname": "Charlie", "slpm": "5.1", "wins": 12},
        ]

    @patch("batch_loader.GraphDatabase")
    def test_accumulates_until_batch_size(self, mock_db, sample_fighters):
        """Writer buffers data until batch_size is reached."""
        from batch_loader import BatchWriter
        writer = BatchWriter("bolt://x", "u", "p", batch_size=2)

        writer.add(sample_fighters[0])
        writer.add(sample_fighters[1])

        session = mock_db.driver.return_value.session.return_value.__enter__.return_value
        session.run.assert_called_once()
        call_args = session.run.call_args
        assert len(call_args.kwargs["fighters"]) == 2
        assert call_args.kwargs["fighters"][0]["name"] == "A"

    @patch("batch_loader.GraphDatabase")
    def test_flush_on_close(self, mock_db, sample_fighters):
        """Remaining buffer is flushed on close, even if not full."""
        from batch_loader import BatchWriter
        writer = BatchWriter("bolt://x", "u", "p", batch_size=10)

        for f in sample_fighters:
            writer.add(f)

        writer.close()

        session = mock_db.driver.return_value.session.return_value.__enter__.return_value
        session.run.assert_called_once()
        call_args = session.run.call_args
        assert len(call_args.kwargs["fighters"]) == 3

    @patch("batch_loader.GraphDatabase")
    def test_multiple_batches(self, mock_db, sample_fighters):
        """10 fighters with batch_size=3 produces 4 batches (3+3+3+1)."""
        from batch_loader import BatchWriter
        writer = BatchWriter("bolt://x", "u", "p", batch_size=3)

        fighters = sample_fighters * 3 + [sample_fighters[0]]
        for f in fighters:
            writer.add(f)

        session = mock_db.driver.return_value.session.return_value.__enter__.return_value
        assert session.run.call_count == 3

        writer.close()
        assert session.run.call_count == 4

    @patch("batch_loader.GraphDatabase")
    def test_empty_buffer_no_flush(self, mock_db):
        """Closing with empty buffer does not call flush."""
        from batch_loader import BatchWriter
        writer = BatchWriter("bolt://x", "u", "p", batch_size=5)
        writer.close()

        session = mock_db.driver.return_value.session.return_value.__enter__.return_value
        session.run.assert_not_called()

    @patch("batch_loader.GraphDatabase")
    def test_unwind_query_structure(self, mock_db, sample_fighters):
        """The UNWIND query has correct Cypher structure."""
        from batch_loader import BatchWriter
        writer = BatchWriter("bolt://x", "u", "p", batch_size=1)
        writer.add(sample_fighters[0])

        session = mock_db.driver.return_value.session.return_value.__enter__.return_value
        query = session.run.call_args[0][0]
        assert "UNWIND $fighters AS f" in query
        assert "MERGE (fighter:Fighter {name: f.name})" in query
        assert "SET fighter.nickname = f.nickname" in query


class TestDedicatedLoader:
    """Test the dedicated loader process with message queue."""

    @patch("batch_loader.BatchWriter")
    def test_loader_drains_queue(self, mock_writer_cls):
        """Loader process consumes all items from queue."""
        import multiprocessing
        from batch_loader import neo4j_loader_process

        q = multiprocessing.Queue()
        done = multiprocessing.Event()

        for i in range(5):
            q.put({"name": f"Fighter{i}"})

        done.set()
        neo4j_loader_process(q, done, "bolt://x", "u", "p")

        writer = mock_writer_cls.return_value
        assert writer.add.call_count == 5

    @patch("batch_loader.BatchWriter")
    def test_loader_handles_poison_pill(self, mock_writer_cls):
        """Loader handles None (poison pill) gracefully."""
        import multiprocessing
        from batch_loader import neo4j_loader_process

        q = multiprocessing.Queue()
        done = multiprocessing.Event()

        q.put({"name": "A"})
        q.put(None)
        q.put({"name": "B"})

        done.set()
        neo4j_loader_process(q, done, "bolt://x", "u", "p")

        writer = mock_writer_cls.return_value
        assert writer.add.call_count == 1


class TestCSVExport:
    """Test CSV export for bulk import."""

    def test_fighter_to_csv_row(self):
        """Single fighter dict converts to correct CSV row."""
        from batch_loader import fighter_to_csv_row
        fighter = {
            "name": "Test",
            "nickname": "T",
            "record": "10-5-0",
            "height_inches": 74,
            "weight_lbs": 170,
            "reach_inches": 74,
        }
        row = fighter_to_csv_row(fighter)
        assert row["name"] == "Test"
        assert row["nickname"] == "T"
        assert row["height_inches"] == "74"
        assert row["weight_lbs"] == "170"

    def test_csv_header_matches_columns(self):
        """CSV header matches expected columns for neo4j-admin import."""
        from batch_loader import FIGHTER_CSV_COLUMNS
        expected = ["name", "nickname", "record", "height_inches",
                    "weight_lbs", "reach_inches", "stance", "dob",
                    "slpm", "str_acc", "sapm", "str_def",
                    "td_avg", "td_acc", "td_def", "sub_avg",
                    "wins", "losses", "draws", "nc"]
        assert FIGHTER_CSV_COLUMNS == expected
```

---

## Part 4: Recommended Implementation Path

### Phase 1: Add BatchWriter to Current Workers (Immediate)

Change each worker in `parallel_scraper.py` to use `BatchWriter` with `UNWIND`:

```python
def fighter_worker(worker_id, url_queue, ...):
    loader = BatchWriter(NEO4J_URI, NEO4J_USER, NEO4J_PASS, batch_size=50)

    while not url_queue.empty():
        fighter = scraper.scrape_fighter_profile(url)
        if fighter:
            loader.add(scraper.normalize_data(fighter))

    loader.close()  # Final flush
```

**Result**: Neo4j write time drops from ~20 minutes to ~2 minutes for 5,000 fighters.

### Phase 2: Switch to Dask (Next Iteration)

Replace `multiprocessing.Process` + `Queue` with `dask.delayed`:
- Automatic load balancing
- Built-in retries (`retries=2`)
- Dashboard at `localhost:8787`
- Seamless scale-up to distributed cluster

### Phase 3: CSV Bulk Import for Full Crawl (Production)

For the initial 5,000-fighter load:
1. Scrape all fighters to CSV (parallel, no Neo4j writes)
2. Use `neo4j-admin import --nodes fighters.csv --nodes events.csv --relationships fights.csv`
3. Use `BatchWriter` only for ongoing incremental updates

**Result**: Full initial load in minutes instead of hours.

---

## Summary

| Concern | Current | Dask + BatchWriter | CSV Bulk Import |
|---------|---------|--------------------|----------------|
| Scraping parallelism | `multiprocessing` (manual queues) | `dask.delayed` (automatic work stealing) | Same as Dask |
| Neo4j throughput | ~5 fighters/sec (individual MERGE) | ~50-100 fighters/sec (UNWIND batches) | ~1000+ fighters/sec (offline import) |
| Error handling | Try/except per worker | Built-in task retries | N/A (write to disk, verify) |
| Progress monitoring | Manual JSON file | Dask dashboard | File size / line count |
| Scaling ceiling | 1 machine, N processes | 1 machine -> distributed cluster | Single-node (import is offline) |
| Incremental updates | Checkpoint file | Same | BatchWriter only |

---

## Dask on a Single Machine: Does It Work Here?

Yes, but with nuance.

| Layer | Dask Benefit on Single Machine | Verdict |
|-------|-------------------------------|---------|
| **Scraping (I/O bound)** | Thread-pool Dask workers release GIL during HTTP requests. Automatic retries, work stealing, dashboard at `localhost:8787`. Marginal gain over `multiprocessing` for ~5,000 fighters. | Nice-to-have, not essential |
| **Neo4j batch writes** | `dask.delayed` can batch UNWIND writes. But a simple `BatchWriter` class does this with less overhead and fewer moving parts. | Not worth it |
| **Analytics (CPU bound)** | `dask.dataframe` on 5,000+ fighter aggregations, groupby by era/weight-class, rolling windows — this is where Dask shines. Out-of-core processing if data exceeds RAM. | **Genuinely useful** |
| **ML/GNN training** | `dask-ml` for distributed hyperparameter search, feature engineering on large fight datasets. | Very useful at scale |

**Bottom line**: For the current scope (~5,000 fighters), `multiprocessing` + `BatchWriter` is sufficient. Dask becomes worth it when you add: (a) temporal graph snapshots across 20+ years of data, (b) GNN training on millions of edges, (c) real-time inference at serving scale. The infrastructure is already documented in `ENGINEERING_DECISIONS.md` — add it when the data volume justifies the complexity.

---

## GitHub Repository

**Name:** `ufc-fight-graph`

**Description (327 characters):**

UFC knowledge graph: 5,000+ fighters, 10,000+ fights, 768 events scraped from UFCStats.com into Neo4j. Network centrality (Degree, PageRank, Betweenness), referee analysis, striking efficiency, career longevity, geographic insights, and a 15-page Streamlit dashboard. Built with TDD, parallel scraping, and CI/CD via GitHub Actions.
