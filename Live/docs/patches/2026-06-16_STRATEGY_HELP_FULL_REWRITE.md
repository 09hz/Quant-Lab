# Strategy Help Full Rewrite

Files included:

- `Live/ui/tabs_ui.py` — full replacement
- `Live/callbacks.py` — full replacement
- `Live/docs/strategy_examples/sma_fast_test.txt` — new runnable example
- `Live/docs/strategy_examples/ema_supertrend.txt` — clearer planned/not-runnable example
- `strategy_help_css_append.css` — append/replace Strategy Help CSS block in `Live/assets/style.css`

Notes:
- EMA Crossover, Fast SMA Test, and RSI Mean Reversion are runnable with the current v0.1 engine.
- EMA + Supertrend is insertable for documentation, but intentionally warns that it needs Strategy Language v0.2.
- Insert Example now updates the script editor and writes a status message.
