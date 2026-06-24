from __future__ import annotations

from pathlib import Path
import sys


def main() -> int:
    live_dir = Path(__file__).resolve().parents[1]
    repo_root = live_dir.parent
    for path in (str(live_dir), str(repo_root)):
        if path not in sys.path:
            sys.path.insert(0, path)

    replay_path = live_dir / "services" / "replay_service.py"
    callback_path = live_dir / "callbacks.py"

    text = replay_path.read_text(encoding="utf-8")
    callback_text = callback_path.read_text(encoding="utf-8")

    required = [
        "normalize_replay_timeframe",
        "load_timeframe = normalize_replay_timeframe(timeframe or \"1 min\")",
        "is_one_min_source",
        "timeframe=load_timeframe",
        "if is_one_min_source and self._is_historical_replay_date(day):",
        "self.current_timeframe = load_timeframe",
        "def _prepare_history_for_timeframe(",
        "return self._prepare_history_for_timeframe(cached, replay_date, timeframe)",
        "self._prepare_history_for_timeframe(hist, replay_date, timeframe)",
    ]

    missing = [item for item in required if item not in text]

    if 'load_timeframe = "1 min"' in text:
        missing.append('hardcoded load_timeframe = "1 min" is still present')

    stale_prepare = [
        "return self._prepare_history_for_replay_date(cached, replay_date)",
        "prepared = self._prepare_history_for_replay_date(hist, replay_date)",
        "hist = self._prepare_history_for_replay_date(hist, replay_date)",
    ]
    for marker in stale_prepare:
        if marker in text:
            missing.append(f"stale timeframe-blind prepare call remains: {marker}")

    if "raw 1-min bars" in callback_text:
        missing.append('callbacks.py still contains status text "raw 1-min bars"')

    if missing:
        print("[FAIL] Replay native timeframe routing is incomplete:")
        for item in missing:
            print(f"  - {item}")
        return 1

    from services.replay.timeframe_routing import normalize_replay_timeframe

    samples = {
        "1 min": "1 min",
        "1 hour": "1 hour",
        "1h": "1 hour",
        "1 day": "1 day",
        "daily": "1 day",
    }

    for raw, expected in samples.items():
        got = normalize_replay_timeframe(raw)
        if got != expected:
            print(f"[FAIL] normalize_replay_timeframe({raw!r}) -> {got!r}, expected {expected!r}")
            return 1

    print("[OK] Replay range loads should now use the selected native timeframe.")
    print("[OK] Expected daily cache key example: ('NVDA', '1 day', '2025-08-01')")
    print("[OK] Expected hourly cache key example: ('NVDA', '1 hour', '2025-08-01')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
