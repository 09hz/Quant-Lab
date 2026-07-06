from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .source_policy import classify_source
from .tool_registry import get_tool_registry_diagnostics


@dataclass
class ResearchPlanStep:
    source_family: str
    reason: str
    auto_fetch: bool
    evidence_goal: str
    priority: int = 50
    context_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_family": self.source_family,
            "reason": self.reason,
            "auto_fetch": self.auto_fetch,
            "evidence_goal": self.evidence_goal,
            "priority": self.priority,
            "context_only": self.context_only,
        }


@dataclass
class ResearchPlan:
    question: str
    steps: list[ResearchPlanStep] = field(default_factory=list)
    third_party_context_allowed: bool = True
    router_mode: str = "experimental_foundation"
    output_mode: str = "evidence_packet_markdown_summary_chart_ready"

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "router_mode": self.router_mode,
            "output_mode": self.output_mode,
            "third_party_context_allowed": self.third_party_context_allowed,
            "steps": [step.to_dict() for step in self.steps],
        }

    def to_markdown(self) -> str:
        lines = [
            "# AI Research Plan",
            "",
            f"- Router mode: {self.router_mode}",
            f"- Output mode: {self.output_mode}",
            f"- Third-party context allowed: {self.third_party_context_allowed}",
            f"- Question: {self.question}",
            "",
            "## Planned steps",
        ]
        if not self.steps:
            lines.append("- No steps planned.")
        for idx, step in enumerate(sorted(self.steps, key=lambda s: s.priority), start=1):
            mode = "auto-fetch" if step.auto_fetch else "manual/disabled"
            if step.context_only:
                mode += ", context-only"
            lines.append(f"{idx}. {step.source_family} — {mode}")
            lines.append(f"   - Goal: {step.evidence_goal}")
            lines.append(f"   - Reason: {step.reason}")
        return "\n".join(lines)


def _contains_any(text: str, words: set[str]) -> bool:
    return any(word in text for word in words)


def _tool_enabled(source_family: str) -> bool:
    diagnostics = get_tool_registry_diagnostics()
    for tool in diagnostics.tools:
        if tool.source_family.lower() == source_family.lower() and tool.enabled:
            return True
    return False


def _official_auto_fetch(source_family: str) -> bool:
    diagnostics = get_tool_registry_diagnostics()
    for tool in diagnostics.tools:
        if tool.source_family.lower() == source_family.lower() and tool.auto_fetch_allowed:
            return True
    return False


def build_research_plan(question: str, third_party_context_allowed: bool = True) -> ResearchPlan:
    q = str(question or "").lower()
    plan = ResearchPlan(question=str(question or ""), third_party_context_allowed=third_party_context_allowed)
    planned: dict[str, ResearchPlanStep] = {}

    def add(source_family: str, reason: str, evidence_goal: str, priority: int, context_only: bool = False) -> None:
        policy = classify_source(source_family)
        auto_fetch = bool(policy.allowed and not context_only and _official_auto_fetch(source_family))
        if context_only:
            auto_fetch = False
        if source_family not in planned or priority < planned[source_family].priority:
            planned[source_family] = ResearchPlanStep(
                source_family=source_family,
                reason=reason,
                auto_fetch=auto_fetch,
                evidence_goal=evidence_goal,
                priority=priority,
                context_only=context_only,
            )

    company_terms = {"amd", "nvidia", "intel", "ticker", "revenue", "eps", "net income", "operating income", "cash", "shares", "10-q", "10-k", "filing", "companyfacts"}
    inflation_terms = {"cpi", "core cpi", "pce", "core pce", "inflation", "ppi", "price index", "prices"}
    labor_terms = {"unemployment", "payrolls", "jobs", "wages", "earnings", "labor"}
    growth_terms = {"gdp", "real gdp", "growth", "recession", "income", "spending", "consumption"}
    rates_terms = {"fed", "rates", "fed funds", "treasury", "yield", "10y", "2y"}
    context_terms = {"news", "headline", "third-party", "reuters", "bloomberg", "market reaction", "narrative"}

    if _contains_any(q, company_terms):
        add("SEC", "question includes company fundamentals or filing terms", "official company financial facts", 10)

    if _contains_any(q, inflation_terms):
        add("FRED", "question includes inflation/price-level terms", "official macro time-series observations", 20)
        add("BLS", "question includes CPI/PPI/inflation terms", "official CPI/PPI/labor observations", 21)
        add("BEA", "question includes PCE/inflation terms", "official PCE and national accounts data", 30)

    if _contains_any(q, labor_terms):
        add("BLS", "question includes labor/wage terms", "official labor market observations", 20)
        add("FRED", "question includes labor/wage terms", "official macro/labor series mirrors", 32)

    if _contains_any(q, growth_terms):
        add("BEA", "question includes GDP/income/spending/growth terms", "official national accounts data", 20)
        add("FRED", "question includes growth/recession terms", "official macro series and recession indicators", 35)

    if _contains_any(q, rates_terms):
        add("FRED", "question includes rate/yield/policy terms", "official rate/yield time series", 22)
        add("Federal Reserve", "question includes monetary-policy terms", "official policy context", 40)

    if third_party_context_allowed and _contains_any(q, context_terms):
        add(
            "third_party_news",
            "question asks for current narrative or news context",
            "context-only narrative; cannot override official facts",
            80,
            context_only=True,
        )

    if not planned:
        add("FRED", "default official macro source for broad economic questions", "official macro evidence", 50)
        add("SEC", "default official company source if a ticker appears later", "official company facts when applicable", 60)

    plan.steps = sorted(planned.values(), key=lambda step: step.priority)
    return plan
