#!/usr/bin/env python3
import argparse
import builtins
import contextlib
import hashlib
import importlib.machinery
import importlib.metadata
import importlib.util
import inspect
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import sysconfig
import tempfile
import time
import traceback
import types
from pathlib import Path

DESCRIPTION = """Records the calls that a macro-benchmark package makes while its tests
run, into dynamic/PROJECT.json (evaluation/macro-benchmark/README.md,
"Traces").

    python evaluation/macro-benchmark/trace.py --python ENV/bin/python PROJECT"""
CHILD_ENTRY_ARGUMENT = "--child"
CHILD_INTERPRETER_FLAGS = ("-s", "-P", "-B")


def _load_sibling(name):
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"macro_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


projects = _load_sibling("projects")
BENCHMARK_DIR = projects.BENCHMARK_DIR
CONFIG_PATH = projects.CONFIG_PATH
Project = projects.Project
load_projects = projects.load_projects
_is_under = projects.is_under
VALIDATOR_PATH = projects.MICRO_BENCHMARK / "validate.py"
_MONITORING_TOOL_ID_STARTS = 3
assert _MONITORING_TOOL_ID_STARTS != sys.monitoring.PROFILER_ID
TIMEOUT_SECONDS_DEFAULT = 600
OUTCOMES_IN_SUMMARY_ORDER = (
    "passed",
    "failed",
    "errors",
    "skipped",
    "xfailed",
    "xpassed",
)
_BOUND_METHOD_TYPES = (
    types.MethodType,
    types.BuiltinMethodType,
    types.MethodWrapperType,
)
_UNBOUND_METHOD_TYPES = (
    types.FunctionType,
    types.MethodDescriptorType,
    types.WrapperDescriptorType,
)


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate = _load_validator()
_isinstance_static = validate._is_a
_TYPES_NAMED_AS_CLASS_ATTRIBUTE = (
    type,
    types.FunctionType,
    types.BuiltinFunctionType,
    *validate._DESCRIPTOR_TYPES,
)


class TraceError(Exception):
    pass


