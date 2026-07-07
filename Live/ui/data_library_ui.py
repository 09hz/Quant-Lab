from __future__ import annotations

from dash import dcc, html


ARTIFACT_TYPE_OPTIONS = [
    {"label": "All artifact types", "value": ""},
    {"label": "Market Memory packets", "value": "market_memory_packet"},
    {"label": "Market Memory reports", "value": "market_memory_report"},
    {"label": "Backtest results", "value": "backtest_result"},
    {"label": "Walk-forward results", "value": "walk_forward_result"},
    {"label": "Universe runs", "value": "universe_run"},
    {"label": "Strategy results", "value": "strategy_result"},
    {"label": "Markdown reports", "value": "markdown_report"},
    {"label": "JSON exports", "value": "json_export"},
    {"label": "CSV exports", "value": "csv_export"},
    {"label": "Diagnostics", "value": "diagnostic_report"},
    {"label": "Newsroom exports", "value": "newsroom_export"},
    {"label": "SQLite databases", "value": "sqlite_database"},
    {"label": "Other data files", "value": "data_file"},
]


EXTENSION_OPTIONS = [
    {"label": "All extensions", "value": ""},
    {"label": "Markdown", "value": "md"},
    {"label": "JSON", "value": "json"},
    {"label": "CSV", "value": "csv"},
    {"label": "SQLite", "value": "sqlite"},
    {"label": "Text", "value": "txt"},
]


def build_data_library_layout():
    """Build the Data Library panel.

    Research/simulation only. This UI only reads catalog metadata and previews.
    It never moves/deletes files and never places orders.
    """
    return html.Div(
        id="data-library-root",
        className="data-library-root",
        children=[
            dcc.Store(id="data-library-artifacts-store", storage_type="memory"),
            html.Div(
                className="data-library-header",
                children=[
                    html.Div(
                        children=[
                            html.H2("Data Library", className="data-library-title"),
                            html.P(
                                "Browse Markdown, JSON, and CSV artifacts indexed by the Data Catalog.",
                                className="data-library-muted",
                            ),
                        ]
                    ),
                    html.Div("Research / simulation only", className="data-library-badge"),
                ],
            ),
            html.Div(
                className="data-library-toolbar",
                children=[
                    html.Button(
                        "Refresh Catalog",
                        id="data-library-refresh-btn",
                        n_clicks=0,
                        className="data-library-button",
                    ),
                    html.Button(
                        "Rescan Live/data",
                        id="data-library-scan-btn",
                        n_clicks=0,
                        className="data-library-button data-library-button-primary",
                    ),
                    html.Div(
                        className="data-library-field",
                        children=[
                            html.Label("Artifact type", htmlFor="data-library-artifact-type-filter"),
                            dcc.Dropdown(
                                id="data-library-artifact-type-filter",
                                options=ARTIFACT_TYPE_OPTIONS,
                                value="",
                                clearable=False,
                                className="data-library-dropdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="data-library-field data-library-small-field",
                        children=[
                            html.Label("Extension", htmlFor="data-library-extension-filter"),
                            dcc.Dropdown(
                                id="data-library-extension-filter",
                                options=EXTENSION_OPTIONS,
                                value="",
                                clearable=False,
                                className="data-library-dropdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="data-library-field",
                        children=[
                            html.Label("Search", htmlFor="data-library-search-input"),
                            dcc.Input(
                                id="data-library-search-input",
                                type="text",
                                placeholder="symbol, theme, filename, path, tag...",
                                debounce=True,
                                className="data-library-input",
                            ),
                        ],
                    ),
                    html.Div(
                        className="data-library-field data-library-small-field",
                        children=[
                            html.Label("Limit", htmlFor="data-library-limit-input"),
                            dcc.Input(
                                id="data-library-limit-input",
                                type="number",
                                value=100,
                                min=10,
                                max=500,
                                step=10,
                                debounce=True,
                                className="data-library-input",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(id="data-library-status", className="data-library-status"),
            html.Div(
                className="data-library-main",
                children=[
                    html.Div(
                        className="data-library-left",
                        children=[
                            html.H3("Cataloged artifacts"),
                            dcc.Dropdown(
                                id="data-library-artifact-select",
                                options=[],
                                value=None,
                                placeholder="Select an artifact to preview...",
                                className="data-library-dropdown",
                            ),
                            html.Div(id="data-library-results-table", className="data-library-results"),
                        ],
                    ),
                    html.Div(
                        className="data-library-right",
                        children=[
                            html.H3("Preview"),
                            dcc.Markdown(
                                id="data-library-preview",
                                className="data-library-preview",
                                children=(
                                    "Select an artifact to preview Markdown, JSON, or CSV catalog data.\n\n"
                                    "Use **Rescan Live/data** after generating new backtests, packets, or reports."
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

# --- v24.1 PostgreSQL Status Panel integration ---
try:
    from services.data_catalog.postgres_status_ui import build_postgres_status_panel as _v24_1_build_postgres_status_panel

    _v24_1_original_build_data_library_layout = build_data_library_layout

    def _v24_1_has_postgres_panel(component):
        stack = [component]
        while stack:
            item = stack.pop()
            if item is None:
                continue
            if isinstance(item, (list, tuple)):
                stack.extend(item)
                continue
            if getattr(item, "id", None) == "data-library-postgres-status-panel":
                return True
            children = getattr(item, "children", None)
            if isinstance(children, (list, tuple)):
                stack.extend(children)
            elif children is not None and not isinstance(children, str):
                stack.append(children)
        return False

    def build_data_library_layout(*args, **kwargs):
        layout = _v24_1_original_build_data_library_layout(*args, **kwargs)
        if _v24_1_has_postgres_panel(layout):
            return layout
        panel = _v24_1_build_postgres_status_panel()
        children = getattr(layout, "children", None)
        try:
            if children is None:
                layout.children = [panel]
            elif isinstance(children, (list, tuple)):
                layout.children = [*list(children), panel]
            else:
                layout.children = [children, panel]
            return layout
        except Exception:
            from dash import html as _v24_1_html
            return _v24_1_html.Div([layout, panel])
except Exception as _v24_1_pg_ui_error:
    print(f"v24.1 PostgreSQL panel integration failed: {_v24_1_pg_ui_error}")
# --- end v24.1 PostgreSQL Status Panel integration ---
