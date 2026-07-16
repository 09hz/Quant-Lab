from __future__ import annotations

from dataclasses import fields
from pathlib import Path
import py_compile


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "Live" / "app.py").exists():
            return parent
        if parent.name.lower() == "live" and (parent / "app.py").exists():
            return parent.parent
    return Path.cwd()


def _extract_block(text: str) -> str:
    begin = "# BEGIN v24.9.4 research loop evaluation mode controls"
    end = "# END v24.9.4 research loop evaluation mode controls"
    start = text.find(begin)
    finish = text.find(end)
    assert start >= 0, "v24.9.4 block start missing"
    assert finish >= 0, "v24.9.4 block end missing"
    return text[start:finish]


def main() -> int:
    repo = _repo_root()
    live = repo / "Live"
    app_path = live / "app.py"
    models_path = live / "services" / "research_loop" / "models.py"
    orchestrator_path = live / "services" / "research_loop" / "orchestrator.py"
    adapter_path = live / "services" / "research_loop" / "backtest_engine_adapter.py"
    pipeline_path = live / "services" / "research_loop" / "evaluation_pipeline.py"
    css_path = live / "assets" / "v24_9_4_research_loop_evaluation_mode.css"

    for path in [app_path, models_path, orchestrator_path, adapter_path, pipeline_path]:
        py_compile.compile(str(path), doraise=True)

    text = app_path.read_text(encoding="utf-8", errors="replace")
    block = _extract_block(text)

    assert "research-loop-evaluation-mode" in block, "Evaluation mode dropdown missing"
    assert "hybrid_safe" in block, "hybrid_safe option missing"
    assert "real_required" in block, "real_required option missing"
    assert "proxy" in block, "proxy option missing"
    assert "Evaluation Source" in block, "Browser results missing evaluation source"
    assert "evaluation_mode" in block, "Callback does not pass evaluation_mode"
    assert text.count("BEGIN v24.9.4 research loop evaluation mode controls") == 1, "Duplicate v24.9.4 blocks"
    assert "BEGIN v24.9.1 research loop controls in quant dashboard" not in text, "Old v24.9.1 controls block still present"

    from services.research_loop.models import ResearchLoopConfig
    field_names = {field.name for field in fields(ResearchLoopConfig)}
    assert "evaluation_mode" in field_names, "ResearchLoopConfig missing evaluation_mode"

    orch = orchestrator_path.read_text(encoding="utf-8", errors="replace")
    assert "evaluate_candidate_for_loop" in orch, "Orchestrator not using evaluation pipeline"
    assert "--evaluation-mode" in orch, "Orchestrator missing CLI evaluation-mode"

    adapter = adapter_path.read_text(encoding="utf-8", errors="replace")
    assert "core.BackTestEngine" in adapter, "Adapter does not try project BackTestEngine import"
    assert "ALGOTRADER_DISABLE_BROKER" in adapter, "Adapter missing broker-disable guard"
    assert "DANGEROUS_NAME_TOKENS" in adapter, "Adapter missing dangerous callable-name guard"

    assert css_path.exists(), f"Missing CSS: {css_path}"
    css = css_path.read_text(encoding="utf-8", errors="replace")
    assert ".research-loop-controls-grid-v24-9-4" in css

    data_ui = live / "ui" / "data_library_ui.py"
    if data_ui.exists():
        data_text = data_ui.read_text(encoding="utf-8", errors="replace")
        assert "v24.9.4 research loop" not in data_text.lower(), "Data Library UI was modified"

    print("v24.9.4 Research Loop Evaluation Mode UI self-test: PASS")
    print("Evaluation mode dropdown: PASS")
    print("Browser evaluation source column: PASS")
    print("ResearchLoopConfig.evaluation_mode: PASS")
    print("Orchestrator evaluation pipeline: PASS")
    print("Safe BackTestEngine adapter guards: PASS")
    print("Data Library untouched: PASS")
    print("Research/simulation only. No broker calls or trade execution were made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
