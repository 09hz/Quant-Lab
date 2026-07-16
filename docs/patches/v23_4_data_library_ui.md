# v23.4 — Data Library UI

## Purpose

Make the new Data Catalog usable from the Dash app.

This adds a Data Library UI that lets you browse and preview cataloged artifacts:

```text
Markdown reports
Market Memory packets
JSON result files
CSV exports
Backtest results
Walk-forward results
Universe runs
Diagnostics
Newsroom exports
```

## Scope

```text
Add Data Library tab/panel: yes
Browse cataloged artifacts: yes
Filter by artifact type: yes
Filter by extension: yes
Search by filename/path/theme/symbol/tags: yes
View Markdown previews: yes
View JSON previews: yes
View CSV previews: yes
Rescan Live/data from UI: yes
Move/delete files: no
PostgreSQL: not yet
Research/simulation only: yes
```

## Adds

```text
Live/ui/data_library_ui.py
Live/services/data_catalog/data_library_queries.py
Live/services/data_catalog/data_library_callbacks.py
Live/services/data_catalog/data_library_self_test.py
Live/assets/data_library.css
```

## Patches

```text
Live/app.py
```

## Safety

```text
No live orders.
No broker connection.
No PaperBroker calls.
No account credentials.
No trade execution.
No files moved.
No files deleted.
```
