import importlib.util
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

PROGRAM = Path("target") / "release" / "pycg"
DOCUMENT = "document.json"
EDGES = Path(__file__).resolve().parent / "edges.py"
RU_MAXRSS_UNITS_PER_MIB = 1 << 20 if sys.platform == "darwin" else 1 << 10


def load_edges():
    spec = importlib.util.spec_from_file_location("document_edges", EDGES)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.edges


edges = load_edges()


class ProgramExit(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def graph_of(request):
    program = Path(request["checkout"]) / PROGRAM
    document_path = Path(request["result"]).with_name(DOCUMENT)
    command = [
        str(program),
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
        raise ProgramExit(done.returncode, lines[-1] if lines else "")
    return edges(json.loads(document_path.read_text(encoding="utf-8")))


def peak_rss_mib_of_children():
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return round(peak / RU_MAXRSS_UNITS_PER_MIB, 1)


def analyse(request):
    start = time.perf_counter()
    try:
        output = graph_of(request)
        graph = {
            caller: sorted(set(callees)) for caller, callees in sorted(output.items())
        }
        result = {"status": "ok"}
    except ProgramExit as error:
        graph = None
        result = {
            "status": "crash",
            "error": str(error),
            "where": f"{PROGRAM} (exit {error.code})",
            "exit_status": error.code,
        }
    result["seconds"] = round(time.perf_counter() - start, 3)
    result["peak_rss_mib"] = peak_rss_mib_of_children()
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
