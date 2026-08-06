from __future__ import annotations

from pathlib import Path
from typing import Any

from dash import Input, Output, State, callback_context, html

from services.data_catalog.postgres_setup_service import (
    normalize_credentials,
    setup_or_repair_database,
    temporary_postgres_env,
    test_app_connection,
)
from services.data_catalog.postgres_status_service import get_postgres_status, env_setup_hint

try:
    from services.data_catalog.database_ingestion import ingest_catalog_to_database
except Exception:  # pragma: no cover
    ingest_catalog_to_database = None


def _repo_root() -> Path:
    start = Path.cwd().resolve()
    for candidate in [start, *start.parents]:
        if (candidate / "Live" / "app.py").exists():
            return candidate
        if candidate.name.lower() == "live" and (candidate / "app.py").exists():
            return candidate.parent
    return start


def _table_from_dict(data: dict[str, Any]):
    if not data:
        return html.Div("No table counts available yet.")
    rows = []
    for key, value in data.items():
        label = key.replace("_", " ")
        rows.append(html.Tr([html.Td(label), html.Td(str(value))]))
    return html.Table([html.Tbody(rows)], className="surfaceTextWhite")


def _latest_run_view(run: dict[str, Any] | None):
    if not run:
        return html.Div([html.H4("Latest ingestion run"), html.P("No ingestion run found.")])
    rows = []
    for key in [
        "run_id",
        "backend",
        "started_at",
        "finished_at",
        "status",
        "artifacts_seen",
        "json_ingested",
        "csv_datasets_ingested",
        "csv_rows_ingested",
        "skipped",
        "errors",
    ]:
        rows.append(html.Tr([html.Td(key), html.Td(str(run.get(key, "")))]))
    return html.Div([html.H4("Latest ingestion run"), html.Table([html.Tbody(rows)], className="data-library-pg-mini-table")])


def _skipped_view(rows: list[dict[str, Any]]):
    if not rows:
        return html.Div([html.H4("Skipped/status summary"), html.P("No skipped/status rows available yet.")])
    header = html.Tr([html.Th("Status"), html.Th("Skip reason"), html.Th("Count")])
    body = []
    for row in rows[:15]:
        if "error" in row:
            body.append(html.Tr([html.Td("error"), html.Td(str(row["error"])), html.Td("")]))
        else:
            body.append(html.Tr([html.Td(str(row.get("status"))), html.Td(str(row.get("skip_reason"))), html.Td(str(row.get("count")))]))
    return html.Div([html.H4("Skipped/status summary"), html.Table([html.Thead(header), html.Tbody(body)], className="data-library-pg-mini-table")])


def _status_banner(status, action_message: str | None = None):
    if status.connected:
        text = f"PostgreSQL connected: {status.user}@{status.host}:{status.port}/{status.database} schema={status.schema}"
        if status.migrated:
            text += " | migration: PASS"
        if action_message:
            text += f" | {action_message}"
        return html.Div(text, className="data-library-pg-ok")

    children = [
        html.Div("PostgreSQL not connected.", className="data-library-pg-bad"),
        html.Pre(status.error or "Unknown connection error."),
        html.Details(
            [
                html.Summary("Environment setup hint"),
                html.Pre(env_setup_hint()),
            ]
        ),
    ]
    if status.traceback_tail:
        children.append(html.Details([html.Summary("Traceback tail"), html.Pre(status.traceback_tail)]))
    return html.Div(children)


def _setup_result_view(result):
    if result is None:
        return html.Div()
    class_name = "data-library-pg-ok" if result.ok else "data-library-pg-bad"
    children = [html.Div(f"{result.action}: {'PASS' if result.ok else 'FAILED'}", className=class_name)]
    if result.messages:
        children.append(html.Ul([html.Li(message) for message in result.messages]))
    if result.error:
        children.append(html.Pre(result.error))
    return html.Div(children)


