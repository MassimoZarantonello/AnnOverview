"""A fake shared folder in the AnnoCell layout, written as the pipeline and AnnoCell would."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pytest
from annocell import folder as af


def write_roi(
    root: Path, annotator: str, round_number: int | None, name: str, checked: int | None = None, source="slide_a"
) -> Path:
    """An ROI with 4 proposed cells (a test region: none); ``checked``: AnnoCell saved it with that many cells OK
    (None: never opened). Test regions: ``checked`` cells drawn."""
    test = round_number is None
    group = af.test_regions_folder(root, annotator) if test else af.round_folder(root, annotator, round_number)
    folder = group / name
    af.write_image(folder, np.zeros((1, 8, 8), dtype=np.uint16))
    start = np.zeros((8, 8), dtype=np.uint32)
    if not test:
        start[0:4, 0:4], start[0:4, 4:8], start[4:8, 0:4], start[4:8, 4:8] = 1, 2, 3, 4
        af.write_masks(folder, start, af.START)
    record = {"annotator": annotator, "image": name, "mode": "test" if test else "train", "source": source}
    record |= {"format_version": af.FORMAT_VERSION} | ({} if test else {"round": round_number})
    af.write_record(folder, record)
    if checked is not None:
        masks = start.copy()
        if test:
            masks[: 2 * checked, 0:2] = np.repeat(np.arange(1, checked + 1), 2)[:, None]
        cells = af.sync_cells({}, masks, start)
        for i in list(cells)[:checked]:
            cells[i].state = af.OK
        af.save(folder, masks, cells)
    return folder


def demo_tree(root: Path) -> Path:
    """Two rounds for alice and bob (round 1 closed), a test region for carla, two slides."""
    write_roi(root, "alice", 1, "exp201_a", checked=4)
    write_roi(root, "alice", 1, "exp201_b", checked=2)  # unfinished when the round was closed
    write_roi(root, "bob", 1, "exp305_a", checked=4, source="slide_b")
    for annotator in ("alice", "bob"):
        for folder in (root / annotator / "round_01").iterdir():
            af.close(folder, date(2026, 10, 20))
    write_roi(root, "alice", 2, "exp201_c", checked=4)
    write_roi(root, "alice", 2, "exp305_b", checked=1, source="slide_b")
    write_roi(root, "bob", 2, "exp201_d")
    write_roi(root, "bob", 2, "exp305_c", checked=3, source="slide_b")
    write_roi(root, "carla", None, "exp201_test", checked=3)
    return root


@pytest.fixture
def tree(tmp_path) -> Path:
    return demo_tree(tmp_path / "annotations")
