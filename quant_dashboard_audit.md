# Quant Research Dashboard — Full Audit and Porting Guide

This document audits the Quant Dashboard (architecture, components, callbacks, CSS, data contract) and provides a step‑by‑step recipe to recreate it in another application.

Scope
- Variants covered: Standalone (v24.8.0), Main‑app Iframe Tab (v24.8.1), Main‑app Native Tab (v24.8.3, current)
- Codebase paths use Windows style

====================================================================
1) System Overview
====================================================================
Purpose
- Read‑only dashboard for typed Quant Schema outputs: recent experiments/strategies, best backtests, walk‑forward/universe runs, data quality events.
- No writes, no broker/trading side effects.

Primary modules
- Data service: Live\services\quant_dashboard\queries.py (authoritative source)
- Standalone Dash app: Live\services\quant_dashboard\app.py
- Native main‑app integration: Live\app.py (block: BEGIN/END v24.8.3 native quant dashboard tab)
- Data Library variant: Live\services\data_catalog\quant_dashboard_{queries,callbacks}.py, UI helper: quant_dashboard_ui.py
- CSS: Live\assets\zzzz_all_merged.css (contains .quant-native-* rules)

Backends
- sqlite (fallback), postgres (when env vars provided)
- ALGOTRADER_DB_BACKEND selects default: "sqlite" or "postgres" ("postgresql" also accepted)

====================================================================
2) Data Service (contracts and behavior)
====================================================================
File
- Live\services\quant_dashboard\queries.py

API
- load_quant_dashboard(repo_root: str|Path|None = None, backend: str|None = None, limit: int = 10) -> QuantDashboardPayload

Tables counted (QUANT_TABLES)
- symbols, experiment_runs, strategy_runs, backtest_runs, walk_forward_runs, universe_runs, feature_snapshots, risk_snapshots, model_candidates, data_quality_events

Sections and ordering (SECTION_SPECS)
- recent_experiments: experiment_runs ORDER BY created_at DESC
- recent_strategies: strategy_runs ORDER BY created_at DESC
- best_backtests: backtest_runs ORDER BY COALESCE(sharpe, -999999) DESC, created_at DESC
- walk_forward_runs: walk_forward_runs ORDER BY created_at DESC
- universe_runs: universe_runs ORDER BY created_at DESC
- data_quality_events: data_quality_events ORDER BY created_at DESC

Return type (QuantDashboardPayload)
- status: "PASS" | "WARN" | "FAIL"
- backend: "sqlite" | "postgres"
- repo_root: resolved repository root
- counts: { table_name: int }
- sections: { section_key: [ { column: value } ] }
- errors: [str] (truncated to ~25)
- message: human message

Connection
- services.database.config.load_database_config(repo_root, backend)
- services.database.backend.connect_database (fallback: services.database.connections.connect_database)
- Works with drivers that expose either conn.execute(sql) or a cursor() with fetchone()/fetchall() and description

Resilience
- Rolls back on query errors, downgrades to WARN with captured errors; never writes/migrates
- limit is clamped to 1..100

Example payload shape
{
  "status": "PASS",
  "backend": "sqlite",
  "repo_root": "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader",
  "counts": {"experiment_runs": 12, ...},
  "sections": {
    "best_backtests": [
      {"created_at": "2026-07-21T10:30:00Z", "backtest_run_id": "bt_123", "symbol": "NVDA", "strategy_name": "X", "sharpe": 1.42, ...}
    ],
    ...
  },
  "errors": [],
  "message": "Quant dashboard loaded."
}

====================================================================
3) Standalone Dashboard (v24.8.0)
====================================================================
File
- Live\services\quant_dashboard\app.py

Key elements
- Dash(title: "Quant Research Dashboard"), layout with controls:
  - dcc.Dropdown id=backend (sqlite|postgres)
  - dcc.Input id=limit (1..100)
  - html.Button id=refresh
  - dcc.Store id=repo-root
