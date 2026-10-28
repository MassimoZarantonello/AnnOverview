"""The look of the page: neutral graphite. Grey grounds one step apart, rounded nodes clearly lighter than the ground
with a light grey edge, an off-white for selection instead of a bright accent, and state colours kept muted (sage,
ochre, grey, a dull red) so that the only vivid colours on the page are the ROI images themselves. IBM Plex Sans
Condensed for text, IBM Plex Mono for numbers and names. The graph's style (Cytoscape) uses the same colours.

States keep AnnoCell's meaning: grey not started, ochre (yellow) in progress, sage (green) complete; red a folder
that cannot be read.
"""

from __future__ import annotations

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Condensed:wght@400;500;600&'
    'family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">'
)
SANS = "'IBM Plex Sans Condensed', 'Arial Narrow', sans-serif"
MONO = "'IBM Plex Mono', ui-monospace, Menlo, monospace"

BG = "#101113"  # the page and the graph
GRID = "#18191c"
SURFACE = "#16171a"  # bars, panels, the areas of the graph
RAISED = "#23252a"  # nodes: clearly lighter than the ground
LINE = "#2a2c30"  # hairlines, area frames
EDGE = "#5c6068"  # node edges
LINK = "#3e4148"  # links from slides
TEXT = "#e4e3e0"
MUTED = "#9b9c9e"
FAINT = "#68696c"
ACCENT = "#d9d6cf"  # off-white: selection, the active tab
STATE = {"not-started": "#73767c", "in-progress": "#c2a05c", "complete": "#7ea58c", "problem": "#bf6b66"}

PAGE_CSS = f"""
body, body.body--dark, .q-page, .nicegui-content {{ background: {BG}; color: {TEXT}; font-family: {SANS}; }}
.nicegui-content {{ padding: 0; gap: 0; }}
.mono {{ font-family: {MONO}; font-variant-numeric: tabular-nums; }}
.eyebrow {{ font-size: 12px; letter-spacing: .04em; color: {MUTED}; font-weight: 500; }}
.muted {{ color: {MUTED}; }}
.faint {{ color: {FAINT}; }}
.topbar {{ height: 54px; padding: 0 20px; background: {SURFACE}; border-bottom: 1px solid {LINE}; }}
.wordmark {{ font-weight: 600; font-size: 17px; letter-spacing: .02em; }}
.wordmark i {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: {ACCENT};
  margin-right: 10px; vertical-align: 1px; }}
.section {{ padding: 14px 20px; }}
.panel {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 10px; }}
.kpi {{ padding: 6px 18px; border-left: 1px solid {LINE}; }}
.kpi:first-child {{ border-left: none; }}
.kpi .value {{ font-family: {MONO}; font-size: 21px; line-height: 1.15; }}
.swatch {{ display: inline-block; width: 10px; height: 10px; margin-right: 6px; vertical-align: -1px; }}
.st-not-started {{ color: {STATE["not-started"]}; }}
.st-in-progress {{ color: {STATE["in-progress"]}; }}
.st-complete {{ color: {STATE["complete"]}; }}
.st-problem {{ color: {STATE["problem"]}; }}
.q-btn {{ border-radius: 6px; text-transform: none; letter-spacing: .02em; font-weight: 500; font-family: {SANS}; }}
.q-btn-group {{ border-radius: 8px; overflow: hidden; border: 1px solid {LINE}; box-shadow: none; }}
.q-btn-group .q-btn {{ font-family: {MONO}; font-size: 12px; padding: 4px 14px; min-height: 30px; }}
.q-tabs {{ border-bottom: 1px solid {LINE}; padding: 0 12px; background: {SURFACE}; }}
.q-tab {{ text-transform: none; letter-spacing: .03em; font-size: 14px; font-weight: 500; min-height: 40px; }}
.q-tab__indicator {{ height: 2px; }}
.q-tab-panels, .q-tab-panel {{ background: transparent !important; padding: 0; }}
.q-field--outlined .q-field__control {{ border-radius: 6px; }}
.q-field__native, .q-field__input {{ font-family: {MONO}; font-size: 12px; }}
.q-card {{ border-radius: 10px; box-shadow: none; border: 1px solid {LINE}; background: {SURFACE}; }}
.q-table__container {{ background: {SURFACE} !important; border: 1px solid {LINE}; border-radius: 10px;
  box-shadow: none; }}
.q-table th {{ font-size: 12px; letter-spacing: .03em; color: {MUTED}; font-weight: 500; }}
.q-table td {{ font-family: {MONO}; font-size: 12px; }}
.q-table tbody td, .q-table thead th {{ border-color: {LINE} !important; }}
.q-tree {{ font-family: {MONO}; font-size: 12.5px; }}
.q-menu {{ border-radius: 8px; border: 1px solid {LINE}; background: {SURFACE}; }}
"""

