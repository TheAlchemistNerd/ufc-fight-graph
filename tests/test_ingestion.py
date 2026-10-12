"""Ingestion contracts exercised without network or a running database."""

import json
import threading
from dataclasses import replace
from unittest.mock import MagicMock, Mock

import pytest

import run_backfill
import run_crawl
from config.settings import Neo4jConfig
from data_access.loader import DETAILS_VERSION, Neo4jLoader
from infrastructure.checkpoint import Checkpoint
from infrastructure.ufcstats import ScrapeError


@pytest.fixture
def config():
    return Neo4jConfig(uri="bolt://test:7687", user="neo4j", password="test", database="test")


@pytest.fixture
def fight():
    return {
        "url": "http://ufcstats.com/fight-details/a",
        "event": "UFC Test",
        "fighters": ["Fighter A", "Fighter B"],
        "date": "November 15, 2025",
        "fighter_urls": [
            "http://ufcstats.com/fighter-details/a",
            "http://ufcstats.com/fighter-details/b",
        ],
        "method": "KO/TKO",
        "round": "2",
        "time": "1:28",
        "f1_result": "L",
        "f2_result": "W",
        "referee": " Keith Peterson ",
    }


def test_sparse_fighter_write_omits_missing_fields_and_preserves_zero():
    db = Mock()
    Neo4jLoader(db).create_fighter(
        {
            "name": " Fighter A ",
            "url": "fighter-a",
            "nickname": "--",
            "reach": None,
            "dob": None,
            "wins": 0,
            "height_inches": 74,
        }
    )
    params = db.run_write.call_args.args[1]
    assert params == {
        "name": "Fighter A",
        "url": "fighter-a",
        "props": {"wins": 0, "height_inches": 74},
    }


def test_fight_write_preserves_sparse_values_and_tracks_referee(fight):
    db = Mock()
    loader = Neo4jLoader(db)
    loader.create_fight({**fight, "is_title_fight": False, "finish_details": "--"}, enriched=True)
    params = db.run_write.call_args.args[1]
    assert params["referees"] == ["Keith Peterson"]
    assert params["props"]["referee_status"] == "available"
    assert params["props"]["details_version"] == DETAILS_VERSION
    assert params["props"]["date"] == "2025-11-15"
    assert params["props"]["is_title_fight"] is False
    assert "finish_details" not in params["props"]
    assert [p["result"] for p in params["participants"]] == [{"result": "loss"}, {"result": "win"}]

    loader.create_fight(
        {
            "url": fight["url"],
            "event": fight["event"],
            "fighters": fight["fighters"],
            "fighter_urls": fight["fighter_urls"],
        }
    )
    sparse = db.run_write.call_args.args[1]
    assert sparse["props"] == {}
    assert sparse["referees"] == sparse["checked"] == []
    assert all(p["result"] == {} for p in sparse["participants"])
    assert [p["url"] for p in sparse["participants"]] == fight["fighter_urls"]


def test_successful_scrape_with_no_referee_records_source_unavailability(fight):
    db = Mock()
    Neo4jLoader(db).create_fight({**fight, "referee": "--"}, enriched=True)
    params = db.run_write.call_args.args[1]
    assert params["referees"] == []
    assert params["props"]["referee_status"] == "unavailable"
    assert params["props"]["details_version"] == DETAILS_VERSION


@pytest.mark.parametrize(
    "patch",
    [
        {"url": ""},
        {"event": None},
        {"fighters": ["A"]},
        {"fighter_urls": ["a", "a"]},
        {"fighter_urls": []},
        {"fighter_urls": ["a", ""]},
    ],
)
def test_invalid_fight_never_writes(fight, patch):
    db = Mock()
    with pytest.raises(ValueError):
        Neo4jLoader(db).create_fight({**fight, **patch})
    db.run_write.assert_not_called()


