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
    """
    Stable de-duplication key for Research Analyst evidence items.

    SEC companyfacts cards must not be deduped by URL because several distinct
    cards often point to the same SEC filing index or same companyfacts JSON URL.
    """
    if not isinstance(item, dict):
        return ""

    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    def pick(*names: str) -> str:
        for name in names:
            value = item.get(name)
            if value not in (None, ""):
                return str(value)
            value = metadata.get(name)
            if value not in (None, ""):
                return str(value)
        return ""

    blob = " ".join(
        str(x or "")
        for x in [
            item.get("kind"),
            item.get("source"),
            item.get("title"),
            item.get("summary"),
            item.get("evidence_role"),
            item.get("path"),
            item.get("url"),
            metadata.get("kind"),
            metadata.get("source"),
            metadata.get("title"),
            metadata.get("summary"),
            metadata.get("evidence_role"),
            metadata.get("path"),
            metadata.get("url"),
            metadata.get("source_url"),
        ]
    ).lower()

    is_sec_companyfacts = (
        "sec-companyfacts" in blob
        or "sec edgar companyfacts" in blob
        or "confirmed-official-sec-companyfacts" in blob
        or "normal newsroom checkbox/add selected to brief" in blob
    )

    if is_sec_companyfacts:
        for key_name in ("brief_selection_id", "id", "brief_dedupe_key"):
            value = pick(key_name)
            if value:
                return "sec-card:" + value

        ticker = pick("ticker", "symbol")
        metric = pick("metric", "label")
        concept = pick("concept", "xbrl_concept", "tag")
        period_end = pick("period_end", "end", "period")
        filed = pick("filed", "filed_date", "filing_date")
        accession = pick("accession", "accn", "accession_number")
        value = pick("latest_value", "value", "val")
        unit = pick("unit", "latest_unit", "units")
        title = pick("title", "headline")
        return "sec-card:" + "|".join(
            [ticker, metric, concept, period_end, filed, accession, value, unit, title]
        ).lower()

    series_id = ""
    try:
        series_id = _extract_fred_series_id(item)
    except Exception:
        series_id = ""
    if series_id:
        return "fred-series:" + str(series_id).upper()

    for key_name in ("brief_selection_id", "id", "brief_dedupe_key"):
        value = pick(key_name)
        if value:
            return key_name + ":" + value

    url = pick("url", "source_url", "link")
    if url:
        return "url:" + url

    source = pick("source", "publisher")
    title = pick("title", "headline", "name")
    if source or title:
        return "title:" + source.lower() + ":" + title.lower()

    return ""

def _merge_newsroom_payloads(*payloads: Any, max_items: int = 28) -> list[dict[str, Any]]:
    """
    Merge Newsroom evidence for the Research Analyst.

    If user-selected SEC/companyfacts brief cards are present, use all of them
    as the primary packet. Do not dedupe SEC cards by shared filing URL.
    """
    raw_items: list[dict[str, Any]] = []
    for payload in payloads:
        raw_items.extend(_research_items_from_payload(payload, max_items=max_items * 4))

    def text_blob(item: dict[str, Any]) -> str:
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        fields = [
            item.get("kind"),
            item.get("source"),
            item.get("title"),
            item.get("summary"),
            item.get("evidence_role"),
            item.get("path"),
            item.get("url"),
            metadata.get("kind"),
            metadata.get("source"),
            metadata.get("title"),
            metadata.get("summary"),
            metadata.get("evidence_role"),
            metadata.get("path"),
            metadata.get("url"),
            metadata.get("source_url"),
        ]
        return " ".join(str(x or "") for x in fields).lower()

    def is_sec_companyfacts_card(item: dict[str, Any]) -> bool:
        blob = text_blob(item)
        return (
            "confirmed-official-sec-companyfacts" in blob
            or "normal newsroom checkbox/add selected to brief" in blob
            or "sec-companyfacts-official-data-card" in blob
            or ("sec edgar companyfacts" in blob and "companyfacts" in blob)
        )

    def is_auto_extra_noise(item: dict[str, Any]) -> bool:
        blob = text_blob(item)
        return (
            "macro anchor" in blob
            or "macro-anchor" in blob
            or "structured fred macro anchors" in blob
            or "supplemental newsroom source candidate" in blob
            or "official evidence staging" in blob
            or "approved_structured_evidence" in blob
            or "quant research playbook" in blob
        )

    sec_items = [item for item in raw_items if isinstance(item, dict) and is_sec_companyfacts_card(item)]

    if sec_items:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for idx, item in enumerate(sec_items):
            key = _research_item_key(item)
            if not key:
                key = "sec-card-pos:" + str(idx)
            if key in seen:
                continue
            merged.append(item)
            seen.add(key)
            if len(merged) >= max_items:
                break
        return merged

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_items:
        if not isinstance(item, dict) or is_auto_extra_noise(item):
            continue
        key = _research_item_key(item)
        if not key:
            continue
        if key in seen:
            continue
        merged.append(item)
        seen.add(key)
        if len(merged) >= max_items:
            break

    return merged

def _build_supplemental_research_sources(*args, **kwargs):
    # Disabled: old automatic supplemental source path.
    # Use Newsroom selected cards / current Research Brief instead.
    return [], "disabled", None

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


def _quant_playbook_requested(*args, **kwargs):
    # Disabled: old optional auto-augmentation path.
    # Use Newsroom selected cards / current Research Brief instead.
    return False

