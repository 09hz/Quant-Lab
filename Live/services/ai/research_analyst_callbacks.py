from __future__ import annotations

from typing import Any

from dash import Input, Output, State, dcc, html, no_update


def _clean_text(value: Any, *, max_len: int = 4000) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = " ".join(text.split())
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "..."
    return text


def _extract_answer_text(result: Any) -> str:
    if result is None:
        return ""

    if isinstance(result, str):
        return result.strip()

    if isinstance(result, dict):
        for key in ("answer", "text", "content", "message", "response", "output"):
            value = result.get(key)
            if value:
                return str(value).strip()
        return str(result).strip()

    for attr in ("answer", "text", "content", "message", "response", "output"):
        try:
            value = getattr(result, attr)
            if value:
                return str(value).strip()
        except Exception:
            pass

    return str(result).strip()


def _call_ai_research_advisor(*, system_prompt: str, user_prompt: str, context: str, max_output: int) -> str:
    # Call the shared advisory AI service with a real Research Analyst output budget.
    try:
        from services.ai.advisor import build_ai_advisor_service
    except Exception as exc:
        raise RuntimeError(f"AI advisor service is unavailable: {exc}") from exc

    advisor = build_ai_advisor_service()

    try:
        max_output_int = max(800, min(8000, int(max_output or 3000)))
    except Exception:
        max_output_int = 3000

    context_text = str(context or "")
    separator = chr(10) + chr(10)
    combined_prompt = separator.join(part for part in (str(user_prompt or ""), context_text) if part)

    # Keep context large enough for Research Analyst evidence packets, but bounded.
    context_budget = max(18000, min(50000, len(context_text) + 2500))

    attempts = (
        {
            "prompt": user_prompt,
            "context": context_text,
            "system_prompt": system_prompt,
            "max_output_tokens": max_output_int,
            "max_context_chars": context_budget,
        },
        {
            "prompt": user_prompt,
            "context": context_text,
            "system_prompt": system_prompt,
            "max_output_tokens": max_output_int,
        },
        {
            "prompt": combined_prompt,
            "system_prompt": system_prompt,
            "max_output_tokens": max_output_int,
        },
        {
            "prompt": combined_prompt,
            "max_output_tokens": max_output_int,
        },
    )

    last_error: Exception | None = None

    for kwargs in attempts:
        try:
            result = advisor.ask(**kwargs)

            ok_value = getattr(result, "ok", None)
            if ok_value is False:
                reason = str(getattr(result, "reason", "") or "AI advisor returned a blocked or failed result.")
                raise RuntimeError(reason)

            text = _extract_answer_text(result)
            if text:
                return text

            reason = str(getattr(result, "reason", "") or "").strip()
            if reason:
                raise RuntimeError(reason)

        except TypeError as exc:
            # Older advisor signatures may not support every keyword. Try the
            # next narrower attempt before failing.
            last_error = exc
            continue
        except Exception as exc:
            last_error = exc
            break

    if last_error is not None:
        raise RuntimeError(str(last_error)) from last_error

    raise RuntimeError("AI advisor returned an empty response.")

def _source_links_children(packet: dict[str, Any]) -> list[Any]:
    links = packet.get("source_links") or []
    if not links:
        return [html.Div("No source links found in the current evidence packet.", className="research-analyst-muted")]

    rows: list[Any] = [
        html.Div("Sources used", className="research-analyst-source-title")
    ]

    for link in links[:12]:
        title = _clean_text(link.get("title"), max_len=140) or "Source"
        source = _clean_text(link.get("source"), max_len=80)
        validity = _clean_text(link.get("validity"), max_len=40) or "unknown"
        url = _clean_text(link.get("url"), max_len=800)

        meta = " - ".join(part for part in (source, f"validity: {validity}") if part)

        if url:
            rows.append(
                html.Div(
                    className="research-analyst-source-row",
                    children=[
                        html.A(title, href=url, target="_blank", rel="noopener noreferrer"),
                        html.Div(meta, className="research-analyst-source-meta"),
                    ],
                )
            )
        else:
            rows.append(
                html.Div(
                    className="research-analyst-source-row",
                    children=[
                        html.Div(title),
                        html.Div(meta, className="research-analyst-source-meta"),
                    ],
                )
            )

    return rows




