from __future__ import annotations

# Reuse existing, backend-agnostic loader. This remains the single query entry.
try:
    from services.data_catalog.quant_dashboard_queries import (
        load_quant_dashboard as _original_load,
    )
except Exception as exc:  # pragma: no cover
    _original_load = None  # type: ignore
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


def load_quant_dashboard(*, repo_root=None, backend=None, limit: int = 10):
    if _original_load is None:
        raise RuntimeError(f"Quant Dashboard queries unavailable: {_IMPORT_ERROR}")
    return _original_load(repo_root=repo_root, backend=backend, limit=limit)
