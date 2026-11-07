"""The append-only source for all derived run outputs."""
import json
import os
from pathlib import Path
from datetime import datetime, timezone


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_events(directory):
    return [json.loads(line) for line in (directory / "events.jsonl").read_text(encoding="utf-8").splitlines()]


class EventStore:
    def __init__(self, directory: Path):
        self.file = (directory / "events.jsonl").open("x", encoding="utf-8")
        self.run_id = directory.name
        self.sequence = 0
        self.round = 0
        self.simulated_at = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.file.close()

    def sync(self):
        self.file.flush()
        os.fsync(self.file.fileno())

    def record(self, kind, *, source=None, **fields):
        self.sequence += 1
        event = {
            "id": f"E{self.sequence:06d}", "run_id": self.run_id, "round": self.round,
            "simulated_at": self.simulated_at, "recorded_at": datetime.now(timezone.utc).isoformat(),
            "kind": kind, "source": source or "experiment_controller", **fields,
        }
        self.file.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.file.flush()
        return event["id"]
