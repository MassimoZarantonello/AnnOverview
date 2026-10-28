"""The shared folder read into one status per ROI, with annocell core only (no GUI): what the page shows.

Everything is read through ``annocell.folder`` (the tree walker ``rois``, ``is_complete``, ``is_closed``), so the
layout and the meaning of "complete" are AnnoCell's, the same as the pipeline's training. Nothing is ever written.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from annocell import folder as af

# State of an ROI, from what AnnoCell saved.
NOT_STARTED, IN_PROGRESS, COMPLETE = "not started", "in progress", "complete"
DRAWN = "drawn"  # a test region with cells: whether the expert has finished cannot be told from the files


@dataclass(frozen=True)
class RoiStatus:
    """One ROI folder: who, which round (None for a test region), where, and how far the annotator got."""

    folder: Path
    annotator: str
    round: int | None
    name: str
    state: str
    closed: bool = False
    cells: int = 0
    ok: int = 0
    unreviewed: int = 0
    saved_at: datetime | None = None
    started_at: datetime | None = None  # the annotator's first save (first change)
    completed_at: datetime | None = None  # when the last cell was checked; None while not complete
    source: str | None = None  # the slide
    problem: str | None = None  # could not be read (e.g. half synced, or a newer folder format)

    @property
    def is_test(self) -> bool:
        return self.round is None

    @property
    def into_training(self) -> bool:
        """What the next training takes: a complete training ROI."""
        return not self.is_test and self.state == COMPLETE


def read_tree(root: str | Path) -> list[RoiStatus]:
    """Every ROI under ``root``, in the order of ``annocell.folder.rois`` (annotator, round, test last, name)."""
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
    review = record.get("review") or {}
    if not review.get("saved_at"):
        state = NOT_STARTED  # never saved by AnnoCell
    elif roi.round is None:
        state = DRAWN if review.get("cells", 0) else NOT_STARTED
    else:
        state = COMPLETE if af.is_complete(record) else IN_PROGRESS
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
        saved_at=_moment(review.get("saved_at")),
        started_at=_moment(review.get("started_at")),
        completed_at=_moment(review.get("completed_at")),
        source=record.get("source"),
    )


def _moment(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def history(rois: Sequence[RoiStatus]) -> list[RoiStatus]:
    """The ROIs started so far, most recently started first: who worked on what, and when they finished."""
    return sorted((r for r in rois if r.started_at), key=lambda r: r.started_at, reverse=True)


def round_summary(rois: Sequence[RoiStatus]) -> list[dict]:
    """Per round: annotators, ROIs by state, ROIs going into training, cells checked, whether closed."""
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


def latest_saves(rois: Sequence[RoiStatus]) -> dict[str, RoiStatus]:
    """Per annotator, the ROI saved last: what they are working on (as of their last save, not live)."""
    latest = {}
    for roi in rois:
        if roi.saved_at and (roi.annotator not in latest or roi.saved_at > latest[roi.annotator].saved_at):
            latest[roi.annotator] = roi
    return latest


def ago(moment: datetime | None, now: datetime) -> str:
    """``moment`` as "5 min ago", "3 h ago", "2 days ago"; "never" for None."""
    if moment is None:
        return "never"
    minutes = int((now - moment).total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    if minutes < 48 * 60:
        return f"{minutes // 60} h ago"
    return f"{minutes // (24 * 60)} days ago"
