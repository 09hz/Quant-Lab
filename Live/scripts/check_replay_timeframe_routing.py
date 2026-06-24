from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.replay.timeframe_routing import describe_timeframe_route, normalize_replay_timeframe


def _extract_watch_loader_block(callbacks_path: Path) -> str:
    text = callbacks_path.read_text(encoding="utf-8")
    marker = "def load_watch_symbol_from_request("
    start = text.find(marker)
    if start < 0:
        return ""
    end = text.find("\n    @app.callback", start + len(marker))
    if end < 0:
        end = len(text)
    return text[start:end]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeframe", default="1 hour")
    parser.add_argument("--scan-callbacks", action="store_true")
    args = parser.parse_args()

    route = describe_timeframe_route(args.timeframe)
    print(f"input={route['input']!r}")
    print(f"normalized={route['normalized']!r}")
    print(f"cache_key={route['cache_key']!r}")

    samples = ["1 min", "15 min", "30 min", "1h", "1 hour", "1 day"]
    print("\nNormalization samples:")
    for sample in samples:
        print(f"  {sample!r} -> {normalize_replay_timeframe(sample)!r}")

    if args.scan_callbacks:
        callbacks_path = ROOT / "callbacks.py"
        block = _extract_watch_loader_block(callbacks_path)
        print("\nCallback scan:")
        print(f"  load_watch_symbol_from_request found: {bool(block)}")
        print(f"  normalize_replay_timeframe wired: {'normalize_replay_timeframe' in block}")
        suspicious = []
        for lineno, line in enumerate(block.splitlines(), start=1):
            stripped = line.strip()
            if '"1 min"' in stripped or "'1 min'" in stripped:
                if "normalize_replay_timeframe" not in stripped and 'or "1 min"' not in stripped:
                    suspicious.append((lineno, stripped))
        if suspicious:
            print("  suspicious hardcoded 1 min lines:")
            for lineno, line in suspicious:
                print(f"    {lineno}: {line}")
        else:
            print("  no suspicious hardcoded 1 min loader lines found")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
