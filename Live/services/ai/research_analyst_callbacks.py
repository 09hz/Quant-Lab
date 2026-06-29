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


def _research_item_key(item: dict[str, Any]) -> str:
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
    # Build extra source candidates through the approved Newsroom source pipeline.
    #
    # This is intentionally not unrestricted browsing. It uses the same Newsroom
    # source builders/search-link generators already exposed in the app, then the
    # Research Analyst must label them as supplemental evidence.
    question_clean = _clean_text(question, max_len=500)
    topic_clean = _clean_text(topic, max_len=240)
    symbol_clean = _clean_text(symbol, max_len=32).upper()

    query_parts = [
        symbol_clean,
        topic_clean,
        question_clean,
        "market impact sector impact tech manufacturing current quarter earnings guidance macro rates inflation PMI industrial production",
    ]
    query = " ".join(part for part in query_parts if part).strip()
    query = _clean_text(query, max_len=900)

    sources = list(selected_sources or [])
    if not sources:
        sources = ["fred", "sec", "bls", "bea", "fed", "news"]

    try:
        from services.research.newsroom_callbacks import _build_results
    except Exception as exc:
        return [], query, f"Newsroom source builder unavailable: {exc}"

    try:
        raw_results = _build_results(query, sources)
    except Exception as exc:
        return [], query, f"Supplemental source build failed: {exc}"

    try:
        from services.research.result_hygiene import clean_newsroom_results

        raw_results = clean_newsroom_results(raw_results)
    except Exception:
        pass

    supplemental: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_results or [], start=1):
        if not isinstance(raw, dict):
            continue

        item = dict(raw)
        item["id"] = f"research-analyst-supplemental-{index}-{item.get('id', index)}"
        item["source_role"] = "supplemental-gap-fill"
        item["used_for_ai"] = True
        item["selectable"] = True

        metadata = dict(item.get("metadata") or {})
        metadata["research_analyst_supplemental"] = True
        metadata["supplemental_query"] = query
        item["metadata"] = metadata

        summary = _clean_text(item.get("summary"), max_len=900)
        if summary:
            item["summary"] = (
                "Supplemental source candidate for missing market/sector context. "
                + summary
            )
        else:
            item["summary"] = (
                "Supplemental source candidate returned by the approved Newsroom "
                "source pipeline for this Research Analyst question."
            )

        supplemental.append(item)
        if len(supplemental) >= max_items:
            break

    return supplemental, query, None


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
        analysis_question = _enhance_research_analyst_user_prompt(question, output_style)
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

            brief_items = _research_items_from_payload(brief_store, max_items=24)
            result_items = _research_items_from_payload(results_store, max_items=24)
            supplemental_items, supplemental_query, supplemental_error = _build_supplemental_research_sources(
                question=question,
                topic=str(topic or "").strip(),
                symbol=str(symbol or "").upper().strip(),
                selected_sources=selected_sources,
                max_items=12,
            )

            combined_payload = _merge_newsroom_payloads(
                brief_items,
                result_items,
                supplemental_items,
                max_items=28,
            )

            packet = build_newsroom_evidence_packet(
                combined_payload,
                question=question,
                symbol=str(symbol or "").upper().strip(),
                topic=str(topic or "").strip(),
                max_items=28,
            )
            packet["supplemental_research"] = {
                "enabled": True,
                "query": supplemental_query,
                "item_count": len(supplemental_items),
                "error": supplemental_error,
                "note": "Supplemental sources are pulled from approved Newsroom source builders when the brief may not cover the full question.",
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
            prompt = ResearchAnalystService().build_prompt(
                question=analysis_question,
                raw_items=packet.get("items", []),
                symbol=str(symbol or "").upper().strip(),
                topic=str(topic or "").strip(),
                max_items=16,
                output_style=output_style,
            )

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

            supplemental_note = ""
            if supplemental_items:
                supplemental_note = f" Added {len(supplemental_items)} supplemental Newsroom source candidate(s)."
            if supplemental_error:
                supplemental_note += f" Supplemental source warning: {supplemental_error}"

            status = (
                f"Answered from {item_count} evidence item(s). "
                "Current facts are limited to the Newsroom evidence packet."
                + supplemental_note
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
