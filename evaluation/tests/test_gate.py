"""Behaviour tests for evaluation/common/gate.py: the values of a result
against the floors of metrics.json, the rule that floors only rise, and the
summary of a pull request. Small hand-made results; no run."""

import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "evaluation_gate", Path(__file__).resolve().parents[1] / "common" / "gate.py"
)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

METRICS = Path(__file__).resolve().parents[1] / "metrics.json"


def counts(precision, recall):
    return {"tp": 1, "fp": 0, "fn": 0, "precision": precision, "recall": recall}


def result(micro=(0.9, 0.8), inside=(0.7, 0.6), outside=(0.5, 0.4), failed=()):
    runs = {
        "macro/a": {"status": "ok", "seconds": 1.5, "peak_rss_mib": 40.0},
        "macro/b": {"status": "ok", "seconds": 0.5, "peak_rss_mib": 90.0},
    }
    return {
        "micro": {"total": {"raw": {"all": counts(*micro)}}},
        "macro": {
            "summed": {"raw": {"inside": counts(*inside), "outside": counts(*outside)}}
        },
        "macro_runs": {"runs": runs},
        "failed": list(failed),
    }


def metrics(**best):
    values = {
        "micro P": 0.9,
        "micro R": 0.8,
        "macro inside P": 0.7,
        "macro inside R": 0.6,
        "macro outside P": 0.5,
        "macro outside R": 0.4,
    }
    values.update({name.replace("_", " "): v for name, v in best.items()})
    return {"margin": 0.01, "best": values}


def write(path, data):
    path.write_text(json.dumps(data))
    return path


def test_the_committed_metrics_have_a_best_of_each_value_and_a_margin():
    data = json.loads(METRICS.read_text())
    assert set(data["best"]) == set(gate.VALUES)
    assert data["margin"] == 0.01


def test_a_value_on_its_floor_passes_and_one_below_it_fails():
    lines, failures = gate.check(result(inside=(0.69, 0.6)), metrics())
    assert failures == []
    assert any(line.startswith("macro inside P") for line in lines)
    _, failures = gate.check(result(inside=(0.6899, 0.6)), metrics())
    assert failures == ["macro inside P is 0.6899, below its floor 0.6900"]


def test_each_value_below_its_floor_is_named():
    low = result(micro=(0.5, 0.5), inside=(0.7, 0.6), outside=(0.1, 0.4))
    _, failures = gate.check(low, metrics())
    assert [f.split(" is ")[0] for f in failures] == [
        "micro P",
        "micro R",
        "macro outside P",
    ]


def test_a_failed_run_fails_the_gate():
    failed = [{"run": "macro/a", "status": "timeout"}]
    _, failures = gate.check(result(failed=failed), metrics())
    assert failures == ["the run macro/a failed: timeout"]


def test_a_value_without_edges_is_an_error():
    with pytest.raises(gate.GateError, match="micro P: no edges"):
        gate.measured(result(micro=(None, 0.8)))


def test_record_keeps_the_larger_of_the_base_and_the_measured_value():
    base = metrics(macro_inside_P=0.75)
    recorded = gate.recorded(base, gate.measured(result(micro=(0.95, 0.79))))
    assert recorded == metrics(micro_P=0.95, macro_inside_P=0.75)


def test_floors_only_rise():
    base = metrics()
    improved = result(micro=(0.95, 0.8))
    _, failures = gate.check(improved, metrics(micro_P=0.95), base)
    assert failures == []
    _, failures = gate.check(improved, metrics(), base)
    assert len(failures) == 1 and "run make eval-record" in failures[0]
    lowered = metrics(macro_inside_P=0.69)
    _, failures = gate.check(result(inside=(0.69, 0.6)), lowered, base)
    assert len(failures) == 1 and '"macro inside P": 0.7' in failures[0]


def test_the_command_exits_with_1_and_names_each_failure(tmp_path, capsys):
    path = write(tmp_path / "result.json", result(inside=(0.6, 0.6)))
    floors = write(tmp_path / "metrics.json", metrics())
    assert gate.main(["check", str(path), str(floors)]) == 1
    out = capsys.readouterr().out
    assert "gate failed:\n  macro inside P is 0.6000, below its floor 0.6900" in out
    assert "floors only rise: not checked (no base metrics)" in out


def test_an_empty_base_is_a_base_without_metrics(tmp_path, capsys):
    path = write(tmp_path / "result.json", result())
    floors = write(tmp_path / "metrics.json", metrics())
    empty = tmp_path / "base.json"
    empty.write_text("")
    assert gate.main(["check", str(path), str(floors), "--base", str(empty)]) == 0
    captured = capsys.readouterr()
    assert "the base has no metrics" in captured.err
    assert captured.out.endswith("gate passed\n")
    assert gate.main(["record", str(path), str(floors), "--base", str(empty)]) == 0
    assert json.loads(capsys.readouterr().out) == metrics()


def test_record_prints_the_new_metrics(tmp_path, capsys):
    path = write(tmp_path / "result.json", result(outside=(0.55, 0.3)))
    floors = write(tmp_path / "metrics.json", metrics())
    assert gate.main(["record", str(path), str(floors)]) == 0
    assert json.loads(capsys.readouterr().out) == metrics(macro_outside_P=0.55)


def test_the_summary_has_the_values_the_changes_and_the_runs(tmp_path):
    changes = tmp_path / "changes.txt"
    changes.write_text("a: +TP 1  -TP 0  +FP 0  -FP 0\n")
    lines = gate.summary(
        result(inside=(0.6, 0.6)), metrics(), result(inside=(0.71, 0.6)), changes
    )
    text = "\n".join(lines)
    assert "| macro inside P | 0.7100 | 0.6000 | 0.6900 | **fail** |" in text
    assert "| micro P | 0.9000 | 0.9000 | 0.8900 | pass |" in text
    assert "a: +TP 1  -TP 0  +FP 0  -FP 0" in text
    assert "| a | 1.5 | 1.5 | 40.0 | 40.0 |" in text
    assert "| total time, largest peak | 2.0 | 2.0 | 90.0 | 90.0 |" in text
