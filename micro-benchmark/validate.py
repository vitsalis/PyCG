#!/usr/bin/env python3
"""Check micro-benchmark ground truth against the calls a snippet really makes.

    python micro-benchmark/validate.py             # validate every case
    python micro-benchmark/validate.py CASE [...]  # validate the given cases

Each case runs in its own child process. The child traces the run with
sys.monitoring and names every call edge with the benchmark naming scheme
(see micro-benchmark/README.md). A callee outside the snippet takes the
name from callgraph.json that resolves to the same function, so that
os.path.join matches posixpath.join. The child writes the edges to a JSON
file and the parent compares them with callgraph.json. The exit status is
1 if a case has a problem.
"""

import argparse
import builtins
import dis
import importlib.machinery
import inspect
import json
import os
import subprocess
import sys
import tempfile
import traceback
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NamedTuple

if sys.version_info < (3, 14):
    sys.exit("validate.py needs Python 3.14 or later (sys.monitoring, LOAD_SPECIAL)")

SNIPPETS_DIR = Path(__file__).resolve().parent / "snippets"
TIMEOUT_SECONDS = 30
UNKNOWN_CALLER = "<unknown>"

# Code objects that are scopes for the compiler but not nodes of the call
# graph. Calls made in them belong to the enclosing scope.
_TRANSPARENT_PREFIXES = ("<genexpr>", "__annotate__", "<generic parameters of ")
# Calling one of these starts a generator or coroutine instead of running the
# body, so the edge is taken from the call site (CALL), not from PY_START.
_DEFERRED_BODY = (
    inspect.CO_GENERATOR
    | inspect.CO_COROUTINE
    | inspect.CO_ITERABLE_COROUTINE
    | inspect.CO_ASYNC_GENERATOR
)
# Methods that a `with` statement calls. Those calls are not call expressions.
_WITH_METHODS = {"__enter__", "__exit__", "__aenter__", "__aexit__"}
_DESCRIPTOR_TYPES = (
    types.MethodDescriptorType,
    types.ClassMethodDescriptorType,
    types.WrapperDescriptorType,
    types.MethodWrapperType,
)
# Instructions that push one value with no side effect (see _load).
_LOADS = {
    "LOAD_CONST",
    "LOAD_COMMON_CONSTANT",
    "LOAD_SMALL_INT",
    "LOAD_FAST",
    "LOAD_FAST_BORROW",
    "LOAD_FAST_CHECK",
    "LOAD_DEREF",
    "LOAD_NAME",
    "LOAD_GLOBAL",
    "LOAD_FROM_DICT_OR_GLOBALS",
}
_DOUBLE_LOADS = {"LOAD_FAST_LOAD_FAST", "LOAD_FAST_BORROW_LOAD_FAST_BORROW"}


class Trace(NamedTuple):
    edges: frozenset = frozenset()  # {(caller, callee)}
    modules: frozenset = frozenset()  # snippet modules that were executed
    functions: frozenset = frozenset()  # functions and lambdas in those modules
    stubbed: frozenset = frozenset()  # missing modules replaced by stubs
    error: str | None = None  # why the snippet did not finish normally


# --------------------------------------------------------------------------
# Child process: run the snippet and record its calls.
# --------------------------------------------------------------------------


