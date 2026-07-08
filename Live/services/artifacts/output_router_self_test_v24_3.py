from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import tempfile


def make_repo(root: Path) -> Path:
    repo = root / "AlgoTrader"
    live = repo / "Live"
    data = live / "data"
    (live / "services").mkdir(parents=True, exist_ok=True)
    (live / "app.py").write_text("# temp app\n", encoding="utf-8")
    (data / "market_memory" / "research_packets").mkdir(parents=True, exist_ok=True)
    (data / "auto_lab").mkdir(parents=True, exist_ok=True)
    (data / "walk_forward").mkdir(parents=True, exist_ok=True)

    (data / "market_memory" / "research_packets" / "AI_infrastructure_semiconductors_research_packet.md").write_text(
        "# AI infrastructure semiconductors\n\nResearch only.\n",
        encoding="utf-8",
    )
    (data / "auto_lab" / "autolab_NVDA_result.json").write_text(
        '{"symbol": "NVDA", "score": 1.25, "research_only": true}\n',
        encoding="utf-8",
    )
    (data / "walk_forward" / "walk_forward_AMD.csv").write_text(
        "symbol,value\nAMD,1\nNVDA,2\n",
        encoding="utf-8",
    )
    (data / "catalog").mkdir(parents=True, exist_ok=True)
    (data / "catalog" / "data_catalog.sqlite").write_text("not a real db but should be skipped", encoding="utf-8")
    return repo


def main() -> int:
    keys = ["ALGOTRADER_ARTIFACT_POSTGRES_INGEST", "ALGOTRADER_DB_BACKEND", "ALGOTRADER_DB_PASSWORD", "ALGOTRADER_DATABASE_URL"]
    old = {key: os.environ.get(key) for key in keys}
    try:
        os.environ["ALGOTRADER_ARTIFACT_POSTGRES_INGEST"] = "0"
        for key in ["ALGOTRADER_DB_BACKEND", "ALGOTRADER_DB_PASSWORD", "ALGOTRADER_DATABASE_URL"]:
            os.environ.pop(key, None)

        from services.artifacts.output_router import route_existing_outputs, classify_artifact

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            repo = make_repo(Path(tmp))
            summary = route_existing_outputs(repo, ingest=False)

            assert summary.errors == 0, summary
            assert summary.routed == 3, summary
            assert summary.candidates == 3, summary

            registry = repo / "Live" / "data" / "catalog" / "artifact_writer.sqlite"
            assert registry.exists(), registry
            conn = sqlite3.connect(registry)
            try:
                count = conn.execute("SELECT COUNT(*) FROM managed_artifacts").fetchone()[0]
                modules = {row[0] for row in conn.execute("SELECT DISTINCT module FROM managed_artifacts").fetchall()}
            finally:
                conn.close()

            assert count == 3, count
            assert "market_memory" in modules, modules
            assert "auto_lab" in modules, modules
            assert "walk_forward" in modules, modules

            second = route_existing_outputs(repo, ingest=False)
            assert second.routed == 0, second
            assert second.skipped_existing == 3, second

            module, artifact_type, symbol, theme = classify_artifact(repo / "Live" / "data" / "auto_lab" / "autolab_NVDA_result.json")
            assert module == "auto_lab", module
            assert artifact_type == "auto_lab_result", artifact_type
            assert symbol == "NVDA", symbol

    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    print("v24.3 managed output router self-test: PASS")
    print("discovery/classification: PASS")
    print("artifact-writer registration: PASS")
    print("duplicate reroute protection: PASS")
    print("No credentials were written.")
    print("No files were moved or deleted.")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
