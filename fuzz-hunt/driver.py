import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

TREE = Path(sys.argv[1])
OUT = Path(sys.argv[2])
FIRST, LAST = int(sys.argv[3]), int(sys.argv[4])
SCALE = sys.argv[5]
JOBS = int(sys.argv[6])
TIMEOUT = 300

SCALES = {
    "ci": {},
    "large": {
        "MODULES_MAX": 9,
        "DEFINITIONS_PER_MODULE_MAX": 8,
        "IMPORTS_PER_MODULE_MAX": 5,
        "STATEMENTS_PER_BLOCK_MAX": 6,
        "BLOCK_DEPTH_MAX": 4,
        "EXPRESSION_DEPTH_MAX": 4,
        "METHODS_PER_CLASS_MAX": 7,
        "ARGUMENTS_PER_CALL_MAX": 4,
        "ELEMENTS_PER_CONTAINER_MAX": 4,
        "CASES_PER_MATCH_MAX": 4,
    },
}

RUN = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1] + "/tests")
sys.path.insert(0, sys.argv[1])
from pycg.analysis import solver
order = sys.argv[3]
if order == "lifo":
    solver.Solver.order = solver.LastInFirstOut()
elif order == "reversed":
    solver.Solver.order = solver.Reversed()
elif order.startswith("shuffled"):
    solver.Solver.order = solver.Shuffled(int(order[8:]))
from programs import analysed
from pycg.formats import dumps
print(dumps(analysed(Path(sys.argv[2]), {}).document()))
"""

VARIANTS = (("0", "fifo"), ("1", "fifo"), ("0", "lifo"), ("0", "reversed"))


def generate(seed):
    sys.path.insert(0, str(TREE / "tests"))
    import fuzz_programs

    for name, value in SCALES[SCALE].items():
        setattr(fuzz_programs, name, value)
    return fuzz_programs.program(seed)


def run(root, hash_seed, order):
    started = time.monotonic()
    try:
        done = subprocess.run(
            [sys.executable, "-c", RUN, str(TREE), str(root), order],
            env=dict(os.environ, PYTHONHASHSEED=hash_seed),
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return ("timeout", None, TIMEOUT)
    elapsed = time.monotonic() - started
    if done.returncode != 0:
        return ("crash", f"exit {done.returncode}\n" + done.stderr[-4000:], elapsed)
    return ("ok", done.stdout, elapsed)


def check(seed):
    files = generate(seed)
    with tempfile.TemporaryDirectory(dir="/tmp") as directory:
        root = Path(directory)
        for path, source in files.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source)
        variants = list(VARIANTS) + [("0", f"shuffled{seed}")]
        results = [(h, o, *run(root, h, o)) for h, o in variants]
    lines = sum(source.count("\n") for source in files.values())
    problems = []
    reference = None
    for hash_seed, order, status, text, _ in results:
        if status != "ok":
            problems.append({"variant": [hash_seed, order], "status": status,
                             "detail": text})
        elif reference is None:
            reference = (hash_seed, order, text)
        elif text != reference[2]:
            problems.append({"variant": [hash_seed, order], "status": "differs",
                             "from": reference[:2]})
    seconds = max(r[4] for r in results)
    return {"seed": seed, "scale": SCALE, "lines": lines, "seconds": round(seconds, 2),
            "problems": problems}


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(JOBS) as pool, OUT.open("a") as out:
        futures = [pool.submit(check, seed) for seed in range(FIRST, LAST + 1)]
        for future in as_completed(futures):
            out.write(json.dumps(future.result()) + "\n")
            out.flush()


main()
