from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import EvidenceItem, ResearchRunRecord, stable_hash, utc_now_iso
from .hypothesis_engine import hypotheses_from_evidence, strategy_memory_from_text
from .relationship_engine import (
    entities_from_signals,
    extract_memory_signals,
    relationship_records_from_signals,
)
from .storage import MarketMemoryStore, default_market_memory_paths


MAX_FILE_BYTES = 2_000_000


def summarize_text(text: str, max_chars: int = 500) -> str:
    cleaned = " ".join((text or "").replace("\x00", " ").split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3] + "..."


def read_text_file(path: Path) -> str:
    data = path.read_bytes()
    if len(data) > MAX_FILE_BYTES:
        data = data[:MAX_FILE_BYTES]
    return data.decode("utf-8", errors="replace")


def infer_source_type(path: Path) -> str:
    lower = str(path).lower()
    if "walk_forward" in lower:
        return "auto_lab_walk_forward"
    if "auto_lab_universe" in lower or "universe_report" in lower:
        return "auto_lab_universe"
    if "symbol_discovery" in lower:
        return "auto_lab_symbol_discovery"
    if "newsroom" in lower or "research" in lower:
        return "newsroom"
    if "diagnostic" in lower:
        return "diagnostic"
    return "artifact"


def _metadata_from_json_if_possible(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except Exception:
        return {}
    if isinstance(data, dict):
        wanted = {}
        for key in [
            "symbols",
            "suggested_symbols",
            "theme",
            "themes",
            "ranked_candidates",
            "objective_hit",
            "overfit_label",
            "test_score",
            "research_pass",
            "strategy_name",
        ]:
            if key in data:
                wanted[key] = data[key]
        return wanted
    return {}


def ingest_text_packet(
    store: MarketMemoryStore,
    source_type: str,
    source_path: str,
    title: str,
    text: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = dict(metadata or {})
    json_metadata = _metadata_from_json_if_possible(text)
    metadata = {**json_metadata, **metadata}

    observed_at = metadata.get("observed_at") or utc_now_iso()
    ingested_at = utc_now_iso()
    content_hash = stable_hash(f"{source_type}|{source_path}|{text}")
    evidence_id = stable_hash(f"{source_type}|{source_path}|{content_hash}", prefix="ev_")

    signals = extract_memory_signals(text, metadata)
    evidence = EvidenceItem(
        id=evidence_id,
        source_type=source_type,
        source_path=source_path,
        title=title or source_path,
        summary=summarize_text(text),
        content_hash=content_hash,
        observed_at=observed_at,
        ingested_at=ingested_at,
        symbols=signals.get("symbols", []),
        entities=signals.get("entities", []),
        themes=signals.get("themes", []),
        metadata=metadata,
    )

    inserted = store.save_evidence(evidence)

    for entity in entities_from_signals(signals, evidence_id):
        store.upsert_entity(entity)

    rels = relationship_records_from_signals(signals, evidence_id, source_type)
    for rel in rels:
        store.upsert_relationship(rel)

    hypotheses = hypotheses_from_evidence(
        evidence_id=evidence_id,
        source_type=source_type,
        title=title,
        text=text,
        symbols=signals.get("symbols", []),
        themes=signals.get("themes", []),
        metadata=metadata,
    )
    for hypothesis in hypotheses:
        store.save_hypothesis(hypothesis)

    strategy_items = strategy_memory_from_text(
        evidence_id=evidence_id,
        source_type=source_type,
        title=title,
        text=text,
        symbols=signals.get("symbols", []),
        themes=signals.get("themes", []),
        metadata=metadata,
    )
    for strategy_item in strategy_items:
        store.save_strategy_memory(strategy_item)

    if source_type.startswith("auto_lab"):
        run = ResearchRunRecord(
            id=stable_hash(source_path, prefix="run_"),
            run_type=source_type,
            run_path=source_path,
            title=title or Path(source_path).name,
            status="observed",
            started_at=observed_at,
            ended_at=observed_at,
            metrics={k: metadata[k] for k in metadata.keys() if k in {"objective_hit", "overfit_label", "test_score", "research_pass"}},
            symbols=signals.get("symbols", []),
            metadata={"evidence_id": evidence_id},
        )
        store.save_research_run(run)

    return {
        "inserted": inserted,
        "evidence_id": evidence_id,
        "symbols": signals.get("symbols", []),
        "themes": signals.get("themes", []),
        "relationship_count": len(rels),
        "hypothesis_count": len(hypotheses),
        "strategy_memory_count": len(strategy_items),
    }


def ingest_file(store: MarketMemoryStore, path: Path, source_type: str | None = None) -> dict[str, Any]:
    path = Path(path)
    text = read_text_file(path)
    return ingest_text_packet(
        store=store,
        source_type=source_type or infer_source_type(path),
        source_path=str(path),
        title=path.name,
        text=text,
        metadata={"file_name": path.name, "file_suffix": path.suffix},
    )


def discover_candidate_artifacts(live_root: Path, limit: int = 80) -> list[Path]:
    live_root = Path(live_root)
    data_root = live_root / "data"
    patterns = [
        "auto_lab_symbol_discovery/**/symbol_discovery_report.md",
        "auto_lab_symbol_discovery/**/suggested_universe.json",
        "auto_lab_universe_runs/**/universe_report.md",
        "auto_lab_universe_runs/**/symbol_leaderboard.md",
        "auto_lab_universe_runs/**/strategy_robustness_report.md",
        "auto_lab_universe_runs/**/top_universe_strategy_algorithm.md",
        "auto_lab_walk_forward_runs/**/walk_forward_universe_report.md",
        "auto_lab_walk_forward_runs/**/walk_forward_symbol_leaderboard.md",
        "auto_lab_walk_forward_runs/**/overfit_warning_report.md",
        "auto_lab_walk_forward_runs/**/top_walk_forward_strategy_algorithm.md",
        "auto_lab_research_cycles/**/*.md",
        "research_autolab/**/*.md",
        "newsroom/**/*.md",
        "diagnostics/**/*.md",
    ]

    files: list[Path] = []
    for pattern in patterns:
        files.extend(data_root.glob(pattern))

    files = [path for path in files if path.is_file()]
    files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    return files[: max(1, int(limit))]


def seed_sample_memory(store: MarketMemoryStore) -> dict[str, Any]:
    text = """
    AMD and NVDA keep appearing together in AI infrastructure and semiconductor research.
    TSM and ASML are upstream supply-chain exposures.
    Prior Auto Lab runs should test AMD, NVDA, AVGO, TSM, ASML, MU, SMH and SOXX.
    Walk-forward validation must be required because prior single-symbol in-sample wins can overfit.
    """
    return ingest_text_packet(
        store=store,
        source_type="manual_seed",
        source_path="manual://v23.0_sample_market_memory_seed",
        title="v23.0 sample market memory seed",
        text=text,
        metadata={"symbols": ["AMD", "NVDA", "AVGO", "TSM", "ASML", "MU", "SMH", "SOXX"], "themes": ["AI infrastructure", "Semiconductors"]},
    )


def ingest_latest_artifacts(live_root: Path, limit: int = 80, seed_sample: bool = False) -> dict[str, Any]:
    paths = default_market_memory_paths(live_root)
    store = MarketMemoryStore(paths["db_path"], paths["evidence_ledger_path"])

    results: list[dict[str, Any]] = []
    if seed_sample:
        sample = seed_sample_memory(store)
        sample["path"] = "manual://v23.0_sample_market_memory_seed"
        results.append(sample)

    for path in discover_candidate_artifacts(live_root, limit=limit):
        try:
            result = ingest_file(store, path)
            result["path"] = str(path)
            results.append(result)
        except Exception as exc:
            results.append({"path": str(path), "error": str(exc)})

    return {
        "ingested_count": sum(1 for item in results if item.get("inserted")),
        "observed_count": len(results),
        "results": results,
        "counts": store.summary_counts(),
    }
