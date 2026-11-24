#!/usr/bin/env python3
"""Run a PyCG checkout on the micro- and macro-benchmark; keep its call graphs.

    python -I evaluation/common/run.py --flavour original --checkout PATH --name NAME
    python -I evaluation/common/run.py --flavour new --checkout PATH --name NAME \\
        --benchmark macro --timeout 1800

Each analysis runs in its own child interpreter (`python -S -s -P -B
evaluation/common/analyse.py`: no `site` module, so no .pth file or sitecustomize
runs) with the checkout first on sys.path, a wall-clock limit and an
environment built from nothing but PYTHONHASHSEED (default 0): the original
analysis iterates over sets, and its result depends on the hash seed. The
analysed sources are data: their paths go to PyCG, which reads them;
nothing imports or runs them. `--flavour` selects the
API adapter of evaluation/common/analyse.py.

The jobs of a benchmark:
- micro: every case of micro-benchmark/snippets; the entry point is
  main.py, the package root the case directory. A case whose
  requires-python is newer than the interpreter is skipped.
- macro: every project of evaluation/macro-benchmark/projects.toml; the entry points
  are all modules of the analysed source, the package root is the
  project's `root`.

A checkout with changes (`git status --porcelain` not empty), or not under
git, is refused unless --allow-dirty: the recorded commit must say which code
ran.

Writes OUT/NAME/BENCHMARK/runs.json (the tool, the benchmark commit and, for
each job, its status: ok, crash with the error, timeout or skipped; wall
time and peak memory) and one graph per job that finished:
OUT/NAME/micro/<category>/<case>.json, OUT/NAME/macro/<project>.json. OUT is
$TMPDIR/pycg-evaluation by default, outside the repository.
"""

import argparse
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import NamedTuple

HERE = Path(__file__).resolve().parent
EVALUATION = HERE.parent
REPO = EVALUATION.parent
BENCHMARK = EVALUATION / "macro-benchmark"
ANALYSE = HERE / "analyse.py"
DEFAULT_OUT = Path(tempfile.gettempdir()) / "pycg-evaluation"
DEFAULT_TIMEOUT = 1800  # seconds per job: the one limit of every run


