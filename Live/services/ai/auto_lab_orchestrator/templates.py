from __future__ import annotations

from pathlib import Path
import re

from .models import StrategyCandidate


BAD_FILE_NAME_TOKENS = {
    "requirements",
    "changelog",
    "readme",
    "language",
    "reference",
    "guide",
    "notes",
    "todo",
    "dev",
    "patch",
}

STRATEGY_ONLY_DIR_TOKENS = {
    "strategy_examples",
    "strategies",
    "strategy_lab_examples",
}


def starter_strategy_candidates(symbol: str = "AMD") -> list[StrategyCandidate]:
    """
    Starter candidates kept for toy adapter compatibility.

    For real core-engine smoke tests, prefer seed_library.discover_strategy_seed_candidates().
    """
    return [
        StrategyCandidate(
            candidate_id="template_momentum_sma_20",
            name="Momentum SMA 20",
            family="momentum",
            script="close > sma(close, 20)",
            parameters={"lookback": 20, "quantity": 10},
            symbols=[symbol],
            tags=["template", "trend", "simulation-only", "toy-preferred"],
            notes="Toy/self-test adapter buys when close is above a moving average and exits below it.",
        ),
        StrategyCandidate(
            candidate_id="template_dip_reversion_3pct",
            name="Dip Reversion 3pct",
            family="mean_reversion",
            script="close drops more than 3 percent then rebounds",
            parameters={"dip_pct": 3.0, "profit_take_pct": 4.0, "max_hold_bars": 10, "quantity": 10},
            symbols=[symbol],
            tags=["template", "mean-reversion", "simulation-only", "toy-preferred"],
            notes="Toy/self-test adapter buys after a dip and exits after recovery or max hold.",
        ),
        StrategyCandidate(
            candidate_id="template_breakout_30",
            name="Breakout 30",
            family="breakout",
            script="close > highest(close, 30)",
            parameters={"lookback": 30, "stop_pct": 6.0, "quantity": 10},
            symbols=[symbol],
            tags=["template", "breakout", "simulation-only", "toy-preferred"],
            notes="Toy/self-test adapter buys breakouts and exits on stop or trend failure.",
        ),
    ]


def _candidate_id_from_path(path: Path) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_]+", "_", path.stem.strip().lower()).strip("_")
    return ("example_" + stem)[:80] if stem else "example_strategy"


def _is_strategy_only_dir(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    return bool(parts.intersection(STRATEGY_ONLY_DIR_TOKENS))


def _bad_file_name(path: Path) -> bool:
    stem = path.stem.lower()
    return any(token in stem for token in BAD_FILE_NAME_TOKENS) and not _is_strategy_only_dir(path.parent)


def _looks_like_strategy_script(text: str) -> bool:
    if not text or len(text.strip()) < 10:
        return False

    lower = text.lower()
    if lower.count("\n") > 120:
        return False

    bad_markers = [
        "pip install",
        "lightweight-charts",
        "yfinance",
        "pandas_ta",
        "this is the supported strategy lab scripting language",
        "planned features",
        "unplanned features",
        "replay date-range loading works",
        "wire `barviewservice`",
    ]
    if any(marker in lower for marker in bad_markers):
        return False

    signal_hits = sum(
        1 for token in (
            "buy when",
            "sell when",
            "buy =",
            "sell =",
            "crossover",
            "crossunder",
            "sma(",
            "ema(",
            "rsi(",
            "close",
        )
        if token in lower
    )
    if signal_hits < 2:
        return False

    # Reject prose-heavy markdown/doc chunks.
    prose_lines = 0
    code_like_lines = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("-", "*", "#")) and not re.search(r"\b(buy|sell|close|ema|sma|rsi|crossover|crossunder)\b", line, re.I):
            prose_lines += 1
        elif re.search(r"\b(buy|sell|close|ema|sma|rsi|crossover|crossunder)\b", line, re.I):
            code_like_lines += 1
    if prose_lines > code_like_lines * 2 and prose_lines > 5:
        return False

    return True


def _extract_script_from_text(text: str) -> str:
    """
    Extract likely Strategy Lab script from markdown/text.

    This does not execute code. It only prepares text for the controlled
    StrategyEngine adapter.
    """
    if not text:
        return ""

    fences = re.findall(r"```(?:[a-zA-Z0-9_-]+)?\s*(.*?)```", text, flags=re.DOTALL)
    if fences:
        strategy_blocks = []
        for block in fences:
            block_clean = block.strip()
            if _looks_like_strategy_script(block_clean):
                strategy_blocks.append(block_clean)
        if strategy_blocks:
            return strategy_blocks[0][:8000]

    lines = []
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            if lines:
                lines.append("")
            continue
        if stripped.startswith("#") and not re.search(r"\b(buy|sell|close|open|high|low|rsi|sma|ema|macd|crossover|crossunder)\b", stripped, re.I):
            continue
        lines.append(line)

    script = "\n".join(lines).strip()[:8000]
    return script if _looks_like_strategy_script(script) else ""


def strategy_example_search_roots(live_root: Path) -> list[Path]:
    """
    Strict allowlist only. Do not include broad Live/docs.
    """
    return [
        live_root / "strategy_examples",
        live_root / "strategies",
        live_root / "examples" / "strategies",
        live_root / "examples" / "strategy_examples",
        live_root / "data" / "strategy_examples",
        live_root / "docs" / "strategy_examples",
        live_root / "docs" / "strategies",
    ]


def find_strategy_example_files(live_root: Path, limit: int = 20) -> list[Path]:
    candidates: list[Path] = []
    exts = {".txt", ".md", ".strategy", ".strat"}
    for root in strategy_example_search_roots(live_root):
        if not root.exists() or not root.is_dir():
            continue
        for path in root.rglob("*"):
            if len(candidates) >= limit:
                break
            if not path.is_file():
                continue
            if path.suffix.lower() not in exts:
                continue
            blob = str(path).lower()
            if "node_modules" in blob or "__pycache__" in blob:
                continue
            if _bad_file_name(path):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if not _extract_script_from_text(text):
                continue
            candidates.append(path)
    return candidates[:limit]


def load_strategy_example_candidates(live_root: Path, symbol: str = "AMD", limit: int = 10) -> list[StrategyCandidate]:
    result: list[StrategyCandidate] = []
    for path in find_strategy_example_files(live_root, limit=limit):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        script = _extract_script_from_text(text)
        if not script:
            continue
        result.append(
            StrategyCandidate(
                candidate_id=_candidate_id_from_path(path),
                name=path.stem.replace("_", " ").replace("-", " ").title(),
                family="example_file",
                script=script,
                parameters={"quantity": 10},
                symbols=[symbol],
                tags=["example-file", "core-smoke", "simulation-only"],
                source=str(path),
                notes=f"Loaded from strict strategy example folder: {path}",
            )
        )
    return result