- Views: Div ids status, counts, sections
- Single callback on (refresh, backend, limit, repo-root) calls services.quant_dashboard.queries.load_quant_dashboard
- Inline minimal CSS via app.index_string <style> for a self‑contained run

Run
- cd "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader\\Live"
- python -m services.quant_dashboard.app --repo-root "C:\\Users\\sunny\\Documents\\GitHub\\AlgoTrader" --backend sqlite --port 8061

When to use
- Quick smoke test or embedding via iframe (older v24.8.1 approach)

====================================================================
4) Native Main‑App Tab (v24.8.3, current)
====================================================================
Location
- Live\app.py, block marked:
  - # BEGIN v24.8.3 native quant dashboard tab
  - # END v24.8.3 native quant dashboard tab

What it does
- Injects a new top‑level dcc.Tab(label="Quant Dashboard", value="quant-dashboard") before Settings
- Builds page with controls and three target containers (status, counts, sections)
- Registers one callback that fetches data and renders all sections

IDs (inventory)
- Inputs/State
  - quant-dashboard-native-backend (Dropdown: sqlite|postgres)
  - quant-dashboard-native-limit (Input number 1..100)
  - quant-dashboard-native-refresh (Button)
  - quant-dashboard-native-repo-root (Store)
- Outputs
  - quant-dashboard-native-status (Div children)
  - quant-dashboard-native-counts (Div children)
  - quant-dashboard-native-sections (Div children)

Rendering helpers inside block
- _v24_8_3_status_view(payload_data) → status banner with PASS/WARN/FAIL class
- _v24_8_3_counts_view(counts) → tiled counts
- _v24_8_3_section_table(section_key, rows) → 10‑column max adaptive table
- _v24_8_3_find_repo_root(): resolves repo root for Store default
- Installer: _v24_8_3_install_native_quant_dashboard_tab() (reorders tabs, moves Settings last)

Callback signature
@app.callback(
  Output(status), Output(counts), Output(sections),
  Input(refresh.n_clicks), Input(backend.value), Input(limit.value), Input(repo_root.data),
  prevent_initial_call=False
)

Data source call
- services.quant_dashboard.queries.load_quant_dashboard(repo_root, backend, limit)

CSS classes used (native)
- .quant-native-page, .quant-native-header, .quant-native-muted, .quant-native-safety-pill
- .quant-native-card, .quant-native-controls
- .quant-native-count-grid, .quant-native-count-tile, .quant-native-count-label, .quant-native-count-value
- .quant-native-table-card
- .quant-native-status-pass | -warn | -fail

Where defined
- Live\assets\zzzz_all_merged.css (search around lines ~1872–1996)

Optional extras present after v24.9.1
- Research loop controls panel injected into the same page (IDs: research-loop-*). Safe to omit when porting if that subsystem isn’t available.

====================================================================
5) Data Library Variant (embedded section)
====================================================================
Files
- Live\services\data_catalog\quant_dashboard_queries.py (same contract)
- Live\services\data_catalog\quant_dashboard_callbacks.py (register_quant_dashboard_callbacks)
- Live\services\data_catalog\quant_dashboard_ui.py (HTML builders)

IDs
- quant-dashboard-status, quant-dashboard-counts
- quant-dashboard-experiments, -strategies, -backtests, -walk-forward, -universe, -data-quality
- Inputs: quant-dashboard-refresh, quant-dashboard-backend, quant-dashboard-limit

CSS notes
- Uses classes like data-library-muted and quant-dashboard-* (table/count) which may not have dedicated rules in merged CSS. Provide styles if you embed this variant.

====================================================================
6) Porting Guide — Rebuild in Another App
====================================================================
Prerequisites
- Python 3.10+
- dash (2.x), plotly
- A DB access layer exposing: context manager, .execute(sql) or .cursor() with description/rows
- Quant tables populated (or empty for smoke; UI tolerates empties)

A. Bring the data service
- Copy Live\services\quant_dashboard\queries.py
- Adapt _connect(...) to your app’s DB config/connector; maintain same API and payload shape
- Keep QUANT_TABLES and SECTION_SPECS semantic ordering