class Tracer:
    def __init__(self, case_dir):
        self.case_dir = case_dir
        self.edges = set()  # {(caller, name)} for snippet callees and stubs
        # (caller, id(target)) -> (target, name) for callees outside the snippet.
        # `target` is the object that runs (see _canonical); it decides which
        # ground-truth name the edge matches.
        self.outside = {}
        self.modules = set()
        self.functions = set()
        self.stubbed = set()
        self.failures = []  # tracebacks of errors inside the tracer itself
        # id(code) -> (owner, function). `owner` is the node that calls made
        # by this code belong to. `function` is the node for the code itself,
        # or None for modules, class bodies and transparent scopes.
        self._codes = {}
        self._alive = []  # keeps registered code objects alive, so ids stay unique
        self._snippet_files = {}
        self._instructions = {}  # id(code) -> {offset: (index, instructions)}

    # -- naming -------------------------------------------------------------

    def in_snippet(self, filename):
        if filename not in self._snippet_files:
            path = os.path.realpath(filename)
            self._snippet_files[filename] = path.endswith(".py") and path.startswith(
                self.case_dir + os.sep
            )
        return self._snippet_files[filename]

    def _register_module(self, code):
        path = os.path.relpath(os.path.realpath(code.co_filename), self.case_dir)
        parts = list(Path(path).with_suffix("").parts)
        if parts[-1] == "__init__" and len(parts) > 1:
            parts.pop()
        name = ".".join(parts)
        self.modules.add(name)
        self._add(code, name, None)
        self._register_scope(code, name, name)

    def _register_scope(self, code, scope, owner):
        """Name the code objects nested in `code`, whose names live in `scope`."""
        lambdas = sorted(_lambdas(code), key=lambda item: item[0])
        numbers = {id(const): n for n, (_, const) in enumerate(lambdas, 1)}
        self._register_children(code, scope, owner, numbers)

    def _register_children(self, code, scope, owner, numbers):
        for const in code.co_consts:
            if not isinstance(const, types.CodeType):
                continue
            if _is_transparent(const):
                self._add(const, owner, None)
                self._register_children(const, scope, owner, numbers)
                continue
            if const.co_name == "<lambda>":
                name = f"{scope}.<lambda{numbers[id(const)]}>"
            else:
                name = f"{scope}.{const.co_name}"
            if const.co_flags & inspect.CO_OPTIMIZED:  # a function or lambda
                self.functions.add(name)
                self._add(const, name, name)
                self._register_scope(const, name, name)
            else:  # a class body: names nest under it, calls go to the owner
                self._add(const, owner, None)
                self._register_scope(const, name, owner)

    def _add(self, code, owner, function):
        self._codes[id(code)] = (owner, function)
        self._alive.append(code)

    def caller(self, frame):
        """The node of the nearest snippet frame, skipping library frames."""
        while frame is not None:
            entry = self._codes.get(id(frame.f_code))
            if entry is not None:
                return entry[0]
            frame = frame.f_back
        return UNKNOWN_CALLER

    def callee(self, obj):
        """Classify a callable seen at a CALL event.

        Return None to record nothing, (name, None) for a snippet function, or
        (name, target) for code outside the snippet. Snippet functions are
        recorded at PY_START instead, so that implicit calls and callbacks
        from builtins are seen too; generators are the exception.
        """
        if isinstance(obj, _External) or obj is builtins.__build_class__:
            return None  # a stub records itself; __build_class__ is a class statement
        if isinstance(obj, (types.MethodType, staticmethod, classmethod)):
            obj = obj.__func__
        if isinstance(obj, types.FunctionType):
            entry = self._codes.get(id(obj.__code__))
            if entry is not None:
                if entry[1] is None or not obj.__code__.co_flags & _DEFERRED_BODY:
                    return None  # a generator expression, or a call seen at PY_START
                return entry[1], None
            if obj.__code__.co_filename == "<string>":
                return None  # defined by exec or eval: there is no name for it
            return _dotted(obj.__module__, obj.__qualname__), obj
        if isinstance(obj, type):
            if self._is_snippet_class(obj):
                return self._init_callee(obj)
            return _class_name(obj), obj
        if isinstance(obj, types.BuiltinFunctionType):
            owner = obj.__self__
            if owner is None or isinstance(owner, types.ModuleType):
                if getattr(builtins, obj.__name__, None) is obj:
                    return f"<builtin>.{obj.__name__}", obj
                module = owner.__name__ if owner is not None else obj.__module__
                return f"{module}.{obj.__name__}", obj
            return _method(_lookup_classes(owner), obj.__name__, obj)
        if isinstance(obj, _DESCRIPTOR_TYPES):
            return _method(obj.__objclass__.__mro__, obj.__name__, obj)
        if self._is_snippet_class(type(obj)):
            return None  # its __call__ is seen at PY_START
        return _method(type(obj).__mro__, "__call__", obj)

    def _init_callee(self, cls):
        """Instantiating a snippet class calls the first __init__ in its MRO.

        A snippet __init__ is recorded at PY_START, object.__init__ gives no
        edge, and any other __init__ is named through the nearest class of
        the MRO that is not in the snippet (`<builtin>.Exception.__init__`).
        """
        owner = next(k for k in cls.__mro__ if "__init__" in vars(k))
        if owner is object or self._is_snippet_class(owner):
            return None
        nearest = next(k for k in cls.__mro__ if not self._is_snippet_class(k))
        return f"{_class_name(nearest)}.__init__", vars(owner)["__init__"]

    def _instruction(self, code, offset):
        """The instruction at `offset` in `code`, with the instructions before it."""
        if id(code) not in self._instructions:
            instructions = list(dis.get_instructions(code))
            self._instructions[id(code)] = (
                instructions,
                {ins.offset: n for n, ins in enumerate(instructions)},
            )
        instructions, index = self._instructions[id(code)]
        return instructions, index.get(offset)

    def _is_with_call(self, code, offset):
        """Whether the CALL at `offset` is made by a `with` statement.

        Those CALLs have the source position of the `with` item, like the
        LOAD_SPECIAL that fetches __enter__ and __exit__ (Python 3.14+).
        """
        instructions, n = self._instruction(code, offset)
        if n is None:
            return False
        position = instructions[n].positions
        return any(
            i.opname == "LOAD_SPECIAL" and i.positions == position for i in instructions
        )

    def _raises_class(self, code, offset, frame, cls):
        """Whether the instruction at `offset` is `raise X` with X evaluating to cls.

        X must be a name or a chain of attributes (`raise E`, `raise A.B from
        None`). It is evaluated again, without side effects, in `frame`.
        """
        instructions, n = self._instruction(code, offset)
        if n is None or instructions[n].opname != "RAISE_VARARGS":
            return False
        before = instructions[:n]
        if instructions[n].arg == 2:  # `raise X from Y`: Y must be one load
            if before and before[-1].opname in _DOUBLE_LOADS:
                return frame.f_locals.get(before[-1].argval[0]) is cls
            if not before or before[-1].opname not in _LOADS:
                return False
            before = before[:-1]
        elif instructions[n].arg != 1:
            return False
        attributes = []
        while before and before[-1].opname == "LOAD_ATTR":
            attributes.insert(0, before.pop().argval)
        if not before or before[-1].opname not in _LOADS:
            return False
        try:
            value = _load(before[-1], frame)
            for attribute in attributes:
                value = inspect.getattr_static(value, attribute)
        except (KeyError, AttributeError):
            return False
        return value is cls

    def _is_snippet_class(self, cls):
        module = sys.modules.get(cls.__module__)
        return self.in_snippet(getattr(module, "__file__", None) or "")

    # -- events -------------------------------------------------------------

    def on_start(self, code, offset):
        try:
            entry = self._codes.get(id(code))
            if entry is None:
                if code.co_name == "<module>" and self.in_snippet(code.co_filename):
                    self._register_module(code)
                    return None
                return sys.monitoring.DISABLE
            function = entry[1]
            if function is not None and not code.co_flags & _DEFERRED_BODY:
                self.edges.add((self.caller(sys._getframe(1).f_back), function))
        except Exception:  # noqa: BLE001 - must not leak into the snippet
            self.failures.append(traceback.format_exc())
        return None

    def on_call(self, code, offset, callee, arg0):
        try:
            entry = self._codes.get(id(code))
            if entry is not None:
                owner = entry[0]
            elif _is_eval_code(code):
                owner = self._eval_owner(sys._getframe(1))
                if owner is None:
                    return None
            else:
                return sys.monitoring.DISABLE
            found = self.callee(callee)
            if found is None:
                return None
            name, target = found
            method = name.rpartition(".")[2]
            if method in _WITH_METHODS and self._is_with_call(code, offset):
                return None  # made by a `with` statement, not a call expression
            self._record(owner, name, target)
        except Exception:  # noqa: BLE001 - must not leak into the snippet
            self.failures.append(traceback.format_exc())
        return None

    def on_raise(self, code, offset, exception):
        """`raise Cls` creates an instance without a CALL event."""
        try:
            entry = self._codes.get(id(code))
            cls = type(exception)
            if entry is None or not self._is_snippet_class(cls):
                return
            if self._raises_class(code, offset, sys._getframe(1), cls):
                found = self._init_callee(cls)
                if found is not None:
                    self._record(entry[0], *found)
        except Exception:  # noqa: BLE001 - must not leak into the snippet
            self.failures.append(traceback.format_exc())

    def _record(self, caller, name, target):
        if target is None:
            self.edges.add((caller, name))
        else:
            target = _canonical(target)
            self.outside[(caller, id(target))] = (target, name)

    def named_edges(self, graph):
        """All edges; an outside callee takes the expected name that resolves to it.

        An expected callee of the same caller matches if its name resolves to
        the same object (os.path.join matches posixpath.join). A callee that
        no expected name matches keeps its own name, which still matches a
        name that does not resolve, such as the stub name ext.Cls.
        """
        own = self.modules | self.functions
        resolved = {}
        edges = set(self.edges)
        for (caller, _), (target, name) in self.outside.items():
            for candidate in sorted(set(graph.get(caller, ())) - own):
                if candidate not in resolved:
                    resolved[candidate] = _resolve(candidate)
                if resolved[candidate] is target:
                    name = candidate
                    break
            edges.add((caller, name))
        return edges

    def _eval_owner(self, frame):
        """Give calls in an eval or exec string to the snippet scope that ran it."""
        while frame is not None and _is_eval_code(frame.f_code):
            frame = frame.f_back
        entry = self._codes.get(id(frame.f_code)) if frame is not None else None
        return entry[0] if entry is not None else None

    def record_external(self, callee):
        self.edges.add((self.caller(sys._getframe()), callee))

    def start(self):
        monitoring = sys.monitoring
        monitoring.use_tool_id(monitoring.PROFILER_ID, "pycg-validate")
        monitoring.register_callback(
            monitoring.PROFILER_ID, monitoring.events.PY_START, self.on_start
        )
        monitoring.register_callback(
            monitoring.PROFILER_ID, monitoring.events.CALL, self.on_call
        )
        monitoring.register_callback(
            monitoring.PROFILER_ID, monitoring.events.RAISE, self.on_raise
        )
        events = monitoring.events
        monitoring.set_events(
            monitoring.PROFILER_ID, events.PY_START | events.CALL | events.RAISE
        )

    def stop(self):
        sys.monitoring.set_events(sys.monitoring.PROFILER_ID, 0)
        sys.monitoring.free_tool_id(sys.monitoring.PROFILER_ID)


