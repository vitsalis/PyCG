"""The recorded draw of batches 3 to 5 (macro-benchmark/selection/round-N.json)
is what macro-benchmark/draw.py draws again from the committed frame and
list, with the seed of each round. The draw reads files only: no network."""

import importlib.util
import json
from pathlib import Path

import pytest

SELECTION = Path(__file__).resolve().parents[1] / "macro-benchmark" / "selection"
DRAW_PATH = SELECTION.parent / "draw.py"
_spec = importlib.util.spec_from_file_location("macro_draw", DRAW_PATH)
draw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(draw)


@pytest.mark.parametrize("number", [1, 2, 3])
def test_each_recorded_round_is_drawn_again_from_its_seed(
    tmp_path, monkeypatch, number
):
    log = json.loads((SELECTION / f"round-{number}.json").read_text(encoding="utf-8"))
    # The benchmark directories that were used then are gone (one benchmark
    # now holds every batch): the round log's own record of them stands in.
    monkeypatch.setattr(draw, "used_names", lambda *args: dict(log["used"]))
    out = tmp_path / "round.json"
    assert draw.main(["draw", "--round", str(number), "--out", str(out)]) == 0
    drawn = json.loads(out.read_text(encoding="utf-8"))
    assert drawn["seed"] == log["seed"]
    assert drawn["strata"] == log["strata"]
    assert drawn["selected"] == log["selected"]
