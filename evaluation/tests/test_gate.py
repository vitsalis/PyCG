"""Behaviour tests for evaluation/common/gate.py: the values of a result
against the floors of metrics.json, the rule that floors only rise on one
benchmark and are re-based on another, the digest of the benchmark, and the
summary of a pull request. Small hand-made results and trees; no run."""

import hashlib
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
DIGEST = "a" * 64
OTHER = "b" * 64


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


def metrics(digest=DIGEST, **best):
    values = {
        "micro P": 0.9,
        "micro R": 0.8,
        "macro inside P": 0.7,
        "macro inside R": 0.6,
        "macro outside P": 0.5,
        "macro outside R": 0.4,
    }
    values.update({name.replace("_", " "): v for name, v in best.items()})
    return {"margin": 0.01, "benchmark_sha256": digest, "best": values}


def write(path, data):
    path.write_text(json.dumps(data))
    return path


def test_the_committed_metrics_have_a_best_of_each_value_a_margin_and_a_digest():
    data = json.loads(METRICS.read_text())
    assert set(data["best"]) == set(gate.VALUES)
    assert data["margin"] == 0.01
    assert len(data["benchmark_sha256"]) == 64
    assert set(data["benchmark_sha256"]) <= set("0123456789abcdef")


def tree(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


BENCHMARK = {
    "evaluation/macro-benchmark/projects.toml": "[demo]\n[bare]\n",
    "evaluation/macro-benchmark/ground-truth/demo.json": "{}",
    "evaluation/macro-benchmark/ground-truth/demo.ledger": "notes",
    "evaluation/macro-benchmark/ground-truth/demo.added.json": "[]",
    "evaluation/macro-benchmark/ground-truth/gone.json": "{}",
    "evaluation/macro-benchmark/dynamic/demo.json": "{}",
    "evaluation/macro-benchmark/test-environments/demo.txt": "pytest==9\n",
    "evaluation/macro-benchmark/README.md": "rules",
    "evaluation/common/same_function.json": "{}",
    "micro-benchmark/snippets/args/call/main.py": "f()",
    "micro-benchmark/snippets/args/call/pkg/mod.py": "",
    "micro-benchmark/snippets/args/call/callgraph.json": "{}",
    "micro-benchmark/snippets/args/call/requires-python": "3.13",
    "micro-benchmark/snippets/args/call/README.md": "a call",
    "micro-benchmark/README.md": "cases",
}


def test_the_benchmark_is_the_files_that_a_measurement_reads(tmp_path):
    assert gate.benchmark_files(tree(tmp_path, BENCHMARK)) == [
        "evaluation/common/same_function.json",
        "evaluation/macro-benchmark/dynamic/demo.json",
        "evaluation/macro-benchmark/ground-truth/demo.json",
        "evaluation/macro-benchmark/projects.toml",
        "micro-benchmark/snippets/args/call/callgraph.json",
        "micro-benchmark/snippets/args/call/main.py",
        "micro-benchmark/snippets/args/call/pkg/mod.py",
        "micro-benchmark/snippets/args/call/requires-python",
    ]


def test_the_digest_is_that_of_the_sha256sum_listing(tmp_path):
    root = tree(tmp_path, BENCHMARK)
    listing = "".join(
        f"{hashlib.sha256((root / p).read_bytes()).hexdigest()}  {p}\n"
        for p in gate.benchmark_files(root)
    )
    assert gate.benchmark_digest(root) == hashlib.sha256(listing.encode()).hexdigest()


@pytest.mark.parametrize(
    "name",
    [
        "evaluation/macro-benchmark/projects.toml",
        "evaluation/macro-benchmark/ground-truth/demo.json",
        "evaluation/macro-benchmark/dynamic/demo.json",
        "evaluation/common/same_function.json",
        "micro-benchmark/snippets/args/call/main.py",
        "micro-benchmark/snippets/args/call/callgraph.json",
    ],
)
def test_a_change_of_a_file_of_the_benchmark_changes_the_digest(tmp_path, name):
    root = tree(tmp_path, BENCHMARK)
    before = gate.benchmark_digest(root)
    (root / name).write_text((root / name).read_text() + "\n")
    assert gate.benchmark_digest(root) != before


@pytest.mark.parametrize(
    "name",
    [
        "evaluation/macro-benchmark/ground-truth/demo.ledger",
        "evaluation/macro-benchmark/ground-truth/demo.added.json",
        "evaluation/macro-benchmark/ground-truth/gone.json",
        "evaluation/macro-benchmark/test-environments/demo.txt",
        "micro-benchmark/snippets/args/call/README.md",
    ],
)
def test_a_change_of_another_file_keeps_the_digest(tmp_path, name):
    root = tree(tmp_path, BENCHMARK)
    before = gate.benchmark_digest(root)
    (root / name).write_text("changed")
    assert gate.benchmark_digest(root) == before


def test_a_new_micro_case_or_project_truth_changes_the_digest(tmp_path):
    root = tree(tmp_path, BENCHMARK)
    before = gate.benchmark_digest(root)
    tree(root, {"evaluation/macro-benchmark/ground-truth/bare.json": "{}"})
    after_truth = gate.benchmark_digest(root)
    tree(root, {"micro-benchmark/snippets/args/new/main.py": ""})
    assert len({before, after_truth, gate.benchmark_digest(root)}) == 3


def test_a_value_on_its_floor_passes_and_one_below_it_fails():
    lines, failures = gate.check(result(inside=(0.69, 0.6)), metrics(), DIGEST)
    assert failures == []
    assert any(line.startswith("macro inside P") for line in lines)
    _, failures = gate.check(result(inside=(0.6899, 0.6)), metrics(), DIGEST)
    assert failures == ["macro inside P is 0.6899, below its floor 0.6900"]


def test_each_value_below_its_floor_is_named():
    low = result(micro=(0.5, 0.5), inside=(0.7, 0.6), outside=(0.1, 0.4))
    _, failures = gate.check(low, metrics(), DIGEST)
    assert [f.split(" is ")[0] for f in failures] == [
        "micro P",
        "micro R",
        "macro outside P",
    ]


def test_a_failed_run_fails_the_gate():
    failed = [{"run": "macro/a", "status": "timeout"}]
    _, failures = gate.check(result(failed=failed), metrics(), DIGEST)
    assert failures == ["the run macro/a failed: timeout"]


def test_a_value_without_edges_is_an_error():
    with pytest.raises(gate.GateError, match="micro P: no edges"):
        gate.measured(result(micro=(None, 0.8)))


def test_record_keeps_the_larger_of_the_base_and_the_measured_value():
    base = metrics(macro_inside_P=0.75)
    values = gate.measured(result(micro=(0.95, 0.79)))
    recorded = gate.recorded(base, values, DIGEST)
    assert recorded == metrics(micro_P=0.95, macro_inside_P=0.75)


def test_record_on_another_benchmark_takes_the_measured_values():
    base = metrics(OTHER, macro_inside_P=0.75)
    values = gate.measured(result(micro=(0.95, 0.79)))
    recorded = gate.recorded(base, values, DIGEST)
    assert recorded == metrics(micro_P=0.95, micro_R=0.79)


def test_a_base_without_a_digest_is_on_the_same_benchmark():
    base = metrics(macro_inside_P=0.75)
    del base["benchmark_sha256"]
    values = gate.measured(result(micro=(0.95, 0.79)))
    recorded = gate.recorded(base, values, DIGEST)
    assert recorded == metrics(micro_P=0.95, macro_inside_P=0.75)


def test_floors_only_rise_on_the_same_benchmark():
    base = metrics()
    improved = result(micro=(0.95, 0.8))
    lines, failures = gate.check(improved, metrics(micro_P=0.95), DIGEST, base)
    assert failures == []
    assert "benchmark unchanged: floors only rise" in lines
    _, failures = gate.check(improved, metrics(), DIGEST, base)
    assert len(failures) == 1 and "run make eval-record" in failures[0]
    lowered = metrics(macro_inside_P=0.69)
    _, failures = gate.check(result(inside=(0.69, 0.6)), lowered, DIGEST, base)
    assert len(failures) == 1 and '"macro inside P": 0.7' in failures[0]


def test_floors_are_re_based_on_a_changed_benchmark():
    base = metrics(OTHER)
    lower = result(inside=(0.6, 0.5))
    rebased = metrics(macro_inside_P=0.6, macro_inside_R=0.5)
    lines, failures = gate.check(lower, rebased, DIGEST, base)
    assert failures == []
    assert "benchmark changed: floors re-based" in lines
    kept = metrics(macro_inside_P=0.7, macro_inside_R=0.6)
    _, failures = gate.check(lower, kept, DIGEST, base)
    assert len(failures) == 3 and '"macro inside P": 0.6' in failures[-1]


def test_metrics_of_another_benchmark_fail_the_check():
    _, failures = gate.check(result(), metrics(OTHER), DIGEST)
    assert failures == [
        "evaluation/metrics.json was recorded on another benchmark "
        f"(benchmark_sha256 {OTHER}, this checkout's {DIGEST}): run make eval-record"
    ]
    _, failures = gate.check(result(), metrics(OTHER), DIGEST, metrics(OTHER))
    assert len(failures) == 2


def test_the_command_reads_the_digest_of_this_checkout(tmp_path, capsys):
    path = write(tmp_path / "result.json", result())
    floors = write(tmp_path / "metrics.json", metrics(gate.benchmark_digest()))
    assert gate.main(["check", str(path), str(floors)]) == 0
    assert capsys.readouterr().out.endswith("gate passed\n")
    stale = write(tmp_path / "stale.json", metrics(OTHER, micro_P=0.99))
    assert gate.main(["record", str(path), str(stale)]) == 0
    assert json.loads(capsys.readouterr().out) == metrics(gate.benchmark_digest())


def test_the_command_exits_with_1_and_names_each_failure(tmp_path, capsys):
    path = write(tmp_path / "result.json", result(inside=(0.6, 0.6)))
    floors = write(tmp_path / "metrics.json", metrics(gate.benchmark_digest()))
    assert gate.main(["check", str(path), str(floors)]) == 1
    out = capsys.readouterr().out
    assert "gate failed:\n  macro inside P is 0.6000, below its floor 0.6900" in out
    assert "floors only rise: not checked (no base metrics)" in out


def test_an_empty_base_is_a_base_without_metrics(tmp_path, capsys):
    path = write(tmp_path / "result.json", result())
    current = metrics(gate.benchmark_digest())
    floors = write(tmp_path / "metrics.json", current)
    empty = tmp_path / "base.json"
    empty.write_text("")
    assert gate.main(["check", str(path), str(floors), "--base", str(empty)]) == 0
    captured = capsys.readouterr()
    assert "the base has no metrics" in captured.err
    assert captured.out.endswith("gate passed\n")
    assert gate.main(["record", str(path), str(floors), "--base", str(empty)]) == 0
    assert json.loads(capsys.readouterr().out) == current


def test_record_prints_the_new_metrics(tmp_path, capsys):
    digest = gate.benchmark_digest()
    path = write(tmp_path / "result.json", result(outside=(0.55, 0.3)))
    floors = write(tmp_path / "metrics.json", metrics(digest))
    assert gate.main(["record", str(path), str(floors)]) == 0
    expected = metrics(digest, macro_outside_P=0.55)
    assert json.loads(capsys.readouterr().out) == expected


def test_the_summary_has_the_values_the_changes_and_the_runs(tmp_path):
    changes = tmp_path / "changes.txt"
    changes.write_text("a: +TP 1  -TP 0  +FP 0  -FP 0\n")
    lines = gate.summary(
        result(inside=(0.6, 0.6)),
        metrics(),
        result(inside=(0.71, 0.6)),
        changes,
        DIGEST,
        metrics(),
    )
    text = "\n".join(lines)
    assert "benchmark unchanged: floors only rise" in lines
    assert "| macro inside P | 0.7100 | 0.6000 | 0.6900 | **fail** |" in text
    assert "| micro P | 0.9000 | 0.9000 | 0.8900 | pass |" in text
    assert "a: +TP 1  -TP 0  +FP 0  -FP 0" in text
    assert "| a | 1.5 | 1.5 | 40.0 | 40.0 |" in text
    assert "| total time, largest peak | 2.0 | 2.0 | 90.0 | 90.0 |" in text


def test_the_summary_says_when_the_floors_were_re_based(tmp_path):
    changes = tmp_path / "changes.txt"
    changes.write_text("")
    args = (result(), metrics(), result(), changes, DIGEST)
    assert "benchmark changed: floors re-based" in gate.summary(*args, metrics(OTHER))
    without_base = gate.summary(*args)
    assert not any(line.startswith("benchmark") for line in without_base)