def _is_transparent(code):
    return code.co_name.startswith(_TRANSPARENT_PREFIXES)


def _lambdas(code):
    """Yield ((line, column), code) for the lambdas that `code` names."""
    starts = {}  # where the instruction that loads a lambda's code points: `lambda`
    for instruction in dis.get_instructions(code):
        if isinstance(instruction.argval, types.CodeType):
            position = (instruction.positions.lineno, instruction.positions.col_offset)
            starts.setdefault(id(instruction.argval), position)
    for const in code.co_consts:
        if not isinstance(const, types.CodeType):
            continue
        if _is_transparent(const):
            yield from _lambdas(const)
        elif const.co_name == "<lambda>":
            yield starts[id(const)], const


def _is_eval_code(code):
    return code.co_filename == "<string>" and code.co_name == "<module>"


def _dotted(module, qualname):
    return f"{module}.{qualname.replace('<locals>.', '')}"


def _class_name(cls):
    if getattr(builtins, cls.__name__, None) is cls:
        return f"<builtin>.{cls.__name__}"
    return _dotted(cls.__module__, cls.__qualname__)


def _method(classes, name, default):
    """(name, target) of the method `name` defined by the first of `classes`.

    If no class defines it, the target is `default`.
    """
    owner = next((k for k in classes if name in vars(k)), None)
    if owner is None:
        return f"{_class_name(classes[0])}.{name}", default
    return f"{_class_name(owner)}.{name}", vars(owner)[name]


