from __future__ import annotations

from dash import dcc, html


def build_postgres_status_panel():
    return html.Div(
        id="data-library-postgres-status-panel",
        className="data-library-postgres-panel",
        children=[
            html.H3("PostgreSQL Research Database"),
            html.P(
                "Check the optional PostgreSQL backend, view ingestion counts, and ingest cataloged JSON/CSV artifacts. "
                "Credentials are read from environment variables only."
            ),
            html.Div(
                className="data-library-postgres-controls",
                children=[
                    html.Button("Check PostgreSQL", id="data-library-pg-check-btn", n_clicks=0),
                    html.Button("Ingest JSON/CSV to PostgreSQL", id="data-library-pg-ingest-btn", n_clicks=0),
                    html.Label("Max JSON bytes"),
                    dcc.Input(
                        id="data-library-pg-max-json-bytes",
                        type="number",
                        value=5242880,
                        min=1024,
                        step=1024,
                    ),
                    html.Label("Max CSV rows per file"),
                    dcc.Input(
                        id="data-library-pg-max-csv-rows",
                        type="number",
                        value=5000,
                        min=1,
                        step=100,
                    ),
                ],
            ),
            html.Div(id="data-library-pg-status-output", className="data-library-pg-status-output"),
            html.Div(id="data-library-pg-table-counts", className="data-library-pg-table-counts"),
            html.Div(id="data-library-pg-last-run", className="data-library-pg-last-run"),
            html.Div(id="data-library-pg-skipped-summary", className="data-library-pg-skipped-summary"),
        ],
    )
