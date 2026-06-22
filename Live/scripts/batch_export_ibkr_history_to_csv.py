from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExportResult:
    symbol: str
    client_id: int
    return_code: int
    elapsed_seconds: float


def repo_root_from_script() -> Path:
    # Live/scripts/batch_export_ibkr_history_to_csv.py -> repo root
    return Path(__file__).resolve().parents[2]


def parse_symbols(raw: str | None, symbols_file: str | None) -> list[str]:
    symbols: list[str] = []

    if raw:
        for part in raw.replace("\n", ",").split(","):
            symbol = part.strip().upper()
            if symbol:
                symbols.append(symbol)

    if symbols_file:
        path = Path(symbols_file).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"Symbols file not found: {path}")

        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            clean = line.split("#", 1)[0].strip()
            if not clean:
                continue
            for part in clean.replace("\t", ",").split(","):
                symbol = part.strip().upper()
                if symbol:
                    symbols.append(symbol)

    deduped: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        if symbol not in seen:
            deduped.append(symbol)
            seen.add(symbol)

    if not deduped:
        raise SystemExit(
            "No symbols provided. Use --symbols MSFT,AAPL or --symbols-file symbols.txt."
        )

    return deduped


def build_command(
    *,
    exporter: Path,
    symbol: str,
    timeframe: str,
    start: str,
    end: str,
    port: int,
    client_id: int,
) -> list[str]:
    return [
        sys.executable,
        str(exporter),
        "--symbol",
        symbol,
        "--timeframe",
        timeframe,
        "--start",
        start,
        "--end",
        end,
        "--port",
        str(port),
        "--client-id",
        str(client_id),
    ]


def run_one_symbol(
    *,
    command: list[str],
    symbol: str,
    client_id: int,
    env: dict[str, str],
    dry_run: bool,
) -> ExportResult:
    print("")
    print("=" * 80)
    print(f"Exporting {symbol} with IBKR client id {client_id}")
    print("=" * 80)
    print(" ".join(command))

    if dry_run:
        return ExportResult(
            symbol=symbol,
            client_id=client_id,
            return_code=0,
            elapsed_seconds=0.0,
        )

    started = time.monotonic()
    completed = subprocess.run(command, env=env)
    elapsed = time.monotonic() - started

    return ExportResult(
        symbol=symbol,
        client_id=client_id,
        return_code=int(completed.returncode),
        elapsed_seconds=elapsed,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Batch export IBKR historical bars to the local CSV cache by calling "
            "Live/scripts/export_ibkr_history_to_csv.py once per symbol."
        )
    )

    parser.add_argument(
        "--symbols",
        default="",
        help='Comma-separated symbols, for example "MSFT,AAPL,NVDA".',
    )
    parser.add_argument(
        "--symbols-file",
        default="",
        help="Optional text file containing one symbol per line or comma-separated symbols.",
    )
    parser.add_argument(
        "--timeframe",
        default="1 min",
        help='Bar timeframe passed to the exporter. Example: "1 min".',
    )
    parser.add_argument(
        "--start",
        required=True,
        help="Start date, for example 2026-06-15.",
    )
    parser.add_argument(
        "--end",
        required=True,
        help=(
            "End date. To include a full regular session, usually pass the next "
            "calendar day as the end."
        ),
    )
    parser.add_argument(
        "--host",
        default=os.getenv("IBKR_HOST", "127.0.0.1"),
        help="IBKR host. Stored in IBKR_HOST for the child exporter.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("IBKR_PORT", "4001")),
        help="IBKR port. Gateway live is commonly 4001; Gateway paper is commonly 4002.",
    )
    parser.add_argument(
        "--client-id",
        type=int,
        default=int(os.getenv("IBKR_CLIENT_ID", "31")),
        help="Starting IBKR client id.",
    )
    parser.add_argument(
        "--client-id-step",
        type=int,
        default=1,
        help="Increment applied to the client id for each symbol.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=3.0,
        help="Pause between symbols to reduce IBKR pacing/connection pressure.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue exporting remaining symbols after a failed symbol.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without running them.",
    )

    args = parser.parse_args()

    root = repo_root_from_script()
    exporter = root / "Live" / "scripts" / "export_ibkr_history_to_csv.py"

    if not exporter.exists():
        raise SystemExit(f"Exporter script not found: {exporter}")

    symbols = parse_symbols(args.symbols, args.symbols_file)

    print("IBKR Historical Batch CSV Export")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Timeframe: {args.timeframe}")
    print(f"Range: {args.start} -> {args.end}")
    print(f"IBKR host: {args.host}")
    print(f"IBKR port: {args.port}")
    print(f"Starting client id: {args.client_id}")
    print(f"Exporter: {exporter}")

    env = os.environ.copy()
    env["IBKR_HOST"] = str(args.host)
    env["IBKR_PORT"] = str(args.port)

    results: list[ExportResult] = []

    for index, symbol in enumerate(symbols):
        client_id = int(args.client_id) + (index * int(args.client_id_step))
        env["IBKR_CLIENT_ID"] = str(client_id)

        command = build_command(
            exporter=exporter,
            symbol=symbol,
            timeframe=args.timeframe,
            start=args.start,
            end=args.end,
            port=args.port,
            client_id=client_id,
        )

        result = run_one_symbol(
            command=command,
            symbol=symbol,
            client_id=client_id,
            env=env,
            dry_run=bool(args.dry_run),
        )
        results.append(result)

        if result.return_code != 0 and not args.continue_on_error:
            print("")
            print(f"[ERROR] Stopping after failed export for {symbol}.")
            break

        if index < len(symbols) - 1 and not args.dry_run:
            time.sleep(max(float(args.sleep_seconds), 0.0))

    print("")
    print("Batch export summary")
    print("-" * 80)

    failures = 0
    for result in results:
        status = "OK" if result.return_code == 0 else f"FAILED({result.return_code})"
        if result.return_code != 0:
            failures += 1
        print(
            f"{result.symbol:8s} client_id={result.client_id:<5d} "
            f"status={status:<12s} elapsed={result.elapsed_seconds:0.1f}s"
        )

    if failures:
        print("")
        print(f"[ERROR] {failures} export(s) failed.")
        return 1

    print("")
    print("[OK] Batch export completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
