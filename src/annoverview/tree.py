"""The shared folder read into one status per image, with annocell core only (no GUI): what the page shows.

Everything is read through ``annocell.folder`` (the tree walker ``rois``, ``read_review``, ``is_complete``,
``is_closed``), so the layout and the meaning of "complete" are AnnoCell's, the same as the pipeline's training.
Nothing is ever written.

No annotator is timed: when each one saved, started or finished an image is not read (AnnoLoop's rule of no
monitoring). What the page shows is per round: images by state, and how many go into training.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from annocell import folder as af

# State of an image, from what AnnoCell saved.
NOT_STARTED, IN_PROGRESS, COMPLETE = "not started", "in progress", "complete"
DRAWN = "drawn"  # a test region with cells: whether the expert has finished cannot be told from the files


@dataclass(frozen=True)
class RoiStatus:
    """One image folder (``annocell.folder.Roi``): who, which round (None for a test region), where, and how far
    the annotator got."""

    folder: Path
    annotator: str
    round: int | None
    name: str
    state: str
    closed: bool = False
    cells: int = 0
    # How the annotator changed the proposal (the review's counts): kept as proposed, edited, drawn new, deleted.
    kept: int = 0
    edited: int = 0
    drawn: int = 0
    deleted: int = 0
    ok: int = 0
    unreviewed: int = 0
    source: str | None = None  # the slide
    problem: str | None = None  # could not be read (e.g. half synced, or a newer folder format)

    @property
    def is_test(self) -> bool:
        return self.round is None

    @property
    def into_training(self) -> bool:
        """What the next training takes: a complete training image."""
        return not self.is_test and self.state == COMPLETE


def read_tree(root: str | Path) -> list[RoiStatus]:
    """Every image under ``root``, in the order of ``annocell.folder.rois`` (annotator, round, test last, name)."""
    return [_status(roi) for roi in af.rois(root)]


def _status(roi: af.Roi) -> RoiStatus:
    try:
        record = af.read_record(roi.folder)
    except (OSError, json.JSONDecodeError) as error:  # a record being written or synced right now
        return RoiStatus(roi.folder, roi.annotator, roi.round, roi.name, NOT_STARTED, problem=str(error))
    version = record.get("format_version", af.FORMAT_VERSION)
    if version > af.FORMAT_VERSION:  # a newer AnnoCell wrote it: update annocell rather than guess
        problem = f"folder format {version}, this AnnOverview reads up to {af.FORMAT_VERSION}"
        return RoiStatus(roi.folder, roi.annotator, roi.round, roi.name, NOT_STARTED, problem=problem)
    if version < af.FORMAT_VERSION:  # an older layout, which annocell no longer reads: shown, not miscounted
        problem = f"folder format {version}, older than {af.FORMAT_VERSION}: export it again"
        return RoiStatus(roi.folder, roi.annotator, roi.round, roi.name, NOT_STARTED, problem=problem)
    try:
        review = af.read_review(roi.folder)  # AnnoCell's review.json (empty if never saved)
    except (OSError, json.JSONDecodeError) as error:
        return RoiStatus(roi.folder, roi.annotator, roi.round, roi.name, NOT_STARTED, problem=str(error))
    if not review.get("saved_at"):
        state = NOT_STARTED  # never saved by AnnoCell
    elif roi.round is None:
        state = DRAWN if review.get("cells", 0) else NOT_STARTED
    else:
        state = COMPLETE if af.is_complete(review) else IN_PROGRESS
    return RoiStatus(
        roi.folder,
        roi.annotator,
        roi.round,
        roi.name,
        state,
        closed=af.is_closed(record),
        cells=review.get("cells", 0),
        ok=review.get(af.OK, 0),
        unreviewed=review.get(af.UNREVIEWED, 0),
        kept=review.get(af.PROPOSED, 0),
        edited=review.get(af.EDITED, 0),
        drawn=review.get(af.DRAWN, 0),
        deleted=review.get("deleted", 0),
        source=record.get("source"),
    )


def corrections(rois: Sequence[RoiStatus]) -> list[dict]:
    """Per round, over its complete training images: how much of the proposal the annotators kept, edited and
    deleted, and how many cells they drew new, as counts and as % of the proposal's cells. If the model improves,
    the kept share grows from round to round."""
    rows = []
    for number in sorted({r.round for r in rois if r.into_training}):
        done = [r for r in rois if r.round == number and r.into_training]
        counts = {k: sum(getattr(r, k) for r in done) for k in ("kept", "edited", "deleted", "drawn")}
        proposal = counts["kept"] + counts["edited"] + counts["deleted"]
        rows.append(
            {
                "round": number,
                "rois": len(done),
                "proposal": proposal,
                **counts,
                **{f"{k}_%": round(100 * v / proposal, 1) if proposal else None for k, v in counts.items()},
            }
        )
    return rows


def model_scores(root: str | Path) -> list[dict]:
    """Per model scored on the test regions (``annocell.folder.read_scores``): its round and its mean AP over the
    test regions, at each threshold, by round."""
    rows = []
    for score in af.read_scores(root):
        regions = score.get("regions") or []
        keys = sorted({k for r in regions for k in r if k.startswith("AP@")})
        means = {}
        for key in keys:
            values = [r[key] for r in regions if r.get(key) is not None]
            means[key] = round(sum(values) / len(values), 4) if values else None
        rows.append({"model": score.get("model"), "round": score.get("round", 0), "regions": len(regions), **means})
    return rows


def round_summary(rois: Sequence[RoiStatus]) -> list[dict]:
    """Per round: annotators, images by state, images going into training, cells checked, whether closed."""
    rows = []
    for number in sorted({r.round for r in rois if not r.is_test}):
        group = [r for r in rois if r.round == number]
        rows.append(
            {
                "round": number,
                "annotators": len({r.annotator for r in group}),
                "rois": len(group),
                NOT_STARTED: sum(r.state == NOT_STARTED for r in group),
                IN_PROGRESS: sum(r.state == IN_PROGRESS for r in group),
                COMPLETE: sum(r.state == COMPLETE for r in group),
                "into_training": sum(r.into_training for r in group),
                "cells": sum(r.cells for r in group),
                "checked": sum(r.ok for r in group),
                "closed": all(r.closed for r in group),
            }
        )
    return rows