def load_sibling(name, path):
    """Load a script by path: neither evaluation/ nor macro-benchmark/ is a package."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


analyse = load_sibling("evaluation_analyse", ANALYSE)
projects = load_sibling("macro_projects", BENCHMARK / "projects.py")
SNIPPETS = projects.MICRO_BENCHMARK / "snippets"


class Tool(NamedTuple):
    name: str  # names the output directory and the results
    flavour: str  # a key of analyse.FLAVOURS
    checkout: Path
    python: str  # the interpreter of the child processes
    hash_seed: int = 0  # PYTHONHASHSEED of the child processes


class Job(NamedTuple):
    key: str  # "micro/<category>/<case>" or "<benchmark>/<project>"
    entry_points: tuple
    package: Path


def run_job(tool, job, graph_path, timeout, memory_limit_mib=None):
    """Analyse one job in a child process; return its run record.

    The child is killed past `timeout` seconds of wall time (status
    timeout) or, if `memory_limit_mib` is given, when a sample of its
    resident set size is over that limit (status memory).

    The child runs in a new temporary directory: every path that it gets is
    made absolute here. Directories (checkout, package root, the directory of
    each entry point) are resolved as the file system does (`link/..` is the
    parent of the link's target); a file keeps its name, a link included (a
    symbolic link b.py to a.py is the module b), and so does the interpreter
    (the interpreter of a virtual environment is a link)."""
    graph_path = Path(graph_path).resolve()  # the child runs elsewhere
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.unlink(missing_ok=True)  # no stale graph of an earlier run
    with tempfile.TemporaryDirectory(prefix="pycg-run-") as scratch:
        scratch = os.path.realpath(scratch)
        request = {
            "checkout": os.path.realpath(tool.checkout),
            "flavour": tool.flavour,
            "entry_points": [_real_directory(p) for p in job.entry_points],
            "package": os.path.realpath(job.package),
            "graph": str(graph_path),
            "result": os.path.join(scratch, "result.json"),
        }
        request_path = os.path.join(scratch, "request.json")
        Path(request_path).write_text(json.dumps(request), encoding="utf-8")
        # -S: no `site` module, so no .pth file and no sitecustomize runs (an
        # installed package that is the analysed target could); -s: no user
        # site-packages; -P: neither the script directory nor the working
        # directory on sys.path; -B: no bytecode in the checkout. Not -E: it
        # would drop PYTHONHASHSEED, the only variable of the environment.
        # analyse.py puts the checkout on sys.path itself.
        python = tool.python
        if os.sep in python:  # a path, not a name looked up on PATH
            python = _real_directory(python)
        command = [python, "-S", "-s", "-P", "-B", str(ANALYSE), request_path]
        start = time.perf_counter()
        # stderr goes to a file: a pipe that nobody reads while the parent
        # watches the child could fill and block it.
        with open(os.path.join(scratch, "stderr"), "w+", encoding="utf-8") as stderr:
            # A new session: the child leads a process group of its own,
            # which holds every process that it starts (unless one of them
            # starts a session of its own).
            child = subprocess.Popen(
                command,
                cwd=scratch,
                env={"PYTHONHASHSEED": str(tool.hash_seed)},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr,
                start_new_session=True,
            )
            unmeasured = cleanup = None
            try:
                killed, largest = _watch(child, timeout, memory_limit_mib)
            except MemoryUnmeasured as error:
                killed, largest, unmeasured = "unmeasured", None, error
            finally:  # also on an exception or an interrupt of the parent
                ended = time.perf_counter()  # the end seen, before the cleanup
                cleanup = _kill_group(child)
            wall = round(ended - start, 3)
            stderr.seek(0)
            error_lines = stderr.read().strip().splitlines()
        sampled = {} if largest is None else {"peak_rss_mib": largest}
        if cleanup:
            cause, detail = cleanup
            return {
                "status": "cleanup failed",
                "error": cause,
                "detail": detail,
                "wall_seconds": wall,
            }
        if killed == "timeout":
            return {"status": "timeout", "wall_seconds": timeout} | sampled
        if killed == "memory":
            return {"status": "memory", "wall_seconds": wall} | sampled
        if killed == "unmeasured":
            return {
                "status": "unmeasured",
                "error": unmeasured.cause,
                "detail": unmeasured.detail,
                "wall_seconds": wall,
            }
        result_path = Path(request["result"])
        if not result_path.exists():  # the child died before it could report
            tail = (error_lines or [""])[-1]
            return {
                "status": "crash",
                "error": f"exit status {child.returncode}: {tail}"[:300],
                "wall_seconds": wall,
            }
        record = json.loads(result_path.read_text(encoding="utf-8"))
    if largest is not None and largest > record["peak_rss_mib"]:
        record["peak_rss_mib"] = largest  # the group held more than the child
    record["wall_seconds"] = wall
    record["files"] = len(job.entry_points)
    return record


def _real_directory(path):
    """`path` with its directory resolved as the file system does and its
    file name kept: split first, so that `link/../a.py` is a.py in the
    parent of the link's target."""
    directory, name = os.path.split(os.fspath(path))
    return os.path.join(os.path.realpath(directory or "."), name)


# Seconds between two samples of the memory of a child under a limit.
WATCH_INTERVAL = 0.2
# The longest pause between two looks at whether the child has ended: the
# wall time of a run is measured to this resolution.
POLL_INTERVAL = 0.01


def _watch(child, timeout, memory_limit_mib):
    """Wait for the child, looking at whether it has ended at most
    POLL_INTERVAL seconds apart; stop past `timeout` seconds, or when a
    sample of the resident set size of its process group (the child and
    the processes it started), taken every WATCH_INTERVAL seconds, is over
    `memory_limit_mib`. Return why (None, "timeout" or "memory") and the
    largest sample in MiB (None without a memory limit). The caller kills
    the group."""
    start = time.monotonic()
    deadline = start + timeout
    largest = None
    next_sample = start  # the first sample at once
    pause = 0.001  # doubles up to POLL_INTERVAL
    while not _exited(child.pid):
        now = time.monotonic()
        if now >= deadline:
            return "timeout", largest
        if memory_limit_mib is not None and now >= next_sample:
            next_sample = now + WATCH_INTERVAL
            sample = group_resident_mib(child.pid)
            if sample is not None:
                largest = max(largest or 0, sample)
                if sample > memory_limit_mib:
                    return "memory", largest
        time.sleep(min(pause, deadline - now))
        pause = min(2 * pause, POLL_INTERVAL)
    return None, largest