def _research_items_from_payload(payload: Any, *, max_items: int = 50) -> list[dict[str, Any]]:
    # Return plain dict research items from common Dash store payload shapes.
    items: list[Any] = []

    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, tuple):
        items = list(payload)
    elif isinstance(payload, dict):
        for key in (
            "items",
            "results",
            "brief",
            "brief_items",
            "selected_items",
            "research_items",
            "evidence_items",
            "sources",
            "links",
        ):
            value = payload.get(key)
            if isinstance(value, (list, tuple)):
                items = list(value)
                break

    out: list[dict[str, Any]] = []
    for raw in items:
        if isinstance(raw, dict):
            out.append(dict(raw))
        elif hasattr(raw, "__dict__"):
            try:
                out.append(dict(vars(raw)))
            except Exception:
                continue

        if len(out) >= max_items:
            break

    return out


def _extract_fred_series_id(item: dict[str, Any]) -> str:
    """Best-effort extraction of a FRED series id from hydrated brief cards."""
    if not isinstance(item, dict):
        return ""

    for key in ("series_id", "fred_series_id", "ticker"):
        value = str(item.get(key) or "").upper().strip()
        if value and len(value) <= 24 and value.replace("_", "").replace("-", "").isalnum():
            return value

    metadata = item.get("metadata") or {}
    if isinstance(metadata, dict):
        for key in ("series_id", "fred_series_id"):
            value = str(metadata.get(key) or "").upper().strip()
            if value and len(value) <= 24 and value.replace("_", "").replace("-", "").isalnum():
                return value

    url = str(item.get("url") or item.get("link") or "").strip()
    marker = "/series/"
    if marker in url:
        value = url.rsplit(marker, 1)[-1].split("?", 1)[0].split("#", 1)[0].upper().strip("/")
        if value and len(value) <= 24 and value.replace("_", "").replace("-", "").isalnum():
            return value

    title = str(item.get("title") or "").upper()
    summary = str(item.get("summary") or "").upper()
    for token in (
        "CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE",
        "DGS2", "DGS10", "FEDFUNDS", "T10Y2Y",
        "VIXCLS", "SP500", "NASDAQCOM",
        "PAYEMS", "UNRATE", "UMCSENT",
        "IPMAN", "INDPRO", "DGORDER", "AMTMNO", "DCOILWTICO",
    ):
        if token in title or token in summary:
            return token

    return ""


def _is_hydrated_fred_item(item: dict[str, Any]) -> bool:
    """Return True for user-approved hydrated official FRED evidence cards."""
    if not isinstance(item, dict):
        return False

    kind = str(item.get("kind") or item.get("type") or "").lower()
    source = str(item.get("source") or item.get("provider") or "").lower()
    summary = str(item.get("summary") or "").lower()
    title = str(item.get("title") or "").lower()
    role = str(item.get("evidence_role") or item.get("source_role") or "").lower()

    return (
        ("fred" in source)
        and (
            "fred-hydrated-official-data" in kind
            or "hydrated official fred" in summary
            or "fred hydrated official data" in title
            or "confirmed official fred data" in summary
            or "confirmed-official" in role
        )
    )


def _hydrated_fred_manifest_markdown(items: list[dict[str, Any]]) -> str:
    # Create a compact authoritative manifest so approved FRED cards survive context trimming.
    hydrated = [item for item in (items or []) if _is_hydrated_fred_item(item)]
    if not hydrated:
        return ""

    series_ids: list[str] = []
    for item in hydrated:
        series_id = _extract_fred_series_id(item)
        if series_id and series_id not in series_ids:
            series_ids.append(series_id)

    lines = [
        "# Approved Hydrated FRED Official Data Cards",
        "",
        f"Approved hydrated FRED official data card count: {len(series_ids)}",
        "Approved hydrated FRED series IDs:",
        ", ".join(series_ids) if series_ids else "none",
        "",
        "Treat every listed series ID as a distinct approved hydrated FRED card.",
        "If any macro anchor conflicts with this manifest, prioritize this manifest.",
    ]
    return "\n".join(lines).strip() + "\n"

