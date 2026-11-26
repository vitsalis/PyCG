import os
import subprocess
import sys
from pathlib import Path

import pytest
from fuzz_programs import program
from programs import write

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
HASH_SEEDS = ("0", "1")
SEEDS = range(8)
SLOW_SEEDS = range(8, 200)
ANALYSIS_SECONDS_MAX = 60
ANALYSE = """
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from programs import analysed
from pycg.formats import dumps

print(dumps(analysed(Path(sys.argv[2]), {}).document()))
"""


def report(seed, files):
    sources = (f"--- {path}\n{source}" for path, source in files.items())
    return f"seed {seed}\n" + "\n".join(sources)


def analyse(root, hash_seed):
    return subprocess.Popen(
        [sys.executable, "-c", ANALYSE, str(TESTS), str(root)],
        cwd=ROOT,
        env=dict(os.environ, PYTHONHASHSEED=hash_seed),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def document(process, seed, files):
    try:
        stdout, stderr = process.communicate(timeout=ANALYSIS_SECONDS_MAX)
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"the analysis ran past {ANALYSIS_SECONDS_MAX} s\n{report(seed, files)}"
        )
    assert process.returncode == 0, f"{stderr}\n{report(seed, files)}"
    return stdout


def check(tmp_path, seed):
    files = program(seed)
    write(tmp_path, files)
    processes = [analyse(tmp_path, hash_seed) for hash_seed in HASH_SEEDS]
    try:
        documents = [document(process, seed, files) for process in processes]
    finally:
        for process in processes:
            process.kill()
            process.wait()
    first, second = documents
    assert first == second, f"hash seeds {HASH_SEEDS} differ\n{report(seed, files)}"


@pytest.mark.parametrize("seed", SEEDS)
def test_generated_program_is_analysed_alike_under_every_hash_seed(tmp_path, seed):
    check(tmp_path, seed)


@pytest.mark.slow
@pytest.mark.parametrize("seed", SLOW_SEEDS)
def test_more_generated_programs_are_analysed_alike(tmp_path, seed):
    check(tmp_path, seed)
