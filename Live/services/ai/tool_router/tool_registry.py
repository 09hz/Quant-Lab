from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolStatus:
    name: str
    source_family: str
    enabled: bool
    env_var: str | None = None
    required: bool = False
    official: bool = True
    auto_fetch_allowed: bool = False
    config_hint: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source_family": self.source_family,
            "enabled": self.enabled,
            "env_var": self.env_var,
            "required": self.required,
            "official": self.official,
            "auto_fetch_allowed": self.auto_fetch_allowed,
            "config_hint": self.config_hint,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ToolRegistryDiagnostics:
    tools: tuple[ToolStatus, ...]

    def enabled_tools(self) -> list[ToolStatus]:
        return [tool for tool in self.tools if tool.enabled]

    def disabled_tools(self) -> list[ToolStatus]:
        return [tool for tool in self.tools if not tool.enabled]

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled_tools": [tool.to_dict() for tool in self.enabled_tools()],
            "disabled_tools": [tool.to_dict() for tool in self.disabled_tools()],
            "tools": [tool.to_dict() for tool in self.tools],
        }

    def to_markdown(self) -> str:
        lines = ["# AI Research Tool Registry", ""]
        for tool in self.tools:
            status = "enabled" if tool.enabled else "not configured"
            lines.append(f"- {tool.name}: {status}")
            if not tool.enabled and tool.config_hint:
                lines.append(f"  - Hint: {tool.config_hint}")
            if tool.auto_fetch_allowed:
                lines.append("  - Auto-fetch: allowed for official-source requests")
            if tool.notes:
                for note in tool.notes:
                    lines.append(f"  - Note: {note}")
        return "\n".join(lines)


def _has_env(name: str | None) -> bool:
    if not name:
        return True
    return bool(os.getenv(name, "").strip())


def get_tool_registry_diagnostics() -> ToolRegistryDiagnostics:
    # SEC companyfacts public API does not require a key, but respectful user-agent
    # config may be added in a later patch.
    tool_specs = [
        {
            "name": "SEC companyfacts",
            "source_family": "SEC",
            "env_var": None,
            "required": False,
            "official": True,
            "auto_fetch_allowed": True,
            "config_hint": "",
            "notes": ("public official SEC data; no shared key embedded",),
        },
        {
            "name": "FRED observations",
            "source_family": "FRED",
            "env_var": "FRED_API_KEY",
            "required": False,
            "official": True,
            "auto_fetch_allowed": True,
            "config_hint": "Set FRED_API_KEY to enable higher-reliability FRED historical tools.",
            "notes": ("official macro time-series source",),
        },
        {
            "name": "BLS public data",
            "source_family": "BLS",
            "env_var": "BLS_API_KEY",
            "required": False,
            "official": True,
            "auto_fetch_allowed": True,
            "config_hint": "Set BLS_API_KEY to enable BLS API-key mode; public no-key mode can be supported separately.",
            "notes": ("official labor/inflation time-series source",),
        },
        {
            "name": "BEA data",
            "source_family": "BEA",
            "env_var": "BEA_API_KEY",
            "required": False,
            "official": True,
            "auto_fetch_allowed": True,
            "config_hint": "Set BEA_API_KEY to enable BEA national accounts tools.",
            "notes": ("official GDP/PCE/income/spending source",),
        },
        {
            "name": "OpenAI API",
            "source_family": "AI",
            "env_var": "OPENAI_API_KEY",
            "required": False,
            "official": False,
            "auto_fetch_allowed": False,
            "config_hint": "Set OPENAI_API_KEY to enable API-backed AI generation. Never expose keys in client/browser code.",
            "notes": ("bring-your-own-key only",),
        },
        {
            "name": "Third-party news",
            "source_family": "third_party_news",
            "env_var": "NEWS_API_KEY",
            "required": False,
            "official": False,
            "auto_fetch_allowed": False,
            "config_hint": "Set NEWS_API_KEY only if third-party context is enabled. Third-party news is context-only.",
            "notes": ("context-only; cannot override official facts",),
        },
        {
            "name": "Alpha Vantage",
            "source_family": "market_data",
            "env_var": "ALPHA_VANTAGE_API_KEY",
            "required": False,
            "official": False,
            "auto_fetch_allowed": False,
            "config_hint": "Set ALPHA_VANTAGE_API_KEY only if market-data features are enabled.",
            "notes": ("optional paid/free-tier market data; not authoritative for SEC filings",),
        },
        {
            "name": "Polygon",
            "source_family": "market_data",
            "env_var": "POLYGON_API_KEY",
            "required": False,
            "official": False,
            "auto_fetch_allowed": False,
            "config_hint": "Set POLYGON_API_KEY only if market-data features are enabled.",
            "notes": ("optional paid market data; no embedded shared keys",),
        },
    ]

    statuses: list[ToolStatus] = []
    for spec in tool_specs:
        enabled = _has_env(spec["env_var"])
        statuses.append(
            ToolStatus(
                name=spec["name"],
                source_family=spec["source_family"],
                enabled=enabled,
                env_var=spec["env_var"],
                required=spec["required"],
                official=spec["official"],
                auto_fetch_allowed=bool(enabled and spec["official"] and spec["auto_fetch_allowed"]),
                config_hint=spec["config_hint"],
                notes=tuple(spec["notes"]),
            )
        )
    return ToolRegistryDiagnostics(tools=tuple(statuses))


def available_auto_fetch_sources() -> list[str]:
    diagnostics = get_tool_registry_diagnostics()
    return sorted({tool.source_family for tool in diagnostics.enabled_tools() if tool.auto_fetch_allowed})
