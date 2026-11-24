#!/usr/bin/env python3
"""Record the calls that a macro-benchmark package makes while its tests run.

    python evaluation/macro-benchmark/trace.py --python ENV/bin/python PROJECT

The test suite of projects/PROJECT runs with pytest in a child process of
the interpreter ENV/bin/python, with the pinned source first on sys.path.
The child records the calls with the tracer of micro-benchmark/validate.py
and the parent writes them to dynamic/PROJECT.json. See
evaluation/macro-benchmark/README.md for the format and for how to prepare ENV.
"""

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


def _load_sibling(name):
    """Load a script of this directory by path (it is not a package)."""
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
# The sys.monitoring tool that records which package functions start (see
# MacroTracer.start); the validator's tracer is sys.monitoring.PROFILER_ID.
_STARTS_TOOL_ID = 3
# Default wall-clock limit of a test suite under the tracer.
TIMEOUT_SECONDS = 600
# Test outcomes that the trace records, in the order of the summary line.
OUTCOMES = ("passed", "failed", "errors", "skipped", "xfailed", "xpassed")
# Bound methods: calling one calls a method of its __self__.
_BOUND_TYPES = (types.MethodType, types.BuiltinMethodType, types.MethodWrapperType)
# What a method call passes, with the object as arg0.
_UNBOUND_TYPES = (
    types.FunctionType,
    types.MethodDescriptorType,
    types.WrapperDescriptorType,
)