def _lookup_classes(owner):
    """Where a method bound to `owner` is looked up (a type: also its metaclass)."""
    if isinstance(owner, type):  # a classmethod, e.g. dict.fromkeys
        return owner.__mro__ + type(owner).__mro__
    return type(owner).__mro__


def _canonical(obj):
    """The function, descriptor or class that runs when `obj` is called.

    Different paths to one function give different objects (a bound method,
    a classmethod bound to its class, a method found on a subclass). They
    all map to the one object stored in the namespace that defines it.
    """
    if isinstance(obj, (types.MethodType, staticmethod, classmethod)):
        return obj.__func__
    if isinstance(obj, types.BuiltinMethodType) and not (
        obj.__self__ is None or isinstance(obj.__self__, types.ModuleType)
    ):
        return _method(_lookup_classes(obj.__self__), obj.__name__, obj)[1]
    return obj


def _resolve(name):
    """The canonical object that a ground-truth name refers to, or None.

    `<builtin>.a.b` starts at the builtins module; any other name starts at
    the longest prefix that is an already imported module, so resolving
    imports nothing. Attributes are read without running code.
    """
    parts = name.split(".")
    if parts[0] == "<builtin>":
        obj, rest = builtins, parts[1:]
    else:
        prefixes = [
            n for n in range(len(parts), 0, -1) if ".".join(parts[:n]) in sys.modules
        ]
        if not prefixes:
            return None
        obj, rest = sys.modules[".".join(parts[: prefixes[0]])], parts[prefixes[0] :]
    try:
        for part in rest:
            obj = inspect.getattr_static(obj, part)
    except AttributeError:
        return None
    return _canonical(obj)