def _research_item_key(item: dict[str, Any]) -> str:
    # User-approved hydrated FRED evidence cards are distinct confirmed data cards.
    # Do not collapse them with macro-anchor/source-discovery cards that reuse the
    # same FRED URL. Key them by series id first.
    if _is_hydrated_fred_item(item):
        series_id = _extract_fred_series_id(item)
        if series_id:
            return "hydrated-fred:" + series_id.lower()

    url = str(item.get("url") or item.get("link") or "").strip().lower()
    if url:
        return "url:" + url

    item_id = str(item.get("id") or "").strip().lower()
    if item_id:
        return "id:" + item_id

    source = str(item.get("source") or item.get("publisher") or "").strip().lower()
    title = str(item.get("title") or item.get("headline") or item.get("name") or "").strip().lower()
    return "title:" + source + ":" + title


def _merge_newsroom_payloads(*payloads: Any, max_items: int = 28) -> list[dict[str, Any]]:
    # Merge brief, result, and supplemental sources without duplicating URLs/titles.
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    for payload in payloads:
        for item in _research_items_from_payload(payload, max_items=max_items * 2):
            key = _research_item_key(item)
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= max_items:
                return merged

    return merged


def _build_supplemental_research_sources(
    *,
    question: str,
    topic: str,
    symbol: str,
    selected_sources: list[str] | tuple[str, ...] | None,
    max_items: int = 12,
) -> tuple[list[dict[str, Any]], str, str | None]:
    # Build extra source candidates through approved Newsroom/FRED pipelines.
    #
    # Structured official data is inserted first. Generic search landing pages
    # are kept as source-discovery context only.
    question_clean = _clean_text(question, max_len=500)
    topic_clean = _clean_text(topic, max_len=240)
    symbol_clean = _clean_text(symbol, max_len=32).upper()

    query_parts = [
        symbol_clean,
        topic_clean,
        question_clean,
        "market impact sector impact tech manufacturing current quarter earnings guidance macro rates inflation PMI industrial production financial conditions volatility yields",
    ]
    query = " ".join(part for part in query_parts if part).strip()
    query = _clean_text(query, max_len=900)

    sources = list(selected_sources or [])
    if not sources:
        sources = ["fred", "sec", "bls", "bea", "fed", "news"]

    supplemental: list[dict[str, Any]] = []
    errors: list[str] = []

    # 1) Structured official gap-fill first.
    try:
        from services.research.research_analyst_gap_fill import build_structured_gap_fill_items

        structured_items, scope_plan, structured_error = build_structured_gap_fill_items(
            question=question_clean,
            topic=topic_clean,
            symbol=symbol_clean,
            selected_sources=sources,
            max_items=max(8, min(18, max_items + 6)),
            fetch_live=True,
        )
        for item in structured_items:
            if isinstance(item, dict):
                metadata = dict(item.get("metadata") or {})
                metadata["research_analyst_scope_plan"] = {
                    "scopes": scope_plan.get("scopes", []),
                    "evidence_labels": scope_plan.get("evidence_labels", []),
                }
                item["metadata"] = metadata
                supplemental.append(item)
        if structured_error:
            errors.append(f"Structured gap-fill warning: {structured_error}")
    except Exception as exc:
        errors.append(f"Structured gap-fill unavailable: {exc}")

    # 2) Search/discovery links second.
    try:
        from services.research.newsroom_callbacks import _build_results
    except Exception as exc:
        return supplemental[:max_items], query, "; ".join(errors + [f"Newsroom source builder unavailable: {exc}"])

    try:
        raw_results = _build_results(query, sources)
    except Exception as exc:
        return supplemental[:max_items], query, "; ".join(errors + [f"Supplemental source build failed: {exc}"])

    try:
        from services.research.result_hygiene import clean_newsroom_results

        raw_results = clean_newsroom_results(raw_results)
    except Exception:
        pass

    for index, raw in enumerate(raw_results or [], start=1):
        if not isinstance(raw, dict):
            continue

        item = dict(raw)
        item["id"] = f"research-analyst-supplemental-{index}-{item.get('id', index)}"
        item["source_role"] = item.get("source_role") or "source-discovery"
        item["used_for_ai"] = True
        item["selectable"] = True

        metadata = dict(item.get("metadata") or {})
        metadata["research_analyst_supplemental"] = True
        metadata["supplemental_query"] = query
        metadata["source_discovery_only"] = True
        item["metadata"] = metadata

        summary = _clean_text(item.get("summary"), max_len=900)
        discovery_note = (
            "Source-discovery candidate only. Use this to identify where to look next; "
            "do not treat a search landing page as confirmed market evidence. "
        )
        item["summary"] = discovery_note + summary if summary else discovery_note
        if not item.get("confidence"):
            item["confidence"] = "low"
        if not item.get("validity"):
            item["validity"] = "source-discovery"

        supplemental.append(item)
        if len(supplemental) >= max_items:
            break

    return supplemental[:max_items], query, "; ".join(errors) if errors else None


