"""CLI: provision, run and archive a new local experiment."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import sys

from .chain import ROOT
from .events import EventStore, read_events, write_json
from .experiment import run_market, validate_config, validate_news
from .analytics import export_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/experiment.json")
    parser.add_argument("--models", type=Path, default=ROOT / "configs/models.example.json")
    args = parser.parse_args()
    if not 1 <= args.rounds <= 10_000 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", args.run_id):
        parser.error("expected 1-10000 rounds and a simple run ID")
    config = json.loads(args.config.read_text())
    models = json.loads(args.models.read_text())
    fixture = ROOT / "data/fixtures/news.json"
    news = json.loads(fixture.read_text())
    validate_config(config, models)
    validate_news(news)
    build = ROOT / "build/contracts.json"
    if not build.exists():
        parser.error("compile the contracts first with npm run compile")
    directory = ROOT / "data/experiments" / args.run_id
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "config.json", {
        "experiment": config, "models": models, "rounds": args.rounds,
        "python": platform.python_version(), "compiler": json.loads(build.read_text())["compiler"],
        "contract_artifacts_sha256": hashlib.sha256(build.read_bytes()).hexdigest(),
        "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "strategy_source_sha256": hashlib.sha256((ROOT / "src/agents.py").read_bytes()).hexdigest(),
    })
    try:
        with EventStore(directory) as store:
            try:
                run_market(directory, store, config, news, args.rounds)
            except BaseException as exc:
                store.record("error", error=repr(exc))
                raise
        export_run(directory, read_events(directory))
    except BaseException:
        print(f"Run evidence: {directory}", file=sys.stderr)
        raise
    print(directory)


if __name__ == "__main__":
    main()
