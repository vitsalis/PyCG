#!/usr/bin/env python3
import argparse
import contextlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from pathlib import Path
from typing import NamedTuple

COMMON = Path(__file__).resolve().parent
EVALUATION = COMMON.parent
REPOSITORY = EVALUATION.parent
BENCHMARK = EVALUATION / "macro-benchmark"
ANALYSE = COMMON / "analyse.py"
OUT_DEFAULT = Path(tempfile.gettempdir()) / "pycg-evaluation"
TIMEOUT_SECONDS_DEFAULT = 1800
INTERPRETER_FLAGS_ISOLATED = ("-S", "-s", "-P", "-B")
DESCRIPTION = """Runs a PyCG checkout on the micro- and macro-benchmark and keeps its
call graphs in OUT/NAME/ (evaluation/README.md, "The runner").

    python -I evaluation/common/run.py --flavour original --checkout PATH --name NAME
    python -I evaluation/common/run.py --flavour new --checkout PATH --name NAME \\
        --benchmark macro --timeout 1800"""


def load_sibling(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


analyse = load_sibling("evaluation_analyse", ANALYSE)
projects = load_sibling("macro_projects", BENCHMARK / "projects.py")
SNIPPETS = projects.MICRO_BENCHMARK / "snippets"


class Tool(NamedTuple):
    name: str
    flavour: str
    checkout: Path
    python: str
    hash_seed: int = 0


class Job(NamedTuple):
    key: str
    entry_points: tuple
    package: Path


def run_job(tool, job, graph_path, timeout_seconds, memory_limit_mib=None):
    graph_path = Path(graph_path).resolve()
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="pycg-run-") as scratch:
        scratch = os.path.realpath(scratch)
        request = {
            "checkout": os.path.realpath(tool.checkout),
            "flavour": tool.flavour,
            "entry_points": [_path_with_real_directory(p) for p in job.entry_points],
            "package": os.path.realpath(job.package),
            "graph": str(graph_path),
            "result": os.path.join(scratch, "result.json"),
        }
        request_path = os.path.join(scratch, "request.json")
        Path(request_path).write_text(json.dumps(request), encoding="utf-8")
        python = tool.python
        python_is_path_not_name_on_path = os.sep in python
        if python_is_path_not_name_on_path:
            python = _path_with_real_directory(python)
        command = [python, *INTERPRETER_FLAGS_ISOLATED, str(ANALYSE), request_path]
        start = time.perf_counter()
        with open(os.path.join(scratch, "stderr"), "w+", encoding="utf-8") as stderr:
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
                with active(child):
                    killed, largest = _watch(child, timeout_seconds, memory_limit_mib)
            except MemoryUnmeasured as error:
                killed, largest, unmeasured = "unmeasured", None, error
            finally:
                end_seen_before_cleanup = time.perf_counter()
                cleanup = _kill_group(child)
            wall = round(end_seen_before_cleanup - start, 3)
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
            return {"status": "timeout", "wall_seconds": timeout_seconds} | sampled
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
        child_died_before_reporting = not result_path.exists()
        if child_died_before_reporting:
            tail = (error_lines or [""])[-1]
            return {
                "status": "crash",
                "error": f"exit status {child.returncode}: {tail}"[:300],
                "wall_seconds": wall,
            }
        record = json.loads(result_path.read_text(encoding="utf-8"))
    if largest is not None and largest > record["peak_rss_mib"]:
        record["peak_rss_mib"] = largest
    record["wall_seconds"] = wall
    record["files"] = len(job.entry_points)
    return record


def _path_with_real_directory(path):
    directory, name = os.path.split(os.fspath(path))
    return os.path.join(os.path.realpath(directory or "."), name)


MEMORY_SAMPLE_INTERVAL_SECONDS = 0.2
EXIT_POLL_PAUSE_SECONDS_MIN = 0.001
EXIT_POLL_PAUSE_SECONDS_MAX = 0.01


_active_children = set()
_active_children_lock = threading.Lock()


@contextlib.contextmanager
def active(child):
    with _active_children_lock:
        _active_children.add(child)
    try:
        yield child
    finally:
        with _active_children_lock:
            _active_children.discard(child)


def run_tasks(tasks, function, jobs):
    stop_starting_tasks = threading.Event()
    indexes_running = set()
    lock = threading.Lock()

    def task(index):
        with lock:
            indexes_running.add(index)
        try:
            return None if stop_starting_tasks.is_set() else function(tasks[index])
        finally:
            with lock:
                indexes_running.discard(index)

    pool = ThreadPoolExecutor(max_workers=jobs)
    futures = []
    try:
        for index in range(len(tasks)):
            futures.append(pool.submit(task, index))
        wait(futures, return_when=FIRST_EXCEPTION)
        for future in futures:
            if future.done() and future.exception() is not None:
                raise future.exception()
        return [future.result() for future in futures]
    except BaseException:
        stop_starting_tasks.set()
        pool.shutdown(wait=False, cancel_futures=True)
        while indexes_running:
            kill_active()
            time.sleep(0.05)
        raise
    finally:
        pool.shutdown()


