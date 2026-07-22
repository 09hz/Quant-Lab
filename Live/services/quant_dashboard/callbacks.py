from __future__ import annotations

try:
    # Reuse existing callback registration
    from services.data_catalog.quant_dashboard_callbacks import (
        register_quant_dashboard_callbacks as _original_register,
    )
except Exception as exc:  # pragma: no cover
    _original_register = None  # type: ignore
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


def register_quant_dashboard_callbacks(app):
    """Canonical callback registration for the Quant Dashboard.

    Delegates to the existing implementation to avoid duplication.
    """
    if _original_register is None:
        raise RuntimeError(f"Quant Dashboard callbacks unavailable: {_IMPORT_ERROR}")
    return _original_register(app)