def _load_validator():
    """Load micro-benchmark/validate.py by path (its directory is not a package)."""
    spec = importlib.util.spec_from_file_location("validate", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate = _load_validator()
_is_a = validate._is_a  # isinstance() that runs no code of the object
# Callees whose __name__ is the attribute name under which a class holds them.
_NAMED_TYPES = (
    type,
    types.FunctionType,
    types.BuiltinFunctionType,
    *validate._DESCRIPTOR_TYPES,
)


class TraceError(Exception):
    """The trace could not be made."""


# --------------------------------------------------------------------------
# Child process: run the test suite and record the calls.
# --------------------------------------------------------------------------


class MacroTracer(validate.Tracer):
    """The validator's tracer, with the analysed package in place of a snippet.

    Code is in one of three zones. The package is the analysed source. Library
    code is the standard library, builtins and the installed dependencies
    of the package. Client code is all other code: tests, conftest files,
    pytest and its plugins, and this tracer. A call has a caller only if a
    package frame made it, directly or through library frames (a callback
    from a builtin belongs to the package scope that called the builtin).
    Client code in between ends the search: what a test callback calls is
    not an edge of the package. A callee defined in client code is not an
    edge either; it is counted as a client callback.
    """

    def __init__(self, project):
        super().__init__(str(project.root))  # module names are relative to it
        self.project = project
        self.client_callbacks = set()  # {(caller, name)} of dropped callees
        self.receivers = {}  # id(cls) -> cls whose methods the package called
        self.started = set()  # functions and lambdas whose code started
        self._recorded = {}  # id(target) -> names the validator gave it
        self._client = {}  # filename -> whether it is client code
        self._stdlib = {
            os.path.realpath(sysconfig.get_path(key))
            for key in ("stdlib", "platstdlib")
        }

    def in_snippet(self, filename):
        if filename not in self._snippet_files:
            self._snippet_files[filename] = self.project.in_scope(filename)
        return self._snippet_files[filename]

    def is_client(self, filename):
        """Whether code in `filename` is client code (see the class docstring)."""
        if filename not in self._client:
            self._client[filename] = self._classify(filename)
        return self._client[filename]

    def _classify(self, filename):
        if filename.startswith("<"):  # frozen modules, exec and eval strings
            return False
        path = os.path.realpath(filename)
        parts = Path(path).parts
        for n in range(len(parts) - 2, -1, -1):
            if parts[n] in ("site-packages", "dist-packages"):
                top = parts[n + 1].partition(".")[0]  # package or module file
                return top not in self.project.dependencies
        if any(_is_under(path, directory) for directory in self._stdlib):
            return False
        return not self.in_snippet(filename)

    def caller(self, frame):
        while frame is not None:
            entry = self._codes.get(id(frame.f_code))
            if entry is not None:
                return entry[0]
            if self.is_client(frame.f_code.co_filename):
                return None  # client code made the call
            frame = frame.f_back
        return super().caller(None)  # the scope that started this thread

    def start(self):
        """Also watch, as a tool of its own, for package functions that start.

        That is the only event of a generator or coroutine function that the
        interpreter drives (`__iter__` written as a generator, `__anext__`):
        no call expression calls it. The validator's tool keeps its events.
        """
        super().start()
        monitoring = sys.monitoring
        monitoring.use_tool_id(_STARTS_TOOL_ID, "pycg-macro-starts")
        monitoring.register_callback(
            _STARTS_TOOL_ID, monitoring.events.PY_START, self._on_started
        )
        monitoring.set_events(_STARTS_TOOL_ID, monitoring.events.PY_START)

    def stop(self):
        sys.monitoring.set_events(_STARTS_TOOL_ID, 0)
        sys.monitoring.free_tool_id(_STARTS_TOOL_ID)
        super().stop()

    def _on_started(self, code, offset):
        """Remember the first start of a package function, then stop watching it.

        A function's code object is registered when its module starts, so
        before the function can run.
        """
        entry = self._codes.get(id(code))
        if entry is not None and entry[1] is not None:
            self.started.add(entry[1])
        return sys.monitoring.DISABLE

    def on_call(self, code, offset, callee, arg0):
        if id(code) in self._codes:
            try:
                self._note_receiver(callee, arg0)
            except Exception:  # noqa: BLE001 - must not leak into the tests
                self.failures.append(traceback.format_exc())
        return super().on_call(code, offset, callee, arg0)

    def _note_receiver(self, callee, arg0):
        """Remember the class of the object whose method package code calls.

        A method call passes a bound method, or the function or descriptor
        of the method with the object as arg0.
        """
        if _is_a(callee, _BOUND_TYPES):
            receiver = callee.__self__
            if receiver is None or _is_a(receiver, types.ModuleType):
                return
        elif _is_a(callee, _UNBOUND_TYPES) and arg0 is not sys.monitoring.MISSING:
            receiver = arg0
            found = inspect.getattr_static(type(receiver), callee.__name__, None)
            if found is None or validate._canonical(found) is not callee:
                return  # a function that takes the object as first argument
        else:
            return
        cls = receiver if _is_a(receiver, type) else type(receiver)
        self.receivers[id(cls)] = cls

    def _record(self, caller, name, target):
        if target is not None:
            if self._defined_by_client(target):
                self.client_callbacks.add((caller, name))
                return
            key = id(validate._canonical(target))
            self._recorded.setdefault(key, set()).add(name)
        super()._record(caller, name, target)

    def _defined_by_client(self, target):
        target = validate._canonical(target)
        if _is_a(target, types.FunctionType):
            return self.is_client(target.__code__.co_filename)
        if _is_a(target, type):
            filename = _module_file(sys.modules.get(target.__module__))
            return filename is not None and self.is_client(filename)
        return False

    # -- result ---------------------------------------------------------------

    def result(self):
        """The call graph of the package, with aliases of the outside callees."""
        edges = {}
        executed, unknown = set(self.started), set()
        for caller, callee in self.edges:  # also generators created, not run
            executed.update({caller, callee} & self.functions)
            if caller is None:  # client code called the package
                continue
            if caller == validate.UNKNOWN_CALLER:
                unknown.add(callee)
                continue
            edges.setdefault(caller, set()).add(callee)
        names = {}  # id(target) -> (target, canonical name)
        for (caller, key), (target, _) in self.outside.items():
            if key not in names:
                names[key] = (target, _defining_name(target, self._recorded[key]))
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
                "client_callbacks": len(self.client_callbacks),
                "unknown_caller": len(unknown),
            },
            "edges": {caller: sorted(edges[caller]) for caller in sorted(edges)},
            "aliases": {
                name: sorted(aliases[name]) for name in sorted(aliases) if aliases[name]
            },
        }

    def _aliases(self, names):
        """{id(target): dotted names that resolve to the target}.

        The names are those the validator recorded, and the paths through
        the library modules that are loaded at the end of the run:
        `module.name`, and `module.Class.name` where the class defines
        `name` or is in the MRO of a package class or of an object whose
        method the package called (inherited methods are named through the
        class that the package names). Only public names count: the names
        in `__all__` if the module defines it, else the names that do not
        start with an underscore, in modules whose path has no part that
        starts with one. `builtins` is written `<builtin>`.
        """
        found = {key: set(self._recorded[key]) for key in names}
        members = {t.__name__ for t, _ in names.values() if _is_a(t, _NAMED_TYPES)}
        inherited = self._named_classes()
        classes = []
        for module_name, module in list(sys.modules.items()):
            if not self._is_library_module(module_name, module):
                continue
            prefix = "<builtin>" if module_name == "builtins" else module_name
            namespace = _namespace(module)
            public = dict.get(namespace, "__all__")
            if _is_a(public, (list, tuple)):
                attrs = [a for a in public if _is_a(a, str) and a in namespace]
            else:
                attrs = [a for a in namespace if _is_a(a, str) and not _is_private(a)]
            for attr in attrs:
                value = namespace[attr]
                _match(found, f"{prefix}.{attr}", value)
                if _is_a(value, type):
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
                _match(found, f"{path}.{attr}", value)
        return found

    def _named_classes(self):
        """{id: class} for the MROs of the package classes and of the receivers."""
        roots = list(self.receivers.values())
        for name in self.modules:
            namespace = _namespace(sys.modules.get(name))
            if namespace is not None:
                roots += [
                    value
                    for value in list(namespace.values())
                    if _is_a(value, type) and self._is_snippet_class(value)
                ]
        return {id(cls): cls for root in roots for cls in root.__mro__}

    def _is_library_module(self, name, module):
        if not _is_a(module, types.ModuleType) or name == "__main__":
            return False
        if any(part.startswith("_") for part in name.split(".")):
            return False
        filename = _module_file(module)
        if filename is None:  # a builtin module or a namespace package
            return True
        return not self.in_snippet(filename) and not self.is_client(filename)