def kill_active():
    with _active_children_lock:
        for child in _active_children:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


def _watch(child, timeout_seconds, memory_limit_mib):
    start = time.monotonic()
    deadline = start + timeout_seconds
    largest = None
    next_sample = start
    pause = EXIT_POLL_PAUSE_SECONDS_MIN
    while not _ended_without_reaping(child.pid):
        now = time.monotonic()
        if now >= deadline:
            return "timeout", largest
        if memory_limit_mib is not None and now >= next_sample:
            next_sample = now + MEMORY_SAMPLE_INTERVAL_SECONDS
            sample = group_resident_mib(child.pid)
            if sample is not None:
                largest = max(largest or 0, sample)
                if sample > memory_limit_mib:
                    return "memory", largest
        time.sleep(min(pause, deadline - now))
        pause = min(2 * pause, EXIT_POLL_PAUSE_SECONDS_MAX)
    return None, largest


_SI_CODES_OF_ENDED_CHILD = (os.CLD_EXITED, os.CLD_KILLED, os.CLD_DUMPED)
_SIGINFO_BUFFER_BYTES = 128
_SIGINFO_SI_CODE_OFFSET = 8
_SIGINFO_SI_PID_OFFSET = 12


def _ended_without_reaping(pid):
    flags = os.WEXITED | os.WNOHANG | os.WNOWAIT
    if hasattr(os, "waitid"):
        result = os.waitid(os.P_PID, pid, flags)
        return result is not None and result.si_code in _SI_CODES_OF_ENDED_CHILD
    import ctypes

    info = ctypes.create_string_buffer(_SIGINFO_BUFFER_BYTES)
    if ctypes.CDLL(None, use_errno=True).waitid(os.P_PID, pid, info, flags) != 0:
        raise OSError(ctypes.get_errno(), "waitid")
    code, child = (
        int.from_bytes(info.raw[offset : offset + 4], sys.byteorder)
        for offset in (_SIGINFO_SI_CODE_OFFSET, _SIGINFO_SI_PID_OFFSET)
    )
    return child != 0 and code in _SI_CODES_OF_ENDED_CHILD


KILL_WAIT_SECONDS = 5


