from __future__ import annotations


def _disabled_callbacks(*args, **kwargs):
    return None


def _live_root(*args, **kwargs):
    return _disabled_callbacks(*args, **kwargs)

def _resolve_live_path(*args, **kwargs):
    return _disabled_callbacks(*args, **kwargs)

def _safe_text(*args, **kwargs):
    return _disabled_callbacks(*args, **kwargs)

def _metric_line(*args, **kwargs):
    return _disabled_callbacks(*args, **kwargs)

def _latest_point(*args, **kwargs):
    return _disabled_callbacks(*args, **kwargs)

def _card_component(*args, **kwargs):
    return _disabled_callbacks(*args, **kwargs)

def _split_csv_values(*args, **kwargs):
    return _disabled_callbacks(*args, **kwargs)

def _structured_frontend_sec_paths(*args, **kwargs):
    return _disabled_callbacks(*args, **kwargs)

def _generate_sec_cards_from_frontend(*args, **kwargs):
    return _disabled_callbacks(*args, **kwargs)

def _approval_paths(*args, **kwargs):
    return _disabled_callbacks(*args, **kwargs)

def _write_approved_cards(*args, **kwargs):
    return _disabled_callbacks(*args, **kwargs)

def _load_cards(*args, **kwargs):
    return _disabled_callbacks(*args, **kwargs)

def register_structured_evidence_callbacks(*args, **kwargs):
    return _disabled_callbacks(*args, **kwargs)