def _namespace(module):
    """The namespace of a module object, read without running code, or None.

    sys.modules can hold an object that runs code when an attribute is read
    (a lazy module), so neither isinstance() nor vars() is used.
    """
    if not _is_a(module, types.ModuleType):
        return None
    return object.__getattribute__(module, "__dict__")


def _module_file(module):
    """The __file__ of a module object, or None."""
    namespace = _namespace(module)
    return None if namespace is None else dict.get(namespace, "__file__")


def _is_private(name):
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def _match(found, name, value):
    """Add `name` to the names of the target that `value` is, if it is one."""
    try:
        key = id(validate._canonical(value))
    except Exception:  # noqa: BLE001 - an attribute that is not a callable
        return
    if key in found:
        found[key].add(name)


def _defining_name(target, recorded):
    """The canonical name of a callee outside the package: where it is defined.

    A function is named by its module and qualified name without
    `<locals>`, a class by its module and qualified name, a builtin by
    `<builtin>` and its name, and a method of a builtin type by the type
    that defines it. Other callables keep the first name the validator gave.
    """
    if _is_a(target, types.FunctionType):
        return validate._function_name(target)
    if _is_a(target, type):
        return validate._class_name(target)
    if _is_a(target, types.BuiltinFunctionType):
        owner = target.__self__
        if owner is None or _is_a(owner, types.ModuleType):
            if getattr(builtins, target.__name__, None) is target:
                return f"<builtin>.{target.__name__}"
            module = owner.__name__ if owner is not None else target.__module__
            return f"{module}.{target.__name__}"
        if _is_a(owner, type):  # e.g. object.__new__
            return f"{validate._class_name(owner)}.{target.__name__}"
    if _is_a(target, validate._DESCRIPTOR_TYPES):  # a method of a builtin type
        return f"{validate._class_name(target.__objclass__)}.{target.__name__}"
    return min(recorded)