def test_same_name_fighters_keep_distinct_source_identity(fight):
    db = Mock()
    Neo4jLoader(db).create_fight({**fight, "fighters": ["Bruno Silva", "Bruno Silva"]})
    participants = db.run_write.call_args.args[1]["participants"]
    assert participants[0]["name"] == participants[1]["name"]
    assert participants[0]["url"] != participants[1]["url"]


def test_checkpoint_persists_once_and_reloads(tmp_path, config):
    path = tmp_path / "nested" / "checkpoint.json"
    checkpoint = Checkpoint(path, config)
    checkpoint.mark("events", "event-a")
    checkpoint.mark("events", "event-a")
    checkpoint.mark("fighters", "fighter-a")
    loaded = Checkpoint(path, config)
    assert loaded.contains("events", "event-a")
    assert loaded.contains("fighters", "fighter-a")
    assert loaded.data["events"] == ["event-a"]
    assert json.loads(path.read_text())["target"] == loaded.target
    assert not path.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize("change", [{"uri": "bolt://another:7687"}, {"database": "another"}])
def test_checkpoint_rejects_another_database(tmp_path, config, change):
    path = tmp_path / "checkpoint.json"
    Checkpoint(path, config).mark("events", "event-a")
    with pytest.raises(ValueError, match="another database"):
        Checkpoint(path, replace(config, **change))


def test_checkpoint_rejects_unreliable_legacy_format(tmp_path, config):
    path = tmp_path / "checkpoint.json"
    path.write_text(json.dumps({"processed_events": ["event-a"]}))
    with pytest.raises(ValueError, match="Legacy checkpoint"):
        Checkpoint(path, config)


def test_failed_event_write_is_retried_before_checkpointing(tmp_path, config, monkeypatch, fight):
    checkpoint = Checkpoint(tmp_path / "checkpoint.json", config)
    scraper = Mock()
    scraper.scrape_event_details.return_value = {
        "name": fight["event"],
        "fights": [fight, {**fight, "url": "fight-b"}],
    }
    monkeypatch.setattr(run_crawl, "UfcStatsScraper", Mock(return_value=scraper))
    loader = Mock()
    loader.create_fight.side_effect = [None, RuntimeError("database write failed")]
    options = {"workers": 1, "delay": 0}

    first = run_crawl.crawl_stage(["event-a", "event-a"], "events", loader, checkpoint, **options)
    assert first == {"loaded": 0, "failed": 1, "skipped": 0}
    assert not checkpoint.contains("events", "event-a")
    assert not checkpoint.path.exists()
    scraper.close.assert_called_once()

    loader.create_fight.side_effect = None
    second = run_crawl.crawl_stage(["event-a"], "events", loader, checkpoint, **options)
    assert second == {"loaded": 1, "failed": 0, "skipped": 0}
    assert Checkpoint(checkpoint.path, config).contains("events", "event-a")
    assert scraper.scrape_event_details.call_count == 2

    third = run_crawl.crawl_stage(["event-a"], "events", loader, checkpoint, **options)
    assert third == {"loaded": 0, "failed": 0, "skipped": 0}
    assert scraper.scrape_event_details.call_count == 2


def test_scrape_failure_and_empty_event_remain_pending(tmp_path, config, monkeypatch):
    checkpoint = Checkpoint(tmp_path / "checkpoint.json", config)
    scraper = Mock()
    scraper.scrape_event_details.side_effect = [
        ScrapeError("incomplete page"),
        {"name": "Upcoming", "fights": []},
    ]
    monkeypatch.setattr(run_crawl, "UfcStatsScraper", Mock(return_value=scraper))
    loader = Mock()
    stats = run_crawl.crawl_stage(
        ["failed", "upcoming"],
        "events",
        loader,
        checkpoint,
        workers=1,
        delay=0,
    )
    assert stats == {"loaded": 0, "failed": 1, "skipped": 1}
    assert checkpoint.data["events"] == []
    loader.create_event.assert_not_called()
    loader.create_fight.assert_not_called()