# The graph canvas: the dark field with a fine grid, like a counting chamber.
CANVAS_STYLE = (
    f"height: 72vh; background-color: {BG}; border: 1px solid {LINE}; border-radius: 12px; "
    f"background-image: linear-gradient({GRID} 1px, transparent 1px), "
    f"linear-gradient(90deg, {GRID} 1px, transparent 1px); background-size: 24px 24px"
)

GRAPH_STYLE = [
    {
        "selector": "node",
        "style": {"label": "data(label)", "color": TEXT, "font-family": SANS, "font-size": 17, "text-wrap": "wrap"},
    },
    {
        "selector": "node.roi",
        "style": {
            # The tissue in a rounded frame in the colour of the ROI's state.
            "shape": "round-rectangle",
            "corner-radius": 14,
            "width": 150,
            "height": 150,
            "background-image": "data(image)",
            "background-fit": "cover",
            "background-color": "#000000",
            "border-width": 4,
            "text-valign": "bottom",
            "text-margin-y": 12,
            "font-family": MONO,
            "font-size": 15,
            "color": MUTED,
        },
    },
    *[{"selector": f"node.roi.{state}", "style": {"border-color": colour}} for state, colour in STATE.items()],
    {"selector": "node.shared", "style": {"border-style": "double", "border-width": 8}},
    {"selector": "node.closed", "style": {"opacity": 0.45}},
    {"selector": "node.spacer", "style": {"width": 1, "height": 1, "opacity": 0, "events": "no"}},
    {
        # The framed areas (compound nodes) around each column: Slides, ROIs, Annotators.
        "selector": "node.area",
        "style": {
            "shape": "round-rectangle",
            "corner-radius": 18,
            "background-color": SURFACE,
            "background-opacity": 0.85,
            "border-width": 1,
            "border-color": LINE,
            "padding": 32,
            "text-valign": "top",
            "text-halign": "center",
            "text-margin-y": -12,
            "font-size": 16,
            "font-weight": 600,
            "color": MUTED,
        },
    },
    {
        "selector": "node.slide",
        "style": {
            "shape": "round-rectangle",
            "corner-radius": 10,
            "width": 200,
            "height": 48,
            "background-color": RAISED,
            "border-width": 1.5,
            "border-color": EDGE,
            "text-valign": "center",
            "font-family": MONO,
        },
    },
    {
        "selector": "node.annotator",
        "style": {
            "shape": "round-rectangle",
            "corner-radius": 12,
            "width": 220,
            "height": 92,
            "background-color": RAISED,
            "border-width": 1.5,
            "border-color": EDGE,
            "text-valign": "center",
            "font-family": MONO,
            "line-height": 1.5,
        },
    },
    {
        "selector": "edge",
        "style": {
            "curve-style": "unbundled-bezier",  # an S from left to right, as in node editors
            "control-point-distances": [30, -30],
            "control-point-weights": [0.3, 0.7],
            "width": 1.6,
            "line-color": LINK,
        },
    },
    *[
        {"selector": f"edge.{state}", "style": {"line-color": colour, "opacity": 0.8}}
        for state, colour in STATE.items()
    ],
    {"selector": "node:selected", "style": {"overlay-opacity": 0}},
    # A click lights up what is connected to the node and fades the rest.
    {"selector": ".faded", "style": {"opacity": 0.12}},
    # Lit nodes get a cyan ring outside their frame, wider than the frame itself, so it reads at any zoom; the
    # clicked node a wider one still.
    {"selector": "edge.lit", "style": {"width": 4, "opacity": 1}},
    {
        "selector": "node.lit",
        "style": {"outline-color": ACCENT, "outline-width": 4, "outline-offset": 5, "outline-opacity": 1},
    },
    {"selector": "node:selected", "style": {"outline-color": ACCENT, "outline-width": 8, "outline-offset": 6}},
    {"selector": "node:selected.slide, node:selected.annotator", "style": {"background-color": "#33363c"}},
]
