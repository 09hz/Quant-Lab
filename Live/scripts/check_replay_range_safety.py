from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _bootstrap_live_path() -> None:
    here = Path(__file__).resolve()
    live_root = here.parents[1]
    if str(live_root) not in sys.path:
        sys.path.insert(0, str(live_root))


_bootstrap_live_path()

from services.replay.range_safety import format_replay_range_decision, validate_interactive_replay_range


def main() -> int:
    parser = argparse.ArgumentParser(description="Check interactive Replay range safety limits.")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--timeframe", default="1 min")
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-06-23")
    parser.add_argument("--mode", default="range")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    decision = validate_interactive_replay_range(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start_date=args.start,
        end_date=args.end,
        load_mode=args.mode,
    )

    if args.as_json:
        print(json.dumps(decision.to_dict(), indent=2))
    else:
        print(format_replay_range_decision(decision))
        print(f"allowed={decision.allowed} reason={decision.reason}")

    return 0 if decision.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