B. Choose integration mode
1) Native Tab (recommended)
- Add a top‑level tab with the IDs listed above
- Register a single callback that:
  - calls load_quant_dashboard(repo_root, backend, limit)
  - renders status/counts/sections using helpers similar to _v24_8_3_*
- Add CSS rules for .quant-native-* (see CSS bundle section below)
- Ensure your main layout exposes a Tabs component you can modify at runtime or construct the tab statically in layout

2) Standalone (quick path)
- Copy Live\services\quant_dashboard\app.py
- Keep inline CSS or switch to external CSS as below
- Run with python -m services.quant_dashboard.app --repo-root <path> --backend sqlite --port 8061

3) Data Library variant (embed into an existing tab)
- Use quant_dashboard_ui.py + quant_dashboard_callbacks.py patterns
- Provide or port CSS for quant-dashboard-* and data-library-* classes

C. Environment variables
- ALGOTRADER_DB_BACKEND = sqlite | postgres (defaulting logic acceptable)
- If re‑adopting the iframe model, allow a QUANT_DASHBOARD_URL override

D. CSS bundle (portable)
Add to your app CSS (tweak colors/fonts as needed):

/* Quant Native Base */
.quant-native-page { padding: 24px; background: #111; color: #eee; }
.quant-native-header { display:flex; align-items:center; justify-content:space-between; gap:16px; }
.quant-native-header h2 { margin:0; }
.quant-native-muted { opacity: .75; }
.quant-native-safety-pill { border:1px solid rgba(255,255,255,.2); border-radius:999px; padding:6px 10px; font-size:.85rem; opacity:.85; }
.quant-native-card { border:1px solid rgba(255,255,255,.14); border-radius:10px; padding:14px; margin:14px 0; background:rgba(255,255,255,.04); }
.quant-native-controls { display:grid; grid-template-columns:120px minmax(220px,340px) 80px 140px 1fr; gap:10px; align-items:center; }
.quant-native-count-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; }
.quant-native-count-tile { border:1px solid rgba(255,255,255,.14); border-radius:10px; padding:12px; background:rgba(255,255,255,.04); }
.quant-native-count-label { opacity:.75; font-size:.86rem; }
.quant-native-count-value { font-size:1.5rem; font-weight:700; margin-top:4px; }
.quant-native-table-card { overflow-x:auto; }
.quant-native-table-card table { border-collapse:collapse; width:100%; font-size:.88rem; }
.quant-native-table-card th, .quant-native-table-card td { border-bottom:1px solid rgba(255,255,255,.12); padding:7px 9px; text-align:left; vertical-align:top; }
.quant-native-status-pass { font-weight:700; color:#7ce38b; }
.quant-native-status-warn { font-weight:700; color:#ffd166; }
.quant-native-status-fail { font-weight:700; color:#ff6b6b; }

Optional (Data Library variant helpers)
.data-library-muted { opacity:.75; }
/* If you use quant-dashboard-* classes from the Data Library variant, define them similarly to the quant-native-* set. */

E. Minimal native tab example (pseudocode)
from dash import Dash, dcc, html, Input, Output
from services.quant_dashboard.queries import load_quant_dashboard

def layout(repo_root, backend_default, limit_default=10):
  return dcc.Tab(label="Quant Dashboard", value="quant-dashboard", children=[
    html.Div(className="quant-native-page", children=[
      html.Div(className="quant-native-controls quant-native-card", children=[
        html.Label("Backend"), dcc.Dropdown(id="quant-dashboard-native-backend", value=backend_default,
          options=[{"label":"SQLite fallback","value":"sqlite"},{"label":"PostgreSQL","value":"postgres"}], clearable=False),
        html.Label("Rows"), dcc.Input(id="quant-dashboard-native-limit", type="number", min=1, max=100, step=1, value=limit_default, debounce=True),
        html.Button("Refresh", id="quant-dashboard-native-refresh", n_clicks=0),
        dcc.Store(id="quant-dashboard-native-repo-root", data=repo_root)
      ]),
      html.Div(id="quant-dashboard-native-status"),
      html.Div(id="quant-dashboard-native-counts"),
      html.Div(id="quant-dashboard-native-sections", className="quant-native-sections"),
    ])
  ])

# In app init
a = Dash(__name__)
a.layout = html.Div([ dcc.Tabs(id="main-tabs", children=[ layout(repo_root, backend_default) ]) ])

@a.callback(Output("quant-dashboard-native-status","children"), Output("quant-dashboard-native-counts","children"), Output("quant-dashboard-native-sections","children"),
            Input("quant-dashboard-native-refresh","n_clicks"), Input("quant-dashboard-native-backend","value"), Input("quant-dashboard-native-limit","value"), Input("quant-dashboard-native-repo-root","data"),
            prevent_initial_call=False)
def refresh(_n, backend, limit, root):
  payload = load_quant_dashboard(repo_root=root, backend=backend or "sqlite", limit=limit or 10)
  # Render using helpers akin to _status_view/_counts_view/_section_table (see native block)
  ...

F. Error handling and UX
- Show PASS/WARN/FAIL with details (payload.errors) using a collapsible <details> block
- Truncate long values when rendering table cells (~120–140 chars)
- Limit columns to ~10 per section; prefer key columns first, then extras discovered dynamically

G. Security/Safety
- Keep service read‑only. Do not write, migrate, or place orders
- Do not couple to any live trading/broker modules
- Propagate environment‑selected backend but validate to {sqlite, postgres}

====================================================================
7) Testing & Verification
====================================================================
Self‑tests (reference)
- Live\services\quant_dashboard\self_test_v24_8_0.py (standalone)
- Live\services\quant_dashboard\self_test_v24_8_1.py (iframe tab markers)
- Live\services\quant_dashboard\self_test_v24_8_2.py (unified tabs CSS/doc presence)
- Live\services\quant_dashboard\self_test_v24_8_3.py (native tab block + CSS)

Ported‑app checklist
- queries.py imports resolve; connect works to your DB
- Payload returns PASS or WARN with non‑throwing behavior on empty/missing tables
- All IDs exist in layout and callback is registered exactly once
- CSS rules applied; status colors and count tiles render
- Manual smoke: change backend and limit; click Refresh; see updated content

====================================================================
8) Known Integration Markers (for diffs/rollbacks)
====================================================================
- Live\app.py: "BEGIN v24.8.3 native quant dashboard tab" / "END v24.8.3 native quant dashboard tab"
- Older iframe version: "BEGIN v24.8.1 quant dashboard top-level tab" (now removed in current code)

====================================================================
9) Appendix — Column Preferences per Section
====================================================================
Native/default preferences (auto‑prunes to available columns at runtime)
- recent_experiments: created_at, experiment_id, module, experiment_name, status
- recent_strategies: created_at, strategy_run_id, strategy_name, strategy_family, symbol, status
- best_backtests: created_at, backtest_run_id, symbol, strategy_name, sharpe, total_return, max_drawdown, win_rate, trade_count
- walk_forward_runs: created_at, walk_forward_run_id, symbol, strategy_name, avg_sharpe, pass_rate, status
- universe_runs: created_at, universe_run_id, universe_name, theme, selected_count, status
- data_quality_events: created_at, event_id, symbol, severity, event_type, message

Data Library variant adds optional fields (timeframe, profit_factor, window_count, stability_score, dataset_name) if present.

====================================================================
10) Troubleshooting
====================================================================
- Empty sections: Verify tables exist; WARN is acceptable until populated
- Postgres connection fails: Confirm env vars and driver; fallback to sqlite
- Callback not firing: Ensure IDs match and prevent_initial_call=False when you want first render
- CSS missing: Include the CSS bundle above or port the rules from Live\assets\zzzz_all_merged.css

End of document.
