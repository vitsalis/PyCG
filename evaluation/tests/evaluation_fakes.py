import importlib.util
import os
import sys
import time
from pathlib import Path

EVALUATION = Path(__file__).resolve().parents[1]


def load(name_under_evaluation):
    spec = importlib.util.spec_from_file_location(
        f"evaluation_{Path(name_under_evaluation).name}",
        EVALUATION / f"{name_under_evaluation}.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run = load("common/run")

FAKE_PROGRAM = """
import json, os, sys, time

arguments = sys.argv[1:]
package = arguments[arguments.index("--package") + 1]
output = arguments[arguments.index("-o") + 1]
entry_points = arguments[2:-2]
behaviour = open(os.path.join(package, "BEHAVIOUR")).read().strip()


def mark(name):
    path = os.path.join(package, name)
    with open(path + ".part", "w") as file:
        file.write(str(os.getpid()))
    os.rename(path + ".part", path)


if behaviour == "crash":
    print("pycg: internal error at crates/a.rs:1:2: a message", file=sys.stderr)
    sys.exit(101)
if behaviour == "not ported":
    print("pycg: not ported: outside attributes", file=sys.stderr)
    sys.exit(3)
if behaviour == "hang":
    mark("child.pid")
    time.sleep(60)
if behaviour == "fork-eat":
    if os.fork() == 0:
        mark("worker.pid")
        memory = b"x" * (400 << 20)
        time.sleep(60)
        os._exit(0)
    while not os.path.exists(os.path.join(package, "worker.pid")):
        time.sleep(0.05)
    time.sleep(60)
if behaviour == "eat":
    memory = b"x" * (400 << 20)
    time.sleep(60)
if behaviour == "die":
    with open(output, "w") as file:
        file.write("{")
    sys.exit(0)
if behaviour == "killed-by-the-machine":
    events = os.path.join(package, "memory.events")
    counts = dict(line.split() for line in open(events).read().splitlines())
    counts["oom_kill"] = str(int(counts["oom_kill"]) + 1)
    with open(events, "w") as file:
        file.writelines(f"{name} {value}\\n" for name, value in counts.items())
    time.sleep(1)
    os.kill(os.getpid(), 9)
seen = {
    "arguments": arguments,
    "environment": sorted(os.environ),
    "cwd": os.getcwd(),
    "found": [os.path.isfile(path) for path in entry_points],
}
with open(os.path.join(package, "seen.json"), "w") as file:
    json.dump(seen, file)
document = {
    "format": "pycg/1",
    "definitions": {
        "main": {"kind": "module", "module": "main", "lines": [1, 1]},
        "main.a": {"kind": "function", "module": "main", "lines": [1, 1]},
        "main.b": {"kind": "function", "module": "main", "lines": [1, 1]},
    },
    "outside": {"os.getcwd": {"known": "stub"}},
    "calls": {"main": [{"callees": ["os.getcwd", "main.b", "main.a"]}]},
}
with open(output, "w") as file:
    json.dump(document, file)
"""


def fake_checkout(tmp_path):
    checkout = tmp_path / "fake-pycg"
    program = checkout / "target" / "release" / "pycg"
    program.parent.mkdir(parents=True)
    program.write_text(f"#!{sys.executable} -I\n" + FAKE_PROGRAM)
    program.chmod(0o755)
    return checkout


def project(tmp_path, behaviour):
    directory = tmp_path / f"project-{behaviour}"
    directory.mkdir()
    (directory / "BEHAVIOUR").write_text(behaviour)
    source_that_leaves_a_file_when_run = (
        "open(__file__ + '.ran', 'w').close()\nimport os\n"
    )
    (directory / "main.py").write_text(source_that_leaves_a_file_when_run)
    return run.Job(f"micro/demo/{behaviour}", (directory / "main.py",), directory)


def tool(tmp_path):
    return run.Tool("fake", fake_checkout(tmp_path), sys.executable)


def process_ends_within_five_seconds(pid):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        killed_but_not_yet_reaped = run.resident_mib(pid) in (None, 0.0)
        if killed_but_not_yet_reaped:
            return True
        time.sleep(0.05)
    return False
