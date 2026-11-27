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

FAKE_TOOL = """
import json, os, sys, time

class CallGraphGenerator:
    def __init__(self, entry_points, package, *rest):
        self.entry_points, self.package, self.rest = entry_points, package, rest

    def analyze(self):
        behaviour = open(os.path.join(self.package, "BEHAVIOUR")).read().strip()
        if behaviour == "crash":
            json.loads("{")  # raises in the standard library
        if behaviour == "hang":
            self.mark("child.pid")
            time.sleep(60)
        if behaviour == "fork-eat":
            # A worker process, as a tool that analyses each file in a new
            # process would start.
            if os.fork() == 0:
                self.mark("worker.pid")  # before it can be killed
                memory = b"x" * (400 << 20)  # noqa: F841
                time.sleep(60)
                os._exit(0)
            while not os.path.exists(os.path.join(self.package, "worker.pid")):
                time.sleep(0.05)
            time.sleep(60)
        if behaviour == "eat":
            memory = b"x" * (400 << 20)  # noqa: F841
            time.sleep(60)
        if behaviour == "die":
            os._exit(3)
        if behaviour == "killed-by-the-machine":
            # As the kernel's OOM killer of the machine does: the counter of
            # the cgroup rises and the process gets SIGKILL.
            events = os.path.join(self.package, "memory.events")
            counts = dict(line.split() for line in open(events).read().splitlines())
            counts["oom_kill"] = str(int(counts["oom_kill"]) + 1)
            with open(events, "w") as file:
                file.writelines(f"{name} {value}\\n" for name, value in counts.items())
            time.sleep(1)
            os.kill(os.getpid(), 9)

    def mark(self, name):
        # Write the id of this process to a file of the package, for the test.
        path = os.path.join(self.package, name)
        with open(path + ".part", "w") as file:
            file.write(str(os.getpid()))
        os.rename(path + ".part", path)

    def output(self):
        return {
            "main": {"main.b", "main.a"},
            "rest": set(map(str, self.rest)),
            "path": set(sys.path),
            "cwd": {os.getcwd()},
            "hash": {str(hash("seed"))},
            "environment": set(os.environ),
            "found": {str(os.path.isfile(p)) for p in self.entry_points},
        }
"""


FAKE_RUST_TOOL = """
import json, os, sys

arguments = sys.argv[1:]
package = arguments[arguments.index("--package") + 1]
output = arguments[arguments.index("-o") + 1]
behaviour = open(os.path.join(package, "BEHAVIOUR")).read().strip()
if behaviour == "not ported":
    print("pycg: the analysis is not ported yet", file=sys.stderr)
    sys.exit(1)
seen = {"arguments": arguments, "environment": sorted(os.environ), "cwd": os.getcwd()}
with open(os.path.join(package, "seen.json"), "w") as file:
    json.dump(seen, file)
document = {
    "format": "pycg/1",
    "definitions": {
        "main": {"kind": "module", "module": "main", "lines": [1, 1]},
        "main.a": {"kind": "function", "module": "main", "lines": [1, 1]},
    },
    "outside": {"os.getcwd": {"known": "stub"}},
    "calls": {"main": [{"callees": ["os.getcwd", "main.a"]}]},
}
with open(output, "w") as file:
    json.dump(document, file)
"""


def fake_checkout(tmp_path, original=False, rust=False):
    checkout = tmp_path / "fake-pycg"
    (checkout / "pycg").mkdir(parents=True)
    (checkout / "pycg" / "__init__.py").write_text("")
    (checkout / "pycg" / "pycg.py").write_text(FAKE_TOOL)
    if rust:
        formats = checkout / "pycg" / "formats"
        formats.mkdir()
        real_formats = EVALUATION.parent / "pycg" / "formats" / "__init__.py"
        (formats / "__init__.py").write_text(real_formats.read_text())
        binary = checkout / "target" / "release" / "pycg"
        binary.parent.mkdir(parents=True)
        binary.write_text(f"#!{sys.executable} -I\n" + FAKE_RUST_TOOL)
        binary.chmod(0o755)
    if original:
        (checkout / "pycg" / "utils").mkdir()
        (checkout / "pycg" / "utils" / "__init__.py").write_text(
            "from pycg.utils import constants\n"
        )
        (checkout / "pycg" / "utils" / "constants.py").write_text(
            'CALL_GRAPH_OP = "call-graph"\n'
        )
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


def tool(tmp_path, flavour="new"):
    checkout = fake_checkout(
        tmp_path, original=flavour == "original", rust=flavour == "rust"
    )
    return run.Tool("fake", flavour, checkout, sys.executable)


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
