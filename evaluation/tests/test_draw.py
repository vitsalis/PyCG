import importlib.util
import json
from pathlib import Path

import pytest

SELECTION = Path(__file__).resolve().parents[1] / "macro-benchmark" / "selection"
DRAW_PATH = SELECTION.parent / "draw.py"
_spec = importlib.util.spec_from_file_location("macro_draw", DRAW_PATH)
draw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(draw)


@pytest.mark.parametrize("number", [1, 2, 3, 6, 7, 8, 9, 10])
def test_each_recorded_round_is_drawn_again_from_its_seed(
    tmp_path, monkeypatch, number
):
    log = json.loads((SELECTION / f"round-{number}.json").read_text(encoding="utf-8"))
    used_names_recorded_in_round_log = dict(log["used"])
    monkeypatch.setattr(
        draw, "used_names", lambda *args: used_names_recorded_in_round_log
    )
    drops = [f"--drop={entry['name']}={entry['reason']}" for entry in log["dropped"]]
    skips = [
        f"--skip-stratum={n}={r}" for n, r in log.get("skipped_strata", {}).items()
    ]
    out = tmp_path / "round.json"
    argv = ["draw", "--round", str(number), "--out", str(out), *drops, *skips]
    assert draw.main(argv) == 0
    drawn = json.loads(out.read_text(encoding="utf-8"))
    assert drawn["seed"] == log["seed"]
    assert drawn["strata"] == log["strata"]
    assert drawn["selected"] == log["selected"]
    assert drawn["dropped"] == log["dropped"]
    assert drawn == log


def draw_round_8(tmp_path, monkeypatch, *options):
    used = json.loads((SELECTION / "round-7.json").read_text(encoding="utf-8"))["used"]
    monkeypatch.setattr(draw, "used_names", lambda *args: dict(used))
    out = tmp_path / f"round-{len(list(tmp_path.iterdir()))}.json"
    status = draw.main(["draw", "--round", "8", "--out", str(out), *options])
    return status, (
        json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    )


def test_a_skipped_stratum_is_recorded_and_the_others_are_drawn_as_without_it(
    tmp_path, monkeypatch
):
    status, whole = draw_round_8(tmp_path, monkeypatch)
    assert status == 0 and "skipped_strata" not in whole
    reason = "exhausted: its one package left is touched"
    status, partial = draw_round_8(
        tmp_path, monkeypatch, "--skip-stratum", f"2={reason}"
    )
    assert status == 0
    assert partial["skipped_strata"] == {"2": reason}
    assert partial["complete"] is True
    skipped = partial["strata"][1]
    assert skipped["skipped"] == reason
    assert skipped["selected"] is None and skipped["examined"] == []
    assert skipped["members"] == whole["strata"][1]["members"]
    for number in (0, 2, 3, 4):
        assert partial["strata"][number] == whole["strata"][number]
    assert partial["selected"] == [
        s["selected"]["name"] for i, s in enumerate(whole["strata"]) if i != 1
    ]


def test_a_partial_round_draws_only_the_strata_that_are_not_skipped(
    tmp_path, monkeypatch
):
    options = []
    for number in (2, 4, 5):
        options += ["--skip-stratum", f"{number}=a partial round"]
    status, log = draw_round_8(tmp_path, monkeypatch, *options)
    assert status == 0
    assert [s["stratum"] for s in log["strata"] if s["selected"]] == [1, 3]
    assert len(log["selected"]) == 2


@pytest.mark.parametrize("value", ["2", "0=x", "6=x", "two=x", "2= ", "\u00b2=x"])
def test_a_skipped_stratum_needs_a_number_and_a_reason(tmp_path, monkeypatch, value):
    status, log = draw_round_8(tmp_path, monkeypatch, "--skip-stratum", value)
    assert status == 2 and log is None


def test_a_stratum_is_skipped_once_and_a_round_skips_not_every_stratum(
    tmp_path, monkeypatch
):
    twice = ["--skip-stratum", "2=a", "--skip-stratum", "2=b"]
    assert draw_round_8(tmp_path, monkeypatch, *twice) == (2, None)
    every = [x for n in range(1, 6) for x in ("--skip-stratum", f"{n}=x")]
    assert draw_round_8(tmp_path, monkeypatch, *every) == (2, None)


def test_a_round_without_a_project_left_in_an_unskipped_stratum_is_incomplete(
    tmp_path, monkeypatch
):
    frame = json.loads((SELECTION / "frame.json").read_text(encoding="utf-8"))
    every = {draw.normalise_pep503(p["name"]): "used: test" for p in frame["packages"]}
    monkeypatch.setattr(draw, "used_names", lambda *args: dict(every))
    out = tmp_path / "round.json"
    argv = ["draw", "--round", "8", "--out", str(out), "--skip-stratum", "2=x"]
    assert draw.main(argv) == 1
    log = json.loads(out.read_text(encoding="utf-8"))
    assert log["complete"] is False and log["selected"] == []