# The si_code of a child that has ended (<sys/wait.h>): exited, killed, or
# killed with a core dump. macOS reports a stopped child too, though only
# ended ones are asked for.
_ENDED_CODES = (os.CLD_EXITED, os.CLD_KILLED, os.CLD_DUMPED)


def _exited(pid):
    """Whether the child `pid` has ended, without reaping it: until it is
    reaped, its pid, which is the id of its process group, cannot go to
    another process. A stopped child has not ended."""
    flags = os.WEXITED | os.WNOHANG | os.WNOWAIT
    if hasattr(os, "waitid"):
        result = os.waitid(os.P_PID, pid, flags)
        return result is not None and result.si_code in _ENDED_CODES
    # macOS before Python 3.13 has no os.waitid: the C function, whose
    # siginfo_t has si_code at byte 8 and si_pid at byte 12 (0 while the
    # child runs).
    import ctypes

    info = ctypes.create_string_buffer(128)
    if ctypes.CDLL(None, use_errno=True).waitid(os.P_PID, pid, info, flags) != 0:
        raise OSError(ctypes.get_errno(), "waitid")
    code, child = (int.from_bytes(info.raw[i : i + 4], sys.byteorder) for i in (8, 12))
    return child != 0 and code in _ENDED_CODES


KILL_WAIT = 5  # seconds for a child killed alone to end


def _kill_group(child):
    """Kill the process group that the child leads, then reap the child;
    return None, or why the group could not be killed. The child is not
    reaped before (_exited does not reap it), so the signal cannot reach a
    group that reuses its id. The other processes of the group are reaped
    by their new parent, not by this process.

    macOS refuses (EPERM) to signal a group that holds the ended, unreaped
    child alone: harmless when no member of the group is alive. Otherwise
    see _kill_members."""
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # the group is gone
    except PermissionError:
        failure = _kill_members(child)
        if failure:
            try:
                child.wait(timeout=KILL_WAIT)
            except subprocess.TimeoutExpired:
                pass
            return failure
    child.wait()
    return None


KILL_PASSES = 3  # lists and kills of the members of a group that was denied


def _kill_members(child):
    """After a denied group kill: list the live members of the group and
    send each SIGKILL, KILL_PASSES times (a member can start another), then
    list them once more. Return None if no member was alive, else (cause,
    detail): the signals sent and denied, the members gone and still alive.
    If the group cannot be listed, the child alone is killed."""
    sent, denied, left, unlisted = set(), set(), [], None
    try:
        for _ in range(KILL_PASSES):
            alive = _live_members(child.pid)
            if not alive:
                break
            for pid in alive:
                try:
                    os.kill(pid, signal.SIGKILL)
                    sent.add(pid)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    denied.add(pid)
            _wait_ended(alive)
        left = _live_members(child.pid)
    except MemoryUnmeasured as error:
        unlisted = error.detail
        child.kill()  # the child, at least; it is not reaped, so it is there
    if not (sent or denied or left or unlisted):
        return None
    detail = (
        f"signal sent to {len(sent)}, denied to {len(denied)}; "
        f"{len((sent | denied) - set(left))} gone, {len(left)} still alive"
    )
    if unlisted:
        detail += f"; the group could not be listed: {unlisted}"
    return "the process group could not be killed (EPERM)", detail


def _wait_ended(pids, seconds=1.0):
    """Wait a little for processes sent SIGKILL to end: it is not at once."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not all(_ended(pid) for pid in pids):
        time.sleep(0.01)


def _live_members(pgid):
    return [pid for pid in _group_pids(pgid) if not _ended(pid)]


def _ended(pid):
    """Whether a process has gone, or has ended and is not yet reaped."""
    if sys.platform.startswith("linux"):
        try:
            stat = Path(f"/proc/{pid}/stat").read_bytes()
        except (FileNotFoundError, ProcessLookupError):
            return True
        return stat[stat.rindex(b")") + 2 :].split()[0] == b"Z"  # the state
    size = _process_resident_mib(pid)
    if size is None:
        return not _there(pid)  # gone; one that cannot be read counts as alive
    return size == ENDED


def _there(pid):
    """Whether a process exists (an ended one that is not reaped included)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    return True


