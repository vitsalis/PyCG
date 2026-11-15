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
import ast
import builtins
import dis
import functools
import importlib.machinery
import inspect
import json
import opcode
import os
import subprocess
import sys
import tempfile
import threading
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
# graph. Calls made in them belong to the enclosing scope. Besides these
# names, the lazily evaluated scopes of `type X = ...` values and of type
# parameter bounds, constraints and defaults are transparent: their only
# parameter is `.format`, a name that source code cannot use.
_TRANSPARENT_PREFIXES = ("<genexpr>", "__annotate__", "<generic parameters of ")
_LAZY_SCOPE_PARAMETERS = (".format",)
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
        # __name__ of each snippet module that ran ("__main__" for main.py):
        # the __module__ of the snippet's classes.
        self._module_names = set()
        self.failures = []  # tracebacks of errors inside the tracer itself
        # id(code) -> (owner, function). `owner` is the node that calls made
        # by this code belong to. `function` is the node for the code itself,
        # or None for modules, class bodies and transparent scopes.
        self._codes = {}
        self._alive = []  # keeps registered code objects alive, so ids stay unique
        self._snippet_files = {}
        self._instructions = {}  # id(code) -> {offset: (index, instructions)}
        self._lines = {}  # id(code) -> the source lines of its instructions
        # id(code) -> {offset of FOR_ITER: builtin} for inlined builtin calls,
        # and the source positions of the calls that can be inlined, per file.
        self._inlined = {}
        self._generator_calls = {}
        # id(thread) -> (thread, scope): the snippet scope that called the
        # thread's start(). Calls in that thread with no snippet frame on the
        # stack belong to that scope.
        self._thread_scopes = {}

    # -- naming -------------------------------------------------------------

    def in_snippet(self, filename):
        if filename not in self._snippet_files:
            path = os.path.realpath(filename)
            self._snippet_files[filename] = path.endswith(".py") and path.startswith(
                self.case_dir + os.sep
            )
        return self._snippet_files[filename]

    def _register_module(self, code, module_name):
        self._module_names.add(module_name)
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
        if code.co_filename not in self._generator_calls:
            self._generator_calls[code.co_filename] = _generator_calls(code.co_filename)
        loops = _inlined_calls(code, self._generator_calls[code.co_filename])
        if loops:
            self._inlined[id(code)] = loops

    def caller(self, frame):
        """The node of the nearest snippet frame, skipping library frames.

        In a thread without a snippet frame, it is the scope that started
        the thread.
        """
        while frame is not None:
            entry = self._codes.get(id(frame.f_code))
            if entry is not None:
                return entry[0]
            frame = frame.f_back
        thread = threading.current_thread()
        entry = self._thread_scopes.get(id(thread))
        if entry is not None and entry[0] is thread:
            return entry[1]
        return UNKNOWN_CALLER

    def deferred_function(self, obj):
        """The node of a snippet generator or coroutine function, or None.

        Calling one creates a generator or coroutine and does not run the
        body, so the call is recorded at the CALL event, not at PY_START.
        """
        if _is_a(obj, (types.MethodType, staticmethod, classmethod)):
            obj = obj.__func__
        if not _is_a(obj, types.FunctionType):
            return None
        entry = self._codes.get(id(obj.__code__))
        if entry is None or not obj.__code__.co_flags & _DEFERRED_BODY:
            return None
        return entry[1]  # None for a generator expression

    def callee(self, obj):
        """Classify a callable outside the snippet, seen at a CALL event.

        Return None to record nothing, or (name, target) for code outside the
        snippet. Snippet functions are recorded at PY_START instead, so that
        implicit calls and callbacks from builtins are seen too (see
        deferred_function for the exception).
        """
        if obj is builtins.__build_class__:
            return None  # a class statement
        stub = _stub_class(obj)
        if stub is not None:  # a stub or an instance of one: named by its path
            return vars(stub)["_stub_path"], None
        if _is_a(obj, (types.MethodType, staticmethod, classmethod)):
            obj = obj.__func__
        if _is_a(obj, types.FunctionType):
            if id(obj.__code__) in self._codes:
                return None  # a snippet function, seen at PY_START
            if obj.__code__.co_filename == "<string>":
                return None  # defined by exec or eval: there is no name for it
            if obj.__code__.co_filename == __file__:  # a method of a stub
                if obj.__module__ not in self.stubbed:
                    return None  # of _StubMeta or _Stub: not named, no edge
                return _dotted(obj.__module__, obj.__qualname__), None
            return _function_name(obj), obj
        if _is_a(obj, type):
            if self._is_snippet_class(obj):
                return self._outside_method(obj, "__init__")
            return _class_name(obj), obj
        if _is_a(obj, types.BuiltinFunctionType):
            owner = obj.__self__
            if owner is None or _is_a(owner, types.ModuleType):
                if getattr(builtins, obj.__name__, None) is obj:
                    return f"<builtin>.{obj.__name__}", obj
                module = owner.__name__ if owner is not None else obj.__module__
                return f"{module}.{obj.__name__}", obj
            return _builtin_method(obj)
        if _is_a(obj, _DESCRIPTOR_TYPES):
            return _method(obj.__objclass__.__mro__, obj.__name__, obj)
        if self._is_snippet_class(type(obj)):
            return self._outside_method(type(obj), "__call__")
        return _method(type(obj).__mro__, "__call__", obj)

    def _outside_method(self, cls, name):
        """(name, target) of the method that a snippet class inherits from outside.

        Instantiating a snippet class calls the first __init__ in its MRO, and
        calling an instance calls the first __call__. A snippet method is
        recorded at PY_START and object.__init__ gives no edge. Any other
        method is named through the nearest class of the MRO that is not in
        the snippet (`<builtin>.Exception.__init__`).
        """
        owner = next((k for k in cls.__mro__ if name in vars(k)), None)
        if owner is None or owner is object or self._is_snippet_class(owner):
            return None
        nearest = next(k for k in cls.__mro__ if not self._is_snippet_class(k))
        return f"{_class_name(nearest)}.{name}", vars(owner)[name]

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

        The statement fetches __enter__ and __exit__ with LOAD_SPECIAL
        (Python 3.14+) and calls __enter__ right after that. It calls
        __exit__ after loading None three times. These loads have the source
        position of the `with` item, like the LOAD_SPECIAL. An explicit call
        `item.__enter__()` can have that position too, but not these loads.
        """
        instructions, n = self._instruction(code, offset)
        if n is None:
            return False
        if n > 0 and instructions[n - 1].opname == "LOAD_SPECIAL":
            return True
        position = instructions[n].positions
        nones = instructions[max(n - 3, 0) : n]
        return (
            len(nones) == 3
            and all(_loads_none(i) and i.positions == position for i in nones)
            and any(
                i.opname == "LOAD_SPECIAL" and i.positions == position
                for i in instructions
            )
        )

    def _is_assert_call(self, code, offset):
        """Whether the CALL at `offset` creates the AssertionError of an `assert`.

        That CALL has the source position of the instruction that loads
        AssertionError, which only an `assert` statement loads as a common
        constant.
        """
        instructions, n = self._instruction(code, offset)
        if n is None:
            return False
        position = instructions[n].positions
        return any(
            i.opname == "LOAD_COMMON_CONSTANT"
            and _common_constant(i) is AssertionError
            and i.positions == position
            for i in instructions
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
        """Whether a snippet module defines `cls`, by its __module__.

        No attribute of the module object is read: a snippet can replace a
        module in sys.modules with an object that runs code on access.
        """
        return cls.__module__ in self._module_names

    # -- events -------------------------------------------------------------

    def on_start(self, code, offset):
        try:
            _track_coroutine_origins()
            entry = self._codes.get(id(code))
            frame = sys._getframe(1)
            if entry is None:
                if code.co_name == "<module>" and self.in_snippet(code.co_filename):
                    self._register_module(code, dict.get(frame.f_globals, "__name__"))
                    return None
                return sys.monitoring.DISABLE
            function = entry[1]
            if function is None:  # e.g. a generator expression
                self._record_inlined_call(frame.f_back)
                return None
            if not code.co_flags & _DEFERRED_BODY:
                self.edges.add((self.caller(frame.f_back), function))
            elif code.co_flags & inspect.CO_COROUTINE:
                creator = self._coroutine_creator(frame)
                if creator is not None:
                    self.edges.add((creator, function))
        except Exception:  # noqa: BLE001 - must not leak into the snippet
            self.failures.append(traceback.format_exc())
        return None

    def _record_inlined_call(self, frame):
        """Record the builtin call that `frame` inlines, if it runs now.

        An inlined builtin starts consuming its generator expression in the
        loop that replaces the call, after the argument is evaluated. So the
        generator expression starts while `frame` is at that loop's FOR_ITER.
        """
        if frame is None:
            return
        builtin = self._inlined.get(id(frame.f_code), {}).get(frame.f_lasti)
        if builtin is not None:
            owner = self._codes[id(frame.f_code)][0]
            self._record(owner, *self.callee(builtin))

    def _coroutine_creator(self, frame):
        """The scope that created the coroutine starting in `frame`, if it awaits it.

        The interpreter calls a coroutine method without a CALL event
        (`__anext__` in `async for`), and so does builtin code (`anext`). A
        coroutine records the file, line and function name of the frame that
        created it (cr_origin). If that is a line of the snippet code that
        awaits it, the edge belongs to the scope of that code. For a coroutine
        that a call expression there created, this gives the edge of the CALL
        event again.
        """
        origin = frame.f_generator.cr_origin
        awaiting = frame.f_back
        if not origin or awaiting is None:
            return None
        entry = self._codes.get(id(awaiting.f_code))
        if entry is None:
            return None
        code = awaiting.f_code
        filename, line, name = origin[0]
        if (filename, name) != (code.co_filename, code.co_name):
            return None
        if id(code) not in self._lines:
            self._lines[id(code)] = {line for *_, line in code.co_lines()}
        return entry[0] if line in self._lines[id(code)] else None

    def on_call(self, code, offset, callee, arg0):
        try:
            _track_coroutine_origins()
            entry = self._codes.get(id(code))
            if entry is not None:
                owner = entry[0]
            elif _is_eval_code(code):
                owner = self._eval_owner(sys._getframe(1))
            else:
                owner = None  # library code
            # CALL events in library code stay enabled: a call there can start
            # a thread or call a snippet generator function
            # (contextlib.contextmanager). Both belong to the snippet scope
            # whose library call made them run.
            thread = _started_thread(callee, arg0)
            function = self.deferred_function(callee)
            if thread is not None or function is not None:
                scope = owner if owner is not None else self.caller(sys._getframe(1))
                if thread is not None:
                    self._thread_scopes[id(thread)] = (thread, scope)
                if function is not None:
                    self.edges.add((scope, function))
                    return None
            if owner is None:
                return None  # other calls that library code makes are not edges
            found = self.callee(callee)
            if found is None:
                return None
            name, target = found
            method = name.rpartition(".")[2]
            if method in _WITH_METHODS and self._is_with_call(code, offset):
                return None  # made by a `with` statement, not a call expression
            if target is AssertionError and self._is_assert_call(code, offset):
                return None  # made by an `assert` statement
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
                found = self._outside_method(cls, "__init__")
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
        _track_coroutine_origins()

    def stop(self):
        sys.set_coroutine_origin_tracking_depth(0)
        sys.monitoring.set_events(sys.monitoring.PROFILER_ID, 0)
        sys.monitoring.free_tool_id(sys.monitoring.PROFILER_ID)


def _is_a(obj, classes):
    """isinstance() by the real type of `obj`.

    When the real type does not match, isinstance() reads obj.__class__,
    which runs a __class__ property of a snippet class (a lazy proxy). The
    tracer must not run snippet code.
    """
    return issubclass(type(obj), classes)


def _track_coroutine_origins():
    """Make coroutines created in this thread record their creator frame.

    The setting is per thread, so every event turns it on in the thread
    where it happens: a new thread gets an event (its first call) before it
    can create a coroutine. See Tracer._coroutine_creator.
    """
    if not sys.get_coroutine_origin_tracking_depth():
        sys.set_coroutine_origin_tracking_depth(1)


def _started_thread(callee, arg0):
    """The thread that a call of threading.Thread.start starts, or None.

    The CALL event comes before start() runs. start() raises RuntimeError
    if Thread.__init__ did not run or the thread is started already. These
    are its own checks, read statically: properties such as Thread.ident
    can raise on such a thread.
    """
    thread = arg0
    if _is_a(callee, types.MethodType):
        callee, thread = callee.__func__, callee.__self__
    if callee is not threading.Thread.start or thread is sys.monitoring.MISSING:
        return None
    initialized = inspect.getattr_static(thread, "_initialized", False)
    started = inspect.getattr_static(thread, "_started", None)
    if initialized is not True or inspect.getattr_static(started, "_flag", True):
        return None
    return thread


def _is_transparent(code):
    return (
        code.co_name.startswith(_TRANSPARENT_PREFIXES)
        or code.co_varnames[: code.co_argcount] == _LAZY_SCOPE_PARAMETERS
    )


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


def _generator_calls(path):
    """{source position of the name: name} for each call `name(<genexpr>)` in a file.

    These are the calls that the compiler can inline (see _inlined_calls). A
    position is (line, end line, column, end column), as in dis.Positions.
    """
    tree = ast.parse(Path(path).read_bytes())
    return {
        (
            call.func.lineno,
            call.func.end_lineno,
            call.func.col_offset,
            call.func.end_col_offset,
        ): call.func.id
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and len(call.args) == 1
        and not call.keywords
        and isinstance(call.args[0], ast.GeneratorExp)
    }


def _inlined_calls(code, calls):
    """{offset of FOR_ITER: builtin} for the builtin calls that `code` inlines.

    For a call `name(<genexpr>)` of any(), all(), tuple() and, from Python
    3.15, list() and set(), Python 3.14+ compiles a check `name is builtin`
    (LOAD_COMMON_CONSTANT, IS_OP 0, POP_JUMP_IF_FALSE to the real call) and
    a loop in place of the call. The check and the FOR_ITER of the loop have
    the source position of the name. `calls` gives the positions of such
    calls in the source (see _generator_calls).
    """
    instructions = list(dis.get_instructions(code))
    loops = {}
    for n, (load, test, jump) in enumerate(
        zip(instructions, instructions[1:], instructions[2:])
    ):
        builtin = getattr(builtins, calls.get(tuple(load.positions), ""), None)
        if (
            builtin is None
            or load.opname != "LOAD_COMMON_CONSTANT"
            or _common_constant(load) is not builtin
            or (test.opname, test.arg, jump.opname) != ("IS_OP", 0, "POP_JUMP_IF_FALSE")
        ):
            continue
        for loop in instructions[n + 3 :]:
            if loop.offset >= jump.jump_target:
                break
            if loop.opname == "FOR_ITER" and loop.positions == load.positions:
                loops[loop.offset] = builtin
                break
    return loops


def _common_constant(instruction):
    """The value that a LOAD_COMMON_CONSTANT instruction loads."""
    return opcode._common_constants[instruction.arg]


def _loads_none(instruction):
    if instruction.opname == "LOAD_COMMON_CONSTANT":  # Python 3.15+
        return _common_constant(instruction) is None
    return instruction.opname == "LOAD_CONST" and instruction.argval is None


def _is_eval_code(code):
    return code.co_filename == "<string>" and code.co_name == "<module>"


def _dotted(module, qualname):
    return f"{module}.{qualname.replace('<locals>.', '')}"


def _function_name(func):
    """The name of a function outside the snippet, from where it is defined.

    Wrappers made with functools.wraps carry the __module__ and __qualname__
    of the function they wrap, so the name comes from the module whose
    globals the function uses and from the qualified name of its code
    (`contextlib.contextmanager.helper`). It is the name of an edge only when
    no expected name resolves to the function (see named_edges).
    """
    module = dict.get(func.__globals__, "__name__", func.__module__)
    return _dotted(module, func.__code__.co_qualname)


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


def _builtin_method(method):
    """(name, target) of a builtin method bound to a class or an instance.

    The first class that defines the name in the lookup order can be a
    snippet class that overrides the method (`super().__init_subclass__()`
    in an `__init_subclass__`). The definer is the first class whose
    descriptor gives this method when bound to the same object.
    """
    owner, name = method.__self__, method.__name__
    for cls in _lookup_classes(owner):
        descriptor = vars(cls).get(name)
        if _binds_to(descriptor, owner, method):
            return f"{_class_name(cls)}.{name}", descriptor
    return _method(_lookup_classes(owner), name, method)


def _binds_to(descriptor, owner, method):
    """Whether a builtin `descriptor`, bound to `owner`, is the builtin `method`.

    Two builtin methods are equal if they have the same self and the same C
    function. Only builtin descriptors are bound, so no snippet code runs.
    """
    try:
        if _is_a(descriptor, types.BuiltinFunctionType):  # e.g. __new__
            return descriptor == method
        if _is_a(descriptor, types.ClassMethodDescriptorType):
            cls = owner if _is_a(owner, type) else type(owner)
            return descriptor.__get__(None, cls) == method
        if _is_a(descriptor, types.MethodDescriptorType):
            return descriptor.__get__(owner) == method
    except TypeError:  # owner is not an instance or subclass of the definer
        pass
    return False


def _lookup_classes(owner):
    """Where a method bound to `owner` is looked up (a type: also its metaclass)."""
    if _is_a(owner, type):  # a classmethod, e.g. dict.fromkeys
        return owner.__mro__ + type(owner).__mro__
    return type(owner).__mro__


def _canonical(obj):
    """The function, descriptor or class that runs when `obj` is called.

    Different paths to one function give different objects (a bound method,
    a classmethod bound to its class, a method found on a subclass). They
    all map to the one object stored in the namespace that defines it.
    """
    if _is_a(obj, (types.MethodType, staticmethod, classmethod)):
        return obj.__func__
    if _is_a(obj, types.BuiltinMethodType) and not (
        obj.__self__ is None or _is_a(obj.__self__, types.ModuleType)
    ):
        return _builtin_method(obj)[1]
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
    """The value that a load instruction pushed, read again from `frame`.

    No snippet code runs. The variables of a function are read through the
    frame. A namespace is read as a plain dict, and only if it is a dict: a
    class body can have a mapping from __prepare__ with snippet methods.
    """
    name = instruction.argval
    if instruction.opname == "LOAD_COMMON_CONSTANT":
        return _common_constant(instruction)
    if instruction.opname in ("LOAD_CONST", "LOAD_SMALL_INT"):
        return name
    local = frame.f_locals
    if not frame.f_code.co_flags & inspect.CO_OPTIMIZED and not _is_a(local, dict):
        local = {}  # a class namespace that is not a dict
    if instruction.opname.startswith(("LOAD_FAST", "LOAD_DEREF")):
        return _get(local, name)
    namespaces = [frame.f_globals, vars(builtins)]
    if instruction.opname != "LOAD_GLOBAL":
        namespaces.insert(0, local)
    for namespace in namespaces:
        try:
            return _get(namespace, name)
        except KeyError:
            pass
    raise KeyError(name)


def _get(namespace, name):
    """namespace[name], with dict methods for a dict (also of a subclass).

    Any other namespace is the C proxy of a function's variables.
    """
    if _is_a(namespace, dict):
        # dict.__getitem__ would still call a __missing__ of the subclass.
        value = dict.get(namespace, name, _MISSING)
        if value is _MISSING:
            raise KeyError(name)
        return value
    return namespace[name]


_MISSING = object()


class _StubMeta(type):
    """Metaclass of the stubs that stand in for names of missing modules.

    The stub for `ext.Cls` is a class with that dotted path. It derives from
    Exception, so the snippet can raise and catch it. A stub and an instance
    of a stub behave the same way:

    - An attribute is the stub with the longer path (`ext.Cls.fun`), unless
      its name starts with `__` or BaseException or type defines it (`args`,
      `mro`).
    - A call returns an instance of the stub. It calls none of its arguments.
    - In a `with` statement, it gives itself and lets exceptions through.
    - Iteration gives no items.

    Calls of stubs are recorded at CALL events, like other calls of code
    outside the snippet. A snippet class that derives from a stub inherits
    the stub `__init__` and `__init_subclass__` (see __new__ for `super()`).
    """

    # Not __main__: in the child process, that is the snippet's module.
    __module__ = "validate"

    def __new__(mcs, name, bases, namespace, **kwargs):
        """Create a stub, a proxy, or a snippet class that derives from stubs.

        A snippet class derives from the proxy of a stub in place of the
        stub: one subclass of the stub, with its name, that all snippet
        classes share. So the MRO and duplicate bases are as for a real base.
        For each name that a snippet class defines, the proxy holds the stub
        with the longer path, so `super().name` finds it. That is the object
        that attribute lookup on the stub gives, so the shared names change
        no attribute; names that the stub's own classes define are left out.
        The names are in place before type.__new__ runs any class hook.
        """
        if "_stub_path" in namespace or "_stub_proxy" in namespace:
            return super().__new__(mcs, name, bases, namespace, **kwargs)
        bases = tuple(_proxy(b) if "_stub_path" in vars(b) else b for b in bases)
        proxy = next(
            (k for b in bases for k in b.__mro__ if "_stub_proxy" in vars(k)), None
        )
        if proxy is not None:
            for attr in namespace:
                if attr.startswith("__"):
                    continue
                if all(attr not in vars(k) for k in proxy.__mro__):
                    setattr(proxy, attr, _stub_attribute(proxy, attr))
        return super().__new__(mcs, name, bases, namespace, **kwargs)

    def __getattr__(cls, attr):
        return _stub_attribute(cls, attr)

    def __call__(cls, *args, **kwargs):
        if "_stub_path" in vars(cls):
            return cls.__new__(cls)
        return super().__call__(*args, **kwargs)  # a snippet subclass

    def __enter__(cls):
        return cls

    def __exit__(cls, *exc_info):
        return None

    def __iter__(cls):
        return iter(())


class _Stub(Exception, metaclass=_StubMeta):
    """Base class of the stubs (see _StubMeta)."""

    __module__ = "validate"

    def __getattr__(self, attr):
        return _stub_attribute(type(self), attr)


@functools.cache
def _proxy(stub):
    """The subclass of `stub`, with its name, for snippet classes (see __new__)."""
    namespace = {
        "__module__": stub.__module__,
        "__qualname__": stub.__qualname__,
        "_stub_proxy": True,
    }
    return _StubMeta(stub.__name__, (stub,), namespace)


@functools.cache
def _stub(path):
    """The stub for the dotted path `path` (see _StubMeta)."""
    module, _, qualname = path.partition(".")
    namespace = {"__module__": module, "__qualname__": qualname, "_stub_path": path}
    stub = _StubMeta(qualname.rpartition(".")[2], (_Stub,), namespace)
    methods = {
        "__init__": lambda _: None,
        "__call__": lambda _: _new(path),
        "__enter__": lambda self: self,
        "__exit__": lambda _: None,
        "__iter__": lambda _: iter(()),
    }
    for name, result in methods.items():
        setattr(stub, name, _stub_method(stub, name, result))
    # Class keyword arguments are for the missing base class: ignored.
    hook = _stub_method(stub, "__init_subclass__", lambda _: None)
    stub.__init_subclass__ = classmethod(hook)
    return stub


def _stub_method(stub, name, result):
    """A method `name` of `stub`, `ext.Cls.name`, that returns result(self).

    Its __module__ and __qualname__ give the name that a call of it records.
    """
    path = f"{vars(stub)['_stub_path']}.{name}"

    def method(self, *args, **kwargs):
        return result(self)

    method.__name__ = name
    method.__module__, _, method.__qualname__ = path.partition(".")
    return method


def _new(path):
    """A new instance of the stub for `path`."""
    stub = _stub(path)
    return stub.__new__(stub)


def _stub_attribute(cls, attr):
    """Attribute `attr` of a stub, of a snippet subclass, or of their instances."""
    path = next(
        (vars(k)["_stub_path"] for k in cls.__mro__ if "_stub_path" in vars(k)), None
    )
    if path is None or attr.startswith("__"):
        raise AttributeError(attr)
    return _stub(f"{path}.{attr}")


def _stub_class(obj):
    """The stub that `obj` is or is an instance of, or None."""
    cls = obj if _is_a(obj, type) else type(obj)
    if _is_a(cls, _StubMeta) and "_stub_path" in vars(cls):
        return cls
    return None


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
        name = module.__name__
        self.tracer.stubbed.add(name)

        def __getattr__(attr):
            if attr.startswith("__"):
                raise AttributeError(attr)
            return _stub(f"{name}.{attr}")

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


def version_skip_reason(case_dir):
    """Why this interpreter cannot run the case (its `requires-python`), or None."""
    path = Path(case_dir) / "requires-python"
    if not path.is_file():
        return None
    version = path.read_text(encoding="utf-8").strip()
    if sys.version_info >= tuple(int(part) for part in version.split(".")):
        return None
    return f"needs Python {version}"


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
    skips = {case: version_skip_reason(case) for case in cases}
    runnable = [case for case in cases if skips[case] is None]
    with ThreadPoolExecutor() as pool:
        results = dict(zip(runnable, pool.map(validate, runnable)))
    failed = skipped = 0
    for case in cases:
        label = (
            case.resolve().relative_to(SNIPPETS_DIR)
            if case.resolve().is_relative_to(SNIPPETS_DIR)
            else case
        )
        if skips[case]:
            skipped += 1
            print(f"{label}: skipped ({skips[case]})")
        elif results[case]:
            failed += 1
            print(f"{label}: FAIL")
            for problem in results[case]:
                print(f"    {problem}")
        elif args.cases:
            print(f"{label}: ok")
    print(f"{len(cases)} cases, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["--trace"]:  # internal: the child process entry point
        _run_child(*sys.argv[2:5])
    else:
        sys.exit(main())
