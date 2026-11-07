"""Integrity manifests and boundary checkpoints for local experiments."""
import argparse
import hashlib
import json
from pathlib import Path

from .events import write_json
from .replay import trace


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_atomic(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    write_json(temp, value)
    temp.replace(path)


def seal(directory):
    files = sorted(path for path in directory.iterdir() if path.is_file() and path.name != "manifest.json")
    write_atomic(directory / "manifest.json", {
        "schema": 1,
        "files": {path.name: dict(bytes=path.stat().st_size, sha256=sha256(path)) for path in files},
    })


def verify(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest["schema"] != 1:
        raise ValueError("unknown manifest schema")
    if not {"events.jsonl", "config.json", "status.json"} <= manifest["files"].keys():
        raise ValueError("archive manifest lacks core evidence")
    for name, metadata in manifest["files"].items():
        path = directory / name
        if name != path.name or path.is_symlink() or path.stat().st_size != metadata["bytes"] or sha256(path) != metadata["sha256"]:
            raise ValueError(f"archive integrity mismatch: {name}")
    return len(manifest["files"])


def trace_digest(events, rounds):
    payload = json.dumps(trace(events, rounds), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    directory = parser.parse_args().directory
    print(f"{directory.name}: {verify(directory)} verified artifacts")
