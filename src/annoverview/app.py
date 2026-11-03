"""The page: ``annoverview <root>`` opens it in the browser, read from the shared folder at every Refresh.

Three tabs, all filterable by slide. **Graph**: one round as nodes and links (slides → images, a picture each →
annotators), moved and zoomed with the mouse; a click on a node shows its details. **Progress**: how much of the
model's proposal was kept, round by round, and the models' scores on the test regions. **Tables**: the rounds (images
by state, how many go into training) and the tree (annotator → round → image, or round → annotator → image).
Read-only: the page has no control that writes anything. No annotator is timed: no last save, no started or finished
dates (AnnoLoop's rule of no monitoring).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from annoverview import theme
from annoverview.graph import graph_elements, round_keys
from annoverview.thumbs import thumbnail_uri
from annoverview.tree import (
    COMPLETE,
    DRAWN,
    IN_PROGRESS,
    NOT_STARTED,
    RoiStatus,
    corrections,
    model_scores,
    read_tree,
)
from annoverview.tree import round_summary as summarize

# Text colour class per state (``theme.PAGE_CSS``; AnnoCell's meaning: amber to do, green done).
STATE_CLASS = {
    NOT_STARTED: "st-not-started",
    IN_PROGRESS: "st-in-progress",
    COMPLETE: "st-complete",
    DRAWN: "st-complete",
}
ALL_SLIDES = "all slides"
UNSET = "unset"


def roi_label(roi: RoiStatus) -> str:
    """One line per image: name, state, cells checked, closed."""
    if roi.problem:
        return f"{roi.name}: cannot be read ({roi.problem})"
    parts = [roi.state]
    if roi.state == IN_PROGRESS:
        parts.append(f"{roi.ok} of {roi.cells} cells checked")
    elif roi.cells:
        parts.append(f"{roi.cells} cells")
    if roi.closed:
        parts.append("closed")
    return f"{roi.name}: {', '.join(parts)}"


def group_label(title: str, rois: list[RoiStatus]) -> str:
    """A round or an annotator: how many of its images are done."""
    done = sum(r.state in (COMPLETE, DRAWN) for r in rois)
    closed = ", closed" if rois and all(r.closed for r in rois) else ""
    return f"{title}: {done} of {len(rois)} done{closed}"


def tree_nodes(rois: list[RoiStatus], by: str) -> list[dict]:
    """``ui.tree`` nodes: annotator → round → image (``by == "annotator"``) or round → annotator → image.
    Second-level nodes have ``open``: not every image in them is closed (the page shows those expanded)."""

    def round_title(number):
        return "test regions" if number is None else f"round {number}"

    def leaf(roi):
        return {"id": str(roi.folder), "label": roi_label(roi), "cls": _cls(roi)}

    def order(number):  # rounds in order, test regions last
        return (number is None, number or 0)

    if by == "annotator":
        outer = sorted({r.annotator for r in rois})
        nodes = []
        for annotator in outer:
            mine = [r for r in rois if r.annotator == annotator]
            children = []
            for number in sorted({r.round for r in mine}, key=order):
                group = [r for r in mine if r.round == number]
                children.append(
                    {
                        "id": f"{annotator}/{number}",
                        "label": group_label(round_title(number), group),
                        "children": [leaf(r) for r in group],
                        "open": not all(r.closed for r in group),
                    }
                )
            nodes.append({"id": annotator, "label": group_label(annotator, mine), "children": children})
        return nodes
    nodes = []
    for number in sorted({r.round for r in rois}, key=order):
        group = [r for r in rois if r.round == number]
        children = []
        for annotator in sorted({r.annotator for r in group}):
            theirs = [r for r in group if r.annotator == annotator]
            children.append(
                {
                    "id": f"{number}/{annotator}",
                    "label": group_label(annotator, theirs),
                    "children": [leaf(r) for r in theirs],
                    "open": not all(r.closed for r in theirs),
                }
            )
        nodes.append({"id": str(number), "label": group_label(round_title(number), group), "children": children})
    return nodes


def _cls(roi: RoiStatus) -> str:
    return "st-problem" if roi.problem else STATE_CLASS[roi.state]


CYTOSCAPE_JS = "https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.30.2/cytoscape.min.js"
LEGEND = (("not-started", "not started"), ("in-progress", "in progress"), ("complete", "complete"))


def build_page(root: Path) -> None:
    """The whole page; ``content`` is read again from the folder when Refresh is clicked. A top bar, then two tabs:
    the graph of one round, and the tables."""
    from nicegui import ui

    ui.dark_mode(True)
    ui.colors(primary=theme.ACCENT)
    ui.add_head_html(theme.FONTS + f'<script src="{CYTOSCAPE_JS}"></script>')
    ui.add_css(theme.PAGE_CSS)
    # "round": the round shown in the graph (None: the test regions); UNSET until the page picks one.
    view = {"by": "annotator", "slide": ALL_SLIDES, "round": UNSET, "tab": "Graph", "selected": None}
    details: dict[str, list[str]] = {}

    @ui.refreshable
    def detail_panel():
        ui.label("Selection").classes("eyebrow")
        lines = details.get(view["selected"])
        if not lines:
            ui.label("Click a node: a slide, an image or an annotator.").classes("text-sm muted")
            return
        ui.label(lines[0]).classes("mono text-sm").style("margin: 2px 0 6px")
        for line in lines[1:]:
            head, _, rest = line.partition(": ")
            with ui.row().classes("gap-2 w-full no-wrap").style(f"border-top: 1px solid {theme.LINE}; padding: 5px 0"):
                if not rest:  # a summary line, not "name: state"
                    ui.label(line).classes("text-xs muted")
                    continue
                ui.label(head).classes("mono text-xs").style("width: 118px; flex: none; overflow-wrap: anywhere")
                ui.label(rest).classes("text-xs muted")

    def on_node(event):
        view["selected"] = event.args
        detail_panel.refresh()

    ui.on("graph_node", on_node)

    @ui.refreshable
    def content():
        now = datetime.now()
        rois = read_tree(root)
        slides = sorted({r.source for r in rois if r.source})
        shown = [r for r in rois if view["slide"] == ALL_SLIDES or r.source == view["slide"]]
        with ui.row().classes("topbar w-full items-center no-wrap"):
            ui.html('<span class="wordmark"><i></i>AnnOverview</span>')
            ui.label(str(root)).classes("mono text-xs faint ellipsis").style("max-width: 40vw")
            ui.space()
            ui.label(f"read {now:%H:%M:%S}").classes("mono text-xs muted")
            ui.select([ALL_SLIDES, *slides], value=view["slide"], on_change=_set(view, "slide")).props(
                "dense outlined options-dense"
            ).classes("w-52")
            ui.button("Refresh", icon="refresh", on_click=content.refresh).props("outline dense size=sm").style(
                "padding: 4px 12px"
            )
        if not rois:
            with ui.element("div").classes("section"):
                ui.label("No image folder here: the root holds one folder per annotator.").classes("st-problem")
            return
        with ui.tabs(value=view["tab"], on_change=lambda e: view.update(tab=e.value)).props(
            "dense align=left active-color=white indicator-color=primary"
        ) as tabs:
            ui.tab("Graph")
            ui.tab("Progress")
            ui.tab("Tables")
        with ui.tab_panels(tabs, value=view["tab"]).classes("w-full").props("animated=false"):
            with ui.tab_panel("Graph"):
                graph_panel(shown)
            with ui.tab_panel("Progress"):
                progress(shown)
            with ui.tab_panel("Tables"):
                tables(shown)

    def graph_panel(shown):
        keys = round_keys(shown)
        if not keys:
            with ui.element("div").classes("section"):
                ui.label("No image for this slide.").classes("muted")
            return
        if view["round"] not in keys:  # default: the latest round still open, else the latest
            open_rounds = [k for k in keys if k is not None and not all(r.closed for r in shown if r.round == k)]
            view["round"] = open_rounds[-1] if open_rounds else keys[0] if keys[0] is not None else keys[-1]
        names = {k: "test regions" if k is None else f"round {k}" for k in keys}
        this_round = [r for r in shown if r.round == view["round"]]
        with ui.row().classes("section w-full items-center no-wrap"):
            ui.toggle(
                {names[k]: names[k] for k in keys}, value=names[view["round"]], on_change=lambda e: _round(e, names)
            ).props("unelevated dense toggle-color=grey-4 toggle-text-color=grey-10 text-color=grey-5")
            ui.button("Reset layout", icon="restart_alt", on_click=lambda: reset_layout()).props(
                "flat dense size=sm no-caps"
            ).classes("muted")
            ui.space()
            kpis(this_round)
        elements, found = graph_elements(shown, view["round"], picture=_picture)
        details.clear()
        details.update(found)
        # The graph and, in a column of its own beside it, the details of the node clicked: they never cover the
        # graph, and long details scroll in their column. The legend sits in the graph's bottom left corner.
        with ui.row().classes("w-full no-wrap items-stretch gap-4").style("padding: 0 20px 20px"):
            with ui.element("div").classes("relative").style("flex: 1; min-width: 0"):
                canvas = ui.element("div").classes("w-full").style(theme.CANVAS_STYLE)
                with (
                    ui.row()
                    .classes("panel absolute items-center gap-4")
                    .style("bottom: 12px; left: 12px; padding: 6px 12px")
                ):
                    for state, text in LEGEND:
                        ui.html(
                            f'<span class="swatch" style="background:{theme.STATE[state]}"></span>'
                            f'<span class="text-xs muted">{text}</span>'
                        )
                    ui.html(
                        f'<span class="swatch" style="border: 3px double {theme.MUTED}"></span>'
                        '<span class="text-xs muted">shared</span>'
                    )
            with (
                ui.element("div")
                .classes("panel")
                .style("width: 340px; flex: none; height: 72vh; overflow-y: auto; padding: 12px 14px")
            ):
                detail_panel()
        # Positions the viewer dragged nodes to, kept in this browser per folder and round (a convenience: the
        # default layout comes back with Reset layout, or in another browser).
        key = json.dumps(f"annoverview:{root}:{view['round']}")
        script = f"""
            (function draw() {{
                const container = document.getElementById("c{canvas.id}");
                if (typeof cytoscape === "undefined" || !container) {{ return setTimeout(draw, 100); }}
                if (window.annoGraph) {{ window.annoGraph.destroy(); }}
                let saved = {{}};
                try {{ saved = JSON.parse(localStorage.getItem({key}) || "{{}}"); }} catch (error) {{}}
                const elements = {json.dumps(elements)};
                for (const element of elements) {{
                    const moved = saved[element.data.id];
                    if (moved && element.position) {{ element.position = moved; }}
                }}
                const cy = cytoscape({{
                    container, elements, style: {json.dumps(theme.GRAPH_STYLE)},
                    layout: {{ name: "preset" }}, wheelSensitivity: 0.3, minZoom: 0.05, maxZoom: 4,
                }});
                cy.nodes(".spacer").ungrabify();
                // The canvas may still be settling into its column when this runs: measure again, then fit.
                const refit = () => {{ cy.resize(); cy.fit(undefined, 48); }};
                refit();
                setTimeout(refit, 200);
                window.onresize = refit;
                cy.on("dragfree", "node", () => {{
                    const positions = {{}};
                    cy.nodes().not(".area, .spacer").forEach((node) => {{ positions[node.id()] = node.position(); }});
                    try {{ localStorage.setItem({key}, JSON.stringify(positions)); }} catch (error) {{}}
                }});
                // What a node is connected to: an image its slide and annotators; an annotator their images and the
                // slides they come from; a slide its images and who has them.
                const connected = (node) => node.hasClass("roi") ? node.closedNeighborhood()
                    : node.hasClass("annotator") ? node.predecessors().add(node)
                    : node.successors().add(node);
                const clear = () => cy.elements().removeClass("faded lit");
                cy.on("tap", "node", (event) => {{
                    const node = event.target;
                    if (node.hasClass("area")) {{ return; }}
                    clear();
                    cy.elements().not(".area, .spacer").difference(connected(node)).addClass("faded");
                    connected(node).addClass("lit");
                    emitEvent("graph_node", node.id());
                }});
                cy.on("tap", (event) => {{ if (event.target === cy) {{ clear(); emitEvent("graph_node", ""); }} }});
                window.annoGraph = cy;
            }})();
        """
        ui.timer(0.05, lambda: ui.run_javascript(script), once=True)

    def kpis(rois):
        """The numbers of the round shown: images, by state, and how many go into training."""
        values = [
            ("images", len({r.name for r in rois}), ""),
            ("complete", sum(r.state in (COMPLETE, DRAWN) for r in rois), "st-complete"),
            ("in progress", sum(r.state == IN_PROGRESS for r in rois), "st-in-progress"),
            ("not started", sum(r.state == NOT_STARTED for r in rois), "st-not-started"),
            ("into training", sum(r.into_training for r in rois), ""),
        ]
        with ui.row().classes("panel gap-0 no-wrap"):
            for label, value, cls in values:
                with ui.element("div").classes("kpi"):
                    ui.label(str(value)).classes(f"value {cls}")
                    ui.label(label).classes("eyebrow")

    def reset_layout():
        """Forget where the viewer dragged the nodes of the round shown, and draw it again."""
        ui.run_javascript(f"localStorage.removeItem({json.dumps(f'annoverview:{root}:{view["round"]}')})")
        content.refresh()

    def _round(event, names):
        view["round"] = next(k for k, name in names.items() if name == event.value)
        view["selected"] = None
        content.refresh()

    def progress(shown):
        """Is the model getting better? How much of its proposal the annotators had to fix, round by round, and its
        score on the test regions."""
        with ui.element("div").classes("section w-full"):
            fixes = corrections(shown)
            with ui.row().classes("w-full no-wrap gap-4 items-stretch"):
                with ui.element("div").classes("panel").style("flex: 1; min-width: 0; padding: 14px 16px"):
                    ui.label("How much of the proposal was kept, round by round").classes("eyebrow")
                    ui.label("Complete images only. If the model improves, the kept share grows.").classes(
                        "text-xs faint"
                    )
                    if fixes:
                        ui.echart(_corrections_chart(fixes)).style("height: 340px")
                    else:
                        ui.label("No complete image yet.").classes("text-sm muted").style("margin-top: 12px")
                scores = model_scores(root)
                with ui.element("div").classes("panel").style("flex: 1; min-width: 0; padding: 14px 16px"):
                    ui.label("Score on the test regions, model by model").classes("eyebrow")
                    ui.label("Mean AP over the test regions; round 0 is the starting model.").classes("text-xs faint")
                    if scores:
                        ui.echart(_scores_chart(scores)).style("height: 340px")
                    else:
                        ui.label("No model scored yet: AnnoLoop's score_model writes the scores.").classes(
                            "text-sm muted"
                        ).style("margin-top: 12px")
            heading("Corrections per round")
            columns = [
                {"name": k, "label": label, "field": k, "align": "left" if k == "round" else "right"}
                for k, label in (
                    ("round", "Round"),
                    ("rois", "Complete images"),
                    ("proposal", "Proposed cells"),
                    ("kept_%", "Kept %"),
                    ("edited_%", "Edited %"),
                    ("deleted_%", "Deleted %"),
                    ("drawn", "Drawn new"),
                )
            ]
            ui.table(columns=columns, rows=fixes, row_key="round").props("dense flat").classes("w-full")
            heading("Models on the test regions")
            keys = sorted({k for row in scores for k in row if k.startswith("AP@")})
            titles = {"model": "Model", "round": "Trained on round", "regions": "Test regions"}
            columns = [
                {"name": k, "label": titles.get(k, k), "field": k, "align": "left" if k == "model" else "right"}
                for k in ("model", "round", "regions", *keys)
            ]
            ui.table(columns=columns, rows=scores, row_key="model").props("dense flat").classes("w-full")

    def heading(text):
        ui.label(text).classes("eyebrow").style("margin: 22px 0 8px")

    def tables(shown):
        with ui.element("div").classes("section w-full"):
            heading("Rounds")
            columns = [
                {"name": "round", "label": "Round", "field": "round", "align": "left"},
                {"name": "annotators", "label": "Annotators", "field": "annotators"},
                {"name": "rois", "label": "Images", "field": "rois"},
                {"name": NOT_STARTED, "label": "Not started", "field": NOT_STARTED},
                {"name": IN_PROGRESS, "label": "In progress", "field": IN_PROGRESS},
                {"name": COMPLETE, "label": "Complete", "field": COMPLETE},
                {"name": "into_training", "label": "Into training", "field": "into_training"},
                {"name": "checked", "label": "Cells checked", "field": "checked"},
                {"name": "closed", "label": "Closed", "field": "closed"},
            ]
            rows = [{**row, "closed": "yes" if row["closed"] else ""} for row in summarize(shown)]
            ui.table(columns=columns, rows=rows, row_key="round").props("dense flat").classes("w-full")

            heading("Images")
            ui.toggle(
                {"annotator": "by annotator", "round": "by round"}, value=view["by"], on_change=_set(view, "by")
            ).props("unelevated dense toggle-color=grey-4 toggle-text-color=grey-10 text-color=grey-5")
            nodes = tree_nodes(shown, view["by"])
            with ui.element("div").classes("panel w-full").style("margin-top: 8px; padding: 8px"):
                tree = ui.tree(nodes, label_key="label").props("dense")
                tree.add_slot("default-header", '<span :class="props.node.cls">{{ props.node.label }}</span>')
                # The first level, and below it what is not closed: the images still being worked on show at once.
                tree.expand([n["id"] for n in nodes] + [c["id"] for n in nodes for c in n["children"] if c["open"]])

    def _set(state, key):
        def change(event):
            state[key] = event.value
            content.refresh()

        return change

    content()


def _chart_base() -> dict:
    """What every chart shares: no background of its own, the page's fonts and muted greys."""
    axis = {"axisLine": {"lineStyle": {"color": theme.LINE}}, "axisLabel": {"color": theme.MUTED}}
    return {
        "backgroundColor": "transparent",
        "textStyle": {"fontFamily": theme.SANS, "color": theme.MUTED},
        "grid": {"left": 48, "right": 16, "top": 40, "bottom": 36},
        "legend": {"top": 0, "textStyle": {"color": theme.MUTED}},
        "tooltip": {"trigger": "axis"},
        "xAxis": {**axis, "type": "category"},
        "yAxis": {**axis, "type": "value", "splitLine": {"lineStyle": {"color": theme.GRID}}},
    }