def _load(instruction, frame):
    """The value that a load instruction pushed, read again from `frame`."""
    name = instruction.argval
    if instruction.opname in ("LOAD_CONST", "LOAD_COMMON_CONSTANT", "LOAD_SMALL_INT"):
        return name
    if instruction.opname.startswith(("LOAD_FAST", "LOAD_DEREF")):
        return frame.f_locals[name]
    namespaces = [frame.f_globals, vars(builtins)]
    if instruction.opname != "LOAD_GLOBAL":
        namespaces.insert(0, frame.f_locals)
    for namespace in namespaces:
        if name in namespace:
            return namespace[name]
    raise KeyError(name)


class _External:
    """Stand-in for a name from a module that is not installed.

    Calling it records an edge to its dotted name (`ext.Cls`). Attributes
    extend the name (`ext.Cls.fun`), also on the object a call returns.
    """

    def __init__(self, name, tracer):
        self._name = name
        self._tracer = tracer

    def __getattr__(self, attr):
        if attr.startswith("__"):
            raise AttributeError(attr)
        return _External(f"{self._name}.{attr}", self._tracer)

    def __call__(self, *args, **kwargs):
        self._tracer.record_external(self._name)
        return _External(self._name, self._tracer)

    def __mro_entries__(self, bases):
        """Subclassing a stub gives a class named `ext.Base`, with an `__init__`."""
        name, tracer = self._name, self._tracer
        module, _, cls_name = name.rpartition(".")

        def __init__(instance, *args, **kwargs):
            pass

        __init__.__module__, __init__.__qualname__ = module, f"{cls_name}.__init__"

        def __getattr__(instance, attr):
            if attr.startswith("__"):
                raise AttributeError(attr)
            return _External(f"{name}.{attr}", tracer)

        namespace = {
            "__init__": __init__,
            "__getattr__": __getattr__,
            "__module__": module,
        }
        return (type(cls_name, (), namespace),)


