# Watch Architecture Refactor v1A Foundation

This patch adds the first foundation files for a TradingView-style architecture while keeping your Dash UI.

## Added files

```text
Live/models/watch_models.py
Live/services/bar_view_service.py
Live/services/chart_viewport_service.py
Live/renderers/watch_chart_renderer.py
```

## Why this exists

The Watch tab has become too heavy because `callbacks.py` is doing too much:

- live/replay source branching
- bar cleaning
- resampling
- chart rendering
- viewport/range logic
- strategy overlays
- paper markers
- metrics/stats

This patch starts moving responsibilities into services/renderers.

## Install

Create folders if needed:

```powershell
New-Item -ItemType Directory -Force .\Live\models
New-Item -ItemType Directory -Force .\Live\renderers
```

Copy the files into your project:

```powershell
Copy-Item .\watch_architecture_refactor_v1a_foundation\Live\models\watch_models.py .\Live\models\watch_models.py
Copy-Item .\watch_architecture_refactor_v1a_foundation\Live\services\bar_view_service.py .\Live\services\bar_view_service.py
Copy-Item .\watch_architecture_refactor_v1a_foundation\Live\services\chart_viewport_service.py .\Live\services\chart_viewport_service.py
Copy-Item .\watch_architecture_refactor_v1a_foundation\Live\renderers\watch_chart_renderer.py .\Live\renderers\watch_chart_renderer.py
```

Compile:

```powershell
python -m py_compile .\Live\models\watch_models.py
python -m py_compile .\Live\services\bar_view_service.py
python -m py_compile .\Live\services\chart_viewport_service.py
python -m py_compile .\Live\renderers\watch_chart_renderer.py
```

## Next manual wiring step

After these files compile, update `callbacks.py` in small steps:

1. Import services.
2. Instantiate them inside `register_callbacks`.
3. Replace only the top live/replay bar-building block in `render_watch_tab`.
4. Leave overlays/paper markers untouched until the chart still works.
5. Then move viewport logic.
6. Then move rendering logic.

Do not rewrite the full Watch callback in one pass.
