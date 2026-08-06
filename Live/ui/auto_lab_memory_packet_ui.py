from __future__ import annotations

from pydoc import classname

from dash import dcc, html


def build_market_memory_packet_panel():
    """Small additive Market Memory panel for the AI Auto Lab tab.

    Research/simulation only. This panel never places orders.
    """
    return html.Div(
        id="main-autolab-memory-packet-panel",
        className="autolab-card autolab-memory-card",
        children=[
            dcc.Store(id="main-autolab-memory-packet-store", storage_type="memory"),
            html.Div(
                className="autolab-section-header",
                children=[
                    html.Div(
                        children=[
                            html.H3("Market Memory Research Packet", className="surfaceTextWhite"),
                            html.P(
                                "Load the latest persistent Market Memory packet, review quality, then apply its symbols to Auto Lab.",
                                className="autolab-muted",
                            ),
                        ]
                    ),
                    html.Div(
                        className="autolab-badge autolab-badge-research",
                        children="Research / simulation only",
                    ),
                ],
            ),
            html.Div(
                className="autolab-memory-controls",
                children=[
                    html.Div(
                        className="autolab-field",
                        children=[
                            html.Label("Research theme", className="surfaceTextWhite"),
                            dcc.Input(
                                id="main-autolab-memory-theme",
                                type="text",
                                value="AI infrastructure semiconductors",
                                debounce=False,
                                className="autolab-input",
                            ),
                        ],
                    ),
                    html.Div(
                        className="autolab-field autolab-small-field",
                        children=[
                            html.Label("Max symbols", className="surfaceTextWhite"),
                            dcc.Input(
                                id="main-autolab-memory-max-symbols",
                                type="number",
                                value=12,
                                min=1,
                                max=30,
                                step=1,
                                debounce=False,
                                className="autolab-input",
                            ),
                        ],
                    ),
                    html.Button(
                        "Load Market Memory Packet",
                        id="main-autolab-memory-load-btn",
                        n_clicks=0,
                        className="autolab-button",
                    ),
                    html.Button(
                        "Apply Memory Symbols",
                        id="main-autolab-memory-apply-symbols-btn",
                        n_clicks=0,
                        className="autolab-button",
                    ),
                ],
            ),
            html.Div(id="main-autolab-memory-packet-status", className="autolab-status"),
            html.Div(id="main-autolab-memory-apply-status", className="autolab-status autolab-status-subtle"),
            dcc.Markdown(
                id="main-autolab-memory-packet-preview",
                className="autolab-muted",
                children=(
                    "No Market Memory packet loaded yet.\n\n"
                    "Click **Load Market Memory Packet** to build and preview the latest research packet."
                ),
            ),
        ],
    )
