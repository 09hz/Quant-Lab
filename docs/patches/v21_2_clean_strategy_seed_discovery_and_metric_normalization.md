# v21_2_clean_strategy_seed_discovery_and_metric_normalization

## Purpose

Clean up the v21.1 real-core-engine smoke path so the Auto Lab can use valid strategy seeds instead of accidentally testing docs, changelogs, and requirements files.

v21.1 proved the real engine path works:

```text
StrategyEngine.run(...)
→ BackTestEngine.run(...)
→ normalized Auto Lab result
→ scorecard/report
```

The v21.1 report also showed three real candidates passed the core-engine path:

```text
example_boolean_crossover
example_ema_crossover
example_rsi_mean_reversion
```

But v21.1 also exposed problems:

```text
1. The example scanner was too broad.
   It tried changelog, requirements, and Strategy Language docs as strategies.

2. Generic templates did not match the current StrategyEngine grammar.

3. max_drawdown_pct from the core engine could be negative.
   It should be normalized as an absolute drawdown magnitude.

4. profit_factor could be 0 even when closed trades won.
   It should be derived from trade PnL when the engine does not provide it.
```

v21.2 fixes those issues and adds the first seed/mutation foundation.

## User-selected variables

```text
1. Strategy seed source: B — passing examples + built-in cleaned templates.
2. Example scanner: A — strict allowlist folders only.
3. Mutation in v21.2: A — foundation only, no loop yet.
4. Metric cleanup: B — normalize metrics before scorecard too.
5. Objective status: A — keep research_pass/objective_hit split.
6. UI changes: A — no UI yet, reports only.
7. Patch name: v21_2_clean_strategy_seed_discovery_and_metric_normalization.py.
```

## Files changed / added

```text
Live/services/ai/auto_lab_orchestrator/templates.py
Live/services/ai/auto_lab_orchestrator/adapters.py
Live/services/ai/auto_lab_orchestrator/seed_library.py
Live/services/ai/auto_lab_orchestrator/mutator.py
Live/services/ai/auto_lab_orchestrator/core_engine_smoke_test.py
Live/services/ai/auto_lab_orchestrator/seed_discovery_self_test.py
```

## Files intentionally not modified

```text
Live/core/BackTestEngine.py
Live/core/StrategyEngine.py
Live/callbacks.py
Live/services/ai/research_autolab/*
Live/ui/*
```

## What changes

### 1. Strict strategy example scanner

The scanner no longer searches broad `Live/docs`.

It only searches likely strategy-only folders:

```text
Live/strategy_examples
Live/strategies
Live/examples/strategies
Live/examples/strategy_examples
Live/data/strategy_examples
Live/docs/strategy_examples
Live/docs/strategies
```

It rejects files with names like:

```text
requirements
changelog
readme
language
reference
guide
notes
```

unless they are inside an explicitly strategy-only directory.

### 2. Strategy script hygiene filter

Before a file becomes a candidate, the script text must look like a Strategy Lab script.

It needs at least one trading/signal keyword such as:

```text
buy
sell
crossover
crossunder
sma
ema
rsi
close
```

and it is rejected if it looks like:

```text
requirements file
markdown changelog
prose-heavy documentation
package list
```

### 3. Seed library

Adds:

```text
Live/services/ai/auto_lab_orchestrator/seed_library.py
```

The seed library includes cleaned built-in seed candidates based on the strategies that worked in v21.1:

```text
boolean crossover
EMA crossover
RSI mean reversion
```

### 4. Mutation foundation

Adds:

```text
Live/services/ai/auto_lab_orchestrator/mutator.py
```

v21.2 does not run mutation loops yet. It creates a safe deterministic foundation for later v21.3/v21.4.

### 5. Metric normalization before scorecard

Core adapter now normalizes before scoring:

```text
max_drawdown_pct = abs(max_drawdown_pct)
profit_factor = derived from trade PnL when missing/zero
trade_count = derived from closed trade count when needed
total_return_pct = derived from final_equity and initial_cash when needed
```

## Run patch

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\v21_2_clean_strategy_seed_discovery_and_metric_normalization.py" `
  --repo-root "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader" `
  --run-seed-self-test `
  --run-core-smoke
```

Expected patch-level output:

```text
v21.2 clean strategy seed discovery and metric normalization complete.
- compile: PASS
- seed_self_test: PASS
```

The core smoke remains non-blocking unless you add `--strict-core-smoke`.

## Run tests later

### Seed discovery self-test

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\Live\\services\\ai\\auto_lab_orchestrator\\seed_discovery_self_test.py"
```

### Core smoke

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader"

& "C:\\Users\\sunny\\Documents\\GitHub\\StockVisualizer\\.venv\\Scripts\\python.exe" ".\\Live\\services\\ai\\auto_lab_orchestrator\\core_engine_smoke_test.py"
```

## Inspect latest report

```powershell
cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader\\Live"

$latest = Get-ChildItem ".\\data\\auto_lab_runs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1

notepad "$($latest.FullName)\\report.md"
```

## Expected report improvement

The core smoke report should no longer include junk candidates like:

```text
example_changelog_dev
example_requirements
example_strategy_language
```

Metrics should show positive drawdown magnitude:

```text
max_drawdown_pct: 0.3178
```

instead of negative drawdown.

## v21.3 target

Start the first real retest loop:

```text
valid seed candidates
→ generate parameter mutations
→ run core engine
→ score
→ keep top candidates
→ write experiment memory
```

Still simulation/research only.
