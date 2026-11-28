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


def result(
    micro=(0.9, 0.8),
    inside=(0.7, 0.6),
    outside=(0.5, 0.4),
    without_open_sets=(0.6, 0.5),
    failed=(),
):
    runs = {
        "macro/a": {"status": "ok", "seconds": 1.5, "peak_rss_mib": 40.0},
        "macro/b": {"status": "ok", "seconds": 0.5, "peak_rss_mib": 90.0},
    }
    return {
        "micro": {"total": {"raw": {"all": counts(*micro)}}},
        "macro": {
            "summed": {"raw": {"inside": counts(*inside), "outside": counts(*outside)}},
            "without_open_sets": {
                "left_out": ["b"],
                "outside": {"raw": counts(*without_open_sets)},
            },
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
    "evaluation/micro-benchmark/snippets/args/call/main.py": "f()",
    "evaluation/micro-benchmark/snippets/args/call/pkg/mod.py": "",
    "evaluation/micro-benchmark/snippets/args/call/callgraph.json": "{}",
    "evaluation/micro-benchmark/snippets/args/call/requires-python": "3.13",
    "evaluation/micro-benchmark/snippets/args/call/README.md": "a call",
    "evaluation/micro-benchmark/README.md": "cases",
}


def test_the_benchmark_is_the_files_that_a_measurement_reads(tmp_path):
    assert gate.benchmark_files(tree(tmp_path, BENCHMARK)) == [
        "evaluation/common/same_function.json",
        "evaluation/macro-benchmark/dynamic/demo.json",
        "evaluation/macro-benchmark/ground-truth/demo.json",
        "evaluation/macro-benchmark/projects.toml",
        "evaluation/micro-benchmark/snippets/args/call/callgraph.json",
        "evaluation/micro-benchmark/snippets/args/call/main.py",
        "evaluation/micro-benchmark/snippets/args/call/pkg/mod.py",
        "evaluation/micro-benchmark/snippets/args/call/requires-python",
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
        "evaluation/micro-benchmark/snippets/args/call/main.py",
        "evaluation/micro-benchmark/snippets/args/call/callgraph.json",
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
        "evaluation/micro-benchmark/snippets/args/call/README.md",
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
    tree(root, {"evaluation/micro-benchmark/snippets/args/new/main.py": ""})
    assert len({before, after_truth, gate.benchmark_digest(root)}) == 3


def measurement(data=None, digest=DIGEST):
    return (result() if data is None else data), digest


def test_a_pr_equal_to_its_base_passes():
    lines, failures = gate.check(measurement(), measurement(), 0.01)
    assert failures == []
    assert (
        "benchmark unchanged: each floor is the base's value minus the margin" in lines
    )
    assert any(line.startswith("macro inside P") and "ok" in line for line in lines)


def test_a_value_on_the_base_minus_the_margin_passes_and_one_below_it_fails():
    _, failures = gate.check(
        measurement(result(inside=(0.69, 0.6))), measurement(), 0.01
    )
    assert failures == []
    low = measurement(result(inside=(0.6899, 0.6)))
    _, failures = gate.check(low, measurement(), 0.01)
    assert failures == ["macro inside P is 0.6899, below its floor 0.6900"]


def test_the_floors_come_from_the_base_and_the_margin():
    base = measurement(result(micro=(0.95, 0.8)))
    _, failures = gate.check(measurement(), base, 0.01)
    assert failures == ["micro P is 0.9000, below its floor 0.9400"]
    _, failures = gate.check(measurement(), base, 0.05)
    assert failures == []


def test_each_value_below_its_floor_is_named():
    low = result(micro=(0.5, 0.5), inside=(0.7, 0.6), outside=(0.1, 0.4))
    _, failures = gate.check(measurement(low), measurement(), 0.01)
    assert [f.split(" is ")[0] for f in failures] == [
        "micro P",
        "micro R",
        "macro outside P",
    ]


def test_a_failed_run_fails_the_gate():
    failed = [{"run": "macro/a", "status": "timeout"}]
    _, failures = gate.check(measurement(result(failed=failed)), measurement(), 0.01)
    assert failures == ["the run macro/a failed: timeout"]


def test_a_failed_run_of_the_base_does_not_fail_the_pr():
    failed = [{"run": "macro/a", "status": "timeout"}]
    _, failures = gate.check(measurement(), measurement(result(failed=failed)), 0.01)
    assert failures == []


def test_a_changed_benchmark_re_bases_the_floors():
    lower = measurement(result(inside=(0.6, 0.5)), DIGEST)
    lines, failures = gate.check(lower, measurement(digest=OTHER), 0.01)
    assert failures == []
    assert "benchmark changed: floors re-based" in lines
    assert any(
        line.startswith("macro inside P") and "re-based" in line for line in lines
    )


def test_a_failed_run_fails_the_gate_on_a_changed_benchmark():
    failed = [{"run": "micro/args/call", "status": "error"}]
    pr = measurement(result(failed=failed), DIGEST)
    _, failures = gate.check(pr, measurement(digest=OTHER), 0.01)
    assert failures == ["the run micro/args/call failed: error"]


def test_a_value_without_edges_is_an_error():
    with pytest.raises(gate.GateError, match="micro P: no edges"):
        gate.measured(result(micro=(None, 0.8)))


def test_record_keeps_the_larger_of_the_stored_and_the_measured_value():
    stored = metrics(macro_inside_P=0.75)
    values = gate.measured(result(micro=(0.95, 0.79)))
    recorded = gate.recorded(stored, values, DIGEST)
    assert recorded == metrics(micro_P=0.95, macro_inside_P=0.75)


def test_record_on_another_benchmark_takes_the_measured_values():
    stored = metrics(OTHER, macro_inside_P=0.75)
    values = gate.measured(result(micro=(0.95, 0.79)))
    recorded = gate.recorded(stored, values, DIGEST)
    assert recorded == metrics(micro_P=0.95, micro_R=0.79)


def test_metrics_without_a_digest_are_an_invalid_state():
    stored = metrics()
    del stored["benchmark_sha256"]
    with pytest.raises(AssertionError):
        gate.recorded(stored, gate.measured(result()), DIGEST)


def test_the_report_names_the_values_that_rose_and_what_record_writes():
    lines, failures = gate.report(measurement(result(micro=(0.95, 0.8))), metrics())
    text = "\n".join(lines)
    assert failures == []
    assert "| micro P | 0.9000 | 0.9500 | rose |" in text
    assert "| micro R | 0.8000 | 0.8000 | kept |" in text
    assert "A value rose" in text
    assert gate.dumps(metrics(micro_P=0.95)).rstrip("\n") in text


def test_the_report_says_when_the_metrics_are_up_to_date():
    lines, failures = gate.report(measurement(result(inside=(0.695, 0.6))), metrics())
    assert failures == []
    assert "No value rose: evaluation/metrics.json is up to date." in lines
    assert "| macro inside P | 0.7000 | 0.6950 | kept |" in lines


def test_the_report_fails_on_a_value_below_its_best_minus_the_margin():
    lines, failures = gate.report(measurement(result(inside=(0.6, 0.6))), metrics())
    assert failures == ["macro inside P is 0.6000, below its floor 0.6900"]
    assert "| macro inside P | 0.7000 | 0.6000 | **below its floor 0.6900** |" in lines


def test_the_report_on_a_changed_benchmark_re_bases_the_bests():
    low = measurement(result(inside=(0.6, 0.6)))
    lines, failures = gate.report(low, metrics(OTHER))
    text = "\n".join(lines)
    assert failures == []
    assert "| macro inside P | 0.7000 | 0.6000 | re-based |" in text
    assert "benchmark changed" in text
    assert gate.dumps(metrics(macro_inside_P=0.6)).rstrip("\n") in text


def test_the_report_gives_outside_without_open_sets_beside_and_does_not_gate_it():
    low = measurement(result(without_open_sets=(0.1, 0.2)))
    lines, failures = gate.report(low, metrics())
    assert failures == []
    assert "| macro outside R | 0.4000 | 0.4000 | kept |" in lines
    assert "| macro outside P without b | - | 0.1000 | not gated |" in lines
    assert "| macro outside R without b | - | 0.2000 | not gated |" in lines
    assert "No value rose: evaluation/metrics.json is up to date." in lines


def test_the_report_refuses_outside_without_open_sets_with_no_edges():
    empty = measurement(result(without_open_sets=(None, None)))
    with pytest.raises(gate.GateError, match="without b: no edges"):
        gate.report(empty, metrics())


def test_the_report_fails_on_a_failed_run():
    failed = [{"run": "macro/b", "status": "timeout"}]
    _, failures = gate.report(measurement(result(failed=failed)), metrics())
    assert failures == ["the run macro/b failed: timeout"]


def measured_into(directory, data, digest=DIGEST):
    directory.mkdir()
    write(directory / "result.json", data)
    (directory / "benchmark_sha256").write_text(digest + "\n")
    return str(directory)


def test_the_check_command_compares_the_pr_with_its_base(tmp_path, capsys):
    pr = measured_into(tmp_path / "pr", result())
    base = measured_into(tmp_path / "base", result())
    stored = str(write(tmp_path / "metrics.json", metrics(OTHER, micro_P=0.99)))
    assert gate.main(["check", pr, base, stored]) == 0
    assert capsys.readouterr().out.endswith("gate passed\n")
    low = measured_into(tmp_path / "low", result(inside=(0.6, 0.6)))
    assert gate.main(["check", low, base, stored]) == 1
    out = capsys.readouterr().out
    assert "gate failed:\n  macro inside P is 0.6000, below its floor 0.6900" in out


def test_the_check_command_re_bases_on_a_changed_benchmark(tmp_path, capsys):
    pr = measured_into(tmp_path / "pr", result(inside=(0.6, 0.6)))
    base = measured_into(tmp_path / "base", result(), OTHER)
    stored = str(write(tmp_path / "metrics.json", metrics()))
    assert gate.main(["check", pr, base, stored]) == 0
    out = capsys.readouterr().out
    assert "benchmark changed: floors re-based" in out
    assert out.endswith("gate passed\n")


def test_a_base_without_metrics_has_no_margin(tmp_path, capsys):
    pr = measured_into(tmp_path / "pr", result())
    base = measured_into(tmp_path / "base", result())
    empty = tmp_path / "base.json"
    empty.write_text("")
    assert gate.main(["check", pr, base, str(empty)]) == 1
    assert "the base has no metrics.json, so no margin" in capsys.readouterr().err


@pytest.mark.parametrize("digest", [None, "", "A" * 64, "a" * 63])
def test_a_result_without_a_valid_digest_is_an_error(tmp_path, capsys, digest):
    pr = tmp_path / "pr"
    pr.mkdir()
    write(pr / "result.json", result())
    if digest is not None:
        (pr / "benchmark_sha256").write_text(digest)
    stored = str(write(tmp_path / "metrics.json", metrics()))
    assert gate.main(["report", str(pr), stored]) == 1
    assert "benchmark_sha256" in capsys.readouterr().err


def test_the_digest_command_prints_the_digest_of_a_checkout(tmp_path, capsys):
    root = tree(tmp_path, BENCHMARK)
    assert gate.main(["digest", str(root)]) == 0
    assert capsys.readouterr().out == gate.benchmark_digest(root) + "\n"


def test_record_prints_the_new_metrics(tmp_path, capsys):
    path = measured_into(tmp_path / "pr", result(outside=(0.55, 0.3)))
    stored = str(write(tmp_path / "metrics.json", metrics()))
    assert gate.main(["record", path, stored]) == 0
    assert json.loads(capsys.readouterr().out) == metrics(macro_outside_P=0.55)


def test_the_report_command_exits_with_1_below_a_floor(tmp_path, capsys):
    path = measured_into(tmp_path / "pr", result(micro=(0.8, 0.8)))
    stored = str(write(tmp_path / "metrics.json", metrics()))
    assert gate.main(["report", path, stored]) == 1
    assert "gate failed:\n  micro P is 0.8000, below its floor 0.8900" in (
        capsys.readouterr().out
    )


def test_the_summary_has_the_values_the_changes_and_the_runs(tmp_path):
    changes = tmp_path / "changes.txt"
    changes.write_text("a: +TP 1  -TP 0  +FP 0  -FP 0\n")
    lines = gate.summary(
        measurement(result(inside=(0.6, 0.6))),
        measurement(result(inside=(0.71, 0.6))),
        0.01,
        changes,
    )
    text = "\n".join(lines)
    assert (
        "benchmark unchanged: each floor is the base's value minus the margin" in lines
    )
    assert "| macro inside P | 0.7100 | 0.6000 | 0.7000 | **fail** |" in text
    assert "| micro P | 0.9000 | 0.9000 | 0.8900 | pass |" in text
    assert "a: +TP 1  -TP 0  +FP 0  -FP 0" in text
    assert "| a | 1.5 | 1.5 | 40.0 | 40.0 |" in text
    assert "| total time, largest peak | 2.0 | 2.0 | 90.0 | 90.0 |" in text


def test_the_summary_says_when_the_floors_were_re_based(tmp_path):
    changes = tmp_path / "changes.txt"
    changes.write_text("")
    lines = gate.summary(measurement(), measurement(digest=OTHER), 0.01, changes)
    assert "benchmark changed: floors re-based" in lines
    assert "| micro P | 0.9000 | 0.9000 | - | re-based |" in lines
