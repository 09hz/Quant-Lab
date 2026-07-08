# v24.6 — Direct Producer Wiring

## Purpose

Start direct wiring of real producer modules into the v24.2 Artifact Writer and v24.4 Quant Research Schema.

v24.5 added capture helpers and broad runtime hooks. v24.6 adds producer-local wiring so target modules can capture their own outputs as soon as they are imported.

## Adds

- `Live/services/quant_schema/producer_runtime.py`
- `Live/services/quant_schema/direct_producer_wiring.py`
- `Live/services/quant_schema/self_test_v24_6.py`
- `docs/direct_producer_wiring.md`
- `docs/patches/v24_6_direct_producer_wiring.md`

## Patches

The patch appends guarded producer-local wiring blocks to existing target files when present, such as:

- `Live/core/BackTestEngine.py`
- `Live/core/StrategyEngine.py`
- `Live/services/ai/auto_lab_orchestrator/auto_lab_main_callbacks.py`
- `Live/services/ai/auto_lab_orchestrator/universe_runner.py`
- `Live/services/ai/auto_lab_orchestrator/walk_forward.py`
- `Live/services/ai/market_memory/research_packet.py`
- `Live/services/ai/market_memory/build_research_packet.py`
- `Live/services/ai/market_memory/reports.py`

It also adds an app startup guard that installs direct producer wiring for already-loaded modules.

## Behavior

When a wired producer method returns a dict/list/dataframe-like output, the wrapper preserves the original return value and best-effort captures the result through:

- Artifact Writer
- Artifact registry
- optional PostgreSQL artifact ingestion
- typed Quant Research Schema when metrics are available

## Controls

Disable direct producer wiring:

```powershell
$env:ALGOTRADER_ENABLE_DIRECT_PRODUCER_WIRING = "0"
```

Disable all quant wiring:

```powershell
$env:ALGOTRADER_ENABLE_QUANT_WIRING = "0"
```

## Safety

Research/simulation only.

- No broker calls
- No live trading
- No order placement
- No file moves
- No file deletes
- No credentials written
