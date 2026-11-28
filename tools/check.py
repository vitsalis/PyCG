import argparse
import subprocess
import sys
import time
from pathlib import Path

DESCRIPTION = """\
The checks before pushing, scoped to what a change touches.

The change is the diff of the working tree, untracked files included,
against the merge base of REF (default origin/main) and HEAD. `lint` always
runs; `rust`, `tools`, `micro` and `evaluation` run when the change touches
one of their TRIGGERS outside their EXCLUDED. A check prints one line, its
name, `pass` or `FAIL` and its seconds, and the output of a failed check
follows. The exit status is 1 if a check failed. --full runs `make lint`
and `make test` whatever the change. A diff that cannot be read runs every
scoped check.

--detect-eval decides whether CI measures a pull request: it appends
`eval=true` or `eval=false` to OUTPUTS (the format of $GITHUB_OUTPUT) and
prints the reason as Markdown. It is true when the change touches
EVAL_PATHS outside EVAL_EXCLUDED, and when the diff cannot be read: the
evaluation builds the program from the crates and runs it with the harness
of evaluation/ and the Makefile.
"""

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_TEST = "evaluation/tests/test_benchmark_validator.py"
PYTEST = (sys.executable, "tools/test.py", "-q")
CHECKS = {
    "lint": ("make", "lint"),
    "rust": ("cargo", "test", "--locked"),
    "tools": (*PYTEST, "tools/tests", "-m", "not slow"),
    "micro": (*PYTEST, VALIDATOR_TEST),
    "evaluation": (*PYTEST, "evaluation/tests", "-m", "not slow"),
}
FULL = {"lint": ("make", "lint"), "test": ("make", "test")}
TRIGGERS = {
    "rust": (
        "crates/",
        "Cargo.toml",
        "Cargo.lock",
        "rust-toolchain.toml",
        "clippy.toml",
        "tests/cases/",
        "tests/known_failures.txt",
        "evaluation/micro-benchmark/snippets/",
    ),
    "tools": (
        "tools/",
        "tests/triage.py",
        "conftest.py",
        "pyproject.toml",
        "uv.lock",
    ),
    "micro": ("evaluation/micro-benchmark/", "conftest.py", VALIDATOR_TEST),
    "evaluation": (
        "evaluation/",
        "AGENTS.md",
        "conftest.py",
        "pyproject.toml",
        "uv.lock",
    ),
}
EXCLUDED = {
    "evaluation": (
        "evaluation/micro-benchmark/snippets/",
        "evaluation/micro-benchmark/README.md",
        VALIDATOR_TEST,
    ),
}
EVAL_PATHS = (
    "crates/",
    "Cargo.toml",
    "Cargo.lock",
    "rust-toolchain.toml",
    "evaluation/",
    "tools/",
    "tests/known_failures.txt",
    "Makefile",
    ".github/",
)
EVAL_EXCLUDED = ("tools/tests/", "tools/data/")


def under(path, patterns):
    return any(path.startswith(p) if p.endswith("/") else path == p for p in patterns)


def scoped(changed):
    names = ["lint"]
    for name, patterns in TRIGGERS.items():
        excluded = EXCLUDED.get(name, ())
        if any(under(p, patterns) and not under(p, excluded) for p in changed):
            names.append(name)
    return names


def git(*args):
    done = subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True
    )
    if done.returncode:
        return None
    return done.stdout.splitlines()


def changed_files(base):
    merge_base = git("merge-base", base, "HEAD")
    if not merge_base:
        return None
    diff = git("diff", "--no-renames", "--name-only", merge_base[0])
    untracked = git("ls-files", "--others", "--exclude-standard")
    if diff is None or untracked is None:
        return None
    return sorted(set(diff) | set(untracked))


def run(name, command):
    start = time.perf_counter()
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    seconds = time.perf_counter() - start
    verdict = "pass" if done.returncode == 0 else "FAIL"
    print(f"{name:12} {verdict:4} {seconds:6.1f} s", flush=True)
    if done.returncode:
        print(done.stdout + done.stderr, flush=True)
    return done.returncode == 0


def detect_eval(changed, base):
    if changed is None:
        return True, [f"### Evaluation: runs (the diff against {base} is unreadable)"]
    touched = [
        p for p in changed if under(p, EVAL_PATHS) and not under(p, EVAL_EXCLUDED)
    ]
    if touched:
        lines = [f"### Evaluation: runs ({len(touched)} changed paths can move it)"]
        return True, lines + [f"- `{path}`" for path in touched]
    paths = ", ".join(f"`{p}`" for p in EVAL_PATHS)
    excluded = ", ".join(f"`{p}`" for p in EVAL_EXCLUDED)
    return False, [
        f"### Evaluation: skipped (the diff touches none of {paths} outside {excluded})"
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base", default="origin/main", metavar="REF")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--detect-eval", type=Path, metavar="OUTPUTS")
    args = parser.parse_args(argv)
    if args.detect_eval:
        needed, lines = detect_eval(changed_files(args.base), args.base)
        with args.detect_eval.open("a", encoding="utf-8") as outputs:
            outputs.write(f"eval={str(needed).lower()}\n")
        print("\n".join(lines))
        return 0
    if args.full:
        checks = FULL
    else:
        changed = changed_files(args.base)
        if changed is None:
            print(f"the diff against {args.base} is unreadable: every check runs")
            names = list(CHECKS)
        else:
            names = scoped(changed)
        checks = {name: CHECKS[name] for name in names}
    results = [run(name, command) for name, command in checks.items()]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