def _brief_only_requested(question: str) -> bool:
    # Return True when the user explicitly asks to audit only the approved Newsroom brief.
    q = " ".join(str(question or "").strip().lower().split())
    if not q:
        return False
    triggers = (
        "approved newsroom brief only",
        "current approved newsroom brief only",
        "newsroom brief only",
        "approved brief only",
        "brief only",
        "audit the current approved newsroom brief only",
        "audit the approved newsroom brief only",
        "use only the approved newsroom brief",
        "use the current approved newsroom brief only",
    )
    return any(token in q for token in triggers)



def _hydrated_fred_audit_requested(question: str) -> bool:
    """
    Return True only for narrow count/list audit questions.

    Do not trigger this path for normal Research Analyst requests that ask for
    market impact, sector impact, summaries, implications, correlations, or a
    bullish/bearish/mixed read.
    """
    q = " ".join(str(question or "").strip().lower().split())
    if not q:
        return False

    if not ("hydrated fred" in q or "fred official data cards" in q):
        return False

    normal_analysis_terms = (
        "summarize",
        "summary",
        "market impact",
        "sector impact",
        "tech sector",
        "manufacturing sector",
        "bullish",
        "bearish",
        "mixed",
        "correlation",
        "transmission",
        "implication",
        "implications",
        "executive read",
        "current-quarter",
        "current quarter",
        "final read",
        "playbook",
        "strategy",
        "backtest",
        "quant",
    )
    if any(term in q for term in normal_analysis_terms):
        return False

    audit_terms = (
        "how many",
        "exact count",
        "count of",
        "tell me how many",
        "list every",
        "list the",
    )
    series_terms = (
        "series id",
        "series ids",
        "official data cards",
        "hydrated fred",
        "evidence packet",
    )
    return any(term in q for term in audit_terms) and any(term in q for term in series_terms)