class MemoryUnmeasured(Exception):
    """The memory of a process group cannot be read: its run stops (status
    unmeasured), as an unread memory is not an empty one. `cause` is the
    same for every run; `detail` (a pid, a path) is not."""

    def __init__(self, cause, detail):
        super().__init__(f"{cause}: {detail}")
        self.cause, self.detail = cause, detail


PID_BUFFER = 4096  # the pids of a group read at once; grown while it is full


def group_resident_mib(pgid):
    """The sum of the resident set sizes of the processes of a process
    group, in MiB (rounded to 0.1), or None if every one has gone. Linux:
    the processes whose /proc/<pid>/stat names the group; macOS:
    proc_listpgrppids of libproc. Memory that two processes share (after a
    fork) counts in each. Raises MemoryUnmeasured if the group, or a process
    of it that is there, cannot be read."""
    sizes = [resident_mib(pid) for pid in _group_pids(pgid)]
    sizes = [size for size in sizes if size is not None]
    return round(sum(sizes), 1) if sizes else None


def _group_pids(pgid):
    if sys.platform.startswith("linux"):
        pids = []
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                stat = Path(f"/proc/{entry}/stat").read_bytes()
            except (FileNotFoundError, ProcessLookupError):
                continue  # gone
            except OSError as error:
                raise MemoryUnmeasured(
                    "the processes of the group cannot be listed",
                    f"/proc/{entry}/stat: {error}",
                ) from error
            if _linux_group(stat) == pgid:
                pids.append(int(entry))
        return pids
    if sys.platform == "darwin":
        import ctypes

        libproc, _, _ = _darwin_library()
        size = PID_BUFFER
        while True:
            buffer = (ctypes.c_int * size)()
            count = libproc.proc_listpgrppids(pgid, buffer, ctypes.sizeof(buffer))
            if count < 0:
                raise MemoryUnmeasured(
                    "the processes of the group cannot be listed",
                    f"group {pgid}: errno {ctypes.get_errno()}",
                )
            if count < size:
                return [pid for pid in buffer[:count] if pid]
            size *= 2  # full: there can be more
    raise NotImplementedError(f"no memory watchdog on {sys.platform}")


def _linux_group(stat):
    """The process group in /proc/<pid>/stat, as bytes: the third field
    after the name, which ends at the last ')' (a name is any bytes)."""
    return int(stat[stat.rindex(b")") + 2 :].split()[2])


def resident_mib(pid):
    """The resident set size of a process, in MiB (rounded to 0.1), or None
    if it has gone or ended (a zombie holds no memory). Raises
    MemoryUnmeasured if it is there and cannot be read."""
    size = _process_resident_mib(pid)
    if size == ENDED:
        return None
    if size is None:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return None  # gone
        except PermissionError:
            pass  # there
        raise MemoryUnmeasured(
            "a process of the group cannot be read", f"process {pid}"
        )
    return size


ENDED = "ended"  # a process that has ended and is not yet reaped


def _process_resident_mib(pid):
    """The resident set size of a process, ENDED for one that has ended (a
    zombie), or None if it cannot be read. Linux: /proc/<pid>/statm, all
    zeros for a zombie, whose memory is freed; macOS: proc_pid_rusage of
    libproc, which still reports a zombie's last resident size, so a
    process with an exit time is ENDED."""
    if sys.platform.startswith("linux"):
        try:
            pages = int(Path(f"/proc/{pid}/statm").read_bytes().split()[1])
        except (OSError, IndexError, ValueError):
            return None
        return round(pages * os.sysconf("SC_PAGE_SIZE") / (1 << 20), 1)
    if sys.platform == "darwin":
        return _darwin_resident_mib(pid)
    raise NotImplementedError(f"no memory watchdog on {sys.platform}")


