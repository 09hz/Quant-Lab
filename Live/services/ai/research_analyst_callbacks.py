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
    try:
        from services.ai.advisor import build_ai_advisor_service
    except Exception as exc:
        raise RuntimeError(f"AI advisor service is unavailable: {exc}") from exc

    advisor = build_ai_advisor_service()

    attempts = (
        {
            "prompt": user_prompt,
            "context": context,
            "system_prompt": system_prompt,
            "max_output": max_output,
        },
        {
            "user_prompt": user_prompt,
            "context": context,
            "system_prompt": system_prompt,
            "max_output": max_output,
        },
        {
            "prompt": user_prompt,
            "context": context,
            "max_output": max_output,
        },
        {
            "user_prompt": user_prompt,
            "context": context,
            "max_output": max_output,
        },
    )

    last_error: Exception | None = None

    for kwargs in attempts:
        try:
            result = advisor.ask(**kwargs)
            text = _extract_answer_text(result)
            if text:
                return text
        except TypeError as exc:
            last_error = exc
            continue
        except Exception as exc:
            last_error = exc
            break

    try:
        result = advisor.ask(user_prompt + "\n\n" + context)
        text = _extract_answer_text(result)
        if text:
            return text
    except Exception as exc:
        last_error = exc

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
        try:
            max_output_int = max(300, min(4000, int(max_output or 1200)))
        except Exception:
            max_output_int = 1200

        try:
            from services.research.newsroom_evidence_bridge import (
                build_newsroom_evidence_packet,
                evidence_packet_to_markdown,
                extract_newsroom_evidence_items,
            )
            from services.ai.research_analyst import ResearchAnalystService

            brief_items = extract_newsroom_evidence_items(brief_store, max_items=16)
            payload = brief_store if brief_items else results_store

            packet = build_newsroom_evidence_packet(
                payload,
                question=question,
                symbol=str(symbol or "").upper().strip(),
                topic=str(topic or "").strip(),
                max_items=16,
            )

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
                question=question,
                raw_items=packet.get("items", []),
                symbol=str(symbol or "").upper().strip(),
                topic=str(topic or "").strip(),
                max_items=16,
                output_style=output_style,
            )

            answer = _call_ai_research_advisor(
                system_prompt=prompt.system_prompt,
                user_prompt=prompt.user_prompt,
                context=context,
                max_output=max_output_int,
            )

            status = (
                f"Answered from {item_count} evidence item(s). "
                "Current facts are limited to the Newsroom evidence packet."
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