def _enhance_research_analyst_user_prompt(question: str, output_style: str = "concise", supplemental_count: int = 0) -> str:
    """Build a non-recursive Research Analyst question with market-impact guardrails."""
    clean_question = _clean_text(question, max_len=1200)
    style = str(output_style or "concise").strip() or "concise"
    try:
        supplemental_count_int = max(0, int(supplemental_count or 0))
    except Exception:
        supplemental_count_int = 0

    instructions = [
        "Answer using only the evidence packet plus approved supplemental Newsroom sources.",
        "Use a professional institutional research tone suitable for a trading research platform.",
        "Do not use emojis, check marks, cross marks, warning icons, chart icons, or decorative symbols.",
        "Use plain words instead of icons: confirmed, missing, warning, rising, falling, flat, improving, deteriorating.",
        "When an Approved Hydrated FRED Official Data Cards manifest is present, treat that manifest as authoritative and list every series in it before declaring evidence missing.",
        "Treat FRED structured macro anchors as confirmed official data when present; treat search landing pages as discovery context only.",
        "Use trend deltas (latest, prior, 1-period, 3-period, and 6-period changes) when provided before making sector or quarter claims.",
        "Treat FRED structured observations as confirmed official data when values are present.",
        "Treat generic search landing pages as source-discovery context only, not confirmed evidence.",
        "Label conclusions as confirmed, proxy-only, or missing depending on the evidence available.",
        "Do not invent current facts, article contents, prices, earnings, or sector data that are not in the evidence.",
        "Do not assign a number, level, or month-over-month change to a series unless that exact value belongs to that same named series in the evidence packet.",
        "Keep CPI, core CPI, PCE, core PCE, FEDFUNDS, yields, earnings, and sector data separate.",
        "If the evidence is incomplete, say what is missing and explain how that limits confidence.",
        "Use this answer structure:",
        "1. Executive read",
        "2. Important highlights",
        "3. Market impact",
        "4. Tech sector impact",
        "5. Manufacturing sector impact",
        "6. Bullish/bearish/mixed current-quarter read",
        "7. Correlation/transmission path",
        "8. What could invalidate the view",
        "9. Sources used and remaining gaps",
        "10. Quant research playbook (only when user asks how to trade, backtest, use this information, or build a strategy): regime label, tradable hypotheses, symbols to test, filters, invalidation rules, and backtest plan.",
        "Never present the quant playbook as a live trade recommendation; it is research-only and must require backtesting/validation before use.",
        "Finish with a final read. Always end with a final read that says bullish, bearish, mixed, or insufficient evidence.",
        "For concise style, use short paragraphs instead of long bullet-only output.",
    ]

    if supplemental_count_int > 0:
        instructions.insert(
            1,
            f"The evidence packet includes {supplemental_count_int} supplemental Newsroom source candidate(s); use them as context, but label them as supplemental and lower-confidence unless confirmed by official or filing evidence.",
        )

    if not clean_question:
        clean_question = (
            "Summarize the evidence packet, explain market and sector impact, "
            "and give a bullish/bearish/mixed read with confidence."
        )

    parts = [
        clean_question,
        "",
        f"Requested output style: {style}",
        "Research Analyst instructions:",
    ]
    parts.extend(f"- {item}" for item in instructions)
    return "\n".join(parts)