def test_fighter_stage_deduplicates_and_respects_limit(tmp_path, config, monkeypatch):
    checkpoint = Checkpoint(tmp_path / "checkpoint.json", config)
    scraper = Mock()
    scraper.scrape_fighter_profile.return_value = {"name": "Fighter A"}
    monkeypatch.setattr(run_crawl, "UfcStatsScraper", Mock(return_value=scraper))
    loader = Mock()
    stats = run_crawl.crawl_stage(
        ["a", "a", "b"],
        "fighters",
        loader,
        checkpoint,
        workers=1,
        delay=0,
        limit=1,
    )
    assert stats["loaded"] == 1
    scraper.scrape_fighter_profile.assert_called_once_with("a")
    loader.create_fighter.assert_called_once_with({"name": "Fighter A"})
    assert checkpoint.data["fighters"] == ["a"]


def test_backfill_continues_after_failure_and_preserves_retry_eligibility(fight):
    loader = Mock()
    scraper = Mock()
    loader.backfill_candidates.side_effect = [
        [{"url": "a", "date": "2025-11-15"}, {"url": "b", "date": None}],
        [],
    ]
    scraper.scrape_fight_details.side_effect = [
        ScrapeError("temporary failure"),
        {**fight, "url": "b", "referee": None},
    ]
    stats = run_backfill.backfill(loader, scraper)
    assert stats == {"selected": 2, "updated": 1, "missing_referee": 1, "failed": 1}
    assert loader.create_fight.call_count == 1
    assert loader.create_fight.call_args.args[0]["url"] == "b"
    assert loader.create_fight.call_args.kwargs == {"enriched": True}
    loader.backfill_candidates.assert_called_with("b", 100, False)


def test_backfill_database_failure_is_reported_without_counting_update(fight):
    loader = Mock()
    loader.backfill_candidates.return_value = [{"url": fight["url"], "date": fight["date"]}]
    loader.create_fight.side_effect = RuntimeError("transaction failed")
    scraper = Mock()
    scraper.scrape_fight_details.return_value = fight
    assert run_backfill.backfill(loader, scraper, limit=1) == {
        "selected": 1,
        "updated": 0,
        "missing_referee": 0,
        "failed": 1,
    }


def test_backfill_dry_run_paginates_with_no_http_or_writes(monkeypatch):
    loader = Mock()
    loader.backfill_candidates.side_effect = [
        [{"url": "a", "date": None}],
        [{"url": "b", "date": None}],
    ]
    scraper = Mock()
    factory = Mock()
    monkeypatch.setattr(run_backfill, "UfcStatsScraper", factory)
    stats = run_backfill.backfill(loader, scraper, limit=2, refresh=True, dry_run=True, workers=4)
    assert stats == {"selected": 2, "updated": 0, "missing_referee": 0, "failed": 0}
    assert [c.args for c in loader.backfill_candidates.call_args_list] == [
        ("", 2, True),
        ("a", 1, True),
    ]
    scraper.scrape_fight_details.assert_not_called()
    loader.create_fight.assert_not_called()
    factory.assert_not_called()