# The fields of rusage_info_v2 (<sys/resource.h>) after its 16-byte UUID.
_RUSAGE_INFO_V2 = (
    "user_time",
    "system_time",
    "pkg_idle_wkups",
    "interrupt_wkups",
    "pageins",
    "wired_size",
    "resident_size",
    "phys_footprint",
    "proc_start_abstime",
    "proc_exit_abstime",
    "child_user_time",
    "child_system_time",
    "child_pkg_idle_wkups",
    "child_interrupt_wkups",
    "child_pageins",
    "child_elapsed_abstime",
    "diskio_bytesread",
    "diskio_byteswritten",
)
_darwin = None  # (libproc, the structure, byref), loaded on first use


def _darwin_library():
    global _darwin
    if _darwin is None:
        import ctypes
        import ctypes.util

        class Info(ctypes.Structure):
            _fields_ = [("uuid", ctypes.c_uint8 * 16)] + [
                (name, ctypes.c_uint64) for name in _RUSAGE_INFO_V2
            ]

        libproc = ctypes.CDLL(ctypes.util.find_library("proc"), use_errno=True)
        _darwin = (libproc, Info, ctypes.byref)
    return _darwin


def _darwin_resident_mib(pid):
    libproc, Info, byref = _darwin_library()
    info = Info()
    if libproc.proc_pid_rusage(pid, 2, byref(info)) != 0:  # 2: RUSAGE_INFO_V2
        return None
    if info.proc_exit_abstime:
        return ENDED
    return round(info.resident_size / (1 << 20), 1)


def python_version(python):
    """The version of an interpreter, as a tuple of ints."""
    done = subprocess.run(
        [python, "-I", "-S", "-c", "import sys; print(*sys.version_info[:3])"],
        capture_output=True,
        text=True,
        check=True,
    )
    return tuple(int(part) for part in done.stdout.split())


def micro_jobs(snippets=SNIPPETS, version=sys.version_info[:3]):
    """The jobs of the micro-benchmark, and the keys of the skipped cases.

    A case is skipped if its requires-python is newer than `version`."""
    jobs, skipped = [], []
    for case in sorted(p for p in snippets.glob("*/*") if p.is_dir()):
        key = f"micro/{case.parent.name}/{case.name}"
        required = case / "requires-python"
        if required.is_file():
            needed = tuple(int(p) for p in required.read_text().strip().split("."))
            if tuple(version) < needed:
                skipped.append(key)
                continue
        jobs.append(Job(key, (case / "main.py",), case))
    return jobs, skipped


def macro_jobs(config=None):
    """The jobs of the macro-benchmark, one per project of projects.toml, and
    the keys of the projects whose source is not there. Only
    macro-benchmark/projects.py is loaded (not the tracer, which needs
    Python 3.14), so that the runner works on Python 3.12 and later."""
    config = Path(config or projects.CONFIG_PATH)
    found = projects.load_projects(config)
    jobs, skipped = [], []
    for name, project in found.items():
        files = tuple(project.source_files())
        if not files:
            skipped.append(f"macro/{name}")
            continue
        jobs.append(Job(f"macro/{name}", files, project.root))
    return jobs, skipped


def git_version(path):
    """The commit of a checkout, its description and whether it has changes."""

    def git(*args):
        done = subprocess.run(
            [
                "git",
                "--no-replace-objects",
                "--no-optional-locks",
                "-C",
                str(path),
                *args,
            ],
            capture_output=True,
            text=True,
        )
        return done.stdout.strip() if done.returncode == 0 else None

    status = git("status", "--porcelain")
    return {
        "commit": git("rev-parse", "HEAD"),
        "describe": git("describe", "--tags", "--always"),
        "dirty": bool(status) if status is not None else None,
    }


class DirtyCheckout(Exception):
    """A tool checkout with changes, or not under git: its commit does not
    say which code ran."""


def graph_file(directory, key):
    """The graph file of a job; a key that leads outside `directory` (a
    project name with `..`) is a ValueError."""
    directory = Path(directory).resolve()
    path = (directory / f"{key}.json").resolve()
    if not path.is_relative_to(directory):
        raise ValueError(f"the graph of {key} would be outside {directory}")
    return path


