from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from .strategy_journal import append_strategy_journal, journal_rows_from_comparison, write_strategy_cards


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _score(row: dict[str, Any]) -> float:
    ret = _f(row.get('macro_return_pct'))
    dd = abs(_f(row.get('macro_max_drawdown_pct')))
    trades = _f(row.get('macro_trades'))
    delta = _f(row.get('return_delta'))
    sample_penalty = 0.5 if trades < 20 else 1.0
    return ((ret + max(delta, 0.0)) / max(0.01, dd)) * sample_penalty


def build_detailed_report(payload: dict[str, Any]) -> str:
    rows = list(payload.get('comparison') or [])
    rows.sort(key=_score, reverse=True)

    total = len(rows)
    improved = sum(1 for r in rows if r.get('macro_improved_return'))
    reduced_dd = sum(1 for r in rows if r.get('macro_reduced_drawdown'))
    both = sum(1 for r in rows if r.get('macro_improved_return') and r.get('macro_reduced_drawdown'))

    by_hypothesis: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_hypothesis[str(row.get('hypothesis_id', ''))].append(row)

    lines: list[str] = []
    lines.append('# Research Autolab Detailed Report')
    lines.append('')
    lines.append(f"Generated at: `{payload.get('generated_at') or datetime.now(timezone.utc).isoformat()}`")
    lines.append(f"Safety mode: `{payload.get('safety', 'simulation-only')}`")
    lines.append(f"Bars directory: `{payload.get('bars_dir', '')}`")
    lines.append(f"Macro directory: `{payload.get('macro_dir', '')}`")
    lines.append('')
    lines.append('## Executive result')
    lines.append('')
    lines.append(f'- Matched baseline-vs-macro runs: **{total}**')
    lines.append(f'- Macro improved return: **{improved}/{total}**')
    lines.append(f'- Macro reduced drawdown: **{reduced_dd}/{total}**')
    lines.append(f'- Macro improved both return and drawdown: **{both}/{total}**')
    lines.append('')

    if rows:
        best = rows[0]
        lines.append('## Top candidate by risk-adjusted smoke-test score')
        lines.append('')
        lines.append(f"- Hypothesis: **{best.get('hypothesis_id')}**")
        lines.append(f"- Symbol: **{best.get('symbol')}**")
        lines.append(f"- Lookback / hold: **{best.get('lookback')} / {best.get('holding_days')}**")
        lines.append(f"- Baseline return: **{_f(best.get('baseline_return_pct')):.4f}**")
        lines.append(f"- Macro return: **{_f(best.get('macro_return_pct')):.4f}**")
        lines.append(f"- Return delta: **{_f(best.get('return_delta')):.4f}**")
        lines.append(f"- Baseline drawdown: **{_f(best.get('baseline_max_drawdown_pct')):.4f}**")
        lines.append(f"- Macro drawdown: **{_f(best.get('macro_max_drawdown_pct')):.4f}**")
        lines.append(f"- Trades: **{_f(best.get('baseline_trades')):.0f} -> {_f(best.get('macro_trades')):.0f}**")
        lines.append('')

    lines.append('## Top 15 strategy records')
    lines.append('')
    lines.append('| Rank | Hypothesis | Symbol | Lookback | Hold | Base Ret | Macro Ret | Delta | Base DD | Macro DD | Trades | Score | Verdict |')
    lines.append('|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|')

    for idx, row in enumerate(rows[:15], start=1):
        trades = _f(row.get('macro_trades'))
        verdict = 'candidate'
        if not row.get('macro_improved_return') or not row.get('macro_reduced_drawdown'):
            verdict = 'reject/tune'
        if trades < 20:
            verdict = 'more sample needed'

        lines.append(
            f"| {idx} | {row.get('hypothesis_id')} | {row.get('symbol')} | {row.get('lookback')} | {row.get('holding_days')} | "
            f"{_f(row.get('baseline_return_pct')):.4f} | {_f(row.get('macro_return_pct')):.4f} | {_f(row.get('return_delta')):.4f} | "
            f"{_f(row.get('baseline_max_drawdown_pct')):.4f} | {_f(row.get('macro_max_drawdown_pct')):.4f} | {trades:.0f} | {_score(row):.4f} | {verdict} |"
        )

    lines.append('')
    lines.append('## Hypothesis-level summary')
    lines.append('')
    lines.append('| Hypothesis | Runs | Avg macro return | Avg return delta | Avg macro DD | Avg trades |')
    lines.append('|---|---:|---:|---:|---:|---:|')
    for hyp, group in sorted(by_hypothesis.items()):
        lines.append(
            f"| {hyp} | {len(group)} | "
            f"{mean(_f(r.get('macro_return_pct')) for r in group):.4f} | "
            f"{mean(_f(r.get('return_delta')) for r in group):.4f} | "
            f"{mean(_f(r.get('macro_max_drawdown_pct')) for r in group):.4f} | "
            f"{mean(_f(r.get('macro_trades')) for r in group):.1f} |"
        )

    lines.append('')
    lines.append('## Required next tests')
    lines.append('')
    lines.append('1. Add transaction costs and slippage.')
    lines.append('2. Add walk-forward splits.')
    lines.append('3. Add macro release-lag handling so a signal only sees data available at that time.')
    lines.append('4. Reject candidates that do not beat baseline after costs.')
    lines.append('5. Keep all outputs simulation-only until a human explicitly promotes a strategy.')
    lines.append('')
    lines.append('## Safety statement')
    lines.append('')
    lines.append('This report is a simulation artifact. It is not a trade instruction. No broker API, order placement, or live execution is used.')

    return '\n'.join(lines) + '\n'