def _kill_group(child):
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        failure = _kill_members(child)
        if failure:
            try:
                child.wait(timeout=KILL_WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                pass
            return failure
    child.wait()
    return None


KILL_MEMBERS_PASSES = 3


def _kill_members(child):
    sent, denied, left, unlisted = set(), set(), [], None
    try:
        for _ in range(KILL_MEMBERS_PASSES):
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
            _wait_until_ended(alive)
        left = _live_members(child.pid)
    except MemoryUnmeasured as error:
        unlisted = error.detail
        child.kill()
    if not (sent or denied or left or unlisted):
        return None
    detail = (
        f"signal sent to {len(sent)}, denied to {len(denied)}; "
        f"{len((sent | denied) - set(left))} gone, {len(left)} still alive"
    )
    if unlisted:
        detail += f"; the group could not be listed: {unlisted}"
    return "the process group could not be killed (EPERM)", detail


def _wait_until_ended(pids, timeout_seconds=1.0):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline and not all(_ended(pid) for pid in pids):
        time.sleep(0.01)


def _live_members(pgid):
    return [pid for pid in _group_pids(pgid) if not _ended(pid)]


def _ended(pid):
    if sys.platform.startswith("linux"):
        try:
            stat = Path(f"/proc/{pid}/stat").read_bytes()
        except (FileNotFoundError, ProcessLookupError):
            return True
        state = stat[stat.rindex(b")") + 2 :].split()[0]
        return state == b"Z"
    size = _process_resident_mib(pid)
    if size is None:
        return not _exists_ended_or_not(pid)
    return size == ENDED_NOT_REAPED


def _exists_ended_or_not(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    return True


class MemoryUnmeasured(Exception):
    def __init__(self, cause, detail):
        super().__init__(f"{cause}: {detail}")
        self.cause, self.detail = cause, detail


PID_BUFFER_COUNT_INITIAL = 4096


def group_resident_mib(pgid):
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
                continue
            except OSError as error:
                raise MemoryUnmeasured(
                    "the processes of the group cannot be listed",
                    f"/proc/{entry}/stat: {error}",
                ) from error
            if _process_group_of_linux_stat(stat) == pgid:
                pids.append(int(entry))
        return pids
    if sys.platform == "darwin":
        import ctypes

        libproc, _, _ = _darwin_library()
        size = PID_BUFFER_COUNT_INITIAL
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
            size *= 2
    raise NotImplementedError(f"no memory watchdog on {sys.platform}")


def _process_group_of_linux_stat(stat):
    return int(stat[stat.rindex(b")") + 2 :].split()[2])


def resident_mib(pid):
    size = _process_resident_mib(pid)
    if size == ENDED_NOT_REAPED:
        return None
    if size is None:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return None
        except PermissionError:
            pass
        raise MemoryUnmeasured(
            "a process of the group cannot be read", f"process {pid}"
        )
    return size


ENDED_NOT_REAPED = "ended"


def _process_resident_mib(pid):
    if sys.platform.startswith("linux"):
        try:
            pages = int(Path(f"/proc/{pid}/statm").read_bytes().split()[1])
        except (OSError, IndexError, ValueError):
            return None
        return round(pages * os.sysconf("SC_PAGE_SIZE") / (1 << 20), 1)
    if sys.platform == "darwin":
        return _darwin_resident_mib(pid)
    raise NotImplementedError(f"no memory watchdog on {sys.platform}")


_RUSAGE_INFO_V2 = 2
_RUSAGE_INFO_V2_FIELDS_AFTER_UUID = (
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
_darwin_libproc_info_byref = None


def _darwin_library():
    global _darwin_libproc_info_byref
    if _darwin_libproc_info_byref is None:
        import ctypes
        import ctypes.util

        class Info(ctypes.Structure):
            _fields_ = [("uuid", ctypes.c_uint8 * 16)] + [
                (name, ctypes.c_uint64) for name in _RUSAGE_INFO_V2_FIELDS_AFTER_UUID
            ]

        libproc = ctypes.CDLL(ctypes.util.find_library("proc"), use_errno=True)
        _darwin_libproc_info_byref = (libproc, Info, ctypes.byref)
    return _darwin_libproc_info_byref


def _darwin_resident_mib(pid):
    libproc, Info, byref = _darwin_library()
    info = Info()
    if libproc.proc_pid_rusage(pid, _RUSAGE_INFO_V2, byref(info)) != 0:
        return None
    if info.proc_exit_abstime:
        return ENDED_NOT_REAPED
    return round(info.resident_size / (1 << 20), 1)


def python_version(python):
    done = subprocess.run(
        [python, "-I", "-S", "-c", "import sys; print(*sys.version_info[:3])"],
        capture_output=True,
        text=True,
        check=True,
    )
    return tuple(int(part) for part in done.stdout.split())


def micro_jobs(snippets=SNIPPETS, version=sys.version_info[:3]):
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
    pass


def graph_file(directory, key):
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
    timeout_seconds,
    skipped=(),
    progress=print,
    allow_dirty=False,
    memory_limit_mib=None,
    workers=1,
):
    version = git_version(tool.checkout)
    if not allow_dirty and (version["dirty"] or version["commit"] is None):
        problem = "has changes" if version["commit"] else "is not a git checkout"
        raise DirtyCheckout(f"{tool.checkout} {problem}")
    tool_dir = Path(out).resolve() / tool.name
    runs = {key: {"status": "skipped"} for key in skipped}

    def one(job):
        graph_path = graph_file(tool_dir, job.key)
        record = run_job(tool, job, graph_path, timeout_seconds, memory_limit_mib)
        if progress and not job.key.startswith("micro/"):
            progress(f"{tool.name} {job.key}: {_summary(record)}")
        return record

    for job, record in zip(jobs, run_tasks(jobs, one, workers)):
        runs[job.key] = record
    if progress and benchmark == "micro":
        counts = {}
        for record in runs.values():
            counts[record["status"]] = counts.get(record["status"], 0) + 1
        progress(f"{tool.name} micro: {counts}")
    data = {
        "tool": {"name": tool.name, "flavour": tool.flavour, **version},
        "benchmark": {"name": benchmark, **git_version(REPOSITORY)},
        "python": ".".join(map(str, python_version(tool.python))),
        "hash_seed": tool.hash_seed,
        "timeout": timeout_seconds,
        "memory_limit_mib": memory_limit_mib,
        "workers": workers,
        "runs": dict(sorted(runs.items())),
    }
    path = tool_dir / benchmark / "runs.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return data


def dumps(data, level=0):
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
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--checkout", type=Path, required=True, help="a PyCG checkout")
    parser.add_argument(
        "--flavour",
        choices=sorted(analyse.GENERATOR_BY_FLAVOUR),
        required=True,
        help="its API",
    )
    parser.add_argument("--name", required=True, help="name of the results")
    parser.add_argument(
        "--benchmark",
        choices=["micro", "macro"],
        action="append",
        help="default: both",
    )
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument(
        "--timeout", type=float, default=TIMEOUT_SECONDS_DEFAULT, help="seconds per job"
    )
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
    jobs_and_skipped_by_benchmark = {}
    for benchmark in args.benchmark or ["micro", "macro"]:
        if benchmark == "micro":
            jobs_and_skipped_by_benchmark[benchmark] = micro_jobs(
                version=python_version(args.python)
            )
        else:
            jobs_and_skipped_by_benchmark[benchmark] = macro_jobs()
    for benchmark, (jobs, skipped) in jobs_and_skipped_by_benchmark.items():
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
