"""Atomic checkpoints containing only committed work, scoped to a database."""

import hashlib
import json
from pathlib import Path


class Checkpoint:
    def __init__(self, path, config):
        self.path = Path(path)
        self.target = hashlib.sha256(f"{config.uri}|{config.database}".encode()).hexdigest()
        self.data = {"version": 1, "target": self.target, "events": [], "fighters": []}
        if self.path.exists():
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(saved, dict) or saved.get("version") != 1:
                raise ValueError("Legacy checkpoint is unreliable; use --reset to rebuild it")
            if saved.get("target") != self.target:
                raise ValueError(
                    "Checkpoint belongs to another database; use a different --checkpoint path"
                )
            self.data = saved

    def contains(self, stage, url):
        return url in self.data[stage]

    def mark(self, stage, url):
        if url not in self.data[stage]:
            self.data[stage].append(url)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        tmp.replace(self.path)
