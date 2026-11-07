"""Small landing-page projection from completed experiment artifacts."""
import json


def load(directory, name):
    path = directory / name
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def summary(directory, config):
    series = load(directory, "prices.json")
    result = load(directory, "costs_and_stats.json")
    fills = sum(row["trades"] for row in series)
    rejected = sum(n for role in result["roles"].values() for code, n in role["risk"].items()
                   if code not in ("hold", "accepted"))
    names = {"first-10":"深池验证", "first-100":"入门回放", "shallow-10":"浅池对照",
             "stage2-rotate-1000":"长程基准"}
    label = f"{len(series):,} 轮{names.get(directory.name, '实验 · ' + directory.name)}"
    return dict(id=directory.name, label=label, rounds=len(series), fills=fills, rejected=rejected,
                mode=config["models"]["mode"], cost_usd=result["costs"]["cost_usd"])


def sample_trade(root, run):
    path = root / run["id"] / "events.jsonl"
    if not path.is_file() or path.is_symlink():
        return None
    with path.open(encoding="utf-8") as events:
        for line in events:
            event = json.loads(line)
            if event["kind"] == "swap_receipt" and event["success"]:
                return dict(run=run["id"], label=run["label"], event=event["id"],
                            round=event["round"], block=event["receipt"]["blockNumber"],
                            amount_in_raw=event["amount_in_raw"], amount_out_raw=event["amount_out_raw"],
                            token_in=event["token_in"])
    return None


def dashboard(root, run_id_pattern):
    candidates = []
    if not root.is_dir():
        return dict(featured=None, sample=None, runs=[])
    for directory in root.iterdir():
        if not run_id_pattern.fullmatch(directory.name) or not directory.is_dir() or directory.is_symlink():
            continue
        try:
            status = directory / "status.json"
            if status.exists() and load(directory, status.name)["state"] != "complete":
                continue
            config = load(directory, "config.json")
            if type(config["rounds"]) is not int or config["rounds"] < 1:
                continue
            if not (directory / "events.jsonl").is_file() or (directory / "events.jsonl").is_symlink():
                continue
            candidates.append((directory, config))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    candidates.sort(key=lambda item: (-item[1]["rounds"], item[0].name))
    results = {}
    for directory, config in candidates:
        if results and directory.name not in {"first-100", "shallow-10", "first-10"}:
            continue
        try:
            results[directory.name] = summary(directory, config)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    featured = next(iter(results.values()), None)
    baseline = results.get("first-100", featured)
    try:
        example = sample_trade(root, baseline) if baseline else None
    except (OSError, ValueError, KeyError, TypeError):
        example = None
    other_runs = [row for row in results.values() if row != featured]
    return dict(featured=featured, sample=example, runs=other_runs)