class MacroTracer(validate.Tracer):
    def __init__(self, project):
        super().__init__(str(project.root))
        self.project = project
        self.client_callback_edges_dropped = set()
        self.receiver_class_by_id = {}
        self.functions_started = set()
        self._recorded_names_by_target_id = {}
        self._is_client_by_filename = {}
        self._stdlib = {
            os.path.realpath(sysconfig.get_path(key))
            for key in ("stdlib", "platstdlib")
        }

    def in_snippet(self, filename):
        if filename not in self._snippet_files:
            self._snippet_files[filename] = self.project.in_scope(filename)
        return self._snippet_files[filename]

    def is_client(self, filename):
        if filename not in self._is_client_by_filename:
            self._is_client_by_filename[filename] = self._is_client_uncached(filename)
        return self._is_client_by_filename[filename]

    def _is_client_uncached(self, filename):
        is_frozen_module_or_exec_string = filename.startswith("<")
        if is_frozen_module_or_exec_string:
            return False
        path = os.path.realpath(filename)
        parts = Path(path).parts
        for n in range(len(parts) - 2, -1, -1):
            if parts[n] in ("site-packages", "dist-packages"):
                top_level_name = parts[n + 1].partition(".")[0]
                return top_level_name not in self.project.dependencies
        if any(_is_under(path, directory) for directory in self._stdlib):
            return False
        return not self.in_snippet(filename)

    def caller(self, frame):
        while frame is not None:
            entry = self._codes.get(id(frame.f_code))
            if entry is not None:
                return entry[0]
            if self.is_client(frame.f_code.co_filename):
                return None
            frame = frame.f_back
        return super().caller(None)

    def start(self):
        super().start()
        monitoring = sys.monitoring
        monitoring.use_tool_id(_MONITORING_TOOL_ID_STARTS, "pycg-macro-starts")
        monitoring.register_callback(
            _MONITORING_TOOL_ID_STARTS, monitoring.events.PY_START, self._on_started
        )
        monitoring.set_events(_MONITORING_TOOL_ID_STARTS, monitoring.events.PY_START)

    def stop(self):
        sys.monitoring.set_events(_MONITORING_TOOL_ID_STARTS, 0)
        sys.monitoring.free_tool_id(_MONITORING_TOOL_ID_STARTS)
        super().stop()

    def _on_started(self, code, offset):
        entry = self._codes.get(id(code))
        if entry is not None and entry[1] is not None:
            self.functions_started.add(entry[1])
        return sys.monitoring.DISABLE

    def on_call(self, code, offset, callee, arg0):
        if id(code) in self._codes:
            try:
                self._note_receiver(callee, arg0)
            except Exception:  # noqa: BLE001 - must not leak into the tests
                self.failures.append(traceback.format_exc())
        return super().on_call(code, offset, callee, arg0)

    def _note_receiver(self, callee, arg0):
        if _isinstance_static(callee, _BOUND_METHOD_TYPES):
            receiver = callee.__self__
            if receiver is None or _isinstance_static(receiver, types.ModuleType):
                return
        elif (
            _isinstance_static(callee, _UNBOUND_METHOD_TYPES)
            and arg0 is not sys.monitoring.MISSING
        ):
            receiver = arg0
            found = inspect.getattr_static(type(receiver), callee.__name__, None)
            is_method_of_receiver_type = (
                found is not None and validate._canonical(found) is callee
            )
            if not is_method_of_receiver_type:
                return
        else:
            return
        cls = receiver if _isinstance_static(receiver, type) else type(receiver)
        self.receiver_class_by_id[id(cls)] = cls

    def _record(self, caller, name, target):
        if target is not None:
            if self._defined_by_client(target):
                self.client_callback_edges_dropped.add((caller, name))
                return
            key = id(validate._canonical(target))
            self._recorded_names_by_target_id.setdefault(key, set()).add(name)
        super()._record(caller, name, target)

    def _defined_by_client(self, target):
        target = validate._canonical(target)
        if _isinstance_static(target, types.FunctionType):
            return self.is_client(target.__code__.co_filename)
        if _isinstance_static(target, type):
            filename = _module_file(sys.modules.get(target.__module__))
            return filename is not None and self.is_client(filename)
        return False

    def result(self):
        edges = {}
        executed, unknown = set(self.functions_started), set()
        for caller, callee in self.edges:
            executed.update({caller, callee} & self.functions)
            called_by_client = caller is None
            if called_by_client:
                continue
            if caller == validate.UNKNOWN_CALLER:
                unknown.add(callee)
                continue
            edges.setdefault(caller, set()).add(callee)
        names = {}
        for (caller, key), (target, _) in self.outside.items():
            if key not in names:
                recorded = self._recorded_names_by_target_id[key]
                names[key] = (target, _defining_name(target, recorded))
            edges.setdefault(caller, set()).add(names[key][1])
        aliases = {}
        for key, found in self._aliases(names).items():
            canonical = names[key][1]
            aliases.setdefault(canonical, set()).update(found - {canonical})
        return {
            "modules": sorted(self.modules),
            "functions": sorted(self.functions),
            "executed": sorted(executed),
            "dropped": {
                "client_callbacks": len(self.client_callback_edges_dropped),
                "unknown_caller": len(unknown),
            },
            "edges": {caller: sorted(edges[caller]) for caller in sorted(edges)},
            "aliases": {
                name: sorted(aliases[name]) for name in sorted(aliases) if aliases[name]
            },
        }

    def _aliases(self, names):
        found = {key: set(self._recorded_names_by_target_id[key]) for key in names}
        members = {
            t.__name__
            for t, _ in names.values()
            if _isinstance_static(t, _TYPES_NAMED_AS_CLASS_ATTRIBUTE)
        }
        inherited = self._named_classes()
        classes = []
        for module_name, module in list(sys.modules.items()):
            if not self._is_library_module(module_name, module):
                continue
            prefix = "<builtin>" if module_name == "builtins" else module_name
            namespace = _namespace(module)
            public = dict.get(namespace, "__all__")
            if _isinstance_static(public, (list, tuple)):
                attrs = [
                    a for a in public if _isinstance_static(a, str) and a in namespace
                ]
            else:
                attrs = [
                    a
                    for a in namespace
                    if _isinstance_static(a, str) and not _is_private(a)
                ]
            for attr in attrs:
                value = namespace[attr]
                _add_name_if_target(found, f"{prefix}.{attr}", value)
                if _isinstance_static(value, type):
                    classes.append((f"{prefix}.{attr}", value))
        for path, cls in classes:
            own = vars(cls)
            for attr in members:
                if attr not in own and id(cls) not in inherited:
                    continue
                try:
                    value = inspect.getattr_static(cls, attr)
                except AttributeError:
                    continue
                _add_name_if_target(found, f"{path}.{attr}", value)
        return found

    def _named_classes(self):
        roots = list(self.receiver_class_by_id.values())
        for name in self.modules:
            namespace = _namespace(sys.modules.get(name))
            if namespace is not None:
                roots += [
                    value
                    for value in list(namespace.values())
                    if _isinstance_static(value, type) and self._is_snippet_class(value)
                ]
        return {id(cls): cls for root in roots for cls in root.__mro__}

    def _is_library_module(self, name, module):
        if not _isinstance_static(module, types.ModuleType) or name == "__main__":
            return False
        if any(part.startswith("_") for part in name.split(".")):
            return False
        filename = _module_file(module)
        builtin_module_or_namespace_package = filename is None
        if builtin_module_or_namespace_package:
            return True
        return not self.in_snippet(filename) and not self.is_client(filename)


