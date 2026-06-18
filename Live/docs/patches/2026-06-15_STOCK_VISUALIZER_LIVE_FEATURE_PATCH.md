# Stock Visualizer Live Feature Patch

Copy these files into your existing `Stock_Visualizer/Live/` folder:

- `Live/app.py`
- `Live/callbacks.py`
- `Live/ui/tabs_ui.py`
- `Live/assets/style.css`
- `Live/services/paper_cache.py`
- `Live/core/PaperBroker.py`

Included changes:
- persistent paper cache wired through `PaperStateCache`
- Watch tab paper trade price source: Replay / Live
- Watch tab position mode: Long Only / Allow Shorts
- Short Buy and Short Sell buttons that show only when shorts are allowed
- paper trade cache save/reset
- safer Pandas datetime parsing with `format="mixed"`
- paper buy/sell markers on the Watch chart
- fixed Watch top title callback for symbol changes
- replacement PaperBroker with short-collateral style accounting

Run after copying:
```bash
python -m py_compile Live/app.py Live/callbacks.py Live/ui/tabs_ui.py Live/services/paper_cache.py Live/core/PaperBroker.py
python Live/app.py
```

Suggested test order:
1. Open Watch.
2. Change symbol and confirm the top title updates.
3. Toggle Position Mode from Long Only to Allow Shorts.
4. Confirm Short Buy / Short Sell appear.
5. Place a Replay paper buy/sell and confirm markers show.
6. Switch Price Source to Live on today's date and test one trade.
7. Confirm `Live/cache/paper/` gets created.
