# force_sec_brief_numbered_renderer_v18_8

## Purpose

Force the visible Research Brief markdown renderer to number SEC companyfacts cards like normal selected evidence rows.

The v18.7 diagnostic confirmed the exact old render path still present:

```python
def _sec_companyfacts_card_markdown(item: dict[str, Any]) -> str:
    ...
    lines = [
        "### SEC companyfacts official-data card",
```

and `_brief_markdown` still called:

```python
sec_md = _sec_companyfacts_card_markdown(item)
```

## What changed

Patches:

```text
Live/services/research/newsroom_callbacks.py
```

### 1. Replaces `_sec_companyfacts_card_markdown`

New signature:

```python
def _sec_companyfacts_card_markdown(item: dict[str, Any], index: int | None = None) -> str:
```

New SEC heading format:

```text
### 5. SEC companyfacts: AMD operating_income
```

or, without an index:

```text
### SEC companyfacts: AMD operating_income
```

### 2. Replaces `_brief_markdown`

The brief renderer now:

1. normalizes SEC companyfacts rows first,
2. calls:

```python
_sec_companyfacts_card_markdown(item, idx)
```

3. falls back to the normal numbered row renderer for non-SEC rows.

## Test tools

### Restart Dash

```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

& "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe" ".\app.py"
```

### Newsroom test search/topic

```text
AMD inflation labor CPI PCE unemployment payrolls wages company fundamentals revenue cash EPS operating income net income shares
```

### Source checkboxes

```text
SEC EDGAR
FRED
BLS
```

### Manual UI test steps

```text
1. Clear Brief.
2. Fetch Research.
3. Select useful SEC, FRED, and BLS rows.
4. Add Selected to Brief.
5. Inspect the Research Brief preview.
```

### Visual pass condition

SEC rows should now appear as numbered headings, for example:

```text
### 5. SEC companyfacts: AMD cash
### 6. SEC companyfacts: AMD eps
### 7. SEC companyfacts: AMD net_income
```

They should no longer appear as:

```text
### SEC companyfacts official-data card
```

### Analyst question

```text
Give me a practical research analyst read on AMD using the current Newsroom Research Brief.

Use the AUTHORITATIVE NEWSROOM EVIDENCE TABLES first.
If the evidence context contains a SEC AUTHORITATIVE REPEAT CHECKPOINT, use it as authoritative SEC evidence.

First inventory the evidence by source.

SEC companyfacts evidence:
Inventory every SEC row you received. If SEC card count is 6, inventory all six SEC rows.
For every SEC row, include ticker, entity, metric, value, unit, period_end, filed, form, accession, concept, and source.

FRED evidence:
Separate FRED numeric rows from FRED metadata-only source links. Do not call metadata-only FRED links blank numeric rows.

BLS evidence:
Inventory every BLS row you received with series ID, title, latest value, latest date, previous value, previous date, change vs prior, units, frequency, category, source, and evidence status.

Then interpret:
1. Company fundamentals from SEC
2. Inflation and price-level context from FRED and BLS
3. Labor and wage context from BLS
4. Combined practical read
5. Missing, metadata-only, or weak evidence

Rules:
Never say no SEC companyfacts rows were provided if the SEC table or SEC repeat checkpoint contains numbered SEC rows.
Never say only one SEC card is present if the SEC table contains multiple numbered SEC rows.
Keep this research-only and simulation/advisory only. No live trading instructions, broker actions, order placement, position sizing, or personalized financial advice.
```

### Debug checks after Ask

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"

Select-String -Path ".\data\autolab_payload\research_analyst_last_combined_context.txt" `
  -Pattern "FULL CURRENT NEWSROOM SEC|SEC card count|metric: revenue|metric: net_income|metric: eps|metric: operating_income|metric: cash|metric: shares"

Select-String -Path ".\data\autolab_payload\research_analyst_last_sec_tail_guard.txt" `
  -Pattern "SEC card count|metric:"
```

## Safety

- No backups are created.
- No broker/order/live trading behavior is added.
- This is UI markdown rendering only.