def _namespace(module):
    if not _isinstance_static(module, types.ModuleType):
        return None
    return object.__getattribute__(module, "__dict__")


def _module_file(module):
    namespace = _namespace(module)
    return None if namespace is None else dict.get(namespace, "__file__")


def _is_private(name):
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def _add_name_if_target(found, name, value):
    try:
        key = id(validate._canonical(value))
    except Exception:  # noqa: BLE001 - an attribute that is not a callable
        return
    if key in found:
        found[key].add(name)


def _defining_name(target, recorded):
    if _isinstance_static(target, types.FunctionType):
        return validate._function_name(target)
    if _isinstance_static(target, type):
        return validate._class_name(target)
    if _isinstance_static(target, types.BuiltinFunctionType):
        owner = target.__self__
        if owner is None or _isinstance_static(owner, types.ModuleType):
            if getattr(builtins, target.__name__, None) is target:
                return f"<builtin>.{target.__name__}"
            module = owner.__name__ if owner is not None else target.__module__
            return f"{module}.{target.__name__}"
        if _isinstance_static(owner, type):
            return f"{validate._class_name(owner)}.{target.__name__}"
    if _isinstance_static(target, validate._DESCRIPTOR_TYPES):
        return f"{validate._class_name(target.__objclass__)}.{target.__name__}"
    return min(recorded)


class _SessionRecorderPlugin:
    def __init__(self):
        self.counts = None
        self.failures = {"errors": [], "failed": []}
        self.rootdir = self.config = None

    def pytest_configure(self, config):
        self.rootdir, self.config = config.rootpath, config.inipath

    def pytest_sessionfinish(self, session):
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is None:
            return
        self.counts = {}
        for category, reports in reporter.stats.items():
            if category and category != "warnings":
                key = "errors" if category == "error" else category
                counted = [
                    r for r in reports if getattr(r, "count_towards_summary", True)
                ]
                self.counts[key] = len(counted)
                if key in self.failures:
                    self.failures[key] = sorted({r.nodeid for r in counted})

    def problems(self, project):
        found = []
        if self.counts is None:
            found.append("pytest ran without its terminal reporter: no test counts")
        if self.rootdir is None or Path(self.rootdir).resolve() != project.directory:
            found.append(f"pytest's rootdir is {self.rootdir}, not {project.directory}")
        expected = project.config.resolve() if project.config else Path(os.devnull)
        config = Path(self.config).resolve() if self.config else None
        if config != expected:
            found.append(f"pytest's configuration is {self.config}, not {expected}")
        return found

    def describe(self, project):
        return {
            "rootdir": _relative_if_inside(self.rootdir, project.directory),
            "config": _relative_if_inside(self.config, project.directory),
        }