def _status_with_optional_typed_creds(creds, repo: Path, migrate: bool = True):
    if creds.app_password:
        with temporary_postgres_env(creds):
            return get_postgres_status(repo_root=repo, migrate=migrate)
    return get_postgres_status(repo_root=repo, migrate=migrate)


def register_postgres_status_callbacks(app):
    if getattr(app, "_v24_1_2_postgres_status_callbacks_registered", False):
        return

    @app.callback(
        Output("data-library-pg-setup-output", "children"),
        Output("data-library-pg-status-output", "children"),
        Output("data-library-pg-table-counts", "children"),
        Output("data-library-pg-last-run", "children"),
        Output("data-library-pg-skipped-summary", "children"),
        Input("data-library-pg-check-btn", "n_clicks"),
        Input("data-library-pg-test-typed-btn", "n_clicks"),
        Input("data-library-pg-setup-btn", "n_clicks"),
        Input("data-library-pg-ingest-btn", "n_clicks"),
        State("data-library-pg-host", "value"),
        State("data-library-pg-port", "value"),
        State("data-library-pg-database", "value"),
        State("data-library-pg-schema", "value"),
        State("data-library-pg-app-user", "value"),
        State("data-library-pg-app-password", "value"),
        State("data-library-pg-admin-user", "value"),
        State("data-library-pg-admin-password", "value"),
        State("data-library-pg-max-json-bytes", "value"),
        State("data-library-pg-max-csv-rows", "value"),
    )
    def _v24_1_2_postgres_status(
        check_clicks,
        test_typed_clicks,
        setup_clicks,
        ingest_clicks,
        host,
        port,
        database,
        schema,
        app_user,
        app_password,
        admin_user,
        admin_password,
        max_json_bytes,
        max_csv_rows,
    ):
        triggered = ""
        try:
            triggered = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else ""
        except Exception:
            triggered = ""

        repo = _repo_root()
        creds = normalize_credentials(
            host=host,
            port=port,
            database=database,
            schema=schema,
            app_user=app_user,
            app_password=app_password,
            admin_user=admin_user,
            admin_password=admin_password,
        )

        setup_result = None
        action_message = None

        if triggered == "data-library-pg-test-typed-btn":
            setup_result = test_app_connection(creds)

        elif triggered == "data-library-pg-setup-btn":
            setup_result = setup_or_repair_database(creds)
            if setup_result.ok:
                try:
                    with temporary_postgres_env(creds):
                        status_after_setup = get_postgres_status(repo_root=repo, migrate=True)
                    if status_after_setup.connected:
                        action_message = "setup/repair complete; migration PASS"
                except Exception as exc:
                    action_message = f"setup done but migration failed: {type(exc).__name__}: {exc}"

        elif triggered == "data-library-pg-ingest-btn":
            if ingest_catalog_to_database is None:
                action_message = "ingestion module unavailable"
            else:
                try:
                    with temporary_postgres_env(creds) if creds.app_password else _null_context():
                        summary = ingest_catalog_to_database(
                            repo_root=repo,
                            backend="postgres",
                            max_json_bytes=int(max_json_bytes or 5242880),
                            max_csv_rows=int(max_csv_rows or 5000),
                        )
                    action_message = (
                        f"ingestion {summary.status}: "
                        f"json={summary.json_ingested}, csv_datasets={summary.csv_datasets_ingested}, "
                        f"csv_rows={summary.csv_rows_ingested}, skipped={summary.skipped}, errors={summary.errors}"
                    )
                except Exception as exc:
                    action_message = f"ingestion failed: {type(exc).__name__}: {exc}"

        status = _status_with_optional_typed_creds(creds, repo=repo, migrate=True)
        return (
            _setup_result_view(setup_result),
            _status_banner(status, action_message=action_message),
            html.Div([html.H4("PostgreSQL table counts"), _table_from_dict(status.counts)], className="data-library-pg-mini-table"),
            _latest_run_view(status.latest_run),
            _skipped_view(status.skipped_summary),
        )

    app._v24_1_2_postgres_status_callbacks_registered = True


class _null_context:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False
