"""The page: ``annoverview <root>`` opens it in the browser, read from the shared folder at every Refresh.

Four parts: the rounds (ROIs by state, how many go into training), now (what each annotator saved last), the tree
(annotator → round → ROI, or round → annotator → ROI) and the history (when each ROI was started and finished), all
filterable by slide. Read-only: the page has no
control that writes anything.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from annoverview.tree import (
    COMPLETE,
    DRAWN,
    IN_PROGRESS,
    NOT_STARTED,
    RoiStatus,
    ago,
    history,
    latest_saves,
    read_tree,
)
from annoverview.tree import round_summary as summarize

# Tailwind text colour per state (the same meaning as AnnoCell's outlines: yellow to do, green done).
STATE_CLASS = {
    NOT_STARTED: "text-gray-500",
    IN_PROGRESS: "text-amber-700",
    COMPLETE: "text-green-700",
    DRAWN: "text-green-700",
}
ALL_SLIDES = "all slides"


def roi_label(roi: RoiStatus, now: datetime) -> str:
    """One line per ROI: name, state, cells checked, last save, closed."""
    if roi.problem:
        return f"{roi.name}: cannot be read ({roi.problem})"
    parts = [roi.state]
    if roi.state == IN_PROGRESS:
        parts.append(f"{roi.ok} of {roi.cells} cells checked")
    elif roi.cells:
        parts.append(f"{roi.cells} cells")
    if roi.completed_at and not roi.is_test:
        parts.append(f"finished {_day(roi.completed_at)}")
    elif roi.started_at:
        parts.append(f"started {_day(roi.started_at)}")
    if roi.saved_at:
        parts.append(f"saved {ago(roi.saved_at, now)}")
    if roi.closed:
        parts.append("closed")
    return f"{roi.name}: {', '.join(parts)}"


def group_label(title: str, rois: list[RoiStatus]) -> str:
    """A round or an annotator: how many of its ROIs are done."""
    done = sum(r.state in (COMPLETE, DRAWN) for r in rois)
    closed = ", closed" if rois and all(r.closed for r in rois) else ""
    return f"{title}: {done} of {len(rois)} done{closed}"


def tree_nodes(rois: list[RoiStatus], by: str, now: datetime) -> list[dict]:
    """``ui.tree`` nodes: annotator → round → ROI (``by == "annotator"``) or round → annotator → ROI. Second-level
    nodes have ``open``: not every ROI in them is closed (the page shows those expanded)."""

    def round_title(number):
        return "test regions" if number is None else f"round {number}"

    def leaf(roi):
        return {"id": str(roi.folder), "label": roi_label(roi, now), "cls": _cls(roi)}

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


def _day(moment: datetime | None) -> str:
    return "" if moment is None else f"{moment:%d %b %H:%M}"


def history_rows(rois: list[RoiStatus]) -> list[dict]:
    """The history table: one row per ROI started, most recent first."""
    return [
        {
            "id": str(r.folder),
            "annotator": r.annotator,
            "round": "test" if r.is_test else r.round,
            "roi": r.name,
            "started": _day(r.started_at),
            "finished": "" if r.is_test else _day(r.completed_at),
            "state": r.state + (", closed" if r.closed else ""),
        }
        for r in history(rois)
    ]


def _cls(roi: RoiStatus) -> str:
    return "text-red-700" if roi.problem else STATE_CLASS[roi.state]


def build_page(root: Path) -> None:
    """The whole page; ``content`` is read again from the folder when Refresh is clicked."""
    from nicegui import ui

    view = {"by": "annotator", "slide": ALL_SLIDES}

    @ui.refreshable
    def content():
        now = datetime.now()
        rois = read_tree(root)
        slides = sorted({r.source for r in rois if r.source})
        shown = [r for r in rois if view["slide"] == ALL_SLIDES or r.source == view["slide"]]
        ui.label(f"{root} · read {now:%H:%M:%S}").classes("text-sm text-gray-500")
        if not rois:
            ui.label("No ROI folder here: the root holds one folder per annotator.").classes("text-red-700")
            return

        ui.label("Rounds").classes("text-xl font-semibold mt-4")
        columns = [
            {"name": "round", "label": "Round", "field": "round", "align": "left"},
            {"name": "annotators", "label": "Annotators", "field": "annotators"},
            {"name": "rois", "label": "ROIs", "field": "rois"},
            {"name": NOT_STARTED, "label": "Not started", "field": NOT_STARTED},
            {"name": IN_PROGRESS, "label": "In progress", "field": IN_PROGRESS},
            {"name": COMPLETE, "label": "Complete", "field": COMPLETE},
            {"name": "into_training", "label": "Into training", "field": "into_training"},
            {"name": "checked", "label": "Cells checked", "field": "checked"},
            {"name": "closed", "label": "Closed", "field": "closed"},
        ]
        rows = [{**row, "closed": "yes" if row["closed"] else ""} for row in summarize(shown)]
        ui.table(columns=columns, rows=rows, row_key="round").props("dense flat bordered")

        ui.label("Now (last save of each annotator)").classes("text-xl font-semibold mt-4")
        latest = latest_saves(shown)
        for annotator in sorted({r.annotator for r in shown}):
            roi = latest.get(annotator)
            where = "nothing saved yet" if roi is None else f"{_where(roi)}, saved {ago(roi.saved_at, now)}"
            ui.label(f"{annotator}: {where}")

        ui.label("ROIs").classes("text-xl font-semibold mt-4")
        with ui.row().classes("items-center"):
            ui.toggle({"annotator": "by annotator", "round": "by round"}, value=view["by"], on_change=_set(view, "by"))
            ui.select([ALL_SLIDES, *slides], value=view["slide"], on_change=_set(view, "slide")).classes("w-64")
        nodes = tree_nodes(shown, view["by"], now)
        tree = ui.tree(nodes, label_key="label")
        tree.add_slot("default-header", '<span :class="props.node.cls">{{ props.node.label }}</span>')
        # The first level, and below it what is not closed: the ROIs still being worked on show at once.
        tree.expand([n["id"] for n in nodes] + [c["id"] for n in nodes for c in n["children"] if c["open"]])

        ui.label("History (when each ROI was started and finished)").classes("text-xl font-semibold mt-4")
        labels = {"annotator": "Annotator", "round": "Round", "roi": "ROI", "started": "Started"}
        labels |= {"finished": "Finished", "state": "State"}
        columns = [
            {"name": key, "label": label, "field": key, "align": "left", "sortable": True}
            for key, label in labels.items()
        ]
        ui.table(columns=columns, rows=history_rows(shown), row_key="id", pagination=20).props("dense flat bordered")

    def _set(state, key):
        def change(event):
            state[key] = event.value
            content.refresh()

        return change

    with ui.row().classes("items-center w-full"):
        ui.label("AnnOverview").classes("text-2xl font-bold")
        ui.button("Refresh", icon="refresh", on_click=content.refresh)
    content()


def _where(roi: RoiStatus) -> str:
    return f"{'test region' if roi.is_test else f'round {roi.round}'} / {roi.name}"


def main(argv: list[str] | None = None) -> None:
    """``annoverview <root>``: the page for the shared folder ``root`` (one folder per annotator), in the browser."""
    parser = argparse.ArgumentParser(prog="annoverview", description="Overview of the annotation rounds.")
    parser.add_argument("root", help="the shared annotation folder (one folder per annotator)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser tab")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        parser.error(f"{root} is not a folder (is the network drive mounted?)")
    from nicegui import ui  # here, so that --help and errors answer without loading the web server

    ui.run(lambda: build_page(root), title="AnnOverview", port=args.port, show=not args.no_browser, reload=False)


if __name__ == "__main__":
    main()