def _corrections_chart(rows: list[dict]) -> dict:
    """Stacked bars, one per round: kept, edited and deleted as % of the proposal's cells."""
    chart = _chart_base()
    chart["xAxis"]["data"] = [f"round {r['round']}" for r in rows]
    chart["yAxis"] |= {"max": 100, "axisLabel": {"color": theme.MUTED, "formatter": "{value} %"}}
    colours = {"kept": theme.STATE["complete"], "edited": theme.STATE["in-progress"]}
    colours["deleted"] = theme.STATE["problem"]
    chart["series"] = [
        {
            "name": name,
            "type": "bar",
            "stack": "proposal",
            "barMaxWidth": 56,
            "itemStyle": {"color": colour},
            "data": [r[f"{name}_%"] for r in rows],
        }
        for name, colour in colours.items()
    ]
    return chart


def _scores_chart(rows: list[dict]) -> dict:
    """One line per AP threshold over the rounds (the starting model at round 0)."""
    chart = _chart_base()
    chart["xAxis"]["data"] = [f"round {r['round']}" for r in rows]
    chart["yAxis"] |= {"min": 0, "max": 1}
    keys = sorted({k for r in rows for k in r if k.startswith("AP@")})
    shades = [theme.TEXT, theme.MUTED, theme.FAINT]
    chart["series"] = [
        {
            "name": key,
            "type": "line",
            "symbolSize": 8,
            "lineStyle": {"width": 2, "color": shades[i % len(shades)]},
            "itemStyle": {"color": shades[i % len(shades)]},
            "data": [r.get(key) for r in rows],
        }
        for i, key in enumerate(keys)
    ]
    return chart


def _picture(roi: RoiStatus) -> str:
    """The image's picture, or nothing if it cannot be drawn (the node then shows its ring only)."""
    try:
        return thumbnail_uri(roi.folder)
    except (OSError, ValueError, KeyError):
        return "none"


def main(argv: list[str] | None = None) -> None:
    """``annoverview <root>``: the page for the shared folder ``root`` (one folder per annotator), in the browser."""
    parser = argparse.ArgumentParser(prog="annoverview", description="Overview of the annotation rounds.")
    parser.add_argument("root", help="the shared annotation folder (one folder per annotator)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser tab")
    parser.add_argument(
        "--share",
        action="store_true",
        help="also accept connections from the network (others can then open the page); default: this computer only",
    )
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        parser.error(f"{root} is not a folder (is the network drive mounted?)")
    from nicegui import ui  # here, so that --help and errors answer without loading the web server

    # Only this computer by default: the page shows annotators' work and unpublished images.
    host = "0.0.0.0" if args.share else "127.0.0.1"
    ui.run(
        lambda: build_page(root),
        title="AnnOverview",
        host=host,
        port=args.port,
        show=not args.no_browser,
        reload=False,
    )


if __name__ == "__main__":
    main()
