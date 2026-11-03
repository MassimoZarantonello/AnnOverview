"""Pictures of the images for the graph: the visible channels (the proteins) in a multiplex palette (magenta, teal,
blue rather than plain red, green, blue), nothing drawn over them. The image's state is the frame of its node.

Drawing an image means reading its whole ``image.tif`` (all channels, tens to hundreds of MB for a whole image)
from the network drive, so every picture is cached on this computer. It depends only on the image and on which
channels are shown in which colours, so the annotator's saves never make it drawn again.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from annocell import folder as af

RENDER_VERSION = 6  # bump when the drawing changes: cached pictures are drawn again
SIZE_PX = 256  # sharp when zoomed in on a node
GAMMA = 0.75  # lifts dim structures: membranes and faint nuclei show
CACHE = Path.home() / ".cache" / "annoverview"
# The channels' napari colours (annotation.json) shown in a multiplex palette: red as magenta, green as teal.
CHANNEL_RGB = {"red": (1, 0.24, 0.78), "green": (0.16, 0.88, 0.69), "blue": (0.3, 0.42, 1)}
CHANNEL_RGB |= {"magenta": (1, 0.24, 0.78), "cyan": (0.2, 0.85, 1), "yellow": (1, 0.85, 0.2), "gray": (1, 1, 1)}


def thumbnail_uri(folder: str | Path) -> str:
    """The picture of the image in ``folder`` as a ``data:`` URI, from the cache when the image and its colours are
    the same."""
    folder = Path(folder)
    record = af.read_record(folder)
    shown = json.dumps([record.get("visible_channels"), record.get("colours")], sort_keys=True)
    stamp = (folder / af.IMAGE).stat().st_mtime_ns
    key = hashlib.sha1(f"{folder.resolve()}|{stamp}|{shown}|{SIZE_PX}|{RENDER_VERSION}".encode()).hexdigest()
    cached = CACHE / f"{key}.png"
    if not cached.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(render(folder))
    return "data:image/png;base64," + base64.b64encode(cached.read_bytes()).decode()


def render(folder: Path, size_px: int = SIZE_PX) -> bytes:
    """PNG bytes of the picture of the image in ``folder``: the visible channels, screen-blended (1 - product of 1 -
    channel: bright where any channel is, without clipping to flat white) in the multiplex palette."""
    from PIL import Image

    image, names = af.read_image(folder)
    record = af.read_record(folder)
    step = max(1, max(image.shape[1:]) // size_px)
    small = _mean_pool(image.astype(np.float32), step)  # averaged, not skipped: no aliasing, less noise
    visible = record.get("visible_channels") or names[:3]
    colours = record.get("colours") or {}
    defaults = iter(["red", "green", "blue"] * len(names))
    dark = np.ones((*small.shape[1:], 3), dtype=np.float32)
    for name, channel in zip(names, small, strict=True):
        colour = colours.get(name) or next(defaults)
        if name in visible:
            dark *= 1 - _scaled(channel)[..., None] * np.asarray(CHANNEL_RGB.get(colour, (1, 1, 1)), np.float32)
    buffer = io.BytesIO()
    Image.fromarray((np.clip(1 - dark, 0, 1) * 255).astype(np.uint8)).save(buffer, format="PNG")
    return buffer.getvalue()


def _scaled(channel: np.ndarray) -> np.ndarray:
    """``channel`` from 0 to 1 between its 1st and 99.7th percentiles, with ``GAMMA``."""
    low, high = np.percentile(channel, (1, 99.7))
    return np.clip((channel - low) / max(high - low, 1e-6), 0, 1) ** GAMMA


def _mean_pool(image: np.ndarray, step: int) -> np.ndarray:
    """(channels, y, x) averaged over ``step`` x ``step`` blocks (the last partial row and column dropped)."""
    c, h, w = image.shape
    h, w = h // step * step, w // step * step
    return image[:, :h, :w].reshape(c, h // step, step, w // step, step).mean(axis=(2, 4))
