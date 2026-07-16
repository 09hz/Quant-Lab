# Watch Daily Rangebreaks Force-Clear Hotfix 34n4

## Purpose

Patch 34n3 failed because its class-detection regex was too strict. This hotfix
uses line-based parsing instead of fragile regex matching.

## Behavior

For `1 day` Watch replay charts:

- keeps the x-axis as a date axis;
- disables the rangeslider;
- force-clears x-axis rangebreaks with direct assignment;
- pads the daily date range by one calendar day on each side;
- logs `[WATCH DAILY RENDER] ... rangebreaks=off`.

## Files changed

- `Live/renderers/watch_chart_renderer.py`
- `Live/scripts/check_watch_daily_rangebreaks.py`
- `Live/docs/patches/watch_daily_rangebreaks_force_clear_hotfix_patch_34n4.md`