class _ExternalFinder:
    """Last meta path entry: stub a module the snippet imports that does not exist."""

    def __init__(self, tracer):
        self.tracer = tracer

    def find_spec(self, fullname, path, target=None):
        parent = fullname.rpartition(".")[0]
        if parent and parent not in self.tracer.stubbed:
            return None  # a missing submodule of a real package is a real error
        frame = sys._getframe(1)
        while frame is not None and frame.f_code.co_filename.startswith(
            "<frozen importlib"
        ):
            frame = frame.f_back
        if frame is None or not self.tracer.in_snippet(frame.f_code.co_filename):
            return None  # a library probing for an optional module
        return importlib.machinery.ModuleSpec(fullname, self, is_package=True)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        name, tracer = module.__name__, self.tracer
        tracer.stubbed.add(name)

        def __getattr__(attr):
            if attr.startswith("__"):
                raise AttributeError(attr)
            return _External(f"{name}.{attr}", tracer)

        module.__getattr__ = __getattr__


def _describe_error(exc, case_dir):
    frames = [
        f
        for f in traceback.extract_tb(exc.__traceback__)
        if f.filename.startswith(case_dir + os.sep)
    ]
    where = (
        f" ({os.path.relpath(frames[-1].filename, case_dir)}:{frames[-1].lineno})"
        if frames
        else ""
    )
    return "".join(traceback.format_exception_only(exc)).strip() + where


def _top_level_modules(case_dir):
    """Names that `import` resolves to a file or package in the case directory."""
    for entry in os.scandir(case_dir):
        if entry.is_file() and entry.name.endswith(".py"):
            yield entry.name.removesuffix(".py")
        elif entry.is_dir() and os.path.isfile(os.path.join(entry.path, "__init__.py")):
            yield entry.name


def _run_snippet(case_dir, tracer):
    """Run main.py like `python main.py` would; return why it failed, or None."""
    main_path = os.path.join(case_dir, "main.py")
    with open(main_path, encoding="utf-8") as f:
        code = compile(f.read(), main_path, "exec")
    os.chdir(case_dir)
    sys.path.insert(0, case_dir)
    sys.argv = [main_path]
    sys.meta_path.append(_ExternalFinder(tracer))
    module = types.ModuleType("__main__")
    module.__file__ = main_path
    module.__builtins__ = builtins
    sys.modules["__main__"] = module

    tracer.start()
    try:
        exec(code, module.__dict__)  # noqa: S102 - running the snippet is the point
    except SystemExit as exc:
        if exc.code not in (None, 0):
            return f"SystemExit: {exc.code!r}"
    except BaseException as exc:  # noqa: BLE001 - any failure is reported
        return _describe_error(exc, case_dir)
    finally:
        tracer.stop()
    return None


def _run_child(case_dir, graph_path, out_path):
    with open(graph_path, encoding="utf-8") as f:
        graph = json.load(f)
    case_dir = os.path.realpath(case_dir)
    tracer = Tracer(case_dir)
    shadowed = sorted(
        name for name in _top_level_modules(case_dir) if name in sys.modules
    )
    if shadowed:
        error = (
            f"snippet modules have the names of loaded modules: {', '.join(shadowed)}"
        )
    else:
        error = _run_snippet(case_dir, tracer)
    if tracer.failures:
        error = "tracer error:\n" + "\n".join(tracer.failures)

    result = {
        "edges": sorted(tracer.named_edges(graph)),
        "modules": sorted(tracer.modules),
        "functions": sorted(tracer.functions),
        "stubbed": sorted(tracer.stubbed),
        "error": error,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f)


# --------------------------------------------------------------------------
# Parent process: compare the trace with the ground truth.
# --------------------------------------------------------------------------


