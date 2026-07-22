from __future__ import annotations

try:
    # Reuse existing, proven UI builder
    from services.data_catalog.quant_dashboard_ui import (
        build_quant_dashboard_panel as _original_build_panel,
    )
except Exception as exc:  # pragma: no cover
    _original_build_panel = None  # type: ignore
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


def build_quant_dashboard_layout():
    """Canonical Quant Dashboard layout.

    Reuses services.data_catalog.quant_dashboard_ui.build_quant_dashboard_panel
    to avoid duplicating layout and CSS wiring. This function is the canonical
    entry point for the Quant Dashboard UI going forward.
    """
    if _original_build_panel is None:
        raise RuntimeError(f"Quant Dashboard UI unavailable: {_IMPORT_ERROR}")
    return _original_build_panel()
