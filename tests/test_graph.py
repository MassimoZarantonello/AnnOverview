"""The graph of a round (nodes, links, details) and the ROI pictures."""

from __future__ import annotations

from datetime import datetime

from annoverview.graph import COLUMN_X, graph_elements, round_keys
from annoverview.thumbs import render, thumbnail_uri
from annoverview.tree import read_tree
from conftest import write_roi


def test_graph_of_a_round_links_slides_rois_and_annotators(tree):
    write_roi(tree, "carla", 2, "exp201_c", checked=1)  # alice's ROI given to carla too: shared
    rois = read_tree(tree)
    assert round_keys(rois) == [1, 2, None]
    elements, details = graph_elements(rois, 2, datetime.now())
    nodes = {e["data"]["id"]: e for e in elements if "source" not in e["data"]}
    links = {(e["data"]["source"], e["data"]["target"]) for e in elements if "source" in e["data"]}
    rois_shown = {n for n in nodes if n.startswith("roi:")}
    assert rois_shown == {"roi:exp201_c", "roi:exp305_b", "roi:exp201_d", "roi:exp305_c"}
    shared = nodes["roi:exp201_c"]
    assert "shared" in shared["classes"] and "in-progress" in shared["classes"]  # complete for alice, not carla
    assert ("roi:exp201_c", "annotator:alice") in links and ("roi:exp201_c", "annotator:carla") in links
    assert ("slide:slide_b", "roi:exp305_b") in links
    assert {n["position"]["x"] for k, n in nodes.items() if k.startswith("annotator:")} == {COLUMN_X["annotator"]}
    assert {k for k in nodes if k.startswith("area:")} == {"area:slide", "area:roi", "area:annotator"}
    assert nodes["roi:exp201_c"]["data"]["parent"] == "area:roi"
    assert nodes["annotator:carla"]["data"]["parent"] == "area:annotator"
    assert details["roi:exp201_c"][2].startswith("alice: complete") and details["roi:exp201_c"][3].startswith("carla")
    closed = graph_elements(rois, 1, datetime.now())[0]
    closed_rois = [e for e in closed if e["data"]["id"].startswith("roi:") and "source" not in e["data"]]
    assert closed_rois and all("closed" in e["classes"] for e in closed_rois)


def test_pictures_are_drawn_and_cached(tree, tmp_path, monkeypatch):
    import annoverview.thumbs as thumbs

    monkeypatch.setattr(thumbs, "CACHE", tmp_path / "cache")
    folder = read_tree(tree)[0].folder
    assert render(folder).startswith(b"\x89PNG")
    uri = thumbnail_uri(folder)
    assert uri.startswith("data:image/png;base64,") and len(list((tmp_path / "cache").iterdir())) == 1
    assert thumbnail_uri(folder) == uri and len(list((tmp_path / "cache").iterdir())) == 1  # from the cache
