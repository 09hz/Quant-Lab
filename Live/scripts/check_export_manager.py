from __future__ import annotations

import argparse
import sys
from pathlib import Path

LIVE_DIR = Path(__file__).resolve().parents[1]
if str(LIVE_DIR) not in sys.path:
    sys.path.insert(0, str(LIVE_DIR))

try:
    from services.config.env_loader import load_app_env
except Exception:
    load_app_env = None

from services.exports_service import (
    ExportManager,
    load_context_file,
    write_backtest_report_markdown,
    write_strategy_context_markdown,
)


def build_demo_strategy_context() -> dict:
    return {
        "symbol": "MSFT",
        "timeframe": "1 min",
        "start": "2026-06-15",
        "end": "2026-06-19",
        "initial_cash": 100000,
        "quantity": 10,
        "strategy_text": (
            "// Demo strategy context only\n"
            "ema_fast = ta.ema(close, 9)\n"
            "ema_slow = ta.ema(close, 21)\n"
            "long_condition = crossover(ema_fast, ema_slow)\n"
            "exit_condition = crossunder(ema_fast, ema_slow)"
        ),
        "validation_messages": [],
        "backtest_summary": {
            "total_pnl": 123.45,
            "trades": 6,
            "win_rate": 0.5,
            "max_drawdown": -45.67,
        },
        "metadata": {
            "note": "Demo export. Do not treat as a trading recommendation.",
            "OPENAI_API_KEY": "sk-demo-should-be-redacted",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Export Center framework.")
    parser.add_argument("--root", default="exports_service", help="Export root directory.")
    parser.add_argument("--no-write", action="store_true", help="Build reports but do not write files.")
    parser.add_argument("--load", default="", help="Load a context file and print a short summary.")
    args = parser.parse_args()

    if load_app_env is not None:
        load_app_env(override=True, verbose=False)

    manager = ExportManager(args.root)

    if args.load:
        loaded = load_context_file(args.load)
        print("Loaded context")
        print(f"  path: {loaded.path}")
        print(f"  format: {loaded.format}")
        print(f"  title: {loaded.title}")
        print(f"  chars: {len(loaded.text)}")
        return 0

    context = build_demo_strategy_context()
    strategy_md = write_strategy_context_markdown(context)
    backtest_md = write_backtest_report_markdown(context)
    ai_text = manager.build_ai_attachment_text(
        title="Demo strategy context",
        sections={
            "strategy context": context,
            "user question": "Explain the risk profile of this demo strategy.",
        },
    )

    print("Export Center Check")
    print(f"Root: {Path(args.root).resolve()}")
    print(f"Strategy markdown chars: {len(strategy_md)}")
    print(f"Backtest markdown chars: {len(backtest_md)}")
    print(f"AI attachment chars: {len(ai_text)}")
    print("Secret redaction present:", "[REDACTED]" in strategy_md or "[REDACTED]" in ai_text)

    if args.no_write:
        print("[OK] Built reports without writing files.")
        return 0

    records = []
    records.append(
        manager.write_markdown(
            kind="strategy_context",
            title="demo_strategy_context",
            markdown=strategy_md,
            metadata={"demo": True},
        )
    )
    records.append(
        manager.write_json(
            kind="strategy_context",
            title="demo_strategy_context",
            payload=context,
            metadata={"demo": True},
        )
    )
    records.append(
        manager.write_markdown(
            kind="backtest_reports",
            title="demo_backtest_report",
            markdown=backtest_md,
            metadata={"demo": True},
        )
    )
    records.append(
        manager.write_markdown(
            kind="ai_attachments",
            title="demo_ai_attachment",
            markdown=ai_text,
            metadata={"demo": True},
        )
    )

    print("\nWritten files:")
    for record in records:
        print(f"  - {record.format:8s} {record.bytes_written:8d} bytes  {record.path}")

    print("\n[OK] Export Center framework is available.")
    print("Do not commit the generated exports_service/ folder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