def run(
    tool,
    benchmark,
    jobs,
    out,
    timeout,
    skipped=(),
    progress=print,
    allow_dirty=False,
    memory_limit_mib=None,
):
    """Run the jobs of one benchmark; write and return its runs.json, each
    job under `timeout` seconds and `memory_limit_mib` (None: no limit).

    Refuses (DirtyCheckout) a checkout whose `git status --porcelain` is not
    empty or that is not a git checkout, unless `allow_dirty`."""
    version = git_version(tool.checkout)
    if not allow_dirty and (version["dirty"] or version["commit"] is None):
        problem = "has changes" if version["commit"] else "is not a git checkout"
        raise DirtyCheckout(f"{tool.checkout} {problem}")
    tool_dir = Path(out).resolve() / tool.name
    runs = {key: {"status": "skipped"} for key in skipped}
    for job in jobs:
        graph_path = graph_file(tool_dir, job.key)
        record = run_job(tool, job, graph_path, timeout, memory_limit_mib)
        runs[job.key] = record
        if progress and not job.key.startswith("micro/"):
            progress(f"{tool.name} {job.key}: {_summary(record)}")
    if progress and benchmark == "micro":
        counts = {}
        for record in runs.values():
            counts[record["status"]] = counts.get(record["status"], 0) + 1
        progress(f"{tool.name} micro: {counts}")
    data = {
        "tool": {"name": tool.name, "flavour": tool.flavour, **version},
        "benchmark": {"name": benchmark, **git_version(REPO)},
        "python": ".".join(map(str, python_version(tool.python))),
        "hash_seed": tool.hash_seed,
        "timeout": timeout,
        "memory_limit_mib": memory_limit_mib,
        "runs": dict(sorted(runs.items())),
    }
    path = tool_dir / benchmark / "runs.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return data


def dumps(data, level=0):
    """JSON with each container of scalars on one line: deterministic, and
    one edge or one case per line in a diff."""
    values = data.values() if isinstance(data, dict) else data
    if not isinstance(data, (dict, list)) or not any(
        isinstance(v, (dict, list)) for v in values
    ):
        return json.dumps(data)
    pad = " " * (level + 1)
    if isinstance(data, dict):
        items = [
            f"{pad}{json.dumps(k)}: {dumps(v, level + 1)}" for k, v in data.items()
        ]
        return "{\n" + ",\n".join(items) + "\n" + " " * level + "}"
    items = [pad + dumps(v, level + 1) for v in data]
    return "[\n" + ",\n".join(items) + "\n" + " " * level + "]"


def _summary(record):
    if record["status"] == "ok":
        return f"ok, {record['seconds']} s, {record['peak_rss_mib']} MiB"
    return f"{record['status']} {record.get('error', '')}".rstrip()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--checkout", type=Path, required=True, help="a PyCG checkout")
    parser.add_argument(
        "--flavour", choices=sorted(analyse.FLAVOURS), required=True, help="its API"
    )
    parser.add_argument("--name", required=True, help="name of the results")
    parser.add_argument(
        "--benchmark",
        choices=["micro", "macro"],
        action="append",
        help="default: both",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--python", default=sys.executable, help="interpreter of the analyses"
    )
    parser.add_argument(
        "--hash-seed", type=int, default=0, help="PYTHONHASHSEED of the analyses"
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="run a checkout with changes, or not under git (recorded)",
    )
    args = parser.parse_args(argv)
    if not (args.checkout / "pycg").is_dir():
        parser.error(f"{args.checkout} has no pycg package")
    tool = Tool(
        args.name, args.flavour, args.checkout.resolve(), args.python, args.hash_seed
    )
    found = {}  # the jobs of every benchmark first: the pins before any run
    for benchmark in args.benchmark or ["micro", "macro"]:
        if benchmark == "micro":
            found[benchmark] = micro_jobs(version=python_version(args.python))
        else:
            found[benchmark] = macro_jobs()
    for benchmark, (jobs, skipped) in found.items():
        try:
            run(
                tool,
                benchmark,
                jobs,
                args.out,
                args.timeout,
                skipped,
                allow_dirty=args.allow_dirty,
            )
        except DirtyCheckout as error:
            parser.error(f"{error}; commit it, or pass --allow-dirty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