def _enhance_research_analyst_user_prompt(question: str, output_style: str = "concise", supplemental_count: int = 0) -> str:
    """Build a flexible Research Analyst prompt. No fixed numbered template."""
    clean_question = _clean_text(question, max_len=1600)
    style = str(output_style or "concise").strip() or "concise"

    if not clean_question:
        clean_question = (
            "Give a practical research analyst read using the current Newsroom Research Brief. "
            "Separate brief evidence from interpretation and state what is missing."
        )

    instructions = [
        "Answer the user's question directly using the current Newsroom Research Brief as the primary source of current facts.",
        "When SEC companyfacts official-data cards are present, inventory every SEC card before interpreting. Do not silently omit any SEC card.",
        "For each SEC companyfacts card present, preserve its ticker, metric, value, unit, period end, filed date, form, accession, and concept.",
        "When making the practical analyst read, use all available SEC metrics together. If revenue, net income, EPS, operating income, cash, or shares are present, discuss each one at least briefly or explain why it is not relevant.",
        "Do not say SEC companyfacts cards are missing when SEC companyfacts official-data cards are present in the evidence packet or brief.",
        "Clearly separate brief evidence from interpretation. Use general accounting, market, and sector knowledge only as interpretation, not as new current facts.",
        "Do not use macro anchors, supplemental source candidates, official evidence staging files, or a quant research playbook unless the user explicitly asks for them.",
        "Do not use a fixed numbered template. Use natural short headings such as Brief evidence, Practical read, and Missing evidence only when they help readability.",
        "Use a professional institutional research tone that is direct and easy to read. Prefer short paragraphs and short lists. Avoid long rigid templates.",
        "Keep this research-only and simulation/advisory only. Do not provide live trading instructions, broker actions, order placement, position sizing, or personalized financial advice.",
        "If evidence is incomplete, explain the specific gap briefly, then still answer what can be answered from the available brief evidence.",
        f"Requested output style: {style}.",
        "",
        "User question:",
        clean_question,
    ]
    return "\n".join(instructions).strip()

def _approved_structured_evidence_markdown(*args, **kwargs):
    # Disabled: old optional auto-augmentation path.
    # Use Newsroom selected cards / current Research Brief instead.
    return ""

def _approved_structured_cards_for_brief(*args, **kwargs):
    # Disabled: old optional auto-augmentation path.
    # Use Newsroom selected cards / current Research Brief instead.
    return []

def _research_analyst_style_instruction(question: str) -> str:
    return (
        "Write like a professional research analyst. Make the result clear, direct, and easy to read. "
        "Do not force a fixed numbered template or a fixed bullet template. "
        "Use short headings and short paragraphs. Use bullets only when the user asks for a list "
        "or when they materially improve readability. "
        "Use the current Newsroom Research Brief for current facts. "
        "You may use general domain knowledge for interpretation when clearly labeled. "
        "Do not invent current facts that are not present in the brief or provided context."
    )

def _approved_structured_staging_blocked(*args, **kwargs):
    # Disabled: old optional auto-augmentation path.
    # Use Newsroom selected cards / current Research Brief instead.
    return ""

def _approved_structured_audit_requested(*args, **kwargs):
    # Disabled: old optional auto-augmentation path.
    # Use Newsroom selected cards / current Research Brief instead.
    return False

def _approved_structured_audit_answer(*args, **kwargs):
    # Disabled: old optional auto-augmentation path.
    # Use Newsroom selected cards / current Research Brief instead.
    return ""

def _approved_structured_sources_children(*args, **kwargs):
    # Disabled: old optional auto-augmentation path.
    # Use Newsroom selected cards / current Research Brief instead.
    return []

