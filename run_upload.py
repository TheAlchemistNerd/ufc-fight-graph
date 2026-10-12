"""Upload a validated backup directly to Google Drive, or wait for a crawl to finish."""

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import time
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

from run_backup import validate

logger = logging.getLogger(__name__)


class UploadError(RuntimeError):
    pass


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


def archive_manifest(path):
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        payload = archive.read("graph.json")
    if manifest.get("format_version") not in (1, 2) or hashlib.sha256(
        payload
    ).hexdigest() != manifest.get("sha256"):
        raise ValueError("Unsupported or damaged backup")
    validate(json.loads(payload), manifest)
    return manifest


class DriveUploader:
    @classmethod
    def from_environment(cls):
        return cls(
            os.getenv("UFC_DRIVE_REMOTE"),
            os.getenv("UFC_DRIVE_FOLDER_ID"),
            os.getenv("RCLONE_EXE", "rclone"),
            os.getenv("RCLONE_CONFIG"),
        )

    def __init__(self, remote, folder_id, executable="rclone", config=None):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*:", remote or ""):
            raise ValueError(
                "Set UFC_DRIVE_REMOTE to a configured rclone remote, e.g. ufc-backups:"
            )
        if not re.fullmatch(r"[A-Za-z0-9_-]+", folder_id or ""):
            raise ValueError("Set UFC_DRIVE_FOLDER_ID to the destination Google Drive folder ID")
        self.remote, self.folder_id = remote, folder_id
        self.command = [
            str(executable),
            "--drive-root-folder-id",
            folder_id,
            "--contimeout",
            "30s",
            "--timeout",
            "2m",
            "--retries",
            "5",
            "--low-level-retries",
            "10",
            "--retries-sleep",
            "10s",
            "--stats",
            "0",
        ]
        if config:
            self.command.extend(["--config", str(config)])

    def run(self, *arguments):
        try:
            process = subprocess.run(
                self.command + list(arguments),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=1800,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise UploadError(f"Could not run rclone: {exc}") from exc
        if process.returncode:
            raise UploadError(f"rclone {arguments[0]} failed: {process.stderr.strip()[-1500:]}")
        return process.stdout

    def upload(self, path):
        path = Path(path).resolve()
        manifest = archive_manifest(path)
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "md5").hexdigest()
        size = path.stat().st_size
        destination = self.remote + path.name
        # A replay skips identical bytes; a conflicting existing name is preserved.
        self.run("copyto", str(path), destination, "--checksum", "--immutable")
        try:
            remote = json.loads(
                self.run("lsjson", destination, "--stat", "--hash", "--hash-type", "MD5")
            )
            hashes = {key.lower(): value.lower() for key, value in remote.get("Hashes", {}).items()}
            if (
                remote.get("IsDir")
                or remote.get("Name") != path.name
                or remote.get("Size") != size
                or hashes.get("md5") != digest
                or not remote.get("ID")
            ):
                raise UploadError(
                    "Google Drive readback did not match the backup name, size, checksum and file ID"
                )
        except (ValueError, AttributeError, TypeError) as exc:
            raise UploadError("Invalid Google Drive verification response") from exc
        receipt = {
            "status": "completed",
            "archive": str(path),
            "remote": destination,
            "folder_id": self.folder_id,
            "file_id": remote["ID"],
            "bytes": size,
            "md5": digest,
            "graph_sha256": manifest["sha256"],
            "nodes": manifest["nodes"],
            "relationships": manifest["relationships"],
            "verified_utc": datetime.now(timezone.utc).isoformat(),
            "url": "https://drive.google.com/file/d/" + quote(remote["ID"], safe="") + "/view",
        }
        save_json(path.with_suffix(".drive.json"), receipt)
        return receipt


@contextmanager
def watcher_lock(path):
    """OS-owned lock: released on exit or crash, including on Windows."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as lock:
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("An upload watcher is already running for this crawl") from exc
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def completed_archive(state):
    if state.get("status") != "completed" or state.get("exit_code") != 0:
        raise ValueError("The crawl must finish successfully before uploading its final snapshot")
    path = Path(state["latest_backup"]).resolve()
    manifest = archive_manifest(path)
    stamp = manifest["created_utc"]
    fmt = "%Y%m%dT%H%M%S%fZ" if len(stamp) > 16 else "%Y%m%dT%H%M%SZ"
    created = datetime.strptime(stamp, fmt).replace(tzinfo=timezone.utc)
    if (
        not datetime.fromisoformat(state["started_utc"])
        <= created
        <= datetime.fromisoformat(state["finished_utc"])
    ):
        raise ValueError("Backup timestamp does not belong to this completed crawl")
    return path


def watch_crawl(state_path, uploader, *, poll_seconds=60, retry_seconds=300):
    state_path = Path(state_path).resolve()
    progress_path = state_path.with_suffix(".upload.json")
    with watcher_lock(state_path.with_suffix(".upload.lock")):
        progress = {"pid": os.getpid(), "status": "waiting"}
        try:
            initial = json.loads(state_path.read_text(encoding="utf-8"))
            run_id = initial["started_utc"]
            progress["crawl_started_utc"] = run_id
            save_json(progress_path, progress)
            while True:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if state["started_utc"] != run_id:
                    raise ValueError("Crawl run changed; start a watcher for the new run")
                if state["status"] == "failed":
                    raise ValueError(
                        "Crawl failed; final upload waits for a successful resumed crawl"
                    )
                if state["status"] == "running":
                    time.sleep(poll_seconds)
                    continue
                path = completed_archive(state)
                try:
                    progress.update(status="uploading", archive=str(path))
                    save_json(progress_path, progress)
                    receipt = uploader.upload(path)
                except UploadError as exc:
                    progress.update(status="retrying", error=str(exc))
                    save_json(progress_path, progress)
                    logger.warning("%s; retrying in %s seconds", exc, retry_seconds)
                    time.sleep(retry_seconds)
                    continue
                # Only the crawler writes its state; upload receipts have their own file.
                progress.pop("error", None)
                save_json(progress_path, {**progress, **receipt, "status": "completed"})
                return receipt
        except Exception as exc:
            progress.update(
                status="failed", error=str(exc), finished_utc=datetime.now(timezone.utc).isoformat()
            )
            save_json(progress_path, progress)
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path)
    parser.add_argument("--watch-state", type=Path)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--poll-seconds", type=float, default=60)
    parser.add_argument("--retry-seconds", type=float, default=300)
    args = parser.parse_args(argv)
    if bool(args.archive) == bool(args.watch_state):
        parser.error("Choose either an archive or --watch-state")
    if args.poll_seconds <= 0 or args.retry_seconds <= 0:
        parser.error("Poll and retry intervals must be positive")
    load_dotenv(args.env_file, override=False)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    uploader = DriveUploader.from_environment()
    receipt = (
        watch_crawl(
            args.watch_state,
            uploader,
            poll_seconds=args.poll_seconds,
            retry_seconds=args.retry_seconds,
        )
        if args.watch_state
        else uploader.upload(args.archive)
    )
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
