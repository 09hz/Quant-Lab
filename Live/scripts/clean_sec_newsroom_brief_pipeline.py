#!/usr/bin/env python3
from __future__ import annotations

import argparse
import py_compile
import re
from pathlib import Path

SEC_ADAPTER = '\nfrom __future__ import annotations\n\nimport re\nfrom datetime import datetime\nfrom typing import Any, Iterable, Optional\n\n\ndef _source_selected(sources: Optional[Iterable[str]], source_id: str) -> bool:\n    if sources is None:\n        return True\n    normalized = {str(item or "").strip().lower().replace("-", "_") for item in sources}\n    aliases = {source_id, source_id.replace("_", "-")}\n    if source_id == "sec":\n        aliases.update({"sec_edgar", "edgar", "filings"})\n    return bool(normalized.intersection(aliases))\n\n\ndef _candidate_tickers(topic: str, *, max_tickers: int = 4) -> list[str]:\n    text = str(topic or "").upper()\n    stop = {\n        "THE", "AND", "FOR", "WITH", "FROM", "THIS", "THAT", "MARKET", "MARKETS",\n        "FED", "FRED", "SEC", "BEA", "BLS", "GDP", "CPI", "PCE", "RATE", "RATES",\n        "NEWS", "RISK", "OIL", "VIX", "USA", "US", "EARNINGS", "REVENUE", "INCOME",\n    }\n\n    candidates: list[str] = []\n    for match in re.finditer(r"(?:\\$|TICKER[:=\\s]+|SYMBOL[:=\\s]+)([A-Z]{1,5})\\b", text):\n        candidates.append(match.group(1))\n\n    for token in re.findall(r"\\b[A-Z]{2,5}\\b", text):\n        if token not in stop:\n            candidates.append(token)\n\n    out: list[str] = []\n    for token in candidates:\n        if token not in out:\n            out.append(token)\n        if len(out) >= max_tickers:\n            break\n    return out\n\n\ndef _card_to_result_item(card: dict[str, Any], *, topic: str, index: int) -> dict[str, Any]:\n    metadata = card.get("metadata") if isinstance(card.get("metadata"), dict) else {}\n    points = metadata.get("points") if isinstance(metadata.get("points"), list) else []\n    latest = points[0] if points and isinstance(points[0], dict) else {}\n\n    ticker = str(metadata.get("ticker") or "").upper()\n    company = str(metadata.get("company") or metadata.get("entity_name") or ticker)\n    metric = str(metadata.get("metric") or "")\n    value = latest.get("value", metadata.get("latest_value", ""))\n    unit = latest.get("unit", metadata.get("latest_unit", ""))\n    end = latest.get("end", metadata.get("period_end", ""))\n    filed = latest.get("filed", metadata.get("filed", ""))\n    form = latest.get("form", metadata.get("form", ""))\n    accession = latest.get("accession", metadata.get("accession", ""))\n    concept = metadata.get("concept", "")\n\n    source_url = str(card.get("source_url") or card.get("url") or latest.get("source_url") or "")\n    filing_url = str(card.get("filing_url") or latest.get("filing_url") or "")\n\n    summary = (\n        f"Latest {metric}: {value} {unit} for period ending {end}; "\n        f"form {form}, filed {filed}, accession {accession}; concept {concept}."\n    ).strip()\n\n    enriched_metadata = dict(metadata)\n    enriched_metadata.update(\n        {\n            "connector": "sec-companyfacts",\n            "official": True,\n            "structured": True,\n            "hydrated": True,\n            "direct_research_result": True,\n            "approved_structured_candidate": True,\n            "ticker": ticker,\n            "company": company,\n            "metric": metric,\n            "concept": concept,\n            "latest_value": value,\n            "latest_unit": unit,\n            "period_end": end,\n            "filed": filed,\n            "form": form,\n            "accession": accession,\n            "filing_url": filing_url,\n            "needs_manual_search": False,\n            "manual_search_needed": False,\n        }\n    )\n\n    return {\n        "id": f"sec-companyfacts-{index}-{ticker.lower()}-{metric.lower()}",\n        "title": str(card.get("title") or f"{company} ({ticker}) {metric} from SEC companyfacts"),\n        "source": "SEC EDGAR",\n        "url": source_url,\n        "summary": summary,\n        "topic": topic,\n        "kind": "sec-companyfacts-official-data",\n        "confidence": "high",\n        "validity": "high",\n        "relevance": "high",\n        "source_type": "official",\n        "source_role": "confirmed-official-sec-companyfacts",\n        "evidence_role": "confirmed-official-sec-companyfacts",\n        "needs_manual_search": False,\n        "manual_search_needed": False,\n        "is_search_page": False,\n        "direct_research_result": True,\n        "selectable": True,\n        "used_for_ai": True,\n        "metadata": enriched_metadata,\n        "filing_url": filing_url,\n        "links": [x for x in (source_url, filing_url) if x],\n        "fetched_at": datetime.now().isoformat(timespec="seconds"),\n    }\n\n\ndef build_sec_companyfacts_newsroom_items(\n    topic: str,\n    *,\n    max_tickers: int = 4,\n    metrics: list[str] | None = None,\n) -> list[dict[str, Any]]:\n    topic_clean = " ".join(str(topic or "").split()) or "company filings"\n    tickers = _candidate_tickers(topic_clean, max_tickers=max_tickers)\n    if not tickers:\n        return []\n\n    try:\n        from services.research.sec_companyfacts_parser import build_sec_evidence_cards\n    except Exception as exc:\n        return [\n            {\n                "id": "sec-companyfacts-parser-unavailable",\n                "title": "SEC companyfacts parser unavailable",\n                "source": "SEC EDGAR",\n                "url": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",\n                "summary": f"SEC companyfacts parser could not be imported: {exc}",\n                "topic": topic_clean,\n                "kind": "sec-companyfacts-warning",\n                "confidence": "low",\n                "needs_manual_search": True,\n                "selectable": False,\n                "metadata": {"connector": "sec-companyfacts", "error": str(exc)},\n                "fetched_at": datetime.now().isoformat(timespec="seconds"),\n            }\n        ]\n\n    metrics = metrics or ["revenue", "net_income", "eps", "operating_income", "cash", "shares"]\n    out: list[dict[str, Any]] = []\n    errors: list[str] = []\n\n    for ticker in tickers:\n        try:\n            cards = build_sec_evidence_cards(\n                ticker,\n                metrics=metrics,\n                user_agent="AlgoTrader Research local@example.com",\n            )\n            for card in cards:\n                out.append(_card_to_result_item(card, topic=topic_clean, index=len(out) + 1))\n        except Exception as exc:\n            errors.append(f"{ticker}: {exc}")\n\n    if errors:\n        out.append(\n            {\n                "id": "sec-companyfacts-partial-error",\n                "title": "Some SEC companyfacts cards could not be generated",\n                "source": "SEC EDGAR",\n                "url": "https://www.sec.gov/files/company_tickers.json",\n                "summary": "; ".join(errors),\n                "topic": topic_clean,\n                "kind": "sec-companyfacts-warning",\n                "confidence": "medium" if out else "low",\n                "needs_manual_search": True,\n                "selectable": False,\n                "metadata": {"connector": "sec-companyfacts", "errors": errors},\n                "fetched_at": datetime.now().isoformat(timespec="seconds"),\n            }\n        )\n\n    return out\n\n\ndef extend_results_with_sec_companyfacts(\n    topic: str,\n    sources: Optional[Iterable[str]],\n    existing_results: list[dict[str, Any]] | None,\n    *,\n    max_tickers: int = 4,\n) -> list[dict[str, Any]]:\n    results = list(existing_results or [])\n    if not _source_selected(sources, "sec"):\n        return results\n\n    sec_items = build_sec_companyfacts_newsroom_items(topic, max_tickers=max_tickers)\n    if not sec_items:\n        return results\n\n    return sec_items + results\n'
NEWSROOM_NORMALIZER = '\ndef _normalize_sec_companyfacts_brief_item(item: dict[str, Any]) -> dict[str, Any]:\n    if not isinstance(item, dict):\n        return item\n\n    kind = str(item.get("kind") or "").lower()\n    url = str(item.get("url") or "").lower()\n    source = str(item.get("source") or "").lower()\n    if "sec-companyfacts" not in kind and "companyfacts" not in url and "sec edgar" not in source:\n        return item\n\n    row = dict(item)\n    row["source"] = row.get("source") or "SEC EDGAR"\n    if "companyfacts" in url or "sec-companyfacts" in kind:\n        row["kind"] = "sec-companyfacts-official-data"\n    row["confidence"] = row.get("confidence") or "high"\n    row["validity"] = row.get("validity") or "high"\n    row["relevance"] = row.get("relevance") or "high"\n    row["source_type"] = "official"\n    row["needs_manual_search"] = False\n    row["manual_search_needed"] = False\n    row["is_search_page"] = False\n    row["selectable"] = True\n    row["used_for_ai"] = True\n    row["direct_research_result"] = True\n    row["source_role"] = row.get("source_role") or "confirmed-official-sec-companyfacts"\n    row["evidence_role"] = row.get("evidence_role") or "confirmed-official-sec-companyfacts"\n\n    bad_phrases = (\n        " · Manual search needed",\n        " Manual search needed: this is a source search page, not a direct research result. It is not added to the AI brief by default.",\n        "Manual search needed: this is a source search page, not a direct research result. It is not added to the AI brief by default.",\n    )\n    for field in ("title", "summary"):\n        value = str(row.get(field) or "")\n        for phrase in bad_phrases:\n            value = value.replace(phrase, "")\n        row[field] = value.strip()\n\n    metadata = dict(row.get("metadata") or {})\n    metadata.update(\n        {\n            "official": True,\n            "structured": True,\n            "direct_research_result": True,\n            "needs_manual_search": False,\n            "manual_search_needed": False,\n        }\n    )\n    row["metadata"] = metadata\n    return row\n'
STAGING_BLOCK_HELPER = '\ndef _approved_structured_staging_blocked(question: str) -> bool:\n    q = str(question or "").lower()\n    block_terms = (\n        "do not use approved structured evidence",\n        "do not use approved structured evidence staging",\n        "do not use staging",\n        "do not use staging files",\n        "do not use approved_structured_evidence",\n        "current newsroom research brief",\n        "current research brief",\n        "normal newsroom checkbox",\n        "add selected to brief",\n        "checkbox/add selected",\n    )\n    return any(term in q for term in block_terms)\n'


