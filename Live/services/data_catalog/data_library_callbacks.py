from __future__ import annotations

from dash import Input, Output, State, callback_context, no_update

from .data_library_queries import get_artifact_preview, refresh_or_scan_catalog


def register_data_library_callbacks(app) -> None:
    """Register callbacks for Data Library UI.

    Research/simulation only. These callbacks read/index artifacts but never move/delete files.
    """
    if getattr(app, "_v23_4_data_library_callbacks_registered", False):
        return
    setattr(app, "_v23_4_data_library_callbacks_registered", True)

    @app.callback(
        Output("data-library-status", "children"),
        Output("data-library-artifacts-store", "data"),
        Output("data-library-artifact-select", "options"),
        Output("data-library-artifact-select", "value"),
        Output("data-library-artifact-type-filter", "options"),
        Output("data-library-extension-filter", "options"),
        Output("data-library-results-table", "children"),
        Input("data-library-refresh-btn", "n_clicks"),
        Input("data-library-scan-btn", "n_clicks"),
        Input("data-library-artifact-type-filter", "value"),
        Input("data-library-extension-filter", "value"),
        Input("data-library-search-input", "value"),
        Input("data-library-limit-input", "value"),
        prevent_initial_call=False,
    )
    def _refresh_data_library(refresh_clicks, scan_clicks, artifact_type, extension, search, limit):
        trigger = ""
        try:
            trigger = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else ""
        except Exception:
            trigger = ""

        do_scan = trigger == "data-library-scan-btn"

        try:
            result = refresh_or_scan_catalog(
                do_scan=do_scan,
                artifact_type=artifact_type or "",
                extension=extension or "",
                search=search or "",
                limit=int(limit or 100),
            )
            artifacts = result.get("artifacts", [])
            scan_result = result.get("scan_result")
            counts = result.get("counts", {})

            if scan_result:
                status = (
                    f"Scan complete. Status={scan_result.get('status')}. "
                    f"Indexed={scan_result.get('files_indexed')} of {scan_result.get('files_seen')} files. "
                    f"Catalog artifacts={counts.get('data_artifacts', 0)}."
                )
            else:
                status = (
                    f"Catalog loaded. Showing {len(artifacts)} artifacts. "
                    f"Catalog artifacts={counts.get('data_artifacts', 0)}. "
                    "No files moved or deleted."
                )

            table_markdown = result.get("table_markdown", "No artifacts found.")
            from dash import dcc
            table_component = dcc.Markdown(table_markdown, className="data-library-table-markdown")

            selected = artifacts[0].get("artifact_id") if artifacts else None
            filters = result.get("filter_options", {})
            return (
                status,
                artifacts,
                result.get("artifact_options", []),
                selected,
                filters.get("artifact_types", []),
                filters.get("extensions", []),
                table_component,
            )
        except Exception as exc:
            return (
                f"Data Library refresh failed: {exc}",
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
            )

    @app.callback(
        Output("data-library-preview", "children"),
        Input("data-library-artifact-select", "value"),
        State("data-library-artifacts-store", "data"),
        prevent_initial_call=False,
    )
    def _preview_artifact(artifact_id, artifacts):
        if not artifact_id:
            return (
                "Select an artifact to preview Markdown, JSON, or CSV catalog data.\n\n"
                "Use **Rescan Live/data** after generating new artifacts."
            )

        try:
            return get_artifact_preview(artifact_id=str(artifact_id))
        except Exception as exc:
            return f"Preview failed:\n\n```text\n{exc}\n```"

# --- v24.1 PostgreSQL Status Callback integration ---
try:
    from services.data_catalog.postgres_status_callbacks import register_postgres_status_callbacks as _v24_1_register_postgres_status_callbacks

    _v24_1_original_register_data_library_callbacks = register_data_library_callbacks

    def register_data_library_callbacks(app):
        result = _v24_1_original_register_data_library_callbacks(app)
        _v24_1_register_postgres_status_callbacks(app)
        return result
except Exception as _v24_1_pg_callback_error:
    print(f"v24.1 PostgreSQL callback integration failed: {_v24_1_pg_callback_error}")
# --- end v24.1 PostgreSQL Status Callback integration ---