def _relative_if_inside(path, directory):
    if path is None:
        return None
    path = Path(path).resolve()
    if path == directory or directory in path.parents:
        return path.relative_to(directory).as_posix()
    return str(path)


def _installed_version_by_distribution(project):
    found = {}
    for distribution in importlib.metadata.distributions():
        location = Path(distribution.locate_file("")).resolve()
        if location == project.directory or project.directory in location.parents:
            continue
        name = distribution.metadata["Name"]
        if name:
            found.setdefault(name, distribution.version)
    return dict(sorted(found.items()))


def _requirement_problems(requirements, distributions):
    installed = {_normalize(name): (name, v) for name, v in distributions.items()}
    problems = []
    for requirement in requirements:
        match = re.fullmatch(r"([A-Za-z0-9._-]+)(?:==(\S+))?", requirement)
        if match is None:
            problems.append(
                f"test requirement {requirement!r}: use name or name==version"
            )
            continue
        found = installed.get(_normalize(match[1]))
        if found is None:
            problems.append(f"{match[1]} is not installed")
        elif match[2] and found[1] != match[2]:
            problems.append(
                f"{found[0]} {found[1]} is installed, projects.toml pins {match[2]}"
            )
    return problems


def _normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def _write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _load_plugin(path):
    spec = importlib.util.spec_from_file_location(f"macro_plugin_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _not_importable_edges(project, edges):
    def inside(name):
        for package in project.not_importable:
            if name == package or name.startswith(package + "."):
                return package
        return None

    return [
        f"{caller} -> {callee}: an edge of {inside(caller) or inside(callee)}, "
        "which is in not_importable"
        for caller, callees in sorted(edges.items())
        for callee in sorted(callees)
        if inside(caller) or inside(callee)
    ]


def _run_child(config_path, name, out_path):
    project = load_projects(config_path)[name]
    benchmark = Path(config_path).resolve().parent
    sys.path.insert(0, str(project.root))
    distributions = _installed_version_by_distribution(project)
    errors = _requirement_problems(project.requirements, distributions)
    errors += [
        f"the variable {name} of the entry's environment is not {value!r}"
        for name, value in project.environment
        if os.environ.get(name) != value
    ]
    if errors:
        _write(out_path, {"errors": errors})
        return
    tracer = MacroTracer(project)
    session = _SessionRecorderPlugin()
    tracer.start()
    try:
        import pytest

        plugins = [_load_plugin(path) for path in project.plugins]
        status = pytest.main(project.pytest_command(), plugins=[session, *plugins])
    except BaseException:  # noqa: BLE001 - reported to the parent
        errors.append(f"pytest raised:\n{traceback.format_exc()}")
        status = None
    finally:
        tracer.stop()
    if status is not None and int(status) not in (0, 1):
        errors.append(f"pytest exit status {int(status)}")
    errors += session.problems(project)
    for package in project.package_names:
        if package in project.not_importable:
            continue
        filename = _module_file(sys.modules.get(package))
        if filename is None or not project.in_scope(filename):
            errors.append(f"{package} was not imported from {project.root}")
        elif package not in tracer.modules:
            errors.append(f"{package} was imported before the trace started")
    result = tracer.result()
    errors += _not_importable_edges(project, result["edges"])
    errors += [f"tracer error:\n{failure}" for failure in tracer.failures]
    _write(
        out_path,
        {
            "project": project.name,
            "commit": project.pin,
            "python": platform.python_version(),
            "distributions": distributions,
            "pytest": session.describe(project),
            "deselect": [dict(entry) for entry in project.deselect],
            "failures": session.failures,
            **(
                {
                    "plugins": [
                        _relative_if_inside(p, benchmark) for p in project.plugins
                    ]
                }
                if project.plugins
                else {}
            ),
            **(
                {"environment": dict(project.environment)}
                if project.environment
                else {}
            ),
            "tests": {
                "exit_status": None if status is None else int(status),
                **dict.fromkeys((*OUTCOMES_IN_SUMMARY_ORDER, "deselected"), 0),
                **(session.counts or {}),
            },
            **result,
            "errors": errors,
        },
    )


def _child_environment(python, scratch, extra=()):
    home, tmp = scratch / "home", scratch / "tmp"
    home.mkdir()
    tmp.mkdir()
    local = "127.0.0.1,localhost"
    environment = {
        "PATH": os.pathsep.join([str(Path(python).parent), "/usr/bin", "/bin"]),
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "LANG": "C.UTF-8",
        "PYTHONHASHSEED": "0",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "NO_PROXY": local,
        "no_proxy": local,
    }
    for name, value in extra:
        if name in environment:
            raise TraceError(
                f"the entry's environment sets {name}, which trace.py sets"
            )
        environment[name] = value
    return environment


def _run_in_process_group(command, cwd, env, timeout_seconds):
    proc = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + timeout_seconds
    try:
        while not os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT):
            if time.monotonic() > deadline:
                raise TraceError(
                    f"the test suite ran longer than {timeout_seconds:g} s"
                )
            time.sleep(0.1)
    finally:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
    return proc.returncode


