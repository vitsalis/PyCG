import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DESCRIPTION = """\
Runs pytest with ARGS in one process per CPU, each on a shard of the
collected tests (PYCG_TEST_SHARD, read by the root conftest.py: the tests
whose position in the collection order is the shard's index modulo the
number of shards). Prints the summary line of each shard, and the whole
output of each shard that fails. The exit status is 0 if every shard
passes, also where a shard is left with no test; else the status of the
first shard that fails.
"""

ROOT = Path(__file__).resolve().parents[1]
NO_TESTS_COLLECTED = 5


def shard(index, count, args):
    env = dict(os.environ, PYCG_TEST_SHARD=f"{index}/{count}")
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def main(args):
    if args[:1] in (["-h"], ["--help"]):
        print(DESCRIPTION)
        return 0
    count = os.cpu_count()
    with ThreadPoolExecutor(count) as pool:
        done = list(pool.map(lambda index: shard(index, count, args), range(count)))
    statuses = [result.returncode for result in done]
    for index, result in enumerate(done, 1):
        lines = result.stdout.strip().splitlines()
        print(f"shard {index}/{count}: {lines[-1] if lines else 'no output'}")
    for index, result in enumerate(done, 1):
        if result.returncode not in (0, NO_TESTS_COLLECTED):
            print(f"--- shard {index}/{count}\n{result.stdout}{result.stderr}")
    failed = [s for s in statuses if s not in (0, NO_TESTS_COLLECTED)]
    if failed:
        return failed[0]
    if all(s == NO_TESTS_COLLECTED for s in statuses):
        return NO_TESTS_COLLECTED
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
