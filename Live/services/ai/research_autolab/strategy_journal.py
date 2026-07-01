from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str)


def strategy_id_from_request(request: dict[str, Any]) -> str:
    material = {
        'hypothesis_id': request.get('hypothesis_id'),
        'symbol': request.get('symbol'),
        'strategy_family': request.get('strategy_family'),
        'timeframe': request.get('timeframe'),
        'parameters': request.get('parameters') or {},
        'macro_filters': request.get('macro_filters') or [],
    }
    digest = hashlib.sha256(_stable_json(material).encode('utf-8')).hexdigest()[:16]
    return f'autolab-{digest}'


def journal_rows_from_comparison(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    generated_at = payload.get('generated_at') or datetime.now(timezone.utc).isoformat()

    baseline_by_key: dict[tuple[str, str, int, int], dict[str, Any]] = {}
    for row in (payload.get('baseline') or {}).get('results', []):
        req = row.get('request') or {}
        params = req.get('parameters') or {}
        key = (
            str(req.get('hypothesis_id') or ''),
            str(req.get('symbol') or ''),
            int(params.get('lookback') or 0),
            int(params.get('holding_days') or 0),
        )
        baseline_by_key[key] = row

    macro_by_key: dict[tuple[str, str, int, int], dict[str, Any]] = {}
    for row in (payload.get('macro') or {}).get('results', []):
        req = row.get('request') or {}
        params = req.get('parameters') or {}
        key = (
            str(req.get('hypothesis_id') or ''),
            str(req.get('symbol') or ''),
            int(params.get('lookback') or 0),
            int(params.get('holding_days') or 0),
        )
        macro_by_key[key] = row

    for comp in payload.get('comparison', []):
        key = (
            str(comp.get('hypothesis_id') or ''),
            str(comp.get('symbol') or ''),
            int(comp.get('lookback') or 0),
            int(comp.get('holding_days') or 0),
        )
        macro_row = macro_by_key.get(key) or {}
        base_row = baseline_by_key.get(key) or {}
        req = macro_row.get('request') or base_row.get('request') or {}
        metrics = macro_row.get('metrics') or {}

        strategy_id = strategy_id_from_request(req)
        status = 'candidate'
        if not comp.get('macro_improved_return') or not comp.get('macro_reduced_drawdown'):
            status = 'rejected_first_pass'
        if float(comp.get('macro_trades') or 0) < 20:
            status = 'needs_more_sample'

        rows.append(
            {
                'strategy_id': strategy_id,
                'generated_at': generated_at,
                'status': status,
                'hypothesis_id': comp.get('hypothesis_id', ''),
                'symbol': comp.get('symbol', ''),
                'strategy_family': req.get('strategy_family', ''),
                'timeframe': req.get('timeframe', ''),
                'lookback': comp.get('lookback', ''),
                'holding_days': comp.get('holding_days', ''),
                'macro_filters': ' | '.join(req.get('macro_filters') or []),
                'baseline_return_pct': comp.get('baseline_return_pct', 0.0),
                'macro_return_pct': comp.get('macro_return_pct', 0.0),
                'return_delta': comp.get('return_delta', 0.0),
                'baseline_max_drawdown_pct': comp.get('baseline_max_drawdown_pct', 0.0),
                'macro_max_drawdown_pct': comp.get('macro_max_drawdown_pct', 0.0),
                'baseline_trades': comp.get('baseline_trades', 0.0),
                'macro_trades': comp.get('macro_trades', 0.0),
                'win_rate_pct': metrics.get('win_rate_pct', 0.0),
                'final_equity': metrics.get('final_equity', 0.0),
                'notes': ' | '.join(str(x) for x in macro_row.get('notes', [])),
            }
        )

    return rows


def append_strategy_journal(path: str | Path, rows: list[dict[str, Any]]) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing_ids: set[str] = set()
    if path.exists():
        with path.open('r', newline='', encoding='utf-8') as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                existing_ids.add(str(row.get('strategy_id', '')))

    new_rows = [row for row in rows if str(row.get('strategy_id', '')) not in existing_ids]
    if not new_rows:
        return 0

    fieldnames = list(new_rows[0].keys())
    write_header = not path.exists() or path.stat().st_size == 0

    with path.open('a', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(new_rows)

    return len(new_rows)


def write_strategy_cards(out_dir: str | Path, rows: list[dict[str, Any]]) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for row in rows:
        strategy_id = str(row.get('strategy_id') or 'unknown')
        path = out_dir / f'{strategy_id}.json'
        path.write_text(json.dumps(row, indent=2, default=str) + '\n', encoding='utf-8')
        paths.append(path)

    return paths
