"""The shared folder read into ROI statuses, round summaries and the page's tree."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from annocell import folder as af

from annoverview.app import history_rows, roi_label, tree_nodes
from annoverview.tree import (
    COMPLETE,
    DRAWN,
    IN_PROGRESS,
    NOT_STARTED,
    ago,
    history,
    latest_saves,
    read_tree,
    round_summary,
)


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
    assert leaf["label"].startswith("exp201_b: in progress, 2 of 4 cells checked, started ")
    assert "closed" in leaf["label"]
    assert leaf["cls"] == "st-in-progress"
    by_round = tree_nodes(rois, "round", now)
    assert [n["label"].split(":")[0] for n in by_round] == ["round 1", "round 2", "test regions"]
    assert [n["label"].split(":")[0] for n in by_round[1]["children"]] == ["alice", "bob"]


def test_history_says_when_each_roi_was_started_and_finished(tree):
    rois = read_tree(tree)
    started = history(rois)
    assert len(started) == 7 and "exp201_d" not in {r.name for r in started}  # never saved: not started
    by_name = {r.name: r for r in rois}
    assert by_name["exp201_a"].completed_at and by_name["exp201_b"].completed_at is None
    assert by_name["exp201_b"].started_at <= by_name["exp201_b"].saved_at
    rows = {row["roi"]: row for row in history_rows(rois)}
    assert rows["exp201_a"]["finished"] and rows["exp201_b"]["finished"] == ""
    assert rows["exp201_a"]["state"] == "complete, closed" and rows["exp201_test"]["round"] == "test"
    assert "finished" in roi_label(by_name["exp201_a"], datetime.now())
    assert "started" in roi_label(by_name["exp201_b"], datetime.now())


def test_corrections_per_round_count_complete_rois_only(tmp_path):
    from annoverview.tree import RoiStatus, corrections

    def roi(round_number, state, kept, edited, deleted, drawn):
        return RoiStatus(
            tmp_path, "alice", round_number, f"r{kept}", state, kept=kept, edited=edited, deleted=deleted, drawn=drawn
        )

    rows = corrections(
        [
            roi(1, COMPLETE, 60, 20, 20, 5),
            roi(1, IN_PROGRESS, 1, 0, 99, 0),
            roi(2, COMPLETE, 90, 5, 5, 1),
            roi(None, DRAWN, 0, 0, 0, 30),
        ]
    )
    assert [r["round"] for r in rows] == [1, 2]  # unfinished ROIs and test regions left out
    assert (rows[0]["kept_%"], rows[0]["edited_%"], rows[0]["deleted_%"], rows[0]["drawn"]) == (60.0, 20.0, 20.0, 5)
    assert rows[1]["kept_%"] == 90.0 and rows[1]["proposal"] == 100


def test_model_scores_average_the_test_regions(tmp_path):
    from annoverview.tree import model_scores

    af.write_score(tmp_path, {"model": "m1", "round": 1, "regions": [{"AP@0.5": 0.6}, {"AP@0.5": 0.8}]})
    af.write_score(tmp_path, {"model": "cpsam", "round": 0, "regions": [{"AP@0.5": 0.5, "AP@0.75": None}]})
    rows = model_scores(tmp_path)
    assert [(r["model"], r["round"]) for r in rows] == [("cpsam", 0), ("m1", 1)]
    assert rows[1]["AP@0.5"] == 0.7 and rows[0]["AP@0.75"] is None


def test_progress_charts_have_one_bar_or_line_per_round():
    from annoverview.app import _corrections_chart, _scores_chart

    bars = _corrections_chart([{"round": 1, "kept_%": 60.0, "edited_%": 20.0, "deleted_%": 20.0}])
    assert [s["name"] for s in bars["series"]] == ["kept", "edited", "deleted"] and bars["xAxis"]["data"] == ["round 1"]
    lines = _scores_chart([{"round": 0, "AP@0.5": 0.5, "AP@0.75": 0.3}, {"round": 1, "AP@0.5": 0.6, "AP@0.75": None}])
    assert [s["name"] for s in lines["series"]] == ["AP@0.5", "AP@0.75"] and lines["series"][1]["data"] == [0.3, None]
