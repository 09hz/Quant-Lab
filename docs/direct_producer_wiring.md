# Direct Producer Wiring

v24.6 adds producer-local wiring. Target modules can wrap their own result-producing functions when they are imported.

## Disable direct producer wiring

```powershell
$env:ALGOTRADER_ENABLE_DIRECT_PRODUCER_WIRING = "0"
```

## Disable all quant wiring

```powershell
$env:ALGOTRADER_ENABLE_QUANT_WIRING = "0"
```

## What gets captured

Best-effort capture happens when a wired function/method returns:

- `dict`
- `list`
- `tuple`
- dataframe-like objects with `to_dict`, `to_json`, or `to_csv`

The original return value is preserved.

## Where output goes

Capture uses:

- Artifact Writer
- Artifact registry
- optional PostgreSQL artifact ingestion
- typed Quant Research Schema

## Safety

This is research/simulation only. It does not call brokers, place orders, move files, or delete files.
