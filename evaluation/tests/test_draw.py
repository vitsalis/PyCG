import importlib.util
import json
from pathlib import Path

import pytest

SELECTION = Path(__file__).resolve().parents[1] / "macro-benchmark" / "selection"
DRAW_PATH = SELECTION.parent / "draw.py"
_spec = importlib.util.spec_from_file_location("macro_draw", DRAW_PATH)
draw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(draw)


@pytest.mark.parametrize("number", [1, 2, 3, 6, 7])
def test_each_recorded_round_is_drawn_again_from_its_seed(
    tmp_path, monkeypatch, number
):
    log = json.loads((SELECTION / f"round-{number}.json").read_text(encoding="utf-8"))
    used_names_recorded_in_round_log = dict(log["used"])
    monkeypatch.setattr(
        draw, "used_names", lambda *args: used_names_recorded_in_round_log
    )
    drops = [f"--drop={entry['name']}={entry['reason']}" for entry in log["dropped"]]
    out = tmp_path / "round.json"
    argv = ["draw", "--round", str(number), "--out", str(out), *drops]
    assert draw.main(argv) == 0
    drawn = json.loads(out.read_text(encoding="utf-8"))
    assert drawn["seed"] == log["seed"]
    assert drawn["strata"] == log["strata"]
    assert drawn["selected"] == log["selected"]
    assert drawn["dropped"] == log["dropped"]