def register_research_analyst_callbacks(app) -> None:
    """Register Newsroom Research Analyst Q&A callbacks."""

    @app.callback(
        Output("research-analyst-response", "children"),
        Output("research-analyst-status", "children"),
        Output("research-analyst-sources", "children"),
        Input("research-analyst-ask", "n_clicks"),
        State("research-analyst-question", "value"),
        State("research-analyst-style", "value"),
        State("research-analyst-max-output", "value"),
        State("newsroom-brief-store", "data"),
        State("newsroom-results-store", "data"),
        State("newsroom-topic-input", "value"),
        State("newsroom-source-filter", "value"),
        State("watch-symbol-dropdown", "value"),
        prevent_initial_call=True,
    )
    def ask_research_analyst(
        n_clicks,
        question,
        output_style,
        max_output,
        brief_store,
        results_store,
        topic,
        selected_sources,
        symbol,
    ):
        if not n_clicks:
            return no_update, no_update, no_update

        question = _clean_text(question, max_len=800)
        if not question:
            return (
                html.Div("Ask a research question first.", className="research-analyst-warning"),
                "Waiting for a question.",
                "",
            )

        output_style = str(output_style or "concise").strip() or "concise"
        brief_only_mode = _brief_only_requested(question)
        audit_only_mode = _hydrated_fred_audit_requested(question)
        analysis_question = question if audit_only_mode else _enhance_research_analyst_user_prompt(question, output_style)
        try:
            max_output_int = max(800, min(6000, int(max_output or 2000)))
        except Exception:
            max_output_int = 2000

        try:
            from services.research.newsroom_evidence_bridge import (
                build_newsroom_evidence_packet,
                evidence_packet_to_markdown,
                extract_newsroom_evidence_items,
            )
            from services.ai.research_analyst import ResearchAnalystService

            brief_items = _research_items_from_payload(brief_store, max_items=96)
            result_items = _research_items_from_payload(results_store, max_items=24)
            if brief_only_mode:
                supplemental_items = []
                supplemental_query = "approved-newsroom-brief-only"
                supplemental_error = None
            else:
                supplemental_items, supplemental_query, supplemental_error = _build_supplemental_research_sources(
                    question=question,
                    topic=str(topic or "").strip(),
                    symbol=str(symbol or "").upper().strip(),
                    selected_sources=selected_sources,
                    max_items=12,
                )

            macro_anchor_items: list[dict[str, Any]] = []
            macro_anchor_coverage: dict[str, Any] = {}
            macro_anchor_error = None
            try:
                from services.research.research_analyst_macro_anchors import build_macro_anchor_evidence

                macro_anchor_items, macro_anchor_coverage, macro_anchor_error = build_macro_anchor_evidence(
                    question=question,
                    topic=str(topic or "").strip(),
                    symbol=str(symbol or "").upper().strip(),
                    selected_sources=selected_sources,
                    max_items=28,
                )
            except Exception as exc:
                macro_anchor_error = f"Macro anchor build failed: {exc}"
            if brief_only_mode:
                macro_anchor_items = []
                macro_anchor_coverage = {"mode": "approved-newsroom-brief-only"}
                macro_anchor_error = None


            # Include mandatory macro anchors directly in the evidence packet.
            #
            # Earlier 36i builds macro_anchor_items but only stores their coverage
            # metadata under packet["mandatory_macro_anchors"]. That status metadata
            # is useful for the UI, but the LLM mainly sees packet["items"] via
            # evidence_packet_to_markdown(...). Merge anchors first so CPI/PCE,
            # FEDFUNDS, yields, market proxies, and manufacturing anchors are
            # available as actual evidence, not just as hidden callback metadata.
            # User-approved Newsroom brief items must be highest priority.
            # In particular, hydrated FRED recommendation cards contain the user's
            # approved official observations/deltas. Keep them before auto-built
            # macro anchors, result-store leftovers, supplemental discovery links,
            # and the quant playbook scaffold.
            combined_payload = _merge_newsroom_payloads(
                brief_items,
                macro_anchor_items,
                result_items,
                supplemental_items,
                max_items=96,
            )

            packet = build_newsroom_evidence_packet(
                combined_payload,
                question=question,
                symbol=str(symbol or "").upper().strip(),
                topic=str(topic or "").strip(),
                max_items=96,
            )
            packet["mandatory_macro_anchors"] = {
                "enabled": True,
                "item_count": len(macro_anchor_items),
                "coverage": macro_anchor_coverage,
                "error": macro_anchor_error,
                "note": "Structured FRED macro anchors are loaded before search/discovery links for market-impact questions.",
            }

            packet["supplemental_research"] = {
                "enabled": True,
                "query": supplemental_query,
                "item_count": len(supplemental_items),
                "error": supplemental_error,
                "note": "Supplemental sources are pulled from approved Newsroom source builders when the brief may not cover the full question.",
            }

            packet["approved_newsroom_brief_only"] = bool(brief_only_mode)

            quant_playbook_error = None
            try:
                from services.ai.quant_research_playbook import build_quant_research_playbook

                packet["quant_research_playbook"] = build_quant_research_playbook(
                    question=question,
                    evidence_items=packet.get("items", []),
                    symbol=str(symbol or "").upper().strip(),
                    topic=str(topic or "").strip(),
                    max_hypotheses=5,
                )
            except Exception as exc:
                quant_playbook_error = f"Quant playbook unavailable: {exc}"
                packet["quant_research_playbook"] = {
                    "enabled": False,
                    "error": quant_playbook_error,
                    "safeguards": [
                        "Research-only output; no broker access or order placement.",
                    ],
                }

            item_count = int(packet.get("item_count", 0) or 0)
            if item_count <= 0:
                return (
                    html.Div(
                        [
                            html.Div("No evidence packet could be built.", className="research-analyst-warning"),
                            html.Div(
                                "Add items to the Newsroom brief or fetch Newsroom results before asking the Research Analyst.",
                                className="research-analyst-muted",
                            ),
                        ]
                    ),
                    "No evidence available.",
                    "",
                )

            context = evidence_packet_to_markdown(packet)

            hydrated_brief_items = [item for item in brief_items if _is_hydrated_fred_item(item)]
            hydrated_manifest = _hydrated_fred_manifest_markdown(hydrated_brief_items)
            if hydrated_manifest:
                context = hydrated_manifest + "\n\n" + context

            # Hydrated FRED audit-only deterministic response.
            # For count/list audit questions, answer directly from the approved brief
            # instead of sending a large market-impact prompt through the LLM.
            if audit_only_mode:
                hydrated_series_ids = [
                    _extract_fred_series_id(item)
                    for item in hydrated_brief_items
                    if _extract_fred_series_id(item)
                ]

                audit_lines = [
                    f"Hydrated FRED official data cards: {len(hydrated_series_ids)}",
                    "",
                    "Hydrated FRED series IDs received:",
                ]
                audit_lines.extend(f"- {series_id}" for series_id in hydrated_series_ids)

                audit_status = (
                    f"Audited approved Newsroom brief. "
                    f"User-approved hydrated FRED brief cards: {len(hydrated_series_ids)}. "
                    "Approved Newsroom brief only mode: enabled."
                )

                return (
                    dcc.Markdown("\n".join(audit_lines), className="research-analyst-markdown", link_target="_blank"),
                    audit_status,
                    _source_links_children(packet),
                )

            try:
                from services.ai.quant_research_playbook import playbook_to_markdown

                quant_playbook_md = playbook_to_markdown(packet.get("quant_research_playbook", {}))
                if quant_playbook_md:
                    context = context + "\n\n" + quant_playbook_md
            except Exception:
                pass

            hydrated_series_ids = [
                _extract_fred_series_id(item)
                for item in hydrated_brief_items
                if _extract_fred_series_id(item)
            ]

            prompt = ResearchAnalystService().build_prompt(
                question=analysis_question,
                raw_items=packet.get("items", []),
                symbol=str(symbol or "").upper().strip(),
                topic=str(topic or "").strip(),
                max_items=96,
                output_style=output_style,
                authoritative_hydrated_manifest=hydrated_manifest,
                authoritative_hydrated_fred_count=len(hydrated_brief_items),
                authoritative_hydrated_fred_series_ids=hydrated_series_ids,
            )

            if audit_only_mode:
                user_prompt = question
            else:
                user_prompt = _enhance_research_analyst_user_prompt(
                    prompt.user_prompt,
                    output_style=output_style,
                    supplemental_count=len(supplemental_items),
                )

            answer = _call_ai_research_advisor(
                system_prompt=prompt.system_prompt,
                user_prompt=user_prompt,
                context=context,
                max_output=max_output_int,
            )

            macro_anchor_note = ""
            if macro_anchor_items:
                macro_anchor_note = f" Added {len(macro_anchor_items)} structured macro anchor item(s)."
            if macro_anchor_error:
                macro_anchor_note += f" Macro anchor warning: {macro_anchor_error}"

            supplemental_note = ""
            if supplemental_items:
                supplemental_note = f" Added {len(supplemental_items)} supplemental Newsroom source candidate(s)."
            if supplemental_error:
                supplemental_note += f" Supplemental source warning: {supplemental_error}"

            quant_playbook_note = ""
            if packet.get("quant_research_playbook", {}).get("enabled"):
                quant_playbook_note = " Added quant research playbook."
            if quant_playbook_error:
                quant_playbook_note += f" Quant playbook warning: {quant_playbook_error}"

            hydrated_note = ""
            try:
                hydrated_count = len([item for item in brief_items if _is_hydrated_fred_item(item)])
                if hydrated_count:
                    hydrated_note = f" User-approved hydrated FRED brief cards: {hydrated_count}."
            except Exception:
                hydrated_note = ""

            brief_only_note = " Approved Newsroom brief only mode: enabled." if brief_only_mode else ""

            status = (
                f"Answered from {item_count} evidence item(s). "
                "Current facts are limited to the Newsroom evidence packet."
                + hydrated_note
                + brief_only_note
                + macro_anchor_note
                + supplemental_note
                + quant_playbook_note
            )

            return (
                dcc.Markdown(answer, className="research-analyst-markdown", link_target="_blank"),
                status,
                _source_links_children(packet),
            )

        except Exception as exc:
            error_text = str(exc)
            return (
                html.Div(
                    [
                        html.Div("Research Analyst error", className="research-analyst-warning"),
                        html.Pre(error_text, className="research-analyst-error-pre"),
                    ]
                ),
                "Research Analyst failed.",
                "",
            )