def _report_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_report_bundle(
    payload: dict[str, Any],
    *,
    out_dir: str | Path,
    run_id: str | None = None,
    report_dir: str | Path | None = None,
    payload_dir: str | Path | None = None,
    journal_dir: str | Path | None = None,
) -> dict[str, str]:
    out_dir = Path(out_dir)
    data_dir = out_dir / 'data'
    run_id = str(run_id or payload.get('run_id') or _report_timestamp())

    report_dir = Path(report_dir) if report_dir is not None else data_dir / 'autolab_report'
    payload_dir = Path(payload_dir) if payload_dir is not None else data_dir / 'autolab_payload'
    journal_dir = Path(journal_dir) if journal_dir is not None else data_dir / 'autolab_journal'

    report_dir.mkdir(parents=True, exist_ok=True)
    payload_dir.mkdir(parents=True, exist_ok=True)
    journal_dir.mkdir(parents=True, exist_ok=True)

    report_md = report_dir / f'autolab_detailed_report_{run_id}.md'
    comparison_json = payload_dir / f'autolab_detailed_payload_{run_id}.json'
    journal_csv = journal_dir / 'autolab_strategy_journal.csv'
    run_journal_csv = journal_dir / f'autolab_strategy_journal_{run_id}.csv'
    cards_dir = journal_dir / f'autolab_strategy_cards_{run_id}'

    report_md.write_text(build_detailed_report(payload), encoding='utf-8')
    comparison_json.write_text(json.dumps(payload, indent=2, default=str) + '\n', encoding='utf-8')

    journal_rows = journal_rows_from_comparison(payload)
    added = append_strategy_journal(journal_csv, journal_rows)

    if journal_rows:
        import csv
        with run_journal_csv.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(journal_rows[0].keys()))
            writer.writeheader()
            writer.writerows(journal_rows)
    else:
        run_journal_csv.write_text('', encoding='utf-8')

    card_paths = write_strategy_cards(cards_dir, journal_rows)

    return {
        'run_id': run_id,
        'report_md': str(report_md),
        'payload_json': str(comparison_json),
        'journal_csv': str(journal_csv),
        'run_journal_csv': str(run_journal_csv),
        'strategy_cards_dir': str(cards_dir),
        'strategy_cards_written': str(len(card_paths)),
        'journal_rows_added': str(added),
    }
