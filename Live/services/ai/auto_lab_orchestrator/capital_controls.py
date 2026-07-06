from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CapitalAssumptions:
    initial_cash: float = 12000.0
    target_cash: float = 24000.0
    cash_exposure_pct: float = 95.0
    sizing_mode: str = "percent_cash_exposure"
    mode: str = "research_simulation_only"

    @property
    def target_return_pct(self) -> float:
        if self.initial_cash <= 0:
            return 0.0
        return ((self.target_cash / self.initial_cash) - 1.0) * 100.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["target_return_pct"] = self.target_return_pct
        return data


def _to_float(value: Any, default: float) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def normalize_capital(
    initial_cash: Any = None,
    target_cash: Any = None,
    cash_exposure_pct: Any = None,
    sizing_mode: str | None = None,
) -> CapitalAssumptions:
    initial = max(1.0, _to_float(initial_cash, 12000.0))
    target = max(1.0, _to_float(target_cash, 24000.0))
    exposure = min(100.0, max(1.0, _to_float(cash_exposure_pct, 95.0)))
    sizing = sizing_mode or "percent_cash_exposure"

    return CapitalAssumptions(
        initial_cash=initial,
        target_cash=target,
        cash_exposure_pct=exposure,
        sizing_mode=sizing,
    )


def money(value: float) -> str:
    return "${:,.2f}".format(float(value))


def capital_markdown(capital: CapitalAssumptions, warnings: list[str] | None = None) -> str:
    warnings = warnings or []
    lines = [
        "### Simulated capital assumptions",
        "",
        f"- Starting cash: `{money(capital.initial_cash)}`",
        f"- Target cash: `{money(capital.target_cash)}`",
        f"- Target return needed: `{capital.target_return_pct:.2f}%`",
        f"- Cash exposure: `{capital.cash_exposure_pct:.2f}%`",
        f"- Sizing mode: `{capital.sizing_mode}`",
        "",
        "**Research/simulation only. These are not real account balances.**",
    ]
    if warnings:
        lines.extend(["", "### Backend flag notes", ""])
        for item in warnings:
            lines.append(f"- {item}")
    return "\n".join(lines)


def _script_text(script_path: Path) -> str:
    try:
        return script_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def first_supported_flag(script_path: Path, candidates: list[str]) -> str | None:
    text = _script_text(script_path)
    for flag in candidates:
        if flag in text:
            return flag
    return None


def append_supported_capital_flags(
    cmd: list[str],
    script_path: Path,
    capital: CapitalAssumptions,
) -> tuple[list[str], list[str]]:
    """Append capital flags only when the target runner appears to support them.

    This prevents breaking older runner scripts with unrecognized CLI flags.
    """
    warnings: list[str] = []
    out = list(cmd)

    initial_flag = first_supported_flag(
        script_path,
        ["--initial-cash", "--initial-capital", "--starting-cash", "--start-cash"],
    )
    target_flag = first_supported_flag(
        script_path,
        ["--target-cash", "--target-capital", "--target-equity", "--objective-target-cash"],
    )

    if initial_flag:
        out.extend([initial_flag, str(capital.initial_cash)])
    else:
        warnings.append(
            "Runner does not expose an initial-cash CLI flag; it may use its built-in/default starting cash."
        )

    if target_flag:
        out.extend([target_flag, str(capital.target_cash)])
    else:
        warnings.append(
            "Runner does not expose a target-cash CLI flag; objective target may use backend defaults."
        )

    return out, warnings
