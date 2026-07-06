# Patch 23 — Export Center Framework

This patch adds a backend-only export framework for user-controlled strategy,
backtest, research, and AI context exports.

## Added files

- `Live/services/exports/__init__.py`
- `Live/services/exports/export_manager.py`
- `Live/services/exports/report_writer.py`
- `Live/services/exports/context_loader.py`
- `Live/scripts/check_export_manager.py`

## Updated files

- `.gitignore`

## Purpose

The Export Center is the local file layer for future UI features such as:

- Export Strategy Script
- Export Backtest Report
- Export Strategy Context JSON
- Export Strategy Context Markdown
- Export Research Brief JSON/Markdown
- Attach Selected Context to AI Advisor

## Safety model

The framework is local-only and user-controlled.

It does not:

- place trades
- access broker/account data
- call LLMs
- upload files
- browse the web
- expose secrets in the browser

Before writing or attaching context, it performs defensive redaction for obvious
fields such as API keys, bearer tokens, passwords, and token-like strings.

This redaction is a safety layer, not a replacement for good data hygiene.
Do not intentionally place secrets in strategy scripts or export contexts.

## Usage

Compile:

```powershell
python -m py_compile .\Live\services\exports\export_manager.py
python -m py_compile .\Live\services\exports\report_writer.py
python -m py_compile .\Live\services\exports\context_loader.py
python -m py_compile .\Live\scripts\check_export_manager.py
```

Check without writing files:

```powershell
python .\Live\scripts\check_export_manager.py --no-write
```

Write demo exports:

```powershell
python .\Live\scripts\check_export_manager.py
```

Generated files are written under:

```text
exports/
```

That directory is ignored by Git.

## Next patch

Patch 24 should wire this framework into Strategy Lab with buttons for:

- Export Strategy
- Export Backtest Report
- Attach Current Strategy Context to AI
- Clear Attached Context
