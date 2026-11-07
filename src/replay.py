"""Reconstruct and compare deterministic market traces from archived runs."""
import argparse
from pathlib import Path

from .events import read_events

DETERMINISTIC_EVENTS = {
    "news", "reference", "round_open", "decision", "risk", "swap_receipt", "round_close",
}
CHAIN_FIELDS = {
    "receipt", "tx_hash", "gas_cost_wei", "gas_used", "eth_before_wei", "eth_after_wei", "checks",
}
RUN_FIELDS = {"run_id", "recorded_at"}


def trace(events, rounds):
    return [
        {key: value for key, value in event.items()
         if key not in RUN_FIELDS and not (event["kind"] == "swap_receipt" and key in CHAIN_FIELDS)}
        for event in events if 1 <= event["round"] <= rounds and event["kind"] in DETERMINISTIC_EVENTS
    ]


def compare(left, right, rounds):
    return trace(left, rounds) == trace(right, rounds)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--rounds", type=int, required=True)
    args = parser.parse_args()
    left, right = read_events(args.left), read_events(args.right)
    if not all(any(event["kind"] == "run_complete" and event["rounds"] >= args.rounds for event in run)
               for run in (left, right)) or args.rounds < 1:
        parser.error("both archives must contain the requested number of complete rounds")
    if not compare(left, right, args.rounds):
        parser.exit(1, "deterministic traces differ\n")
    print(f"{args.rounds} deterministic rounds match")


if __name__ == "__main__":
    main()
