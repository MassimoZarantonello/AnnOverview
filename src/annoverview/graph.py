"""The graph of one round: slides on the left, images in the middle (a picture each), annotators on the right; a
link from the slide an image was cut from, and from the image to each annotator who has it. An image given to several
annotators (shared, to compare them) is one node with several links. (Node ids keep the format's word: ``roi:``.)

Each column sits in a framed area (a compound node) named after it: Slides, Images, Annotators. Positions are computed
here (columns, in order), not by a layout algorithm: the same folder always gives the same
picture, and links cross as little as the order allows. The page draws the elements with Cytoscape.js.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from annoverview.tree import COMPLETE, DRAWN, IN_PROGRESS, NOT_STARTED, RoiStatus

COLUMN_X = {"slide": 0, "roi": 480, "annotator": 960}
ROI_GAP_Y = 200  # between rows of image lenses
ROI_GAP_X = 190  # between image lenses in a row
MIN_GAP_Y = 110  # between slides, and between annotators
NO_SLIDE = "no slide"
AREAS = {"slide": "Slides", "roi": "Images", "annotator": "Annotators"}  # the framed area of each column


def round_keys(rois: Sequence[RoiStatus]) -> list[int | None]:
    """The rounds there are, in order, test regions (None) last."""
    return sorted({r.round for r in rois}, key=lambda n: (n is None, n or 0))


def group_state(versions: Sequence[RoiStatus]) -> str:
    """One state for an image over the annotators who have it: complete only when every version is."""
    if any(v.problem for v in versions):
        return "problem"
    done = [v.state in (COMPLETE, DRAWN) for v in versions]
    if all(done):
        return COMPLETE
    if any(done) or any(v.state == IN_PROGRESS for v in versions):
        return IN_PROGRESS
    return NOT_STARTED


def graph_elements(
    rois: Sequence[RoiStatus], round_key: int | None, picture: Callable[[RoiStatus], str] | None = None
) -> tuple[list[dict], dict[str, list[str]]]:
    """Cytoscape elements (nodes with positions, then links) of round ``round_key`` (None: test regions), and the
    details shown when a node is clicked (lines of text, by node id). ``picture``: the picture URI of an image."""
    shown = [r for r in rois if r.round == round_key]
    groups: dict[str, list[RoiStatus]] = {}
    for roi in shown:  # one image: the same folder name in the same round, whoever has it
        groups.setdefault(roi.name, []).append(roi)
    # Order: by slide, then by the annotators who have it, so that links run as straight as possible.
    order = sorted(groups, key=lambda n: (groups[n][0].source or NO_SLIDE, sorted(v.annotator for v in groups[n]), n))
    # Images in a grid inside their area, a few per row, so that a round with many stays compact enough to read.
    per_row = 1 if len(order) <= 3 else 2 if len(order) <= 10 else 3
    roi_y = {name: (i // per_row) * ROI_GAP_Y for i, name in enumerate(order)}
    roi_x = {name: COLUMN_X["roi"] + (i % per_row - (per_row - 1) / 2) * ROI_GAP_X for i, name in enumerate(order)}

    nodes, edges, details = [], [], {}
    for name in order:
        versions = groups[name]
        node = f"roi:{name}"
        state = group_state(versions)
        classes = ["roi", state.replace(" ", "-")]
        if all(v.closed for v in versions):
            classes.append("closed")
        if len(versions) > 1:
            classes.append("shared")
        label = name if len(versions) == 1 else f"{name}  (shared ×{len(versions)})"
        data = {"id": node, "label": label, "parent": "area:roi"}
        if picture is not None:
            data["image"] = picture(versions[0])
        nodes.append({"data": data, "position": {"x": roi_x[name], "y": roi_y[name]}, "classes": " ".join(classes)})
        details[node] = [f"image {name}", f"slide: {versions[0].source or NO_SLIDE}"]
        for v in sorted(versions, key=lambda v: v.annotator):
            details[node].append(_version_line(v))
            if v.into_training:  # complete: what the annotator did to the proposal
                details[node].append(_corrections_line(v, shared=len(versions) > 1))

    for slide, names in _by(order, lambda n: groups[n][0].source or NO_SLIDE).items():
        node = f"slide:{slide}"
        nodes.append(_side_node(node, slide, "slide", [roi_y[n] for n in names]))
        edges += [{"data": {"id": f"{node}->{n}", "source": node, "target": f"roi:{n}"}} for n in names]
        details[node] = [f"slide {slide}", f"{len(names)} images in this round"]

    for annotator in sorted({r.annotator for r in shown}):
        theirs = [r for r in shown if r.annotator == annotator]
        node = f"annotator:{annotator}"
        done = sum(r.state in (COMPLETE, DRAWN) for r in theirs)
        label = f"{annotator}\n{done} of {len(theirs)} done"
        nodes.append(_side_node(node, label, "annotator", [roi_y[r.name] for r in theirs]))
        edges += [
            {"data": {"id": f"roi:{r.name}->{node}", "source": f"roi:{r.name}", "target": node}, "classes": _cls(r)}
            for r in theirs
        ]
        details[node] = [f"annotator {annotator}", f"{done} of {len(theirs)} images done"]
        details[node] += [_version_line(r, who=False) for r in theirs]
    _spread([n for n in nodes if "slide" in n["classes"]])
    _spread([n for n in nodes if "annotator" in n["classes"]])
    # Invisible points at the top and bottom of the image column in the two side areas: the three areas have the same
    # height, like columns, whatever the number of slides and annotators.
    top, bottom = min(roi_y.values(), default=0), max(roi_y.values(), default=0)
    for kind in ("slide", "annotator"):
        for end, y in (("top", top), ("bottom", bottom)):
            position = {"x": COLUMN_X[kind], "y": y}
            nodes.append({"data": {"id": f"spacer:{kind}:{end}", "parent": f"area:{kind}"}, "position": position})
            nodes[-1]["classes"] = "spacer"
    # The areas first: Cytoscape places a child in its parent, which must exist already.
    title = "test regions" if round_key is None else f"round {round_key}"
    areas = [
        {"data": {"id": f"area:{kind}", "label": f"{label}, {title}" if kind == "roi" else label}, "classes": "area"}
        for kind, label in AREAS.items()
    ]
    return areas + nodes + edges, details


def _corrections_line(roi: RoiStatus, shared: bool) -> str:
    """How a complete image's proposal was corrected: kept, edited and deleted as counts and % of the proposal's
    cells, and the cells drawn new."""
    proposal = roi.kept + roi.edited + roi.deleted
    if not proposal:
        return f"{'corrections ' + roi.annotator if shared else 'corrections'}: no proposal to compare with"

    def part(count):
        return f"{count} ({round(100 * count / proposal)} %)"

    head = f"corrections {roi.annotator}" if shared else "corrections"
    return (
        f"{head}: kept {part(roi.kept)}, edited {part(roi.edited)}, deleted {part(roi.deleted)}, "
        f"drawn new {roi.drawn}, of {proposal} proposed"
    )


def _version_line(roi: RoiStatus, who: bool = True) -> str:
    """One annotator's version of an image: state, cells, closed."""
    head = roi.annotator if who else roi.name
    if roi.problem:
        return f"{head}: cannot be read ({roi.problem})"
    parts = [roi.state, f"{roi.ok} of {roi.cells} cells checked" if roi.state == IN_PROGRESS else f"{roi.cells} cells"]
    if roi.closed:
        parts.append("closed")
    return f"{head}: {', '.join(parts)}"


def _cls(roi: RoiStatus) -> str:
    """The class of a link to an annotator: the state of that annotator's version."""
    return "problem" if roi.problem else ("complete" if roi.state in (COMPLETE, DRAWN) else roi.state).replace(" ", "-")


def _side_node(node: str, label: str, kind: str, ys: list[float]) -> dict:
    """A slide or annotator node, level with the middle of its images."""
    return {
        "data": {"id": node, "label": label, "parent": f"area:{kind}"},
        "position": {"x": COLUMN_X[kind], "y": sum(ys) / len(ys)},
        "classes": kind,
    }


def _spread(nodes: list[dict]) -> None:
    """Push nodes of one column apart (in their order) so that none overlap."""
    nodes.sort(key=lambda n: n["position"]["y"])
    for above, below in zip(nodes, nodes[1:], strict=False):
        below["position"]["y"] = max(below["position"]["y"], above["position"]["y"] + MIN_GAP_Y)


def _by(names: list[str], key: Callable[[str], str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for name in names:
        grouped.setdefault(key(name), []).append(name)
    return grouped