class _Session:
    """A pytest plugin that records the outcomes and the configuration of the run."""

    def __init__(self):
        self.counts = None
        self.failures = {"errors": [], "failed": []}
        self.rootdir = self.config = None

    def pytest_configure(self, config):
        self.rootdir, self.config = config.rootpath, config.inipath

    def pytest_sessionfinish(self, session):
        """Count the tests as the summary line of pytest does.

        The categories are those of pytest's terminal reporter, and only the
        reports that count towards the summary count: a passing subtest of a
        unittest test is not a test (pytest 9).
        """
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
        """Whether pytest used the checkout as rootdir, and the expected config."""
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
            "rootdir": _relative(self.rootdir, project.directory),
            "config": _relative(self.config, project.directory),
        }


def _relative(path, directory):
    """`path` relative to `directory` if it is in it (e.g. "."), else as it is."""
    if path is None:
        return None
    path = Path(path).resolve()
    if path == directory or directory in path.parents:
        return path.relative_to(directory).as_posix()
    return str(path)


def _distributions(project):
    """{name: version} of the installed distributions (pytest, test dependencies).

    Metadata inside the project's own directory is not an installation: an
    sdist carries the metadata of its build (`<name>.egg-info`), and its
    source directory is on the path.
    """
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
    """How the installed distributions differ from the test requirements."""
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
    """Import a pytest plugin of projects.toml by its path; return the module.

    It is not put on sys.path, so that it cannot hide a module of the
    project. Its code is client code for the tracer.
    """
    spec = importlib.util.spec_from_file_location(f"macro_plugin_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _not_importable_edges(project, edges):
    """The edges from or to a package that the entry names in
    not_importable: its code ran, so the entry is wrong."""

    def inside(name):
        """The package of not_importable that `name` is in, or None."""
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
    distributions = _distributions(project)
    errors = _requirement_problems(project.requirements, distributions)
    errors += [
        f"the variable {name} of the entry's environment is not {value!r}"
        for name, value in project.environment
        if os.environ.get(name) != value
    ]
    if errors:  # run nothing in an environment that is not the pinned one
        _write(out_path, {"errors": errors})
        return
    tracer = MacroTracer(project)
    session = _Session()
    tracer.start()
    try:
        import pytest  # after start: pytest imports pluggy

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
                {"plugins": [_relative(p, benchmark) for p in project.plugins]}
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
                **dict.fromkeys((*OUTCOMES, "deselected"), 0),
                **(session.counts or {}),
            },
            **result,
            "errors": errors,
        },
    )


# --------------------------------------------------------------------------
# Parent process
# --------------------------------------------------------------------------


def _environment(python, scratch, extra=()):
    """The whole environment of the child: nothing comes from the caller's,
    and `extra` (the entry's `environment`) is added.

    HOME and TMPDIR are new directories in `scratch`, which is deleted after
    the run. A fixed hash seed makes sets of strings iterate in the same
    order in every run. projects.py refuses an entry's variable that this
    environment sets; the check here is a second one.
    """
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


