"""Run one PyCG analysis in this interpreter (the child process of run.py).

    python -S -s -P -B evaluation/common/analyse.py REQUEST.json

REQUEST.json has `checkout` (a PyCG checkout, put first on sys.path),
`flavour` (a key of FLAVOURS), `entry_points`, `package` (the package root),
`graph` (where to write the call graph) and `result` (where to write the
status). The analysed sources are data: they are passed to PyCG
as paths, and nothing imports or runs them.

The call graph is `{caller: [callees]}`, sorted. The result is `{"status":
"ok"}` or `{"status": "crash", "error": ..., "where": ...}`, with `seconds`
(construction, analysis and output) and `peak_rss_mib` (peak resident set
size of this process).
"""

import json
import os
import resource
import sys
import time
import traceback
from pathlib import Path


# One adapter per API flavour: build the generator of a checkout. The
# checkout is on sys.path when an adapter runs.
def _original(entry_points, package):
    """The original analysis (the 2021 analysis, PyCG commit 046479e)."""
    from pycg import utils
    from pycg.pycg import CallGraphGenerator

    return CallGraphGenerator(entry_points, package, -1, utils.constants.CALL_GRAPH_OP)


def _new(entry_points, package):
    """The new engine."""
    from pycg.pycg import CallGraphGenerator

    return CallGraphGenerator(entry_points, package)


FLAVOURS = {"original": _original, "new": _new}


def _peak_rss_mib():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes, Linux kibibytes.
    return round(peak / (1 << 20 if sys.platform == "darwin" else 1 << 10), 1)


def _where(error, checkout):
    """Where a crash happened: the innermost frame in the checkout (relative
    to it), else the innermost frame."""
    frames = traceback.extract_tb(error.__traceback__)
    inside = [f for f in frames if f.filename.startswith(checkout + os.sep)]
    if not frames:
        return ""
    frame = (inside or frames)[-1]
    path = frame.filename
    if inside:
        path = os.path.relpath(path, checkout)
    return f"{path}:{frame.lineno} in {frame.name}"


def analyse(request):
    """Run the analysis of `request`; return the result and the graph (or None)."""
    checkout = os.path.abspath(request["checkout"])
    sys.path.insert(0, checkout)
    start = time.perf_counter()
    try:
        generator = FLAVOURS[request["flavour"]](
            request["entry_points"], request["package"]
        )
        generator.analyze()
        graph = {
            caller: sorted(set(callees))
            for caller, callees in sorted(generator.output().items())
        }
        result = {"status": "ok"}
    except (Exception, SystemExit) as error:  # a crash of the tool is a result
        graph = None
        message = str(error).splitlines()[0] if str(error) else ""
        result = {
            "status": "crash",
            "error": f"{type(error).__name__}: {message}"[:300],
            "where": _where(error, checkout),
        }
    result["seconds"] = round(time.perf_counter() - start, 3)
    result["peak_rss_mib"] = _peak_rss_mib()
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