def trace(case_dir, graph=None, timeout=TIMEOUT_SECONDS):
    """Run the snippet in `case_dir` in a child process and return its Trace.

    Callees outside the snippet get the name in `graph` (the ground truth)
    that resolves to them, if there is one.
    """
    case_dir = Path(case_dir).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        graph_path = Path(tmp) / "callgraph.json"
        graph_path.write_text(json.dumps(graph or {}), encoding="utf-8")
        out_path = Path(tmp) / "trace.json"
        command = [
            sys.executable,
            "-I",
            "-B",
            str(Path(__file__).resolve()),
            "--trace",
            str(case_dir),
            str(graph_path),
            str(out_path),
        ]
        try:
            proc = subprocess.run(
                command,
                check=False,
                cwd=case_dir,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return Trace(error=f"timed out after {timeout}s")
        if not out_path.exists():
            return Trace(
                error=f"tracer crashed (exit {proc.returncode}):\n"
                + proc.stderr.decode(errors="replace")
            )
        data = json.loads(out_path.read_text(encoding="utf-8"))
    return Trace(
        edges=frozenset(tuple(edge) for edge in data["edges"]),
        modules=frozenset(data["modules"]),
        functions=frozenset(data["functions"]),
        stubbed=frozenset(data["stubbed"]),
        error=data["error"]
        or (f"exit status {proc.returncode}" if proc.returncode else None),
    )


def load_ground_truth(case_dir):
    """Read callgraph.json: a JSON object that maps each node to a list of callees."""
    path = Path(case_dir) / "callgraph.json"
    graph = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(graph, dict) or not all(
        isinstance(callees, list) and all(isinstance(c, str) for c in callees)
        for callees in graph.values()
    ):
        raise ValueError(
            f"{path}: expected an object that maps names to lists of names"
        )
    return graph


def compare(observed, graph):
    """List the differences between a Trace and a ground-truth graph."""
    problems = []
    if observed.error:
        problems.append(f"snippet did not finish: {observed.error}")
    expected = {
        (caller, callee) for caller, callees in graph.items() for callee in callees
    }
    for caller, callee in sorted(observed.edges - expected):
        problems.append(f"missing edge: {caller} -> {callee}")
    unobserved = expected - observed.edges
    for caller, callee in sorted(unobserved):
        problems.append(f"unobserved edge: {caller} -> {callee}")
    nodes = (
        observed.modules
        | observed.functions
        | {node for edge in observed.edges for node in edge}
    )
    for node in sorted(nodes - graph.keys()):
        problems.append(f"missing node: {node}")
    explained = nodes | {node for edge in unobserved for node in edge}
    for node in sorted(graph.keys() - explained):
        problems.append(f"unexpected node: {node}")
    return problems


def validate(case_dir):
    """Return the problems found in one case (an empty list if it is correct)."""
    case_dir = Path(case_dir)
    for required in ("main.py", "callgraph.json"):
        if not (case_dir / required).is_file():
            return [f"{required} not found"]
    try:
        graph = load_ground_truth(case_dir)
    except ValueError as exc:  # json.JSONDecodeError is a ValueError
        return [f"bad callgraph.json: {exc}"]
    return compare(trace(case_dir, graph), graph)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "cases",
        nargs="*",
        type=Path,
        help="case directories (default: every case in snippets/)",
    )
    args = parser.parse_args(argv)
    cases = args.cases or sorted(
        path.parent for path in SNIPPETS_DIR.glob("*/*/main.py")
    )
    with ThreadPoolExecutor() as pool:
        results = list(pool.map(validate, cases))
    failed = 0
    for case, problems in zip(cases, results):
        label = (
            case.resolve().relative_to(SNIPPETS_DIR)
            if case.resolve().is_relative_to(SNIPPETS_DIR)
            else case
        )
        if problems:
            failed += 1
            print(f"{label}: FAIL")
            for problem in problems:
                print(f"    {problem}")
        elif args.cases:
            print(f"{label}: ok")
    print(f"{len(cases)} cases, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["--trace"]:  # internal: the child process entry point
        _run_child(*sys.argv[2:5])
    else:
        sys.exit(main())
