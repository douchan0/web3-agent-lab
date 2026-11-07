"""Provision and archive an isolated Anvil experiment."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re
import signal
import sys
import time

from .analytics import export_run
from .archive import seal, sha256, trace_digest, verify, write_atomic
from .chain import ROOT
from .events import EventStore, read_events, write_json
from .experiment import run_market, validate_config, validate_news
from .report import report
from .model_agent import make_agents
from .study import generate

RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
RUNS = ROOT / "data/experiments"


def clock():
    return datetime.now(timezone.utc).isoformat()


def restart_data(run, archive_root=RUNS):
    if not RUN_ID.fullmatch(run):
        raise ValueError("invalid parent experiment ID")
    directory = archive_root / run
    verify(directory)
    status = json.loads((directory / "status.json").read_text())
    if status["state"] not in ("stopped", "complete") or status["completed_rounds"] < 1:
        raise ValueError("parent run needs a sealed terminal state and a completed round")
    config = json.loads((directory / "config.json").read_text())
    boundary = status["completed_rounds"]
    digest = trace_digest(read_events(directory), boundary)
    return config, {
        "parent": run, "parent_manifest_sha256": sha256(directory / "manifest.json"),
        "verified_prefix_rounds": boundary, "trace_sha256": digest,
        "mode": "new_chain_rebuild_prefix",
    }


def run(args):
    fixture = ROOT / "data/fixtures/news.json"
    build = ROOT / "build/contracts.json"
    archive_root = args.archive_root.resolve()
    parent, lineage = restart_data(args.restart_from, archive_root) if args.restart_from else (None, None)
    selected = sum(value is not None for value in (parent, args.config, args.config_snapshot))
    if selected > 1:
        raise ValueError("choose only one of --config, --config-snapshot or --restart-from")
    snapshot = json.loads(args.config_snapshot.read_text()) if args.config_snapshot else None
    if parent or snapshot:
        source = parent or snapshot
        config = source["experiment"]
        models = source["models"]
        order = args.order or source.get("order", "fixed")
        rounds = args.rounds or source["rounds"]
    else:
        config = json.loads((args.config or ROOT / "configs/experiment.json").read_text())
        models = json.loads((ROOT / "configs/models.example.json").read_text())
        order = args.order or "fixed"
        rounds = args.rounds
    if args.models:
        models = json.loads(args.models.read_text())
    if args.seed is not None:
        config["seed"] = args.seed
    if not rounds or not 1 <= rounds <= 10_000 or not RUN_ID.fullmatch(args.run_id):
        raise ValueError("expected 1–10000 rounds and a simple run ID")
    if not 1 <= args.checkpoint_every <= 10_000:
        raise ValueError("--checkpoint-every must be between 1 and 10000")
    if args.stop_after is not None and not 1 <= args.stop_after < rounds:
        raise ValueError("--stop-after must be a positive round before target")
    if lineage and (rounds <= lineage["verified_prefix_rounds"] or args.seed is not None or args.models
                    or (args.order and args.order != parent["order"])):
        raise ValueError("new run must extend the parent boundary with identical seed, model and order")
    news = json.loads(fixture.read_text())
    validate_config(config, models)
    if models["mode"] == "live" and not args.allow_model_calls:
        raise ValueError("live model requests require explicit --allow-model-calls")
    if lineage and models["mode"] == "live":
        raise ValueError("restart requires deterministic mock or fixture decisions")
    validate_news(news)
    if not build.exists():
        raise ValueError("compile the contracts first with npm run compile")
    versions = dict(contract_artifacts_sha256=sha256(build), fixture_sha256=sha256(fixture),
                    strategy_source_sha256=sha256(ROOT / "src/agents.py"),
                    engine_source_sha256=sha256(ROOT / "src/experiment.py"),
                    adapter_source_sha256=sha256(ROOT / "src/model_agent.py"))
    if parent and any(parent.get(key) != value for key, value in versions.items()):
        raise ValueError("code or inputs differ from parent checkpoint")
    directory = archive_root / args.run_id
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "config.json", dict(
        experiment=config, models=models, rounds=rounds, order=order, lineage=lineage,
        python=platform.python_version(), compiler=json.loads(build.read_text())["compiler"], **versions,
    ))
    write_json(directory / "news_fixture.json", news)
    state = dict(state="running", started_at=clock(), target_rounds=rounds, completed_rounds=0)
    status_path = directory / "status.json"
    write_atomic(status_path, state)
    requested = False
    started = time.monotonic()

    def interrupt(_signal, _frame):
        nonlocal requested
        requested = True

    def stopping(turn):
        return requested or turn == args.stop_after

    with EventStore(directory) as store:
        def checkpoint(turn, event_id, reserves, wallets, stop):
            if lineage and turn == lineage["verified_prefix_rounds"]:
                if trace_digest(read_events(directory), turn) != lineage["trace_sha256"]:
                    raise ValueError("new chain does not reproduce the parent market checkpoint")
                state["parent_prefix_verified"] = True
            state["completed_rounds"] = turn
            if turn == 1 or turn % args.checkpoint_every == 0 or stop or turn == rounds:
                store.sync()
                entry = dict(round=turn, event_id=event_id, reserves=reserves, wallets=wallets,
                             journal_bytes=(directory / "events.jsonl").stat().st_size)
                with (directory / "checkpoints.jsonl").open("a", encoding="utf-8") as output:
                    output.write(json.dumps(entry, ensure_ascii=False) + "\n")
                write_atomic(status_path, state)
                print(f"{directory.name}: {turn}/{rounds} rounds", file=sys.stderr, flush=True)

        previous = {sig: signal.signal(sig, interrupt) for sig in (signal.SIGTERM, signal.SIGINT)}
        try:
            completed = run_market(directory, store, config, news, rounds, order=order, checkpoint=checkpoint,
                                   stopping=stopping, agents=make_agents(models))
            store.sync()
        except BaseException as exc:
            store.record("error", error=type(exc).__name__, detail=str(exc))
            state.update(state="failed", finished_at=clock(), execution_seconds=round(time.monotonic()-started, 3))
            write_atomic(status_path, state)
            print(f"Run evidence: {directory}", file=sys.stderr)
            raise
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    state.update(state="exporting", execution_seconds=round(time.monotonic()-started, 3))
    write_atomic(status_path, state)
    try:
        events = read_events(directory)
        compact = args.compact or rounds > 100 or models["mode"] != "mock"
        export_run(directory, events, compact=compact)
        if completed == rounds and not compact:
            report(directory)
        generate(directory, events)
        state.update(state="complete" if completed == rounds else "stopped", finished_at=clock(),
                     total_seconds=round(time.monotonic()-started, 3))
        write_atomic(status_path, state)
        seal(directory)
    except BaseException:
        state.update(state="failed", finished_at=clock())
        write_atomic(status_path, state)
        raise
    print(directory)
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--config-snapshot", type=Path)
    parser.add_argument("--models", type=Path)
    parser.add_argument("--allow-model-calls", action="store_true")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--order", choices=("fixed", "rotate", "random"))
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--archive-root", type=Path, default=RUNS)
    parser.add_argument("--checkpoint-every", type=int, default=100)
    parser.add_argument("--stop-after", type=int)
    parser.add_argument("--restart-from", metavar="SEALED_RUN_ID")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