def _sec_companyfacts_full_evidence_markdown(*payloads: Any) -> str:
    """
    Build an explicit SEC companyfacts table from raw Newsroom brief/result data.

    Important: prefer raw dicts over _research_items_from_payload(), because the
    generic conversion can collapse rich SEC card metadata into source-title-only
    items.
    """
    import re

    def walk(obj: Any) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        if isinstance(obj, list):
            for value in obj:
                found.extend(walk(value))
            return found
        if isinstance(obj, dict):
            found.append(obj)
            for key in ("items", "source_links", "links", "results", "brief", "data", "metadata", "children"):
                value = obj.get(key)
                if isinstance(value, (list, dict)):
                    found.extend(walk(value))
            return found
        return found

    def pick(item: dict[str, Any], *names: str) -> str:
        pools = [item]
        for key in ("metadata", "data", "raw", "fact", "sec_fact", "extra"):
            value = item.get(key)
            if isinstance(value, dict):
                pools.append(value)
        for pool in pools:
            for name in names:
                value = pool.get(name)
                if value not in (None, ""):
                    return str(value)
        return ""

    def text_blob(item: dict[str, Any]) -> str:
        pools = [item]
        for key in ("metadata", "data", "raw", "fact", "sec_fact", "extra"):
            value = item.get(key)
            if isinstance(value, dict):
                pools.append(value)
        parts: list[str] = []
        for pool in pools:
            for name in (
                "id", "brief_selection_id", "brief_dedupe_key", "kind", "source",
                "title", "headline", "summary", "evidence_role", "path", "url",
                "source_url", "companyfacts_url", "filing_url", "metric", "concept",
            ):
                parts.append(str(pool.get(name) or ""))
        return " ".join(parts)

    def is_sec(item: dict[str, Any]) -> bool:
        blob = text_blob(item).lower()
        return (
            "sec-companyfacts" in blob
            or "sec edgar companyfacts" in blob
            or "confirmed-official-sec-companyfacts" in blob
            or "normal newsroom checkbox/add selected to brief" in blob
            or "from sec companyfacts" in blob
        )

    def parse_from_text(item: dict[str, Any]) -> dict[str, str]:
        text = text_blob(item)
        out: dict[str, str] = {}

        m = re.search(
            r"\(([A-Z]{1,6})\)\s+([A-Za-z_]+)\s*:\s*([-+0-9.,]+)\s+([A-Za-z/$]+)",
            text,
        )
        if m:
            out["ticker"] = m.group(1)
            out["metric"] = m.group(2)
            out["value"] = m.group(3).replace(",", "")
            out["unit"] = m.group(4)

        title_metric = re.search(r"\(([A-Z]{1,6})\)\s+([A-Za-z_]+)\s+from\s+SEC companyfacts", text, flags=re.I)
        if title_metric:
            out.setdefault("ticker", title_metric.group(1).upper())
            out.setdefault("metric", title_metric.group(2))

        patterns = {
            "period_end": r"period end\s+([0-9]{4}-[0-9]{2}-[0-9]{2})",
            "filed": r"filed(?: date)?\s*[:|]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
            "form": r"\b(10-[QK]|20-F|40-F)\b",
            "accession": r"accession\s*[:|]?\s*([0-9-]+)",
            "concept": r"concept\s*[:|]?\s*([A-Za-z0-9_:-]+)",
        }
        for key, pattern in patterns.items():
            mm = re.search(pattern, text, flags=re.I)
            if mm:
                out[key] = mm.group(1).rstrip(".")
        return out

    def row_from_item(item: dict[str, Any]) -> dict[str, str]:
        parsed = parse_from_text(item)
        title = pick(item, "title", "headline") or str(item.get("title") or item.get("headline") or "")
        metric = pick(item, "metric") or parsed.get("metric", "")

        # Do not use label as metric unless metric is absent; label can be a verbose concept label.
        if not metric:
            metric = pick(item, "label")

        if not metric and title:
            m = re.search(r"\)\s+([A-Za-z_]+)\s+from\s+SEC companyfacts", title, flags=re.I)
            if m:
                metric = m.group(1)

        return {
            "ticker": pick(item, "ticker", "symbol") or parsed.get("ticker", ""),
            "entity": pick(item, "entity", "company", "entityName"),
            "metric": metric,
            "value": pick(item, "latest_value", "value", "val") or parsed.get("value", ""),
            "unit": pick(item, "unit", "latest_unit", "units", "uom") or parsed.get("unit", ""),
            "period_end": pick(item, "period_end", "end", "period") or parsed.get("period_end", ""),
            "filed": pick(item, "filed", "filed_date", "filing_date") or parsed.get("filed", ""),
            "form": pick(item, "form", "filing_form") or parsed.get("form", ""),
            "accession": pick(item, "accession", "accn", "accession_number") or parsed.get("accession", ""),
            "concept": pick(item, "concept", "xbrl_concept", "tag") or parsed.get("concept", ""),
            "source": pick(item, "filing_url", "url", "source_url", "companyfacts_url", "link") or str(item.get("url") or ""),
            "title": title,
        }

    def parse_research_brief_markdown(md: str) -> list[dict[str, str]]:
        sections = re.split(r"\n###\s+SEC companyfacts official-data card\s*\n", md)
        rows: list[dict[str, str]] = []
        for section in sections[1:]:
            row: dict[str, str] = {}
            for raw_line in section.splitlines():
                line = raw_line.strip()
                if not line.startswith("- "):
                    continue
                key_value = line[2:].split(":", 1)
                if len(key_value) != 2:
                    continue
                key = key_value[0].strip().lower().replace(" ", "_")
                value = key_value[1].strip()
                mapping = {
                    "ticker": "ticker",
                    "entity": "entity",
                    "metric": "metric",
                    "latest_value": "value",
                    "unit": "unit",
                    "period_end": "period_end",
                    "filed_date": "filed",
                    "form": "form",
                    "accession": "accession",
                    "concept": "concept",
                    "source": "source",
                }
                if key in mapping:
                    row[mapping[key]] = value
            if row:
                rows.append(row)
        return rows

    rows: list[dict[str, str]] = []

    for payload in payloads:
        if isinstance(payload, str) and "SEC companyfacts official-data card" in payload:
            rows.extend(parse_research_brief_markdown(payload))

        for item in walk(payload):
            if isinstance(item, dict) and is_sec(item):
                row = row_from_item(item)
                if any(row.get(k) for k in ("metric", "concept", "value", "title")):
                    rows.append(row)

    # Last resort: use generic conversion only after raw extraction.
    for payload in payloads:
        try:
            for item in _research_items_from_payload(payload, max_items=200):
                if isinstance(item, dict) and is_sec(item):
                    row = row_from_item(item)
                    if any(row.get(k) for k in ("metric", "concept", "value", "title")):
                        rows.append(row)
        except Exception:
            pass

    def norm_metric(row: dict[str, str]) -> str:
        return (row.get("metric") or row.get("concept") or row.get("title") or "").strip().lower()

    def row_quality(row: dict[str, str]) -> int:
        score = 0
        for field in ("ticker", "metric", "value", "unit", "period_end", "filed", "form", "accession", "concept", "source"):
            if row.get(field):
                score += 1
        return score

    # Merge duplicate rows by ticker/metric/concept/accession, keeping the most complete version.
    merged: dict[str, dict[str, str]] = {}
    for row in rows:
        key = "|".join(
            [
                (row.get("ticker") or "").upper(),
                norm_metric(row),
                (row.get("concept") or "").lower(),
                row.get("accession") or "",
            ]
        )
        if not key.strip("|"):
            continue
        existing = merged.get(key)
        if existing is None or row_quality(row) > row_quality(existing):
            merged[key] = dict(row)
        else:
            for field, value in row.items():
                if value and not existing.get(field):
                    existing[field] = value

    final_rows = list(merged.values())

    # If source-title-only duplicates exist for the same metric as a complete row, drop the incomplete duplicate.
    complete = {
        ((r.get("ticker") or "").upper(), norm_metric(r))
        for r in final_rows
        if r.get("value") and r.get("unit")
    }
    final_rows = [
        r for r in final_rows
        if (r.get("value") and r.get("unit"))
        or ((r.get("ticker") or "").upper(), norm_metric(r)) not in complete
    ]

    if not final_rows:
        return ""

    order = {"revenue": 0, "net_income": 1, "eps": 2, "operating_income": 3, "cash": 4, "shares": 5}
    final_rows.sort(key=lambda r: (order.get(norm_metric(r), 99), norm_metric(r), r.get("concept", "")))

    lines = [
        "FULL CURRENT NEWSROOM SEC COMPANYFACTS TABLE",
        f"SEC card count: {len(final_rows)}",
        "Use every row in this table. Values below override any source-title-only summary.",
        "",
    ]

    for idx, row in enumerate(final_rows, start=1):
        lines.extend(
            [
                f"{idx}. ticker: {row.get('ticker') or 'unknown'}",
                f"   entity: {row.get('entity') or 'unknown'}",
                f"   metric: {row.get('metric') or row.get('concept') or row.get('title') or 'unknown'}",
                f"   value: {row.get('value') or 'unknown'}",
                f"   unit: {row.get('unit') or 'unknown'}",
                f"   period_end: {row.get('period_end') or 'unknown'}",
                f"   filed: {row.get('filed') or 'unknown'}",
                f"   form: {row.get('form') or 'unknown'}",
                f"   accession: {row.get('accession') or 'unknown'}",
                f"   concept: {row.get('concept') or 'unknown'}",
                f"   source: {row.get('source') or 'unknown'}",
                "",
            ]
        )

    return "\n".join(lines).strip()

