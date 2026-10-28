"""The shared folder read into ROI statuses, round summaries and the page's tree."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from annocell import folder as af

from annoverview.app import tree_nodes
from annoverview.tree import COMPLETE, DRAWN, IN_PROGRESS, NOT_STARTED, ago, latest_saves, read_tree, round_summary


def test_read_tree_gives_every_roi_its_state(tree):
    rois = {(r.annotator, r.round, r.name): r for r in read_tree(tree)}
    assert len(rois) == 8
    a, b = rois["alice", 1, "exp201_a"], rois["alice", 1, "exp201_b"]
    assert a.state == COMPLETE and a.closed and a.into_training and a.cells == a.ok == 4
    assert b.state == IN_PROGRESS and b.closed and not b.into_training and (b.ok, b.unreviewed) == (2, 2)
    assert rois["bob", 2, "exp201_d"].state == NOT_STARTED and rois["bob", 2, "exp201_d"].saved_at is None
    test = rois["carla", None, "exp201_test"]
    assert test.state == DRAWN and test.cells == 3 and not test.into_training  # test regions never train
    assert rois["bob", 2, "exp305_c"].source == "slide_b"


def test_unreadable_and_newer_folders_are_flagged_not_guessed(tree):
    broken = tree / "bob" / "round_02" / "exp201_d" / af.RECORD
    broken.write_text("{ half synced")
    newer = tree / "alice" / "round_02" / "exp201_c"
    record = af.read_record(newer)
    af.write_record(newer, {**record, "format_version": af.FORMAT_VERSION + 1})
    rois = {r.name: r for r in read_tree(tree)}
    assert rois["exp201_d"].problem and rois["exp201_c"].problem.startswith("folder format")
    assert json.loads((tree / "alice" / "round_01" / "exp201_a" / af.RECORD).read_text())  # the rest still reads


def test_round_summary_counts_what_goes_into_training(tree):
    rounds = {row["round"]: row for row in round_summary(read_tree(tree))}
    assert set(rounds) == {1, 2}  # test regions are not a round
    one, two = rounds[1], rounds[2]
    assert (one["rois"], one[COMPLETE], one[IN_PROGRESS], one["into_training"], one["closed"]) == (3, 2, 1, 2, True)
    assert (two["annotators"], two[NOT_STARTED], two[IN_PROGRESS], two[COMPLETE], two["closed"]) == (2, 1, 2, 1, False)
    assert two["checked"] == 4 + 1 + 3


def test_latest_saves_and_ago(tree):
    latest = latest_saves(read_tree(tree))
    assert set(latest) == {"alice", "bob", "carla"} and latest["bob"].name in {"exp305_a", "exp305_c"}
    now = datetime(2026, 10, 28, 12, 0)
    assert ago(None, now) == "never" and ago(now - timedelta(seconds=20), now) == "just now"
    assert ago(now - timedelta(minutes=5), now) == "5 min ago" and ago(now - timedelta(hours=3), now) == "3 h ago"
    assert ago(now - timedelta(days=4), now) == "4 days ago"


def test_tree_nodes_by_annotator_and_by_round(tree):
    rois = read_tree(tree)
    now = datetime.now()
    by_annotator = tree_nodes(rois, "annotator", now)
    assert [n["label"] for n in by_annotator] == ["alice: 2 of 4 done", "bob: 1 of 3 done", "carla: 1 of 1 done"]
    alice = by_annotator[0]["children"]
    assert [n["label"] for n in alice] == ["round 1: 1 of 2 done, closed", "round 2: 1 of 2 done"]
    leaf = alice[0]["children"][1]
    assert leaf["label"].startswith("exp201_b: in progress, 2 of 4 cells checked, saved ") and "closed" in leaf["label"]
    assert leaf["cls"] == "text-amber-700"
    by_round = tree_nodes(rois, "round", now)
    assert [n["label"].split(":")[0] for n in by_round] == ["round 1", "round 2", "test regions"]
    assert [n["label"].split(":")[0] for n in by_round[1]["children"]] == ["alice", "bob"]