def _run(command, cwd, env, timeout):
    """Run `command` in a new process group; return its exit status.

    After `timeout` seconds it is stopped. Either way, every process that
    is left in its group (a server that a test started) is killed. The
    child is waited for without being reaped first, so that its process
    group id cannot be reused by an unrelated process in between. Its stdin
    is /dev/null, whatever the caller's is, so that code that reads stdin
    when it is not a terminal reads nothing, on every run.
    """
    proc = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + timeout
    try:
        while not os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT):
            if time.monotonic() > deadline:
                raise TraceError(f"the test suite ran longer than {timeout:g} s")
            time.sleep(0.1)
    finally:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
    return proc.returncode


def _snapshot(directory):
    """{relative path: content} of everything below `directory`: the SHA-256
    of a file, the target of a symbolic link, or "dir"."""
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


def _differences(before, after):
    """The changes from one snapshot to the other, in the form of git
    status --porcelain."""
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
    timeout=TIMEOUT_SECONDS,
):
    """Run the test suite of `project` (of the projects.toml in
    `benchmark_dir`) with `python` and return the trace.

    projects/<name> is a copy of the pinned source, which the caller laid
    out in a container (evaluation/container/trace_entry.py, entry.sh):
    the sources come from the inputs image, where the build checked each
    one against its pin. The files after the run are compared with those
    before it.
    """
    config_path = Path(benchmark_dir) / "projects.toml"
    if not project.pytest_args:  # pytest would collect the whole checkout
        raise TraceError("no test run in projects.toml (no pytest_args)")
    if not project.directory.is_dir():
        raise TraceError(f"{project.directory} does not exist")
    for plugin in project.plugins:
        if not plugin.is_file():
            raise TraceError(f"the pytest plugin {plugin} does not exist")
    before = _snapshot(project.directory)
    python = os.path.abspath(shutil.which(python) or python)  # keep venv symlinks
    with tempfile.TemporaryDirectory(prefix="macro-trace-") as tmp:
        scratch = Path(tmp)
        out_path = scratch / "trace.json"
        command = [
            python,
            "-s",  # no user site-packages
            "-P",  # neither the script directory nor the working directory
            "-B",  # no bytecode files in the checkout
            str(Path(__file__).resolve()),
            "--child",
            str(Path(config_path).resolve()),
            project.name,
            str(out_path),
        ]
        problems, status = [], None
        try:
            env = _environment(python, scratch, project.environment)
            status = _run(command, project.directory, env, timeout)
        except TraceError as exc:
            problems.append(str(exc))
        changes = _differences(before, _snapshot(project.directory))
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
    """Where each package of `project` is found, without running its code.

    A package must be found in the root, and no finder of this interpreter
    may find it elsewhere (a builtin or frozen module, sys.path without the
    root, an editable install), so that the environment cannot supply it.
    A package of `also_installed` (pytest requires pluggy) may be found
    elsewhere too; the run then checks that it is imported from the root.
    The finders are asked directly, not through sys.modules, and read the
    file system only. Return (lines, problems).
    """
    lines, problems = [], []
    for package in project.package_names:
        top = package.partition(".")[0]
        spec = importlib.machinery.PathFinder.find_spec(top, [str(project.root)])
        origin = spec.origin if spec is not None else None
        if origin is None or not project.in_scope(origin):
            problems.append(f"{top} is not found in the checkout {project.root}")
            continue
        lines.append(f"{top}: {origin}")
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


def write_trace(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
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
        default=TIMEOUT_SECONDS,
        help=f"wall-clock limit of the run in seconds (default {TIMEOUT_SECONDS})",
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
    tests = ", ".join(f"{data['tests'][o]} {o}" for o in OUTCOMES)
    edges = sum(len(callees) for callees in data["edges"].values())
    print(
        f"{args.project}: {edges} edges, {len(data['executed'])} functions run; "
        f"tests: {tests}; dropped: {data['dropped']['client_callbacks']} client "
        f"callbacks, {data['dropped']['unknown_caller']} calls without a caller"
    )
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["--child"]:  # internal: the child process entry point
        _run_child(*sys.argv[2:5])
    else:
        sys.exit(main())
