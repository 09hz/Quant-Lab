from __future__ import annotations

from dash import dcc, html


def build_postgres_status_panel():
    return html.Div(
        id="data-library-postgres-status-panel",
        className="data-library-postgres-panel",
        children=[
            html.H3("PostgreSQL Research Database"),
            html.P(
                "Check, set up, migrate, and ingest the optional PostgreSQL backend. "
                "Passwords typed here are used for the current request only and are not saved."
            ),
            html.Details(
                open=False,
                children=[
                    html.Summary("Connection settings"),
                    html.Div(
                        className="data-library-pg-grid",
                        children=[
                            html.Label("Host"),
                            dcc.Input(id="data-library-pg-host", type="text", value="localhost"),
                            html.Label("Port"),
                            dcc.Input(id="data-library-pg-port", type="number", value=5432),
                            html.Label("Database"),
                            dcc.Input(id="data-library-pg-database", type="text", value="algotrader"),
                            html.Label("Schema"),
                            dcc.Input(id="data-library-pg-schema", type="text", value="algotrader"),
                            html.Label("App user"),
                            dcc.Input(id="data-library-pg-app-user", type="text", value="algotrader_app"),
                            html.Label("App password"),
                            dcc.Input(
                                id="data-library-pg-app-password",
                                type="password",
                                value="",
                                placeholder="Type app-user password",
                                debounce=True,
                            ),
                        ],
                    ),
                ],
            ),
            html.Details(
                open=False,
                children=[
                    html.Summary("Local setup / repair database"),
                    html.P(
                        "Use this only for a local PostgreSQL server. The admin password is not saved."
                    ),
                    html.Div(
                        className="data-library-pg-grid",
                        children=[
                            html.Label("Admin user"),
                            dcc.Input(id="data-library-pg-admin-user", type="text", value="postgres"),
                            html.Label("Admin password"),
                            dcc.Input(
                                id="data-library-pg-admin-password",
                                type="password",
                                value="",
                                placeholder="Type postgres admin password",
                                debounce=True,
                            ),
                        ],
                    ),
                    html.Button("Set up / repair PostgreSQL database", id="data-library-pg-setup-btn", n_clicks=0),
                ],
            ),
            html.Div(
                className="data-library-postgres-controls",
                children=[
                    html.Button("Check PostgreSQL", id="data-library-pg-check-btn", n_clicks=0),
                    html.Button("Test Typed Credentials", id="data-library-pg-test-typed-btn", n_clicks=0),
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
            html.Div(id="data-library-pg-setup-output", className="data-library-pg-setup-output"),
            html.Div(id="data-library-pg-status-output", className="data-library-pg-status-output"),
            html.Div(id="data-library-pg-table-counts", className="data-library-pg-table-counts"),
            html.Div(id="data-library-pg-last-run", className="data-library-pg-last-run"),
            html.Div(id="data-library-pg-skipped-summary", className="data-library-pg-skipped-summary"),
        ],
    )
