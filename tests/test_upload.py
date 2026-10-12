"""Direct-upload integrity and unattended completion behavior, without Google credentials."""

import hashlib
import json
import subprocess
import zipfile
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

import run_crawl
import run_upload
from run_upload import (
    DriveUploader,
    UploadError,
    completed_archive,
    save_json,
    watch_crawl,
    watcher_lock,
)


@pytest.fixture
def archive(tmp_path):
    path = tmp_path / "backup with spaces.zip"
    payload = json.dumps({"nodes": [], "relationships": []}).encode()
    manifest = {
        "format_version": 2,
        "created_utc": "20261012T210000000000Z",
        "nodes": 0,
        "relationships": 0,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("graph.json", payload)
        z.writestr("manifest.json", json.dumps(manifest))
    return path


def remote_metadata(path):
    return {
        "ID": "verified-file",
        "Name": path.name,
        "IsDir": False,
        "Size": path.stat().st_size,
        "Hashes": {"MD5": hashlib.md5(path.read_bytes()).hexdigest()},
    }


def completed_state(archive):
    return {
        "status": "completed",
        "exit_code": 0,
        "latest_backup": str(archive),
        "started_utc": "2026-10-12T18:00:00+00:00",
        "finished_utc": "2026-10-12T22:00:00+00:00",
    }


def test_upload_reads_back_checksums_and_preserves_existing_files(archive, monkeypatch):
    runner = Mock(
        side_effect=[
            SimpleNamespace(returncode=0, stdout=""),
            SimpleNamespace(returncode=0, stdout=json.dumps(remote_metadata(archive))),
        ]
    )
    monkeypatch.setattr(subprocess, "run", runner)
    uploader = DriveUploader(
        "backups:", "folder-id", executable="C:/tools with spaces/rclone.exe", config="private.conf"
    )
    receipt = uploader.upload(archive)
    copy_args = runner.call_args_list[0].args[0]
    assert str(archive) in copy_args
    assert copy_args[0] == "C:/tools with spaces/rclone.exe"
    assert "--immutable" in copy_args and "--checksum" in copy_args
    assert copy_args[copy_args.index("--drive-root-folder-id") + 1] == "folder-id"
    assert receipt["file_id"] == "verified-file"
    assert json.loads(archive.with_suffix(".drive.json").read_text()) == receipt
    assert "private.conf" not in json.dumps(receipt)


@pytest.mark.parametrize(
    "change",
    [
        {"Size": 1},
        {"Name": "wrong.zip"},
        {"IsDir": True},
        {"ID": ""},
        {"Hashes": {}},
        {"Hashes": {"md5": "wrong"}},
    ],
)
def test_mismatched_remote_never_produces_success_receipt(archive, change):
    uploader = DriveUploader("backups:", "folder-id")
    uploader.run = Mock(side_effect=["", json.dumps({**remote_metadata(archive), **change})])
    with pytest.raises(UploadError, match="readback"):
        uploader.upload(archive)
    assert not archive.with_suffix(".drive.json").exists()


def test_damaged_archive_is_rejected_before_upload(archive):
    with zipfile.ZipFile(archive) as z:
        graph = z.read("graph.json")
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("graph.json", graph)
        z.writestr("manifest.json", json.dumps({"format_version": 2, "sha256": "bad"}))
    uploader = DriveUploader("backups:", "folder-id")
    uploader.run = Mock()
    with pytest.raises(ValueError, match="damaged"):
        uploader.upload(archive)
    uploader.run.assert_not_called()


def test_network_failure_retains_local_backup(archive, monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(return_value=SimpleNamespace(returncode=1, stderr="temporary network failure")),
    )
    with pytest.raises(UploadError, match="temporary network"):
        DriveUploader("backups:", "folder-id").upload(archive)
    assert archive.exists()
    assert not archive.with_suffix(".drive.json").exists()


@pytest.mark.parametrize(
    "change", [{"exit_code": 1}, {"status": "failed"}, {"started_utc": "2026-10-13T00:00:00+00:00"}]
)
def test_failed_or_stale_snapshot_is_not_a_final_backup(archive, change):
    with pytest.raises(ValueError):
        completed_archive({**completed_state(archive), **change})


def test_watcher_waits_for_success_then_records_upload(archive, monkeypatch):
    state_path = archive.parent / "crawl-run.json"
    complete = completed_state(archive)
    save_json(state_path, {**complete, "status": "running"})
    uploader = Mock()
    uploader.upload.return_value = {"file_id": "verified-file", "status": "completed"}

    def finish(_):
        uploader.upload.assert_not_called()
        save_json(state_path, complete)

    monkeypatch.setattr(run_upload.time, "sleep", finish)
    watch_crawl(state_path, uploader, poll_seconds=1)
    assert json.loads(state_path.read_text()) == complete
    progress = json.loads(state_path.with_suffix(".upload.json").read_text())
    assert progress["status"] == "completed"
    assert progress["file_id"] == "verified-file"


def test_watcher_retries_failed_upload_without_changing_archive(archive, monkeypatch):
    state_path = archive.parent / "crawl-run.json"
    save_json(state_path, completed_state(archive))
    uploader = Mock()
    uploader.upload.side_effect = [
        UploadError("network unavailable"),
        {"file_id": "verified-file", "status": "completed"},
    ]
    sleep = Mock()
    monkeypatch.setattr(run_upload.time, "sleep", sleep)
    watch_crawl(state_path, uploader, retry_seconds=1)
    assert [call.args[0] for call in uploader.upload.call_args_list] == [archive, archive]
    sleep.assert_called_once_with(1)
    progress = json.loads(state_path.with_suffix(".upload.json").read_text())
    assert progress["status"] == "completed"
    assert "error" not in progress


def test_watcher_preserves_a_new_crawl_state(archive):
    state_path = archive.parent / "crawl-run.json"
    save_json(state_path, completed_state(archive))
    new_state = {"status": "running", "started_utc": "2026-10-13T00:00:00+00:00"}

    def upload(_):
        save_json(state_path, new_state)
        return {"file_id": "verified-file", "status": "completed"}

    watch_crawl(state_path, SimpleNamespace(upload=upload))
    assert json.loads(state_path.read_text()) == new_state


def test_duplicate_watcher_lock_is_rejected_and_released(tmp_path):
    path = tmp_path / "watch.lock"
    with watcher_lock(path):
        with pytest.raises(RuntimeError, match="already running"), watcher_lock(path):
            pass
    with watcher_lock(path):
        pass


def test_crawl_upload_requires_backup_path():
    with pytest.raises(SystemExit) as error:
        run_crawl.main(["--upload-drive"])
    assert error.value.code == 2


@pytest.mark.parametrize("problem", ["crawl_failed", "new_run", "damaged_state", "stale_archive"])
def test_watcher_records_terminal_failures(archive, monkeypatch, problem):
    state_path = archive.parent / "crawl-run.json"
    state = {**completed_state(archive), "status": "running"}
    save_json(state_path, state)

    def change_state(_):
        if problem == "damaged_state":
            state_path.write_text("broken JSON")
        elif problem == "new_run":
            save_json(state_path, {**state, "started_utc": "2026-10-13T00:00:00+00:00"})
        elif problem == "stale_archive":
            save_json(
                state_path, {**completed_state(archive), "finished_utc": state["started_utc"]}
            )
        else:
            save_json(state_path, {**state, "status": "failed"})

    monkeypatch.setattr(run_upload.time, "sleep", change_state)
    uploader = Mock()
    with pytest.raises(ValueError):
        watch_crawl(state_path, uploader)
    progress = json.loads(state_path.with_suffix(".upload.json").read_text())
    assert progress["status"] == "failed"
    assert progress["error"] and progress["finished_utc"]
    uploader.upload.assert_not_called()


@pytest.mark.parametrize("failed_stage", [None, "events", "details", "fighters"])
def test_crawl_uploads_only_after_all_stages_succeed(archive, monkeypatch, failed_stage):
    events = {"loaded": 1, "failed": int(failed_stage == "events")}
    details = {"updated": 1, "failed": int(failed_stage == "details")}
    fighters = {"loaded": 1, "failed": int(failed_stage == "fighters")}
    uploader = Mock()
    uploader.upload.return_value = {"file_id": "verified-file"}
    monkeypatch.setattr(run_crawl, "load_config", Mock())
    monkeypatch.setattr(run_crawl, "Checkpoint", Mock())
    monkeypatch.setattr(run_crawl, "Neo4jConnection", MagicMock())
    monkeypatch.setattr(run_crawl, "UfcStatsScraper", MagicMock())
    monkeypatch.setattr(run_crawl, "Neo4jLoader", Mock())
    monkeypatch.setattr(run_crawl, "crawl_stage", Mock(side_effect=[events, fighters]))
    monkeypatch.setattr(run_crawl, "backfill", Mock(return_value=details))
    export = Mock(return_value=archive)
    monkeypatch.setattr(run_crawl, "backup", export)
    monkeypatch.setattr(DriveUploader, "from_environment", Mock(return_value=uploader))
    result = run_crawl.main(["--backup-dir", str(archive.parent), "--upload-drive"])
    assert result == int(failed_stage is not None)
    export.assert_called_once()
    if failed_stage:
        uploader.upload.assert_not_called()
    else:
        uploader.upload.assert_called_once_with(archive)
