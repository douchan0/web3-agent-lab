"""Read-only teaching UI. Serve only public project artifacts on IPv4 loopback."""
import argparse
from collections import defaultdict
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import re
from urllib.parse import parse_qs, urlsplit

from .analytics import candles, summarize
from .chain import ROOT
from .reading import document

RUNS = ROOT / "data/experiments"
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
STATIC = {"index.html", "lab.js", "lab.css", "math.mjs"}
PUBLIC_CODE = {"src/experiment.py", "src/execution.py", "src/events.py", "src/analytics.py", "contracts/Market.sol"}
PUBLIC_ARCHIVE = {"events.jsonl", "config.json", "story.md", "research.md", "report.md", "manifest.json", "status.json"}
TOPICS = {
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef": "Transfer",
    "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925": "Approval",
}


def decoded_logs(event, contracts):
    rows = []
    tokens = {address.lower(): symbol for symbol, address in contracts.get("tokens", {}).items()}
    for log in event.get("receipt", {}).get("logs", []):
        topic = log["topics"][0] if log["topics"] else None
        words = [int(log["data"][i:i+64], 16) for i in range(2, len(log["data"]), 64)]
        addresses = ["0x" + value[-40:] for value in log["topics"][1:]]
        address = log["address"].lower()
        name = TOPICS.get(topic, "Unknown")
        if address == contracts.get("pool", "").lower():
            if event["kind"] == "swap_receipt" and len(words) == 5:
                name = "Swap"
            if event.get("operation") == "seed" and len(words) == 2:
                name = "Seed"
        rows.append(dict(name=name, emitter=address, token=tokens.get(address), addresses=addresses,
                         raw_values=[str(word) for word in words], topic=topic))
    return rows


class Journal:
    def __init__(self, path):
        self.path = path
        self.rounds = defaultdict(list)
        self.lookup = {}
        self.hashes = {}
        self.contracts = {}
        self.participants = {}
        self.overview = None
        with path.open("rb") as stream:
            while True:
                offset = stream.tell()
                line = stream.readline()
                if not line or not line.endswith(b"\n"):
                    break
                event = json.loads(line)
                turn = event["round"]
                self.rounds[turn].append(offset)
                self.lookup[event["id"]] = turn
                if "receipt" in event:
                    self.hashes[event["tx_hash"].lower()] = event["id"]
                if event["kind"] == "market_open":
                    self.contracts = {key: event[key] for key in ("pool", "tokens", "reserves", "balances")}
                if event["kind"] == "participants":
                    self.participants = {key: event[key] for key in ("roles", "models")}

    def round_events(self, turn):
        events = []
        with self.path.open("rb") as stream:
            for offset in self.rounds.get(turn, []):
                stream.seek(offset)
                event = json.loads(stream.readline())
                if "receipt" in event:
                    event["decoded_logs"] = decoded_logs(event, self.contracts)
                events.append(event)
        return events

    def series(self):
        if self.overview is not None:
            return self.overview
        # Only a compact projection is retained after the first index build.
        events = []
        volume = defaultdict(int)
        markers = defaultdict(list)
        news = defaultdict(list)
        with self.path.open("rb") as stream:
            for line in stream:
                if not line.endswith(b"\n"):
                    break
                event = json.loads(line)
                events.append(event)
                turn = event["round"]
                if event["kind"] == "news":
                    news[turn].append([event["id"], event["title"], event["news_id"]])
                if event["kind"] == "swap_receipt" and event["success"]:
                    direction = "sell" if event["token_in"] == "RISK" else "buy"
                    volume[turn] += int(event["amount_in_raw"] if direction == "sell" else event["amount_out_raw"])
                    markers[turn].append([event["id"], event["role"], direction, event["price_susd_per_risk"]])
        summary = summarize(events)
        rows = [[c["round"], c["open"], c["high"], c["low"], c["close"], c["reference"],
                 str(volume[c["round"]]), news[c["round"]], markers[c["round"]]] for c in candles(events)]
        roles = {role: [[p["risk_raw"], p["susd_raw"], p["nav"], p["max_drawdown"]] for p in stats["positions"]]
                 for role, stats in summary["roles"].items()}
        self.overview = dict(rows=rows, roles=roles, participants=self.participants,
                             contracts=self.contracts, costs=summary["costs"])
        return self.overview


@lru_cache(maxsize=8)
def cached_journal(path, size, modified):
    return Journal(path)


def journal(run):
    if not RUN_ID.fullmatch(run):
        raise FileNotFoundError(run)
    directory = RUNS / run
    path = directory / "events.jsonl"
    if directory.is_symlink() or path.is_symlink():
        raise FileNotFoundError(run)
    stat = path.stat()
    return cached_journal(path, stat.st_size, stat.st_mtime_ns)


class Handler(BaseHTTPRequestHandler):
    def send_body(self, body, mime):
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, value):
        self.send_body(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(),
                       "application/json; charset=utf-8")

    def send_path(self, path, mime=None):
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError(path)
        if path.suffix == ".md" and not mime:
            self.send_body(document(path.read_text(encoding="utf-8")), "text/html; charset=utf-8")
        else:
            self.send_body(path.read_bytes(), mime or mimetypes.guess_type(path)[0] or "text/plain; charset=utf-8")

    def do_GET(self):
        allowed_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if self.headers.get("Host") not in allowed_hosts:
            self.send_error(403)
            return
        location = urlsplit(self.path)
        path = location.path
        try:
            if path == "/" or path[1:] in STATIC:
                file = path[1:] or "index.html"
                self.send_path(ROOT / "app/lab" / file)
            elif path == "/api/runs":
                self.send_json(sorted(d.name for d in RUNS.iterdir()
                                      if RUN_ID.fullmatch(d.name) and not d.is_symlink()
                                      and (d / "events.jsonl").is_file()))
            elif path == "/api/revert-example":
                example = Journal(ROOT / "tests/chain-evidence/events.jsonl")
                self.send_json([event for event in example.round_events(0) if event["kind"] == "swap_receipt"])
            elif path.startswith("/api/run/"):
                self.api(path.split("/")[3:], parse_qs(location.query))
            elif path.startswith("/artifact/"):
                run, file = path.split("/")[2:]
                if file not in PUBLIC_ARCHIVE:
                    raise FileNotFoundError(file)
                journal(run)
                self.send_path(RUNS / run / file, None if file.endswith(".md") else "text/plain; charset=utf-8")
            elif path.startswith("/project/"):
                file = path.removeprefix("/project/")
                if file not in PUBLIC_CODE and not re.fullmatch(r"docs/course/[a-z0-9-]+\.md|docs/user-manual\.md", file):
                    raise FileNotFoundError(file)
                self.send_path(ROOT / file, None if file.endswith(".md") else "text/plain; charset=utf-8")
            else:
                raise FileNotFoundError(path)
        except (FileNotFoundError, ValueError, KeyError, IndexError):
            self.send_error(404)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def api(self, parts, query):
        run, operation = parts
        archive = journal(run)
        if operation == "overview":
            self.send_json(archive.series())
        elif operation == "round":
            turn = int(query["n"][0])
            if turn not in archive.rounds:
                raise FileNotFoundError(turn)
            self.send_json(archive.round_events(turn))
        elif operation == "locate":
            key = query["key"][0].strip()
            event_id = archive.hashes.get(key.lower(), key.upper())
            self.send_json(dict(id=event_id, round=archive.lookup[event_id]))
        else:
            raise FileNotFoundError(operation)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    port = parser.parse_args().port
    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