def find_live_root(start: Path) -> Path:
    start = start.resolve()
    for candidate in [start, *start.parents]:
        if (candidate / "Live" / "app.py").exists() and (candidate / "Live" / "services").is_dir():
            return candidate / "Live"
        if (candidate / "app.py").exists() and (candidate / "services").is_dir():
            return candidate
    raise SystemExit("Could not locate Live root.")


def patch_newsroom_callbacks(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    changed = False

    import_block = '''try:
    from services.research.sec_newsroom_adapter import extend_results_with_sec_companyfacts
except Exception:
    extend_results_with_sec_companyfacts = None

'''
    if "extend_results_with_sec_companyfacts" not in text:
        anchor = '''try:
    from services.research.fred_newsroom_adapter import extend_results_with_fred
except Exception:
    extend_results_with_fred = None

'''
        if anchor not in text:
            raise SystemExit("Could not find FRED adapter import block in newsroom_callbacks.py")
        text = text.replace(anchor, anchor + import_block, 1)
        changed = True

    call_block = '''    if extend_results_with_sec_companyfacts is not None:
        try:
            results = extend_results_with_sec_companyfacts(topic, sources or None, results)
        except Exception as exc:
            results.insert(0, {
                "id": "sec-companyfacts-ui-extension-error",
                "title": "SEC structured data unavailable",
                "source": "SEC EDGAR",
                "url": "https://www.sec.gov/files/company_tickers.json",
                "summary": f"SEC UI integration could not build structured companyfacts cards: {exc}",
                "topic": topic,
                "kind": "sec-companyfacts-warning",
                "confidence": "low",
                "needs_manual_search": True,
                "selectable": False,
                "metadata": {"connector": "sec-companyfacts", "error": str(exc)},
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
            })

'''
    if "extend_results_with_sec_companyfacts(topic" not in text:
        anchor = '''    if extend_results_with_fred is not None:
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

'''
        if anchor not in text:
            raise SystemExit("Could not find FRED extension call block in newsroom_callbacks.py")
        text = text.replace(anchor, anchor + call_block, 1)
        changed = True

    if "def _normalize_sec_companyfacts_brief_item(" not in text:
        anchor = "\ndef _merge_brief_items("
        if anchor not in text:
            raise SystemExit("Could not find _merge_brief_items anchor in newsroom_callbacks.py")
        text = text.replace(anchor, "\n" + NEWSROOM_NORMALIZER.strip() + "\n\n" + anchor.lstrip(), 1)
        changed = True

    if "_normalize_sec_companyfacts_brief_item(row)" not in text:
        for anchor in (
            '            row["brief_added_at"] = generated_at\n',
            '            row["added_at"] = generated_at\n',
        ):
            if anchor in text:
                text = text.replace(anchor, anchor + "            row = _normalize_sec_companyfacts_brief_item(row)\n", 1)
                changed = True
                break

    if "item = _normalize_sec_companyfacts_brief_item(item)" not in text:
        old = '    for idx, item in enumerate(brief, start=1):\n        lines += [\n'
        new = '    for idx, item in enumerate(brief, start=1):\n        item = _normalize_sec_companyfacts_brief_item(item)\n        lines += [\n'
        if old in text:
            text = text.replace(old, new, 1)
            changed = True

    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return changed


def patch_research_analyst(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    changed = False

    if "def _approved_structured_staging_blocked(" not in text:
        anchor = "\ndef _approved_structured_audit_requested("
        if anchor in text:
            text = text.replace(anchor, "\n" + STAGING_BLOCK_HELPER.strip() + "\n\n" + anchor.lstrip(), 1)
            changed = True

    if "def _approved_structured_audit_requested(" in text and "if _approved_structured_staging_blocked(question):" not in text:
        pattern = r"(def _approved_structured_audit_requested\(question: str\) -> bool:\n)(\s+)"
        match = re.search(pattern, text)
        if match:
            insert = match.group(1) + match.group(2) + "if _approved_structured_staging_blocked(question):\n" + match.group(2) + "    return False\n"
            text = text[:match.start()] + insert + text[match.end():]
            changed = True

    text2 = re.sub(
        r'(?m)^(\s*)approved_structured_context_final = _approved_structured_evidence_markdown\(\)\n'
        r'\1if approved_structured_context_final and "## Approved Structured Official Evidence" not in context:\n'
        r'\1    context = approved_structured_context_final \+ (?:"\\n\\n"|"\\\\n\\\\n") \+ context\n',
        r'\1approved_structured_context_final = (\n'
        r'\1    "" if _approved_structured_staging_blocked(analysis_question)\n'
        r'\1    else _approved_structured_evidence_markdown()\n'
        r'\1)\n'
        r'\1if approved_structured_context_final and "## Approved Structured Official Evidence" not in context:\n'
        r'\1    context = approved_structured_context_final + "\n\n" + context\n',
        text,
    )
    if text2 != text:
        text = text2
        changed = True

    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return changed


def hide_structured_reviewer_from_app(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    changed = False

    pattern = (
        r"(?ms)^try:\n"
        r"\s+from services\.research\.structured_evidence_callbacks import register_structured_evidence_callbacks\n"
        r"\s+register_structured_evidence_callbacks\(app\)\n"
        r"except Exception as exc:\n"
        r"\s+print\([^\n]+\)\n"
    )
    text2 = re.sub(
        pattern,
        "# Structured Evidence Reviewer callbacks kept for developer diagnostics only.\n"
        "# Normal SEC workflow now uses Newsroom source checkboxes and Research Brief cards.\n",
        text,
    )
    if text2 != text:
        text = text2
        changed = True

    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean SEC evidence flow: use Newsroom checkbox/brief path, not Evidence Reviewer staging. No backups are created."
    )
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--keep-reviewer-registered", action="store_true")
    args = parser.parse_args()

    live_root = find_live_root(args.repo_root or Path.cwd())

    sec_adapter = live_root / "services" / "research" / "sec_newsroom_adapter.py"
    newsroom_callbacks = live_root / "services" / "research" / "newsroom_callbacks.py"
    research_analyst = live_root / "services" / "ai" / "research_analyst_callbacks.py"
    app_py = live_root / "app.py"

    sec_adapter.write_text(SEC_ADAPTER.strip() + "\n", encoding="utf-8")
    newsroom_changed = patch_newsroom_callbacks(newsroom_callbacks)
    research_changed = patch_research_analyst(research_analyst)
    app_changed = False if args.keep_reviewer_registered else hide_structured_reviewer_from_app(app_py)

    for path in (sec_adapter, newsroom_callbacks, research_analyst, app_py):
        if path.exists():
            py_compile.compile(str(path), doraise=True)

    print("Clean SEC Newsroom brief pipeline patch complete:")
    print(f"- wrote {sec_adapter}")
    print(f"- patched {newsroom_callbacks} changed={newsroom_changed}")
    print(f"- patched {research_analyst} changed={research_changed}")
    print(f"- patched {app_py} changed={app_changed}")
    print()
    print("Normal user flow after restart:")
    print("1. Newsroom topic: NVDA earnings")
    print("2. SEC EDGAR checked")
    print("3. Fetch Research")
    print("4. Select SEC companyfacts cards")
    print("5. Add Selected to Brief")
    print("6. Ask Research Analyst to audit the current Newsroom Research Brief only")
    print()
    print("The old Evidence Reviewer staging file should no longer override current-brief prompts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