def _router_only_evidence_packet_markdown() -> str:
    """
    v20.0 router-only Analyst context.

    Reads the current selected Research Brief EvidencePacket produced by the
    v19.1 legacy bridge and renders it as the only authoritative Analyst context.
    """
    try:
        import json
        from pathlib import Path

        live_root = Path(__file__).resolve().parents[2]
        packet_path = live_root / "data" / "autolab_payload" / "router_last_evidence_packet.json"
        if not packet_path.exists():
            return (
                "ROUTER ONLY SELECTED RESEARCH BRIEF EVIDENCE PACKET MISSING\n"
                "No router_last_evidence_packet.json was found.\n"
                "Ask the user to fetch research, select rows, and Add Selected to Brief before analysis."
            )

        payload = json.loads(packet_path.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(payload, dict):
            return (
                "ROUTER ONLY SELECTED RESEARCH BRIEF EVIDENCE PACKET INVALID\n"
                "router_last_evidence_packet.json was not a JSON object.\n"
                "Ask the user to rebuild the Research Brief."
            )

        rows = payload.get("rows") or []
        if not isinstance(rows, list) or not rows:
            return (
                "ROUTER ONLY SELECTED RESEARCH BRIEF EVIDENCE PACKET EMPTY\n"
                "The router packet has zero evidence rows.\n"
                "Ask the user to fetch research, select rows, and Add Selected to Brief before analysis."
            )

        def _clean(value):
            if value is None:
                return ""
            return str(value).strip()

        def _safe_dict(value):
            return value if isinstance(value, dict) else {}

        grouped = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            source = _clean(row.get("source_family")) or "unknown"
            grouped.setdefault(source, []).append(row)

        lines = [
            "ROUTER ONLY SELECTED RESEARCH BRIEF EVIDENCE PACKET — ONLY AUTHORITATIVE ANALYST CONTEXT",
            "Use ONLY the rows in this packet.",
            "Ignore older SEC/FRED/BLS legacy contexts, combined contexts, compact source lists, Sources Used panels, and tail guards if they conflict with this packet.",
            "The visible Research Brief is display-only; this router packet is the structured source of truth.",
            "Third-party context is context-only and cannot override official SEC/FRED/BLS/BEA/Fed/Treasury facts.",
            "",
            f"packet_id: {_clean(payload.get('packet_id'))}",
            f"created_at: {_clean(payload.get('created_at'))}",
            f"question: {_clean(payload.get('question'))}",
            f"router_row_count: {len(rows)}",
            "",
            "Source inventory:",
        ]

        for source in sorted(grouped):
            lines.append(f"- {source}: {len(grouped[source])} row(s)")

        chart_ready = payload.get("chart_ready_data") or []
        if isinstance(chart_ready, list):
            lines.append(f"- chart_ready_rows: {len(chart_ready)}")

        value_order = [
            "ticker",
            "entity",
            "metric",
            "value",
            "latest_value",
            "latest_date",
            "previous_value",
            "previous_date",
            "change_vs_prior",
            "unit",
            "units",
            "frequency",
            "period_end",
            "filed",
            "form",
            "accession",
            "concept",
            "cik",
            "series_id",
        ]

        for source in sorted(grouped):
            lines += ["", f"## {source} router evidence rows"]
            for idx, row in enumerate(grouped[source], start=1):
                values = _safe_dict(row.get("values"))
                metadata = _safe_dict(row.get("metadata"))
                title = _clean(row.get("title")) or f"{source} row {idx}"
                evidence_type = _clean(row.get("evidence_type")) or "unknown"
                source_quality = _clean(row.get("source_quality")) or "unknown"
                confidence = _clean(row.get("confidence")) or "unknown"
                url = _clean(row.get("url"))

                lines.append(f"{idx}. title: {title}")
                lines.append(f"   source_family: {source}")
                lines.append(f"   evidence_type: {evidence_type}")
                lines.append(f"   source_quality: {source_quality}")
                lines.append(f"   confidence: {confidence}")
                if url:
                    lines.append(f"   source: {url}")

                emitted = set()
                for key in value_order:
                    if key in values and values.get(key) not in (None, ""):
                        lines.append(f"   {key}: {values.get(key)}")
                        emitted.add(key)

                for key in sorted(values):
                    if key not in emitted and values.get(key) not in (None, ""):
                        lines.append(f"   {key}: {values.get(key)}")

                evidence_status = metadata.get("evidence_status")
                if evidence_status:
                    lines.append(f"   evidence_status: {evidence_status}")

                legacy_index = metadata.get("legacy_index")
                if legacy_index not in (None, ""):
                    lines.append(f"   selected_brief_index: {legacy_index}")

        return "\n".join(lines).strip()
    except Exception as exc:
        try:
            return (
                "ROUTER ONLY SELECTED RESEARCH BRIEF EVIDENCE PACKET ERROR\n"
                + str(exc)
                + "\nAsk the user to rebuild the Research Brief."
            )
        except Exception:
            return ""

def _fred_newsroom_evidence_markdown(*payloads: Any) -> str:
    """
    Build an explicit FRED evidence table from raw Newsroom brief/result data.

    Numeric FRED rows use kind='fred-data' or a "Latest FRED value..." summary.
    Metadata-only official-series cards are kept in a separate section so the
    Analyst does not mislabel them as blank numeric data rows.
    """
    import re

    def walk(obj: Any) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        if isinstance(obj, list):
            for value in obj:
                found.extend(walk(value))
            return found
        if isinstance(obj, dict):
            found.append(obj)
            for key in ("items", "source_links", "links", "results", "brief", "data", "metadata", "children"):
                value = obj.get(key)
                if isinstance(value, (list, dict)):
                    found.extend(walk(value))
            return found
        return found

    def pick(item: dict[str, Any], *names: str) -> str:
        pools = [item]
        for key in ("metadata", "data", "raw", "fact", "extra"):
            value = item.get(key)
            if isinstance(value, dict):
                pools.append(value)
        for pool in pools:
            for name in names:
                value = pool.get(name)
                if value not in (None, ""):
                    return str(value)
        return ""

    def text_blob(item: dict[str, Any]) -> str:
        pools = [item]
        for key in ("metadata", "data", "raw", "fact", "extra"):
            value = item.get(key)
            if isinstance(value, dict):
                pools.append(value)
        parts: list[str] = []
        for pool in pools:
            for name in (
                "id", "kind", "source", "title", "headline", "summary", "url",
                "source_url", "series_id", "fred_series_id", "units", "frequency",
            ):
                parts.append(str(pool.get(name) or ""))
        return " ".join(parts)

    def is_fred(item: dict[str, Any]) -> bool:
        blob = text_blob(item).lower()
        source = pick(item, "source").lower()
        kind = pick(item, "kind").lower()
        return (
            source == "fred"
            or kind in {"fred-data", "fred-data-warning", "official-series"}
            or "latest fred value" in blob
            or "fred.stlouisfed.org/series/" in blob
            or re.search(r"\bfred-data-\d+-[a-z0-9_]+", blob) is not None
        )

    def parse_summary(item: dict[str, Any]) -> dict[str, str]:
        text = text_blob(item)
        out: dict[str, str] = {}

        title = pick(item, "title", "headline") or str(item.get("title") or "")
        tm = re.match(r"\s*([A-Z0-9_]{2,20})\s*:\s*(.+?)\s*$", title)
        if tm:
            out["series_id"] = tm.group(1).upper()
            out["title"] = tm.group(2).strip()

        # Metadata-only cards often look like: "FRED series: Nonfarm Payrolls (PAYEMS)"
        meta = re.search(r"\(([A-Z0-9_]{2,20})\)\s*$", title)
        if meta and "series_id" not in out:
            out["series_id"] = meta.group(1).upper()

        m = re.search(
            r"Latest FRED value for\s+([A-Z0-9_]+)\s*:\s*([-+0-9.,]+|n/a)\s+on\s+([0-9]{4}-[0-9]{2}-[0-9]{2}|n/a)\s*\((.*?),\s*([^)]+)\)",
            text,
            flags=re.I,
        )
        if m:
            out["series_id"] = m.group(1).upper()
            out["latest_value"] = m.group(2).replace(",", "")
            out["latest_date"] = m.group(3)
            out["units"] = m.group(4).strip()
            out["frequency"] = m.group(5).strip()

        p = re.search(
            r"Prior value:\s*([-+0-9.,]+|n/a)\s+on\s+([0-9]{4}-[0-9]{2}-[0-9]{2}|n/a)\s*;\s*change vs prior:\s*([-+0-9.,]+|n/a)",
            text,
            flags=re.I,
        )
        if p:
            out["previous_value"] = p.group(1).replace(",", "")
            out["previous_date"] = p.group(2)
            out["change"] = p.group(3).replace(",", "")

        return out

    numeric_rows: list[dict[str, str]] = []
    metadata_rows: list[dict[str, str]] = []

    for payload in payloads:
        for item in walk(payload):
            if not isinstance(item, dict) or not is_fred(item):
                continue

            parsed = parse_summary(item)
            blob = text_blob(item).lower()
            kind = pick(item, "kind").lower()
            source = pick(item, "source").upper()
            if source != "FRED" and "fred" not in kind and "fred.stlouisfed.org/series/" not in blob:
                continue

            series_id = (
                pick(item, "series_id", "fred_series_id", "ticker")
                or parsed.get("series_id", "")
            ).upper()

            title = pick(item, "title", "headline") or parsed.get("title", "")
            if title.upper().startswith(series_id + ":"):
                title = title.split(":", 1)[1].strip()

            latest_value = pick(item, "latest_value", "value", "latest") or parsed.get("latest_value", "")
            latest_date = pick(item, "latest_date", "date") or parsed.get("latest_date", "")
            has_numeric_payload = bool(latest_value and latest_date) or "latest fred value" in blob
            is_metadata_only = kind == "official-series" and not has_numeric_payload

            if is_metadata_only:
                metadata_rows.append(
                    {
                        "series_id": series_id or "unknown",
                        "title": title or parsed.get("title", "") or "unknown",
                        "url": pick(item, "source_url", "url", "link") or str(item.get("url") or ""),
                        "summary": pick(item, "summary") or "",
                        "kind": kind or "official-series",
                        "evidence_status": "metadata-only FRED source link; numeric latest/prior values were not read or provided",
                    }
                )
                continue

            row = {
                "series_id": series_id or "unknown",
                "title": title or parsed.get("title", "") or "unknown",
                "latest_value": latest_value,
                "latest_date": latest_date,
                "previous_value": pick(item, "previous_value", "prior_value", "previous") or parsed.get("previous_value", ""),
                "previous_date": pick(item, "previous_date", "prior_date") or parsed.get("previous_date", ""),
                "change": pick(item, "change", "delta", "change_vs_prior") or parsed.get("change", ""),
                "units": pick(item, "units", "unit") or parsed.get("units", ""),
                "frequency": pick(item, "frequency", "freq") or parsed.get("frequency", ""),
                "url": pick(item, "source_url", "url", "link") or str(item.get("url") or ""),
                "kind": kind or "fred-data",
            }

            if row["series_id"] == "unknown" and not row["latest_value"]:
                continue
            numeric_rows.append(row)

    def quality(row: dict[str, str]) -> int:
        return sum(1 for value in row.values() if value)

    def dedupe(rows: list[dict[str, str]]) -> list[dict[str, str]]:
        merged: dict[str, dict[str, str]] = {}
        for row in rows:
            key = row.get("series_id") or row.get("title") or row.get("url") or ""
            if not key:
                continue
            old = merged.get(key)
            if old is None or quality(row) > quality(old):
                merged[key] = dict(row)
            else:
                for field, value in row.items():
                    if value and not old.get(field):
                        old[field] = value
        final = list(merged.values())
        final.sort(key=lambda r: r.get("series_id", ""))
        return final

    final_numeric = dedupe(numeric_rows)
    final_metadata = dedupe(metadata_rows)

    if not final_numeric and not final_metadata:
        return ""

    lines = [
        "FULL CURRENT NEWSROOM FRED EVIDENCE TABLE",
        f"FRED numeric data card count: {len(final_numeric)}",
        "Use every numeric row in this table. Metadata-only FRED source links are listed separately and are not numeric evidence.",
        "",
    ]

    for idx, row in enumerate(final_numeric, start=1):
        is_blank = not row.get("latest_value") or not row.get("latest_date")
        lines.extend(
            [
                f"{idx}. series_id: {row.get('series_id') or 'unknown'}",
                f"   title: {row.get('title') or 'unknown'}",
                f"   latest_value: {row.get('latest_value') or 'blank/unavailable'}",
                f"   latest_date: {row.get('latest_date') or 'blank/unavailable'}",
                f"   previous_value: {row.get('previous_value') or 'blank/unavailable'}",
                f"   previous_date: {row.get('previous_date') or 'blank/unavailable'}",
                f"   change_vs_prior: {row.get('change') or 'blank/unavailable'}",
                f"   units: {row.get('units') or 'unknown'}",
                f"   frequency: {row.get('frequency') or 'unknown'}",
                f"   source: {row.get('url') or 'unknown'}",
                f"   evidence_status: {'blank or incomplete FRED numeric data row' if is_blank else 'readable FRED data row'}",
                "",
            ]
        )

    if final_metadata:
        lines.extend(
            [
                "FRED METADATA-ONLY SOURCE LINKS",
                f"FRED metadata-only link count: {len(final_metadata)}",
                "These rows are official source links or search leads only. Do not treat them as blank numeric data rows.",
                "",
            ]
        )
        for idx, row in enumerate(final_metadata, start=1):
            lines.extend(
                [
                    f"{idx}. series_id: {row.get('series_id') or 'unknown'}",
                    f"   title: {row.get('title') or 'unknown'}",
                    f"   source: {row.get('url') or 'unknown'}",
                    f"   summary: {row.get('summary') or 'metadata-only source link'}",
                    f"   evidence_status: {row.get('evidence_status') or 'metadata-only FRED source link'}",
                    "",
                ]
            )

    return "\n".join(lines).strip()

def _bls_newsroom_evidence_markdown(*payloads: Any) -> str:
    """
    Build an explicit BLS evidence table from raw Newsroom brief/result data.
    Normal BLS cards use source='BLS' and kind='bls-data'.
    """
    import re

    def walk(obj: Any) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        if isinstance(obj, list):
            for value in obj:
                found.extend(walk(value))
            return found
        if isinstance(obj, dict):
            found.append(obj)
            for key in ("items", "source_links", "links", "results", "brief", "data", "metadata", "children"):
                value = obj.get(key)
                if isinstance(value, (list, dict)):
                    found.extend(walk(value))
            return found
        return found

    def pick(item: dict[str, Any], *names: str) -> str:
        pools = [item]
        for key in ("metadata", "data", "raw", "fact", "extra"):
            value = item.get(key)
            if isinstance(value, dict):
                pools.append(value)
        for pool in pools:
            for name in names:
                value = pool.get(name)
                if value not in (None, ""):
                    return str(value)
        return ""

    def blob(item: dict[str, Any]) -> str:
        pools = [item]
        for key in ("metadata", "data", "raw", "fact", "extra"):
            value = item.get(key)
            if isinstance(value, dict):
                pools.append(value)
        parts: list[str] = []
        for pool in pools:
            for name in (
                "id", "kind", "source", "title", "headline", "summary", "url",
                "source_url", "series_id", "units", "unit", "frequency", "evidence_status",
            ):
                parts.append(str(pool.get(name) or ""))
        return " ".join(parts)

    def is_bls(item: dict[str, Any]) -> bool:
        text = blob(item).lower()
        return (
            pick(item, "source").upper() == "BLS"
            or pick(item, "kind").lower() in {"bls-data", "bls-data-warning"}
            or "latest bls value" in text
            or "data.bls.gov/timeseries/" in text
        )

    def parse_summary(item: dict[str, Any]) -> dict[str, str]:
        text = blob(item)
        out: dict[str, str] = {}

        title = pick(item, "title", "headline") or str(item.get("title") or "")
        tm = re.match(r"\s*([A-Z0-9_]{2,30})\s*:\s*(.+?)\s*$", title)
        if tm:
            out["series_id"] = tm.group(1).upper()
            out["title"] = tm.group(2).strip()

        m = re.search(
            r"Latest BLS value for\s+([A-Z0-9_]+)\s*:\s*([-+0-9.,]+|n/a)\s+on\s+([^()]+?)\s*\((.*?),\s*([^)]+)\)",
            text,
            flags=re.I,
        )
        if m:
            out["series_id"] = m.group(1).upper()
            out["latest_value"] = m.group(2).replace(",", "")
            out["latest_date"] = m.group(3).strip()
            out["units"] = m.group(4).strip()
            out["frequency"] = m.group(5).strip()

        p = re.search(
            r"Prior value:\s*([-+0-9.,]+|n/a)\s+on\s+([^;]+?)\s*;\s*change vs prior:\s*([-+0-9.,]+|n/a)",
            text,
            flags=re.I,
        )
        if p:
            out["previous_value"] = p.group(1).replace(",", "")
            out["previous_date"] = p.group(2).strip()
            out["change"] = p.group(3).replace(",", "")

        return out

    rows: list[dict[str, str]] = []
    for payload in payloads:
        for item in walk(payload):
            if not isinstance(item, dict) or not is_bls(item):
                continue

            parsed = parse_summary(item)
            series_id = (pick(item, "series_id", "ticker") or parsed.get("series_id", "")).upper()
            title = pick(item, "title", "headline") or parsed.get("title", "")
            if series_id and title.upper().startswith(series_id + ":"):
                title = title.split(":", 1)[1].strip()

            row = {
                "series_id": series_id or "unknown",
                "title": title or parsed.get("title", "") or "unknown",
                "latest_value": pick(item, "latest_value", "value", "latest") or parsed.get("latest_value", ""),
                "latest_date": pick(item, "latest_date", "date") or parsed.get("latest_date", ""),
                "previous_value": pick(item, "previous_value", "prior_value", "previous") or parsed.get("previous_value", ""),
                "previous_date": pick(item, "previous_date", "prior_date") or parsed.get("previous_date", ""),
                "change": pick(item, "change", "delta", "change_vs_prior") or parsed.get("change", ""),
                "units": pick(item, "units", "unit") or parsed.get("units", ""),
                "frequency": pick(item, "frequency", "freq") or parsed.get("frequency", ""),
                "category": pick(item, "category") or "macro_data",
                "url": pick(item, "source_url", "url", "link") or str(item.get("url") or ""),
                "evidence_status": pick(item, "evidence_status") or "",
            }

            if row["series_id"] == "unknown" and not row["latest_value"]:
                continue
            rows.append(row)

    def quality(row: dict[str, str]) -> int:
        return sum(1 for value in row.values() if value)

    merged: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get("series_id") or row.get("title") or row.get("url") or ""
        old = merged.get(key)
        if old is None or quality(row) > quality(old):
            merged[key] = dict(row)
        else:
            for field, value in row.items():
                if value and not old.get(field):
                    old[field] = value

    final_rows = list(merged.values())
    if not final_rows:
        return ""

    final_rows.sort(key=lambda r: (r.get("category", ""), r.get("series_id", "")))

    lines = [
        "FULL CURRENT NEWSROOM BLS EVIDENCE TABLE",
        f"BLS card count: {len(final_rows)}",
        "Use every row in this table. If a BLS row is blank or malformed, report that explicitly.",
        "",
    ]

    for idx, row in enumerate(final_rows, start=1):
        is_blank = not row.get("latest_value") or not row.get("latest_date")
        lines.extend(
            [
                f"{idx}. series_id: {row.get('series_id') or 'unknown'}",
                f"   title: {row.get('title') or 'unknown'}",
                f"   latest_value: {row.get('latest_value') or 'blank/unavailable'}",
                f"   latest_date: {row.get('latest_date') or 'blank/unavailable'}",
                f"   previous_value: {row.get('previous_value') or 'blank/unavailable'}",
                f"   previous_date: {row.get('previous_date') or 'blank/unavailable'}",
                f"   change_vs_prior: {row.get('change') or 'blank/unavailable'}",
                f"   units: {row.get('units') or 'unknown'}",
                f"   frequency: {row.get('frequency') or 'unknown'}",
                f"   category: {row.get('category') or 'macro_data'}",
                f"   source: {row.get('url') or 'unknown'}",
                f"   evidence_status: {row.get('evidence_status') or ('blank or incomplete BLS row' if is_blank else 'readable BLS data row')}",
                "",
            ]
        )

    return "\n".join(lines).strip()

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
        quant_playbook_requested = _quant_playbook_requested(question)
        analysis_question = question if audit_only_mode else _enhance_research_analyst_user_prompt(question, output_style)
        analysis_question = analysis_question + (
            "\n\nSTYLE INSTRUCTION:\n"
            "Write professionally and make the result easy to read. "
            "Do not use a fixed numbered or bullet template. "
            "Do not add macro anchors, supplemental source candidates, official evidence staging, or quant playbook material unless directly requested. "
            "Do not force any fixed section list. "
            "Prefer short paragraphs and simple headings. Use bullets only when they genuinely improve readability.\n"
        )
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


            # Automatic macro anchors disabled.
            # Use current Newsroom Research Brief cards as the evidence packet.
            macro_anchor_items = []
            macro_anchor_coverage = {'mode': 'disabled'}
            macro_anchor_error = None

            # macro anchors, result-store leftovers, supplemental discovery links,
            # and the quant playbook scaffold.
            combined_payload = _merge_newsroom_payloads(
                brief_items,
                macro_anchor_items,
                result_items,
                supplemental_items,
                max_items=96,
            )

            approved_structured_items = _approved_structured_cards_for_brief()
            if approved_structured_items:
                try:
                    brief_items = list(approved_structured_items) + list(brief_items or [])
                except Exception:
                    brief_items = list(approved_structured_items)

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
            if audit_only_mode or (brief_only_mode and not quant_playbook_requested):
                packet["quant_research_playbook"] = {
                    "enabled": False,
                    "error": None,
                    "note": "Quant playbook skipped unless explicitly requested.",
                    "safeguards": [
                        "Research-only output; no broker access or order placement.",
                    ],
                }
            else:
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
            approved_structured_context = _approved_structured_evidence_markdown()
            if approved_structured_context:
                context = approved_structured_context + "\n\n" + context

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

            if not audit_only_mode and (not brief_only_mode or quant_playbook_requested):
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

            if _approved_structured_audit_requested(analysis_question):
                answer = _approved_structured_audit_answer()
                return (
                    answer,
                    "Audited approved structured official evidence staging file. FRED and quant playbook not used.",
                    _approved_structured_sources_children(),
                )

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

            # Put the complete SEC table in the evidence/context, not in the user question.
            # The question may be cleaned/truncated by the prompt builder; context is the FRED-like path.
            analyst_evidence_context = str(getattr(prompt, "evidence_markdown", "") or "")
            sec_companyfacts_brief_md = _sec_companyfacts_full_evidence_markdown(brief_store, results_store, packet.get('items', []), packet.get('source_links', []))
            if sec_companyfacts_brief_md:
                analyst_evidence_context = (
                    sec_companyfacts_brief_md
                    + "\n\nOTHER RESEARCH ANALYST EVIDENCE CONTEXT:\n"
                    + analyst_evidence_context
                )
                try:
                    _debug_dir = __import__('pathlib').Path('data') / 'autolab_payload'
                    _debug_dir.mkdir(parents=True, exist_ok=True)
                    (_debug_dir / 'research_analyst_last_sec_context.txt').write_text(sec_companyfacts_brief_md, encoding='utf-8')
                except Exception:

                    pass

            if audit_only_mode:
                user_prompt = question
            else:
                user_prompt = _enhance_research_analyst_user_prompt(
                    prompt.user_prompt,
                    output_style=output_style,
                    supplemental_count=len(supplemental_items),
                )

            # Final safety merge: make approved structured official evidence visible
            # at the last possible point before the Research Analyst LLM call.
            approved_structured_context_final = (
                "" if _approved_structured_staging_blocked(analysis_question)
                else _approved_structured_evidence_markdown()
            )
            if approved_structured_context_final and "## Approved Structured Official Evidence" not in context:
                context = approved_structured_context_final + "\n\n" + context
            # v16 combined SEC/FRED evidence table
            fred_newsroom_brief_md = _fred_newsroom_evidence_markdown(brief_store, results_store, packet.get('items', []), packet.get('source_links', []))
            bls_newsroom_brief_md = _bls_newsroom_evidence_markdown(brief_store, results_store, packet.get('items', []), packet.get('source_links', []))
            combined_newsroom_evidence_md = "\n\n".join(
                part for part in [sec_companyfacts_brief_md, fred_newsroom_brief_md, bls_newsroom_brief_md] if part
            )
            try:
                _debug_dir = __import__('pathlib').Path('data') / 'autolab_payload'
                _debug_dir.mkdir(parents=True, exist_ok=True)
                (_debug_dir / 'research_analyst_last_fred_context.txt').write_text(fred_newsroom_brief_md or '', encoding='utf-8')
                (_debug_dir / 'research_analyst_last_bls_context.txt').write_text(bls_newsroom_brief_md or '', encoding='utf-8')
                (_debug_dir / 'research_analyst_last_combined_context.txt').write_text(combined_newsroom_evidence_md or '', encoding='utf-8')
                (_debug_dir / 'research_analyst_last_sec_tail_guard.txt').write_text(sec_companyfacts_brief_md or '', encoding='utf-8')
                (_debug_dir / 'research_analyst_last_authoritative_prompt.txt').write_text(combined_newsroom_evidence_md or '', encoding='utf-8')
            except Exception:
                pass
            # end v16 combined SEC/FRED evidence table
            # v20.0 router-only Analyst evidence-context override
            router_only_evidence_packet_md = _router_only_evidence_packet_markdown()

            # Router-only rule:
            # If a router packet exists, it is the only source of truth.
            # If it is missing/empty/invalid, the Analyst should ask the user to add selected rows first.
            analyst_evidence_context = router_only_evidence_packet_md

            # Runtime cleanup for old tail-guard debug files. They are stale by design in v20.0.
            try:
                from pathlib import Path
                _router_live_root = Path(__file__).resolve().parents[2]
                _router_debug_dir = _router_live_root / "data" / "autolab_payload"
                _router_debug_dir.mkdir(parents=True, exist_ok=True)
                (_router_debug_dir / "research_analyst_last_router_only_context.txt").write_text(router_only_evidence_packet_md or "", encoding="utf-8")
                for _tail_name in (
                    "research_analyst_last_sec_tail_guard.txt",
                    "research_analyst_last_fred_tail_guard.txt",
                    "research_analyst_last_bls_tail_guard.txt",
                ):
                    try:
                        (_router_debug_dir / _tail_name).unlink(missing_ok=True)
                    except TypeError:
                        _tail_path = _router_debug_dir / _tail_name
                        if _tail_path.exists():
                            _tail_path.unlink()
                    except Exception:
                        pass
            except Exception:
                pass
            # end v20.0 router-only Analyst evidence-context override
            # v20.0 router-only Analyst user-prompt override
            try:
                router_only_evidence_packet_md
            except NameError:
                router_only_evidence_packet_md = _router_only_evidence_packet_markdown()

            analyst_user_prompt = str(getattr(prompt, "user_prompt", "") or "")
            analyst_user_prompt = (
                "ROUTER ONLY SELECTED RESEARCH BRIEF EVIDENCE PACKET — USE THIS AS THE ONLY SOURCE OF TRUTH.\n"
                "The current selected Research Brief has been converted into the router evidence packet below.\n"
                "Do not use older SEC/FRED/BLS legacy contexts, old tail guards, compact source lists, previous brief states, or Sources Used panels if they conflict with this packet.\n"
                "If this packet is missing, empty, or invalid, do not improvise from stale context; ask the user to fetch research, select rows, and Add Selected to Brief first.\n"
                "If the router packet lists FRED rows, do not say FRED is missing.\n"
                "If the router packet lists only four SEC rows, inventory only those four SEC rows and do not add older SEC metrics.\n"
                "Treat metadata-only FRED rows as source links, not blank numeric data.\n"
                "Official SEC/FRED/BLS/BEA/Fed/Treasury rows override third-party context.\n"
                "Third-party context is context-only and cannot override official numeric facts.\n"
                "Keep this research-only and simulation/advisory only; no broker actions, live trading instructions, order placement, or personalized position sizing.\n\n"
                + (router_only_evidence_packet_md or "")
                + "\n\nRequired answer behavior:\n"
                + "1. Inventory every row in the router packet by source family.\n"
                + "2. Separate FRED numeric rows from FRED metadata-only source links.\n"
                + "3. Use only SEC rows present in the router packet for company fundamentals.\n"
                + "4. Use only FRED/BLS rows present in the router packet for macro facts.\n"
                + "5. Clearly separate facts from interpretation.\n"
                + "6. If the packet is missing or empty, stop and ask the user to rebuild the selected Research Brief.\n"
                + "\n\nUSER QUESTION STARTS BELOW:\n"
                + analyst_user_prompt
            )
            # end v20.0 router-only Analyst user-prompt override

            answer = _call_ai_research_advisor(
                system_prompt=prompt.system_prompt,
                user_prompt=analyst_user_prompt,
                context=analyst_evidence_context,
                max_output=max_output_int,
            )

            macro_anchor_note = ""
            if macro_anchor_items:
                macro_anchor_note = ""
            if macro_anchor_error:
                macro_anchor_note += ""

            supplemental_note = ""
            if supplemental_items:
                supplemental_note = ""
            if supplemental_error:
                supplemental_note += ""

            quant_playbook_note = ""
            if packet.get("quant_research_playbook", {}).get("enabled"):
                quant_playbook_note = ""
            elif quant_playbook_requested:
                quant_playbook_note = " Quant playbook requested but unavailable."
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
