from __future__ import annotations

try:
    from services.research.result_hygiene import clean_newsroom_results, summarize_hygiene
except Exception:  # pragma: no cover - keep Newsroom usable if optional helper is unavailable
    def clean_newsroom_results(results):
        return list(results or [])

    def summarize_hygiene(results):
        return ""


import hashlib
import json
from datetime import datetime
from typing import Any

from dash import Input, Output, State, dcc, html

try:
    from services.research.search_links import build_source_search_links
except Exception:
    build_source_search_links = None

try:
    from services.research.fred_newsroom_adapter import extend_results_with_fred
except Exception:
    extend_results_with_fred = None

def _topic_text(topic: str | None) -> str:
    topic = str(topic or "").strip()
    return topic or "market conditions"

def _build_results(topic: str, sources: list[str] | None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    if build_source_search_links is not None:
        links = build_source_search_links(topic, sources or None, include_skipped=True)
        for idx, link in enumerate(links, start=1):
            metadata = dict(getattr(link, "metadata", {}) or {})
            kind = getattr(link, "result_type", "research_link")
            selectable = bool(metadata.get("selectable", kind != "skipped" and bool(getattr(link, "url", ""))))
            results.append({
                "id": f"research-{idx}",
                "title": getattr(link, "title", "Untitled"),
                "source": getattr(link, "source", "Source"),
                "url": getattr(link, "url", ""),
                "summary": getattr(link, "summary", ""),
                "topic": topic,
                "kind": kind,
                "confidence": getattr(link, "confidence", "manual-search"),
                "needs_manual_search": bool(getattr(link, "needs_manual_search", False)),
                "selectable": selectable,
                "metadata": metadata,
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
            })

    if extend_results_with_fred is not None:
        try:
            results = extend_results_with_fred(topic, sources or None, results)
        except Exception as exc:
            results.insert(0, {
                "id": "fred-ui-extension-error",
                "title": "FRED structured data unavailable",
                "source": "FRED",
                "url": "https://fred.stlouisfed.org/",
                "summary": f"FRED UI integration could not build structured cards: {exc}",
                "topic": topic,
                "kind": "fred-data-warning",
                "confidence": "low",
                "needs_manual_search": True,
                "selectable": False,
                "metadata": {"connector": "fred", "error": str(exc)},
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
            })

    return results


def _confidence_is_low(item: dict[str, Any]) -> bool:
    confidence = str(item.get("confidence", "") or "").lower()
    validity = str(item.get("validity", "") or "").lower()
    relevance = str(item.get("relevance", "") or "").lower()
    return "low" in confidence or "low" in validity or "low" in relevance


def _is_warning_result(item: dict[str, Any]) -> bool:
    kind = str(item.get("kind", "") or "").lower()
    title = str(item.get("title", "") or "").lower()
    return "warning" in kind or "error" in kind or "unavailable" in title


def _is_brief_addable_result(item: dict[str, Any]) -> bool:
    # User-controlled brief mode:
    # every visible Newsroom row can be added to the brief. Low-confidence,
    # search/context, warning, or duplicate-looking rows are not blocked here;
    # they are labeled in the brief so the user can decide how to use them.
    return isinstance(item, dict) and bool(item.get("visible", True))

def _brief_selectable_label(item: dict[str, Any]) -> str:
    if not isinstance(item, dict) or not item.get("visible", True):
        return "Hidden / not shown"
    if item.get("selectable", False) and not _confidence_is_low(item) and not _is_warning_result(item):
        return "Selectable for brief"
    return "Selectable for brief with caution"

def _brief_option_label(item: dict[str, Any]) -> str:
    source = str(item.get("source", "Source") or "Source")
    title = str(item.get("title", "Untitled") or "Untitled")
    confidence = str(item.get("confidence", "unknown") or "unknown")
    prefix = ""
    if not item.get("selectable", False) or _confidence_is_low(item):
        prefix = "[context / lower-confidence] "
    return f"{prefix}{source} - {title} ({confidence})"


def _brief_item_key(item: dict[str, Any]) -> str:
    if not isinstance(item, dict):
        return ""
    for field in ("id", "url", "title"):
        value = str(item.get(field, "") or "").strip().lower()
        if value:
            return f"{field}:{value}"
    return ""


def _merge_brief_items(
    existing_items: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    new_items: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    *,
    max_items: int = 80,
) -> list[dict[str, Any]]:
    # Append selected Newsroom items without clearing the existing brief stack.
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    for source_items in (existing_items or [], new_items or []):
        for item in source_items:
            if not isinstance(item, dict):
                continue
            key = _brief_item_key(item)
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            merged.append(item)
            if len(merged) >= max_items:
                return merged

    return merged

def _normalize_brief_key_part(value: Any, *, max_len: int = 500) -> str:
    text = " ".join(str(value or "").strip().lower().split())
    if len(text) > max_len:
        text = text[:max_len].rstrip()
    return text


def _stable_brief_key(item: dict[str, Any]) -> str:
    # Return a stable key for deduping actual brief items across searches.
    if not isinstance(item, dict):
        return ""

    existing = _normalize_brief_key_part(item.get("brief_dedupe_key"), max_len=900)
    if existing:
        return existing

    url = _normalize_brief_key_part(item.get("url"), max_len=900)
    if url:
        return f"url:{url}"

    source = _normalize_brief_key_part(item.get("source"), max_len=120)
    title = _normalize_brief_key_part(item.get("title"), max_len=240)
    kind = _normalize_brief_key_part(item.get("kind"), max_len=80)
    summary = _normalize_brief_key_part(item.get("summary"), max_len=240)
    raw_id = _normalize_brief_key_part(item.get("id"), max_len=180)

    key_parts = [part for part in (source, title, kind, summary, raw_id) if part]
    return "meta:" + "|".join(key_parts) if key_parts else ""


def _assign_brief_selection_ids(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Give each visible checklist row a unique selection id.
    #
    # The selection id is row-unique so Dash checklist values do not collapse
    # when several results reuse the same source id. The brief_dedupe_key remains
    # stable so exact duplicate URLs/sources are still deduped in the brief.
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(results or []):
        if not isinstance(item, dict):
            continue

        row = dict(item)
        stable_key = _stable_brief_key(row) or f"row:{idx}:{row.get('id', '')}:{row.get('title', '')}"
        digest = hashlib.sha1(f"{idx}|{stable_key}|{row.get('source', '')}|{row.get('title', '')}".encode("utf-8", "ignore")).hexdigest()[:14]
        row["brief_dedupe_key"] = stable_key
        row["brief_selection_id"] = f"brief-row-{idx}-{digest}"
        out.append(row)

    return out


def _selected_values_to_set(selected_ids: Any) -> set[str]:
    if selected_ids is None:
        return set()
    if isinstance(selected_ids, str):
        return {selected_ids}
    try:
        return {str(item) for item in selected_ids if str(item).strip()}
    except Exception:
        return {str(selected_ids)}


def _dedupe_brief_items(brief: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Preserve brief order while removing true duplicate source entries.
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in brief or []:
        if not isinstance(item, dict):
            continue

        row = dict(item)
        key = _stable_brief_key(row)
        if not key:
            key = f"fallback:{len(deduped)}:{row.get('id', '')}:{row.get('title', '')}"

        if key in seen:
            continue

        row["brief_dedupe_key"] = key
        seen.add(key)
        deduped.append(row)

    return deduped


def _brief_stable_key(item: dict[str, Any]) -> str:
    # Return a stable dedupe key for a research brief item.
    if not isinstance(item, dict):
        return ""

    url = str(item.get("url", "") or "").strip().lower()
    if url:
        return "url:" + url

    source = str(item.get("source", "") or "").strip().lower()
    title = str(item.get("title", "") or "").strip().lower()
    kind = str(item.get("kind", "") or "").strip().lower()
    raw_id = str(item.get("id", "") or "").strip().lower()
    return "meta:" + "|".join(part for part in (source, title, kind, raw_id) if part)


def _brief_row_selection_id(item: dict[str, Any], index: int) -> str:
    # Return a unique checklist value for a visible result row.
    key = _brief_stable_key(item) or str(item.get("id", "") or "row")
    import hashlib

    digest = hashlib.sha1(key.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"brief-row-{index + 1}-{digest}"


def _assign_brief_selection_ids(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Copy result rows and attach unique checklist ids plus stable dedupe keys.
    assigned: list[dict[str, Any]] = []
    for index, item in enumerate(results or []):
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["brief_dedupe_key"] = _brief_stable_key(row)
        row["brief_selection_id"] = _brief_row_selection_id(row, index)
        assigned.append(row)
    return assigned


def _brief_selection_matches(item: dict[str, Any], selected: set[str]) -> bool:
    # Match either the new unique row id or old raw id for backward compatibility.
    if not isinstance(item, dict):
        return False
    candidates = {
        str(item.get("brief_selection_id", "") or ""),
        str(item.get("id", "") or ""),
        str(item.get("brief_dedupe_key", "") or ""),
    }
    return any(candidate and candidate in selected for candidate in candidates)

def _render_result_cards(results: list[dict[str, Any]]) -> list[Any]:
    if not results:
        return [html.Div("No research links yet. Enter a topic and click Fetch Research Links.", className="newsroom-empty")]
    cards: list[Any] = []
    for item in results:
        url = item.get("url", "")
        selectable = bool(item.get("selectable", True))
        kind = item.get("kind", "research_link")
        confidence = item.get("confidence", "manual-search")
        manual = "manual search may be needed" if item.get("needs_manual_search") else "direct/openable result"
        title_node = html.A(item.get("title", "Untitled"), href=url, target="_blank", className="newsroom-result-title") if url else html.Div(item.get("title", "Untitled"), className="newsroom-result-title newsroom-result-title-disabled")
        cards.append(html.Div(
            className=f"newsroom-result-card newsroom-result-{kind}",
            children=[
                html.Div(item.get("source", "Source"), className="newsroom-result-source"),
                title_node,
                html.Div(item.get("summary", ""), className="newsroom-result-summary"),
                html.Div(f"Type: {kind} | Confidence: {confidence} | {manual}", className="newsroom-result-kind"),
                html.Div(_brief_selectable_label(item), className="newsroom-result-selectable"),
                html.Div(url, className="newsroom-result-url") if url else html.Div("No link shown because this source was not relevant for the query.", className="newsroom-result-url"),
            ],
        ))
    return cards

def _clean_brief_key_part(value: Any, *, limit: int = 300) -> str:
    text = " ".join(str(value or "").strip().lower().split())
    if len(text) > limit:
        text = text[:limit]
    return text

def _brief_dedupe_key(item: dict[str, Any]) -> str:
    """Return a conservative exact-source key for Research Brief entries.

    Important UX rule:
    - Do NOT collapse different visible rows just because they share the same URL.
      FRED often shows both a live data card and an official series/context card
      for the same series URL. Users may intentionally add both.
    - Only treat rows as duplicates when their source, type, title, URL, and
      summary are effectively the same.
    """
    if not isinstance(item, dict):
        return ""

    source = _clean_brief_key_part(item.get("source"))
    kind = _clean_brief_key_part(item.get("kind") or item.get("type"))
    title = _clean_brief_key_part(item.get("title"), limit=220)
    url = _clean_brief_key_part(item.get("url"), limit=500)
    summary = _clean_brief_key_part(item.get("summary"), limit=500)

    raw = "|".join(part for part in (source, kind, title, url, summary) if part)
    if raw:
        return raw

    # Last-resort fallback. This is intentionally after the content fields so
    # row IDs do not accidentally block distinct source cards.
    return _clean_brief_key_part(item.get("brief_selection_id") or item.get("id"), limit=240)

def _brief_markdown(brief: list[dict[str, Any]]) -> str:
    lines = ["# Research Brief", "", f"Generated: {datetime.now().isoformat(timespec='seconds')}", "", "## Selected Research Links", ""]
    if not brief:
        lines.append("_No items selected yet._")
    for idx, item in enumerate(brief, start=1):
        lines += [
            f"### {idx}. {item.get('title', 'Untitled')}",
            f"- Source: {item.get('source', 'Unknown')}",
            f"- Type: {item.get('kind', 'research_link')}",
            f"- Confidence: {item.get('confidence', 'unknown')}",
            f"- Brief caution: {'lower-confidence/context source; verify before relying on it' if _confidence_is_low(item) or not item.get('selectable', False) else 'standard selected source'}",
            f"- URL: {item.get('url', '')}",
            f"- Summary: {item.get('summary', '')}",
            "",
        ]
    lines += ["## AI Use Notes", "", "Use this brief as user-selected research context only.", "These entries may be direct official pages, search links, or data pages.", "Separate facts from assumptions.", "Do not infer broker/account data from this brief."]
    return "\n".join(lines)

def _brief_stable_key(item: dict[str, Any]) -> str:
    # Stable dedupe key for a Newsroom brief item. Prefer URL, then source/title/summary.
    if not isinstance(item, dict):
        return ""
    url = str(item.get("url") or "").strip().lower()
    if url:
        return "url:" + url
    source = str(item.get("source") or "").strip().lower()
    title = str(item.get("title") or "").strip().lower()
    summary = str(item.get("summary") or "").strip().lower()[:160]
    raw_id = str(item.get("id") or "").strip().lower()
    return "row:" + "|".join(part for part in (source, title, summary, raw_id) if part)


def _ensure_newsroom_brief_row_ids(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Give every visible row a unique selection id and stable dedupe key.
    prepared: list[dict[str, Any]] = []
    seen_row_ids: set[str] = set()
    for idx, item in enumerate(results or [], start=1):
        if not isinstance(item, dict):
            continue
        row = dict(item)
        stable_key = _brief_stable_key(row) or f"fallback:{idx}"
        base = str(row.get("id") or stable_key or f"row-{idx}").strip()
        selection_id = f"brief-row-{idx}-{abs(hash((base, stable_key, idx))) % 1000000000}"
        while selection_id in seen_row_ids:
            idx += 1
            selection_id = f"brief-row-{idx}-{abs(hash((base, stable_key, idx))) % 1000000000}"
        seen_row_ids.add(selection_id)
        row["brief_selection_id"] = selection_id
        row["brief_dedupe_key"] = stable_key
        row["selectable"] = True
        row["used_for_ai"] = True
        if not row.get("confidence"):
            row["confidence"] = "user-selected"
        if not row.get("validity"):
            row["validity"] = "user-selected"
        prepared.append(row)
    return prepared


def _brief_option_value(item: dict[str, Any]) -> str:
    return str(item.get("brief_selection_id") or item.get("id") or _brief_stable_key(item))


def _brief_match_selected(item: dict[str, Any], selected: set[str]) -> bool:
    candidates = {
        str(item.get("brief_selection_id") or ""),
        str(item.get("id") or ""),
        str(item.get("brief_dedupe_key") or ""),
        _brief_stable_key(item),
    }
    return any(candidate and candidate in selected for candidate in candidates)


def _recommendation_markdown(coverage: dict[str, Any], recommendations: list[dict[str, Any]]) -> str:
    try:
        from services.research.evidence_coverage import coverage_to_markdown
    except Exception:
        coverage_to_markdown = None
    lines: list[str] = []
    if coverage_to_markdown is not None:
        lines.append(coverage_to_markdown(coverage))
    else:
        lines.append("## Evidence Coverage")
        lines.append("")
        for key, info in (coverage.get("buckets") or {}).items():
            lines.append(f"- {info.get('label', key)}: {info.get('status', 'unknown')}")
    lines.extend(["", "## Pending Recommendations", ""])
    if not recommendations:
        lines.append("_No missing-evidence recommendations are pending._")
        return "\n".join(lines)
    for idx, rec in enumerate(recommendations, start=1):
        lines.extend([
            f"### {idx}. {rec.get('title', 'Untitled')}",
            f"- Bucket: {rec.get('topic') or rec.get('bucket') or 'evidence'}",
            f"- Source: {rec.get('source', 'Unknown')}",
            f"- Type: {rec.get('kind', 'recommended-source')}",
            f"- Confidence: {rec.get('confidence', 'unknown')}",
            f"- URL: {rec.get('url', '')}",
            f"- Summary: {rec.get('summary', '')}",
            "- Status: pending user approval; not used by AI until approved into the brief.",
            "",
        ])
    return "\n".join(lines)

def register_newsroom_callbacks(app: Any) -> None:
    @app.callback(
        Output("newsroom-results-store", "data"),
        Output("newsroom-result-selection", "options"),
        Output("newsroom-result-selection", "value"),
        Output("newsroom-results-list", "children"),
        Output("newsroom-status", "children"),
        Input("newsroom-fetch", "n_clicks"),
        State("newsroom-topic-input", "value"),
        State("newsroom-source-filter", "value"),
        prevent_initial_call=True,
    )
    def fetch_research(n_clicks: int, topic: str, sources: list[str]):
        topic_clean = _topic_text(topic)
        results = _build_results(topic_clean, sources)
        results = clean_newsroom_results(results)

        # User-controlled selection mode:
        # every visible row gets a unique selection id and appears in the checklist.
        # The raw source id/url/title are preserved on the row, but they no longer
        # control whether the user is allowed to add the row.
        visible_results: list[dict[str, Any]] = []
        for idx, raw_item in enumerate(results or [], start=1):
            if not isinstance(raw_item, dict):
                continue
            if not raw_item.get("visible", True):
                continue
            item = dict(raw_item)
            raw_id = str(item.get("id") or item.get("url") or item.get("title") or "result").strip()
            item["brief_selection_id"] = f"visible-row-{idx}-{raw_id}"
            item["selectable"] = True
            item["user_addable"] = True
            visible_results.append(item)

        options = [
            {"label": _brief_option_label(item), "value": item["brief_selection_id"]}
            for item in visible_results
        ]

        status = (
            f"Loaded {len(visible_results)} visible result(s) for: {topic_clean}. "
            "All visible rows are user-selectable; lower-confidence/context rows remain labeled with caution."
        )
        return visible_results, options, [], _render_result_cards(visible_results), status

    @app.callback(
        Output("newsroom-brief-store", "data"),
        Output("newsroom-brief-preview", "children"),
        Input("newsroom-add-selected", "n_clicks"),
        Input("newsroom-clear-brief", "n_clicks"),
        State("newsroom-result-selection", "value"),
        State("newsroom-results-store", "data"),
        State("newsroom-brief-store", "data"),
        prevent_initial_call=True,
    )
    def update_brief(add_clicks: int, clear_clicks: int, selected_ids: list[str], results: list[dict[str, Any]], brief: list[dict[str, Any]]):
        from dash import callback_context

        triggered = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else ""
        if triggered == "newsroom-clear-brief":
            return [], _brief_markdown([])

        current = list(brief or [])
        selected = {str(value) for value in (selected_ids or []) if str(value).strip()}

        added_count = 0
        matched_count = 0
        unmatched_values = set(selected)
        generated_at = datetime.now().isoformat(timespec="seconds")

        for idx, raw_item in enumerate(results or [], start=1):
            if not isinstance(raw_item, dict):
                continue

            row_id = str(raw_item.get("brief_selection_id") or "").strip()
            raw_id = str(raw_item.get("id") or "").strip()
            url = str(raw_item.get("url") or "").strip()
            title = str(raw_item.get("title") or "").strip()
            candidate_values = {value for value in (row_id, raw_id, url, title) if value}

            if not selected.intersection(candidate_values):
                continue

            matched_count += 1
            unmatched_values.difference_update(candidate_values)

            # No rail-guard dedupe here. If the user selected a visible row,
            # add that visible row. Exact repeats are allowed because the user
            # may intentionally compare a data card, a source page, and a search card
            # that share the same URL or topic.
            item = dict(raw_item)
            item["brief_user_selected"] = True
            item["brief_added_at"] = generated_at
            item["brief_added_sequence"] = len(current) + 1
            item["brief_selection_id"] = row_id or f"manual-row-{idx}-{len(current) + 1}"
            current.append(item)
            added_count += 1

        preview = _brief_markdown(current)
        preview += (
            "\n\n## Last Add Action"
            f"\n- Selected rows: {len(selected)}"
            f"\n- Matched visible rows: {matched_count}"
            f"\n- Added: {added_count}"
            "\n- Skipped duplicates: 0"
            f"\n- Unmatched selections: {len(unmatched_values)}"
            f"\n- Brief total: {len(current)}"
            "\n- Mode: user-controlled add-all; every matched visible row is appended."
        )
        return current, preview

    @app.callback(
        Output("newsroom-recommendations-store", "data"),
        Output("newsroom-recommendation-selection", "options"),
        Output("newsroom-recommendation-selection", "value"),
        Output("newsroom-recommendation-preview", "children"),
        Output("newsroom-recommendation-status", "children"),
        Output("newsroom-brief-store", "data", allow_duplicate=True),
        Output("newsroom-brief-preview", "children", allow_duplicate=True),
        Input("newsroom-generate-recommendations", "n_clicks"),
        # approved recommendation queue marker
        Input("newsroom-approve-recommendations", "n_clicks"),
        Input("newsroom-reject-recommendations", "n_clicks"),
        State("newsroom-brief-store", "data"),
        State("newsroom-recommendations-store", "data"),
        State("newsroom-recommendation-selection", "value"),
        prevent_initial_call=True,
    )
    def update_recommendation_queue(
        generate_clicks: int,
        approve_clicks: int,
        reject_clicks: int,
        brief: list[dict[str, Any]],
        pending: list[dict[str, Any]],
        selected_ids: list[str],
    ):
        from dash import callback_context, no_update
        trigger = callback_context.triggered[0]["prop_id"].split(".")[0] if callback_context.triggered else ""
        current_brief = list(brief or [])
        current_pending = [dict(item) for item in (pending or []) if isinstance(item, dict)]
        selected = {str(value) for value in (selected_ids or []) if str(value).strip()}
        try:
            from services.research.evidence_coverage import analyze_evidence_coverage, build_recommended_evidence_sources, recommendations_to_options
        except Exception as exc:
            status = f"Evidence recommendation tools unavailable: {exc}"
            return current_pending, [], [], status, status, no_update, no_update
        if trigger == "newsroom-generate-recommendations":
            coverage, recommendations = build_recommended_evidence_sources(current_brief)
            options = recommendations_to_options(recommendations)
            values = [option["value"] for option in options]
            preview = _recommendation_markdown(coverage, recommendations)
            missing = len(coverage.get("missing") or [])
            status = f"Generated {len(recommendations)} recommendation(s) across {missing} missing evidence bucket(s). Review and approve selected candidates before they are added to the brief."
            return recommendations, options, values, preview, status, no_update, no_update
        if trigger == "newsroom-approve-recommendations":
            if not current_pending:
                status = "No pending recommendations to approve. Generate recommendations first."
                coverage = analyze_evidence_coverage(current_brief)
                return [], [], [], _recommendation_markdown(coverage, []), status, no_update, no_update
            approved: list[dict[str, Any]] = []
            remaining: list[dict[str, Any]] = []
            generated_at = datetime.now().isoformat(timespec="seconds")
            hydrated_count = 0
            hydration_failed_count = 0
            discovery_only_count = 0
            try:
                from services.research.evidence_hydration import hydrate_approved_recommendation
            except Exception:
                hydrate_approved_recommendation = None
            for item in current_pending:
                rec_id = str(item.get("id") or item.get("rec_id") or "").strip()
                if rec_id in selected:
                    approved_item = dict(item)
                    sequence = len(current_brief) + len(approved) + 1
                    if hydrate_approved_recommendation is not None:
                        approved_item, hydration_status = hydrate_approved_recommendation(
                            approved_item,
                            added_at=generated_at,
                            sequence=sequence,
                        )
                    else:
                        hydration_status = {"hydrated": False, "discovery_only": True, "error": "hydration helper unavailable"}
                        approved_item["brief_user_approved_recommendation"] = True
                        approved_item["brief_added_at"] = generated_at
                        approved_item["brief_added_sequence"] = sequence
                        approved_item["source_role"] = "approved-recommendation-discovery"
                        metadata = dict(approved_item.get("metadata") or {})
                        metadata["approved_at"] = generated_at
                        metadata["approved_from_queue"] = True
                        metadata["hydration_status"] = "helper-unavailable"
                        approved_item["metadata"] = metadata

                    if hydration_status.get("hydrated"):
                        hydrated_count += 1
                    elif hydration_status.get("error"):
                        hydration_failed_count += 1
                    else:
                        discovery_only_count += 1
                    approved.append(approved_item)
                else:
                    remaining.append(item)
            updated_brief = current_brief + approved
            coverage = analyze_evidence_coverage(updated_brief)
            options = recommendations_to_options(remaining)
            preview = _recommendation_markdown(coverage, remaining)
            brief_preview = _brief_markdown(updated_brief)
            brief_preview += (
                "\n\n## Last Recommendation Approval"
                + f"\n- Selected recommendations: {len(selected)}"
                + f"\n- Approved recommendation(s): {len(approved)}"
                + f"\n- Hydrated FRED data card(s): {hydrated_count}"
                + f"\n- Discovery-only approved card(s): {discovery_only_count}"
                + f"\n- Hydration warning/failure card(s): {hydration_failed_count}"
                + f"\n- Pending remaining: {len(remaining)}"
                + f"\n- Brief total: {len(updated_brief)}"
            )
            status = (
                f"Approved {len(approved)} recommendation(s) into the brief. "
                f"Hydrated FRED data cards: {hydrated_count}. "
                f"Discovery-only: {discovery_only_count}. "
                f"Hydration warnings: {hydration_failed_count}. "
                f"Pending remaining: {len(remaining)}."
            )
            return remaining, options, [], preview, status, updated_brief, brief_preview
        if trigger == "newsroom-reject-recommendations":
            if not current_pending:
                status = "No pending recommendations to reject."
                coverage = analyze_evidence_coverage(current_brief)
                return [], [], [], _recommendation_markdown(coverage, []), status, no_update, no_update
            remaining = []
            rejected = 0
            for item in current_pending:
                rec_id = str(item.get("id") or item.get("rec_id") or "").strip()
                if rec_id in selected:
                    rejected += 1
                else:
                    remaining.append(item)
            coverage = analyze_evidence_coverage(current_brief)
            options = recommendations_to_options(remaining)
            preview = _recommendation_markdown(coverage, remaining)
            status = f"Rejected {rejected} recommendation(s). Pending remaining: {len(remaining)}."
            return remaining, options, [], preview, status, no_update, no_update
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update

    @app.callback(
        Output("newsroom-send-to-ai", "disabled"),
        Output("newsroom-send-to-ai", "className"),
        Input("newsroom-brief-store", "data"),
        prevent_initial_call=False,
    )
    def toggle_newsroom_send_to_ai_button(brief: list[dict[str, Any]]):
        count = len(list(brief or []))
        if count > 0:
            return False, "newsroom-btn ai-ready"
        return True, "newsroom-btn disabled"

    @app.callback(
        Output("strategy-ai-advisor-context", "value", allow_duplicate=True),
        Output("strategy-ai-advisor-prompt", "value", allow_duplicate=True),
        Output("newsroom-status", "children", allow_duplicate=True),
        Input("newsroom-send-to-ai", "n_clicks"),
        State("newsroom-brief-store", "data"),
        State("strategy-ai-advisor-context", "value"),
        State("strategy-ai-advisor-prompt", "value"),
        prevent_initial_call=True,
    )
    def send_newsroom_brief_to_strategy_ai(
        n_clicks: int,
        brief: list[dict[str, Any]],
        existing_context: str,
        existing_prompt: str,
    ):
        from dash import no_update
        from services.research.brief_ai_handoff import (
            brief_to_strategy_ai_context,
            default_newsroom_ai_prompt,
        )

        if not n_clicks:
            return no_update, no_update, no_update

        current = list(brief or [])
        if not current:
            return (
                no_update,
                no_update,
                "No Newsroom brief items to send. Add selected results to the brief first.",
            )

        research_context = brief_to_strategy_ai_context(current)
        existing = str(existing_context or "").strip()

        if existing:
            combined_context = existing + "\n\n---\n\n" + research_context
        else:
            combined_context = research_context

        max_context_chars = 18000
        if len(combined_context) > max_context_chars:
            combined_context = (
                combined_context[: max_context_chars - 120].rstrip()
                + "\n\n...[truncated to keep Strategy AI context size safe]\n"
            )

        prompt = str(existing_prompt or "").strip() or default_newsroom_ai_prompt()
        status = (
            f"Sent {len(current)} Newsroom brief item(s) to Strategy AI attached context. "
            "Open Watch -> Strategy Lab -> AI Advisor to review or ask."
        )
        return combined_context, prompt, status

    @app.callback(Output("newsroom-download-json", "data"), Input("newsroom-export-json", "n_clicks"), State("newsroom-brief-store", "data"), prevent_initial_call=True)
    def export_json(n_clicks: int, brief: list[dict[str, Any]]):
        payload = {"kind": "research_brief", "schema_version": "1.2", "generated_at": datetime.now().isoformat(timespec="seconds"), "items": brief or [], "notes": ["JSON is for structured reloads, audit trails, and future app-to-AI attachment.", "Markdown is usually better for direct manual upload to an AI chat."]}
        return dcc.send_string(json.dumps(payload, indent=2), filename="research_brief.json")

    @app.callback(Output("newsroom-download-markdown", "data"), Input("newsroom-export-markdown", "n_clicks"), State("newsroom-brief-store", "data"), prevent_initial_call=True)
    def export_markdown(n_clicks: int, brief: list[dict[str, Any]]):
        return dcc.send_string(_brief_markdown(brief or []), filename="research_brief.md")