def _snapshot(directory):
    found = {}
    for path in sorted(Path(directory).rglob("*")):
        key = path.relative_to(directory).as_posix()
        if path.is_symlink():
            found[key] = f"-> {os.readlink(path)}"
        elif path.is_dir():
            found[key] = "dir"
        else:
            found[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def _differences_as_git_status(before, after):
    lines = []
    for key in sorted(before.keys() | after.keys()):
        if key not in before:
            lines.append(f"?? {key}")
        elif key not in after:
            lines.append(f" D {key}")
        elif before[key] != after[key]:
            lines.append(f" M {key}")
    return "\n".join(lines)


def trace(
    project,
    python,
    benchmark_dir=BENCHMARK_DIR,
    timeout_seconds=TIMEOUT_SECONDS_DEFAULT,
):
    config_path = Path(benchmark_dir) / "projects.toml"
    if not project.pytest_args:
        raise TraceError("no test run in projects.toml (no pytest_args)")
    if not project.directory.is_dir():
        raise TraceError(f"{project.directory} does not exist")
    for plugin in project.plugins:
        if not plugin.is_file():
            raise TraceError(f"the pytest plugin {plugin} does not exist")
    before = _snapshot(project.directory)
    python_absolute_keeping_symbolic_links = os.path.abspath(
        shutil.which(python) or python
    )
    python = python_absolute_keeping_symbolic_links
    with tempfile.TemporaryDirectory(prefix="macro-trace-") as tmp:
        scratch = Path(tmp)
        out_path = scratch / "trace.json"
        command = [
            python,
            *CHILD_INTERPRETER_FLAGS,
            str(Path(__file__).resolve()),
            CHILD_ENTRY_ARGUMENT,
            str(Path(config_path).resolve()),
            project.name,
            str(out_path),
        ]
        problems, status = [], None
        try:
            env = _child_environment(python, scratch, project.environment)
            status = _run_in_process_group(
                command, project.directory, env, timeout_seconds
            )
        except TraceError as exc:
            problems.append(str(exc))
        changes = _differences_as_git_status(before, _snapshot(project.directory))
        if changes:
            problems.append(f"the run left changes in the checkout:\n{changes}")
        if problems:
            raise TraceError("\n".join(problems))
        if not out_path.exists():
            raise TraceError(f"the tracer crashed (exit status {status})")
        data = json.loads(out_path.read_text(encoding="utf-8"))
    if data["errors"]:
        raise TraceError("\n".join(data["errors"]))
    del data["errors"]
    return data


def locate(project):
    lines, problems = [], []
    for package in project.package_names:
        top = package.partition(".")[0]
        spec = _find_in(package, [str(project.root)])
        origin = spec.origin if spec is not None else None
        if origin is None or not project.in_scope(origin):
            problems.append(f"{package} is not found in the checkout {project.root}")
            continue
        lines.append(f"{package}: {origin}")
        for finder in sys.meta_path:
            find = getattr(finder, "find_spec", None)
            path = sys.path if finder is importlib.machinery.PathFinder else None
            other = find(top, path) if find is not None else None
            if other is None:
                continue
            where = other.origin or list(other.submodule_search_locations or ())
            if package in project.also_installed:
                lines.append(f"{top}: also installed (also_installed): {where}")
            else:
                problems.append(f"{top} is also found outside the checkout: {where}")
    return lines, problems


def _find_in(name, path):
    *parents, last = name.split(".")
    for part in parents:
        path = _package_path(part, path)
        if not path:
            return None
    return importlib.machinery.PathFinder.find_spec(last, path)


def _package_path(part, path):
    portions = []
    for directory in path:
        candidate = os.path.join(directory, part)
        is_directory = os.path.isdir(candidate)
        if is_directory and any(
            os.path.isfile(os.path.join(candidate, "__init__" + suffix))
            for suffix in importlib.machinery.all_suffixes()
        ):
            return [candidate]
        if any(
            os.path.isfile(os.path.join(directory, part + suffix))
            for suffix in importlib.machinery.all_suffixes()
        ):
            return []
        if is_directory:
            portions.append(candidate)
    return portions


def write_trace(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("project", help="a project of projects.toml")
    parser.add_argument(
        "--python",
        help="interpreter of the prepared environment (Python 3.14+ with pytest); "
        "required unless --locate",
    )
    parser.add_argument(
        "--benchmark-dir",
        type=Path,
        default=BENCHMARK_DIR,
        help="the benchmark directory: projects.toml, projects/<name>, dynamic/ "
        "(default: evaluation/macro-benchmark/)",
    )
    parser.add_argument(
        "--output", type=Path, help="default: dynamic/PROJECT.json in the directory"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=TIMEOUT_SECONDS_DEFAULT,
        help="wall-clock limit of the run in seconds "
        f"(default {TIMEOUT_SECONDS_DEFAULT})",
    )
    parser.add_argument(
        "--locate",
        action="store_true",
        help="only print where the interpreter running this script finds each "
        "package (in the checkout, and nowhere else), without importing it",
    )
    args = parser.parse_args(argv)
    if args.python is None and not args.locate:
        parser.error("--python is required unless --locate")
    try:
        projects = load_projects(args.benchmark_dir / "projects.toml")
    except ValueError as exc:
        parser.error(str(exc))
    if args.project not in projects:
        parser.error(f"unknown project {args.project!r}")
    if args.locate:
        lines, problems = locate(projects[args.project])
        for line in lines:
            print(line)
        for problem in problems:
            print(f"{args.project}: {problem}", file=sys.stderr)
        return 1 if problems else 0
    output = args.output or args.benchmark_dir / "dynamic" / f"{args.project}.json"
    try:
        data = trace(
            projects[args.project],
            args.python,
            args.benchmark_dir,
            args.timeout,
        )
    except TraceError as exc:
        print(f"{args.project}: {exc}", file=sys.stderr)
        return 1
    write_trace(data, output)
    tests = ", ".join(f"{data['tests'][o]} {o}" for o in OUTCOMES_IN_SUMMARY_ORDER)
    edges = sum(len(callees) for callees in data["edges"].values())
    print(
        f"{args.project}: {edges} edges, {len(data['executed'])} functions run; "
        f"tests: {tests}; dropped: {data['dropped']['client_callbacks']} client "
        f"callbacks, {data['dropped']['unknown_caller']} calls without a caller"
    )
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == [CHILD_ENTRY_ARGUMENT]:
        _run_child(*sys.argv[2:5])
    else:
        sys.exit(main())