def test_parallel_backfill_commits_on_coordinator_and_keeps_url_pagination(monkeypatch):
    coordinator = threading.get_ident()
    b_committed = threading.Event()
    start_together = threading.Barrier(2)
    sessions = []
    fetched = []
    committed = []

    class WorkerScraper:
        def __init__(self, delay):
            assert delay == 0.25
            self.owner = threading.get_ident()
            self.closed = False
            sessions.append(self)

        def scrape_fight_details(self, url, event_date=None):
            assert threading.get_ident() == self.owner != coordinator
            fetched.append(url)
            if url in ("a", "b"):
                start_together.wait(timeout=5)
            if url == "a":
                assert b_committed.wait(timeout=5)
            return {"url": url, "referee": "Ref"}

        def close(self):
            self.closed = True

    def commit(data, *, enriched):
        assert threading.get_ident() == coordinator
        assert enriched
        committed.append(data["url"])
        if data["url"] == "b":
            b_committed.set()

    loader = Mock()
    loader.backfill_candidates.side_effect = [
        [{"url": "a", "date": None}, {"url": "b", "date": None}],
        [{"url": "c", "date": None}],
    ]
    loader.create_fight.side_effect = commit
    monkeypatch.setattr(run_backfill, "UfcStatsScraper", WorkerScraper)
    stats = run_backfill.backfill(loader, Mock(), limit=3, workers=2, delay=0.25)
    assert stats == {"selected": 3, "updated": 3, "missing_referee": 0, "failed": 0}
    assert committed == ["b", "a", "c"]
    assert sorted(fetched) == ["a", "b", "c"]
    assert [call.args for call in loader.backfill_candidates.call_args_list] == [
        ("", 3, False),
        ("b", 1, False),
    ]
    assert len(sessions) == 2 and all(session.closed for session in sessions)


def test_parallel_backfill_retries_only_uncommitted_fights_on_resume(monkeypatch):
    pending = {"a", "b", "c"}
    scrape_failures, write_failures = {"a"}, {"b"}
    fetched = []

    def fetch(url, event_date=None):
        fetched.append(url)
        if url in scrape_failures:
            raise ScrapeError("temporary HTTP failure")
        return {"url": url, "referee": "Ref"}

    def commit(data, *, enriched):
        if data["url"] in write_failures:
            raise RuntimeError("temporary write failure")
        pending.remove(data["url"])

    loader = Mock()
    loader.backfill_candidates.side_effect = lambda after, limit, refresh: [
        {"url": url, "date": None} for url in sorted(pending) if url > after
    ][:limit]
    loader.create_fight.side_effect = commit
    monkeypatch.setattr(
        run_backfill,
        "UfcStatsScraper",
        lambda **kwargs: Mock(scrape_fight_details=fetch),
    )
    first = run_backfill.backfill(loader, Mock(), workers=2)
    assert first["failed"] == 2 and first["updated"] == 1
    assert pending == {"a", "b"}
    scrape_failures.clear()
    write_failures.clear()
    fetched.clear()
    second = run_backfill.backfill(loader, Mock(), workers=2)
    assert second["failed"] == 0 and second["updated"] == 2
    assert sorted(fetched) == ["a", "b"] and not pending


@pytest.mark.parametrize("args", [["--workers", "0"], ["--delay", "-1"]])
def test_backfill_rejects_invalid_concurrency(args):
    with pytest.raises(SystemExit) as error:
        run_backfill.main(args)
    assert error.value.code == 2


def test_backfill_cli_dry_run_does_not_modify_schema_or_metadata(monkeypatch, capsys):
    db, scraper, loader = Mock(), Mock(), Mock()
    db_context, scraper_context = MagicMock(), MagicMock()
    db_context.__enter__.return_value = db
    scraper_context.__enter__.return_value = scraper
    monkeypatch.setattr(run_backfill, "Neo4jConnection", Mock(return_value=db_context))
    monkeypatch.setattr(run_backfill, "UfcStatsScraper", Mock(return_value=scraper_context))
    monkeypatch.setattr(run_backfill, "Neo4jLoader", Mock(return_value=loader))
    monkeypatch.setattr(run_backfill, "load_config", Mock())
    loader.coverage.return_value = {"fights": 0}
    loader.backfill_candidates.return_value = []
    assert run_backfill.main(["--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["backfill"]["selected"] == 0
    db.setup_schema.assert_not_called()
    db.run_write.assert_not_called()
    loader.repair_local_metadata.assert_not_called()
    loader.create_fight.assert_not_called()
    scraper.scrape_fight_details.assert_not_called()
