# Central Artifact Writer

Use the artifact writer for new research outputs.

```python
from services.artifacts import save_json, save_csv, save_markdown

save_json(
    module="auto_lab",
    artifact_type="strategy_result",
    symbol="NVDA",
    payload={"symbol": "NVDA", "research_only": True},
)

save_csv(
    module="backtest",
    artifact_type="equity_curve",
    symbol="AMD",
    rows=[{"date": "2026-01-01", "equity": 100000}],
)

save_markdown(
    module="market_memory",
    artifact_type="research_packet",
    theme="AI infrastructure semiconductors",
    markdown="# Research Packet\n\nResearch only.",
)
```

Files are written to:

```text
Live/data/managed_artifacts/<module>/<artifact_type>/<YYYY-MM-DD>/
```

Local registry:

```text
Live/data/catalog/artifact_writer.sqlite
```

Retry pending database ingestion:

```powershell
cd "C:\Users\sunny\Documents\GitHub\AlgoTrader\Live"
$PY = "C:\Users\sunny\Documents\GitHub\StockVisualizer\.venv\Scripts\python.exe"
& $PY -m services.artifacts.retry_pending_ingestion --repo-root "C:\Users\sunny\Documents\GitHub\AlgoTrader"
```

Research/simulation only. No broker calls or live trading.
