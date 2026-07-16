from __future__ import annotations

from dash import Input, Output, State, no_update

from .market_memory_packet_loader import (
    format_packet_preview,
    load_or_build_market_memory_packet,
    packet_symbols_csv,
)


def _output(component_id: str, prop: str, allow_duplicate: bool = False):
    try:
        return Output(component_id, prop, allow_duplicate=allow_duplicate)
    except TypeError:
        return Output(component_id, prop)


def register_market_memory_packet_callbacks(app, symbol_input_id: str = "main-autolab-symbols") -> None:
    """Register AI Auto Lab callbacks for Market Memory packets.

    Research/simulation only. The apply callback only copies text into the symbols field.
    """
    if getattr(app, "_v23_2_market_memory_packet_callbacks_registered", False):
        return

    setattr(app, "_v23_2_market_memory_packet_callbacks_registered", True)

    @app.callback(
        Output("main-autolab-memory-packet-store", "data"),
        Output("main-autolab-memory-packet-status", "children"),
        Output("main-autolab-memory-packet-preview", "children"),
        Input("main-autolab-memory-load-btn", "n_clicks"),
        State("main-autolab-memory-theme", "value"),
        State("main-autolab-memory-max-symbols", "value"),
        prevent_initial_call=True,
    )
    def _load_market_memory_packet(n_clicks, theme, max_symbols):
        if not n_clicks:
            return no_update, no_update, no_update

        theme = str(theme or "AI infrastructure semiconductors").strip()
        try:
            max_symbols_int = int(max_symbols or 12)
        except Exception:
            max_symbols_int = 12
        max_symbols_int = max(1, min(max_symbols_int, 30))

        try:
            result = load_or_build_market_memory_packet(theme=theme, max_symbols=max_symbols_int, rebuild=True)
            packet = result.get("packet") or {}
            symbols = packet_symbols_csv(packet)
            quality = packet.get("packet_quality_score", "unknown")
            warnings = packet.get("warning_flags") or []
            status = (
                f"Loaded Market Memory packet. Quality={quality}. "
                f"Warnings={', '.join(warnings) if warnings else 'none'}. "
                f"Symbols={symbols or 'none'}."
            )
            preview = format_packet_preview(result)
            return result, status, preview
        except Exception as exc:
            return (
                no_update,
                f"Market Memory packet load failed: {exc}",
                "### Market Memory packet load failed\n\n"
                f"```text\n{exc}\n```\n\n"
                "Run the Market Memory packet builder from PowerShell and try again.",
            )

    @app.callback(
        _output(symbol_input_id, "value", allow_duplicate=True),
        Output("main-autolab-memory-apply-status", "children"),
        Input("main-autolab-memory-apply-symbols-btn", "n_clicks"),
        State("main-autolab-memory-packet-store", "data"),
        prevent_initial_call=True,
    )
    def _apply_market_memory_symbols(n_clicks, packet_result):
        if not n_clicks:
            return no_update, no_update

        packet_result = packet_result or {}
        packet = packet_result.get("packet") or {}
        symbols_csv = packet_symbols_csv(packet)

        if not symbols_csv:
            return no_update, "No symbols found in the loaded Market Memory packet."

        return (
            symbols_csv,
            f"Applied Market Memory symbols to Auto Lab symbol field: {symbols_csv}. Nothing was run automatically.",
        )
