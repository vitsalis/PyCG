import json
import os
import resource
import subprocess
import sys
import time
import traceback
from pathlib import Path


def _generator_original_2021_engine(entry_points, package):
    from pycg import utils
    from pycg.pycg import CallGraphGenerator

    return CallGraphGenerator(entry_points, package, -1, utils.constants.CALL_GRAPH_OP)


def _generator_new_engine(entry_points, package):
    from pycg.pycg import CallGraphGenerator

    return CallGraphGenerator(entry_points, package)


GENERATOR_BY_FLAVOUR = {
    "original": _generator_original_2021_engine,
    "new": _generator_new_engine,
}
RUST = "rust"
FLAVOURS = (*GENERATOR_BY_FLAVOUR, RUST)
RUST_BINARY = Path("target") / "release" / "pycg"
RUST_DOCUMENT = "document.json"


class RustExit(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _rust_graph(request, checkout):
    binary = Path(checkout) / RUST_BINARY
    document_path = Path(request["result"]).with_name(RUST_DOCUMENT)
    command = [
        str(binary),
        "--package",
        request["package"],
        *request["entry_points"],
        "-o",
        str(document_path),
    ]
    done = subprocess.run(
        command,
        env={},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
    )
    if done.returncode != 0:
        lines = done.stderr.strip().splitlines()
        raise RustExit(done.returncode, lines[-1] if lines else "")
    from pycg.formats import edges

    return edges(json.loads(document_path.read_text(encoding="utf-8")))


RU_MAXRSS_UNITS_PER_MIB = 1 << 20 if sys.platform == "darwin" else 1 << 10


def _peak_rss_mib():
    if sys.platform.startswith("linux"):
        status = Path("/proc/self/status").read_text(encoding="utf-8")
        peaks = [
            line.split() for line in status.splitlines() if line.startswith("VmHWM:")
        ]
        assert len(peaks) == 1 and peaks[0][2] == "kB", peaks
        return round(int(peaks[0][1]) / (1 << 10), 1)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(peak / RU_MAXRSS_UNITS_PER_MIB, 1)


def _crash_location_innermost_in_checkout(error, checkout):
    frames = traceback.extract_tb(error.__traceback__)
    inside = [f for f in frames if f.filename.startswith(checkout + os.sep)]
    if not frames:
        return ""
    frame = (inside or frames)[-1]
    path = frame.filename
    if inside:
        path = os.path.relpath(path, checkout)
    return f"{path}:{frame.lineno} in {frame.name}"


def _python_graph(request):
    generator = GENERATOR_BY_FLAVOUR[request["flavour"]](
        request["entry_points"], request["package"]
    )
    generator.analyze()
    return generator.output()


def _peak_rss_mib_of_children():
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return round(peak / RU_MAXRSS_UNITS_PER_MIB, 1)


def analyse(request):
    checkout = os.path.abspath(request["checkout"])
    sys.path.insert(0, checkout)
    rust = request["flavour"] == RUST
    start = time.perf_counter()
    try:
        output = _rust_graph(request, checkout) if rust else _python_graph(request)
        graph = {
            caller: sorted(set(callees)) for caller, callees in sorted(output.items())
        }
        result = {"status": "ok"}
    except RustExit as error:
        graph = None
        result = {
            "status": "crash",
            "error": str(error),
            "where": f"{RUST_BINARY} (exit {error.code})",
            "exit_status": error.code,
        }
    except (Exception, SystemExit) as error:
        graph = None
        message = str(error).splitlines()[0] if str(error) else ""
        result = {
            "status": "crash",
            "error": f"{type(error).__name__}: {message}"[:300],
            "where": _crash_location_innermost_in_checkout(error, checkout),
        }
    result["seconds"] = round(time.perf_counter() - start, 3)
    result["peak_rss_mib"] = _peak_rss_mib_of_children() if rust else _peak_rss_mib()
    return result, graph


def main(argv):
    request = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    result, graph = analyse(request)
    if graph is not None:
        text = json.dumps(graph, indent=1, sort_keys=True) + "\n"
        Path(request["graph"]).write_text(text, encoding="utf-8")
    Path(request["result"]).write_text(json.dumps(result) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
