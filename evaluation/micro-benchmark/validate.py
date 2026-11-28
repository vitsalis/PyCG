#!/usr/bin/env python3
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

DESCRIPTION = """\
Check micro-benchmark ground truth against the calls a snippet really makes.

Each case runs in its own child process. The child traces the run with
sys.monitoring and names every call edge with the benchmark naming scheme
(see evaluation/micro-benchmark/README.md). A callee outside the snippet takes the
name from callgraph.json that resolves to the same function, so that
os.path.join matches posixpath.join. The child writes the edges to a JSON
file and the parent compares them with callgraph.json. The exit status is
1 if a case has a problem.
"""

SNIPPETS_DIR = Path(__file__).resolve().parent / "snippets"
TIMEOUT_SECONDS = 30
UNKNOWN_CALLER = "<unknown>"
CHILD_PROCESS_FLAG = "--trace"

_CODE_NAME_PREFIXES_TRANSPARENT = (
    "<genexpr>",
    "__annotate__",
    "<generic parameters of ",
)
_LAZY_SCOPE_PARAMETERS = (".format",)
_CODE_FLAGS_BODY_DEFERRED = (
    inspect.CO_GENERATOR
    | inspect.CO_COROUTINE
    | inspect.CO_ITERABLE_COROUTINE
    | inspect.CO_ASYNC_GENERATOR
)
_METHODS_CALLED_BY_WITH = {"__enter__", "__exit__", "__aenter__", "__aexit__"}
_DESCRIPTOR_TYPES = (
    types.MethodDescriptorType,
    types.ClassMethodDescriptorType,
    types.WrapperDescriptorType,
    types.MethodWrapperType,
)
_OPNAMES_LOAD_WITHOUT_SIDE_EFFECT = {
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
_OPNAMES_LOAD_TWO_FAST = {"LOAD_FAST_LOAD_FAST", "LOAD_FAST_BORROW_LOAD_FAST_BORROW"}
_STUB_CLASSES_MODULE = "validate"


class Trace(NamedTuple):
    edges: frozenset = frozenset()
    modules: frozenset = frozenset()
    functions: frozenset = frozenset()
    stubbed: frozenset = frozenset()
    error: str | None = None


class CodeNodes(NamedTuple):
    owner: str
    function: str | None


class Tracer:
    def __init__(self, case_dir):
        self.case_dir = case_dir
        self.edges = set()
        self.outside = {}
        self.modules = set()
        self.functions = set()
        self.stubbed = set()
        self._snippet_module_runtime_names = set()
        self.failures = []
        self._codes = {}
        self._codes_kept_alive = []
        self._snippet_files = {}
        self._instructions_by_code = {}
        self._source_lines_by_code = {}
        self._inlined_builtin_by_loop_offset_by_code = {}
        self._inlinable_calls_by_file = {}
        self._starter_scope_by_thread = {}

    def in_snippet(self, filename):
        if filename not in self._snippet_files:
            path = os.path.realpath(filename)
            self._snippet_files[filename] = path.endswith(".py") and path.startswith(
                self.case_dir + os.sep
            )
        return self._snippet_files[filename]

    def _register_module(self, code, module_runtime_name):
        self._snippet_module_runtime_names.add(module_runtime_name)
        path = os.path.relpath(os.path.realpath(code.co_filename), self.case_dir)
        parts = list(Path(path).with_suffix("").parts)
        if parts[-1] == "__init__" and len(parts) > 1:
            parts.pop()
        name = ".".join(parts)
        self.modules.add(name)
        self._add(code, name, None)
        self._register_nested_codes(code, name, name)

    def _register_nested_codes(self, code, scope, owner):
        lambdas = sorted(_lambdas_with_position(code), key=lambda item: item[0])
        lambda_numbers = {id(const): n for n, (_, const) in enumerate(lambdas, 1)}
        self._register_constants(code, scope, owner, lambda_numbers)

    def _register_constants(self, code, scope, owner, lambda_numbers):
        for const in code.co_consts:
            if not isinstance(const, types.CodeType):
                continue
            if _is_transparent(const):
                self._add(const, owner, None)
                self._register_constants(const, scope, owner, lambda_numbers)
                continue
            if const.co_name == "<lambda>":
                name = f"{scope}.<lambda{lambda_numbers[id(const)]}>"
            else:
                name = f"{scope}.{const.co_name}"
            is_function_or_lambda = bool(const.co_flags & inspect.CO_OPTIMIZED)
            if is_function_or_lambda:
                self.functions.add(name)
                self._add(const, name, name)
                self._register_nested_codes(const, name, name)
            else:
                self._add(const, owner, None)
                self._register_nested_codes(const, name, owner)

    def _add(self, code, owner, function):
        self._codes[id(code)] = CodeNodes(owner, function)
        self._codes_kept_alive.append(code)
        filename = code.co_filename
        if filename not in self._inlinable_calls_by_file:
            self._inlinable_calls_by_file[filename] = _inlinable_calls(filename)
        inlined_builtin_by_loop_offset = _inlined_builtin_by_loop_offset(
            code, self._inlinable_calls_by_file[filename]
        )
        if inlined_builtin_by_loop_offset:
            self._inlined_builtin_by_loop_offset_by_code[id(code)] = (
                inlined_builtin_by_loop_offset
            )

    def caller(self, frame):
        while frame is not None:
            entry = self._codes.get(id(frame.f_code))
            if entry is not None:
                return entry.owner
            frame = frame.f_back
        thread = threading.current_thread()
        starter = self._starter_scope_by_thread.get(id(thread))
        if starter is not None and starter[0] is thread:
            return starter[1]
        return UNKNOWN_CALLER

    def deferred_body_function(self, obj):
        if _is_a(obj, (types.MethodType, staticmethod, classmethod)):
            obj = obj.__func__
        if not _is_a(obj, types.FunctionType):
            return None
        entry = self._codes.get(id(obj.__code__))
        if entry is None or not obj.__code__.co_flags & _CODE_FLAGS_BODY_DEFERRED:
            return None
        return entry.function

    def outside_callee(self, obj):
        is_class_statement = obj is builtins.__build_class__
        if is_class_statement:
            return None
        stub = _stub_class_of(obj)
        if stub is not None:
            return vars(stub)["_stub_path"], None
        if _is_a(obj, (types.MethodType, staticmethod, classmethod)):
            obj = obj.__func__
        if _is_a(obj, types.FunctionType):
            code = obj.__code__
            if id(code) in self._codes:
                return None
            defined_by_exec_or_eval = code.co_filename == "<string>"
            if defined_by_exec_or_eval:
                return None
            method_of_stub_classes = code.co_filename == __file__
            if method_of_stub_classes:
                method_of_stub = obj.__module__ in self.stubbed
                if not method_of_stub:
                    return None
                return _dotted(obj.__module__, obj.__qualname__), None
            return _function_name(obj), obj
        if _is_a(obj, type):
            if self._is_snippet_class(obj):
                return self._inherited_outside_method(obj, "__init__")
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
            return _method_of_first_definer(obj.__objclass__.__mro__, obj.__name__, obj)
        if self._is_snippet_class(type(obj)):
            return self._inherited_outside_method(type(obj), "__call__")
        return f"{_class_name(type(obj))}.__call__", _call_of_instance(type(obj))

    def _inherited_outside_method(self, cls, name):
        owner = next((k for k in cls.__mro__ if name in vars(k)), None)
        if owner is None or owner is object or self._is_snippet_class(owner):
            return None
        nearest = next(k for k in cls.__mro__ if not self._is_snippet_class(k))
        return f"{_class_name(nearest)}.{name}", vars(owner)[name]

    def _instructions_and_index(self, code, offset):
        if id(code) not in self._instructions_by_code:
            instructions = list(dis.get_instructions(code))
            self._instructions_by_code[id(code)] = (
                instructions,
                {ins.offset: n for n, ins in enumerate(instructions)},
            )
        instructions, index_by_offset = self._instructions_by_code[id(code)]
        return instructions, index_by_offset.get(offset)

    def _is_with_call(self, code, offset):
        instructions, n = self._instructions_and_index(code, offset)
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
        instructions, n = self._instructions_and_index(code, offset)
        if n is None:
            return False
        position = instructions[n].positions
        return any(
            i.opname == "LOAD_COMMON_CONSTANT"
            and _common_constant_value(i) is AssertionError
            and i.positions == position
            for i in instructions
        )

    def _raises_class(self, code, offset, frame, cls):
        instructions, n = self._instructions_and_index(code, offset)
        if n is None or instructions[n].opname != "RAISE_VARARGS":
            return False
        before = instructions[:n]
        raises_from_cause = instructions[n].arg == 2
        if raises_from_cause:
            if before and before[-1].opname in _OPNAMES_LOAD_TWO_FAST:
                return frame.f_locals.get(before[-1].argval[0]) is cls
            if not before or before[-1].opname not in _OPNAMES_LOAD_WITHOUT_SIDE_EFFECT:
                return False
            before = before[:-1]
        elif instructions[n].arg != 1:
            return False
        attributes = []
        while before and before[-1].opname == "LOAD_ATTR":
            attributes.insert(0, before.pop().argval)
        if not before or before[-1].opname not in _OPNAMES_LOAD_WITHOUT_SIDE_EFFECT:
            return False
        try:
            value = _value_loaded_again(before[-1], frame)
            for attribute in attributes:
                value = inspect.getattr_static(value, attribute)
        except KeyError, AttributeError:
            return False
        return value is cls

    def _is_snippet_class(self, cls):
        return cls.__module__ in self._snippet_module_runtime_names

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
            if entry.function is None:
                self._record_inlined_call(frame.f_back)
                return None
            if not code.co_flags & _CODE_FLAGS_BODY_DEFERRED:
                self.edges.add((self.caller(frame.f_back), entry.function))
            elif code.co_flags & inspect.CO_COROUTINE:
                creator = self._coroutine_creator(frame)
                if creator is not None:
                    self.edges.add((creator, entry.function))
        except Exception:  # noqa: BLE001 - must not leak into the snippet
            self.failures.append(traceback.format_exc())
        return None

    def _record_inlined_call(self, frame):
        if frame is None:
            return
        inlined_builtin_by_loop_offset = (
            self._inlined_builtin_by_loop_offset_by_code.get(id(frame.f_code), {})
        )
        builtin = inlined_builtin_by_loop_offset.get(frame.f_lasti)
        if builtin is not None:
            owner = self._codes[id(frame.f_code)].owner
            self._record(owner, *self.outside_callee(builtin))

    def _coroutine_creator(self, frame):
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
        if id(code) not in self._source_lines_by_code:
            self._source_lines_by_code[id(code)] = {
                source_line for *_, source_line in code.co_lines()
            }
        if line in self._source_lines_by_code[id(code)]:
            return entry.owner
        return None

    def on_call(self, code, offset, callee, arg0):
        try:
            _track_coroutine_origins()
            entry = self._codes.get(id(code))
            if entry is not None:
                owner = entry.owner
            elif _is_eval_code(code):
                owner = self._owner_of_eval_code(sys._getframe(1))
            else:
                owner = None
            thread = _started_thread(callee, arg0)
            function = self.deferred_body_function(callee)
            if thread is not None or function is not None:
                scope = owner if owner is not None else self.caller(sys._getframe(1))
                if thread is not None:
                    self._starter_scope_by_thread[id(thread)] = (thread, scope)
                if function is not None:
                    self.edges.add((scope, function))
                    return None
            called_from_library_code = owner is None
            if called_from_library_code:
                return None
            found = self.outside_callee(callee)
            if found is None:
                return None
            name, target = found
            method = name.rpartition(".")[2]
            if method in _METHODS_CALLED_BY_WITH and self._is_with_call(code, offset):
                return None
            if target is AssertionError and self._is_assert_call(code, offset):
                return None
            self._record(owner, name, target)
        except Exception:  # noqa: BLE001 - must not leak into the snippet
            self.failures.append(traceback.format_exc())
        return None

    def on_raise(self, code, offset, exception):
        try:
            entry = self._codes.get(id(code))
            cls = type(exception)
            if entry is None or not self._is_snippet_class(cls):
                return
            if self._raises_class(code, offset, sys._getframe(1), cls):
                found = self._inherited_outside_method(cls, "__init__")
                if found is not None:
                    self._record(entry.owner, *found)
        except Exception:  # noqa: BLE001 - must not leak into the snippet
            self.failures.append(traceback.format_exc())

    def _record(self, caller, name, target):
        if target is None:
            self.edges.add((caller, name))
        else:
            target = _canonical(target)
            self.outside[(caller, id(target))] = (target, name)

    def named_edges(self, graph):
        own = self.modules | self.functions
        resolved = {}
        edges = set(self.edges)
        for (caller, _), (target, name) in self.outside.items():
            for candidate in sorted(set(graph.get(caller, ())) - own):
                if _names_target(candidate, target, resolved):
                    name = candidate
                    break
            edges.add((caller, name))
        return edges

    def _owner_of_eval_code(self, frame):
        while frame is not None and _is_eval_code(frame.f_code):
            frame = frame.f_back
        entry = self._codes.get(id(frame.f_code)) if frame is not None else None
        return entry.owner if entry is not None else None

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
    return issubclass(type(obj), classes)


def _track_coroutine_origins():
    if not sys.get_coroutine_origin_tracking_depth():
        sys.set_coroutine_origin_tracking_depth(1)


def _started_thread(callee, arg0):
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
        code.co_name.startswith(_CODE_NAME_PREFIXES_TRANSPARENT)
        or code.co_varnames[: code.co_argcount] == _LAZY_SCOPE_PARAMETERS
    )


def _lambdas_with_position(code):
    lambda_keyword_position_by_code = {}
    for instruction in dis.get_instructions(code):
        if isinstance(instruction.argval, types.CodeType):
            position = (instruction.positions.lineno, instruction.positions.col_offset)
            lambda_keyword_position_by_code.setdefault(id(instruction.argval), position)
    for const in code.co_consts:
        if not isinstance(const, types.CodeType):
            continue
        if _is_transparent(const):
            yield from _lambdas_with_position(const)
        elif const.co_name == "<lambda>":
            yield lambda_keyword_position_by_code[id(const)], const


def _inlinable_calls(path):
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


def _inlined_builtin_by_loop_offset(code, inlinable_calls):
    instructions = list(dis.get_instructions(code))
    loops = {}
    for n, (load, test, jump) in enumerate(
        zip(instructions, instructions[1:], instructions[2:])
    ):
        builtin = getattr(
            builtins, inlinable_calls.get(tuple(load.positions), ""), None
        )
        if (
            builtin is None
            or load.opname != "LOAD_COMMON_CONSTANT"
            or _common_constant_value(load) is not builtin
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


def _common_constant_value(instruction):
    return opcode._common_constants[instruction.arg]


def _loads_none(instruction):
    if instruction.opname == "LOAD_COMMON_CONSTANT":
        return _common_constant_value(instruction) is None
    return instruction.opname == "LOAD_CONST" and instruction.argval is None


def _is_eval_code(code):
    return code.co_filename == "<string>" and code.co_name == "<module>"


def _dotted(module, qualname):
    return f"{module}.{qualname.replace('<locals>.', '')}"


def _function_name(func):
    module = dict.get(func.__globals__, "__name__", func.__module__)
    return _dotted(module, func.__code__.co_qualname)


def _class_name(cls):
    if getattr(builtins, cls.__name__, None) is cls:
        return f"<builtin>.{cls.__name__}"
    return _dotted(cls.__module__, cls.__qualname__)


def _method_of_first_definer(classes, name, target_without_definer):
    owner = next((k for k in classes if name in vars(k)), None)
    if owner is None:
        return f"{_class_name(classes[0])}.{name}", target_without_definer
    return f"{_class_name(owner)}.{name}", vars(owner)[name]


def _builtin_method(method):
    owner, name = method.__self__, method.__name__
    for cls in _method_lookup_classes(owner):
        descriptor = vars(cls).get(name)
        if _builtin_descriptor_binds_to(descriptor, owner, method):
            return f"{_class_name(cls)}.{name}", descriptor
    return _method_of_first_definer(_method_lookup_classes(owner), name, method)


def _builtin_descriptor_binds_to(descriptor, owner, method):
    try:
        if _is_a(descriptor, types.BuiltinFunctionType):
            return descriptor == method
        if _is_a(descriptor, types.ClassMethodDescriptorType):
            cls = owner if _is_a(owner, type) else type(owner)
            return descriptor.__get__(None, cls) == method
        if _is_a(descriptor, types.MethodDescriptorType):
            return descriptor.__get__(owner) == method
    except TypeError:
        pass
    return False


def _method_lookup_classes(owner):
    if _is_a(owner, type):
        return owner.__mro__ + type(owner).__mro__
    return type(owner).__mro__


def _canonical(obj):
    if _is_a(obj, (types.MethodType, staticmethod, classmethod)):
        return obj.__func__
    if _is_a(obj, types.BuiltinMethodType) and not (
        obj.__self__ is None or _is_a(obj.__self__, types.ModuleType)
    ):
        return _builtin_method(obj)[1]
    return obj


class _CallOfInstance:
    __slots__ = ("cls",)

    def __init__(self, cls):
        self.cls = cls


_CALLS_OF_INSTANCES = {}


def _call_of_instance(cls):
    if cls not in _CALLS_OF_INSTANCES:
        _CALLS_OF_INSTANCES[cls] = _CallOfInstance(cls)
    return _CALLS_OF_INSTANCES[cls]


def _names_target(candidate, target, resolved):
    if _is_a(target, _CallOfInstance):
        owner, _, method = candidate.rpartition(".")
        return method == "__call__" and _resolved(owner, resolved) is target.cls
    return _resolved(candidate, resolved) is target


def _resolved(name, resolved):
    if name not in resolved:
        resolved[name] = _resolve_ground_truth_name(name)
    return resolved[name]


def _resolve_ground_truth_name(name):
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


def _value_loaded_again(instruction, frame):
    name = instruction.argval
    if instruction.opname == "LOAD_COMMON_CONSTANT":
        return _common_constant_value(instruction)
    if instruction.opname in ("LOAD_CONST", "LOAD_SMALL_INT"):
        return name
    local = frame.f_locals
    frame_of_module_or_class_body = not frame.f_code.co_flags & inspect.CO_OPTIMIZED
    if frame_of_module_or_class_body and not _is_a(local, dict):
        local = {}
    if instruction.opname.startswith(("LOAD_FAST", "LOAD_DEREF")):
        return _namespace_get(local, name)
    namespaces = [frame.f_globals, vars(builtins)]
    if instruction.opname != "LOAD_GLOBAL":
        namespaces.insert(0, local)
    for namespace in namespaces:
        try:
            return _namespace_get(namespace, name)
        except KeyError:
            pass
    raise KeyError(name)


def _namespace_get(namespace, name):
    if _is_a(namespace, dict):
        value = dict.get(namespace, name, _MISSING)
        if value is _MISSING:
            raise KeyError(name)
        return value
    return namespace[name]


_MISSING = object()


class _StubMeta(type):
    __module__ = _STUB_CLASSES_MODULE

    def __new__(mcs, name, bases, namespace, **kwargs):
        if "_stub_path" in namespace or "_stub_proxy" in namespace:
            return super().__new__(mcs, name, bases, namespace, **kwargs)
        bases = tuple(
            _proxy_for_snippet_classes(b) if "_stub_path" in vars(b) else b
            for b in bases
        )
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
        return super().__call__(*args, **kwargs)

    def __enter__(cls):
        return cls

    def __exit__(cls, *exc_info):
        return None

    def __iter__(cls):
        return iter(())


class _Stub(Exception, metaclass=_StubMeta):
    __module__ = _STUB_CLASSES_MODULE

    def __getattr__(self, attr):
        return _stub_attribute(type(self), attr)


@functools.cache
def _proxy_for_snippet_classes(stub):
    namespace = {
        "__module__": stub.__module__,
        "__qualname__": stub.__qualname__,
        "_stub_proxy": True,
    }
    return _StubMeta(stub.__name__, (stub,), namespace)


@functools.cache
def _stub(path):
    module, _, qualname = path.partition(".")
    namespace = {"__module__": module, "__qualname__": qualname, "_stub_path": path}
    stub = _StubMeta(qualname.rpartition(".")[2], (_Stub,), namespace)
    methods = {
        "__init__": lambda _: None,
        "__call__": lambda _: _new_stub_instance(path),
        "__enter__": lambda self: self,
        "__exit__": lambda _: None,
        "__iter__": lambda _: iter(()),
    }
    for name, result in methods.items():
        setattr(stub, name, _stub_method(stub, name, result))
    init_subclass_ignoring_keywords = _stub_method(
        stub, "__init_subclass__", lambda _: None
    )
    stub.__init_subclass__ = classmethod(init_subclass_ignoring_keywords)
    return stub


def _stub_method(stub, name, result):
    path = f"{vars(stub)['_stub_path']}.{name}"

    def method(self, *args, **kwargs):
        return result(self)

    method.__name__ = name
    method.__module__, _, method.__qualname__ = path.partition(".")
    return method


def _new_stub_instance(path):
    stub = _stub(path)
    return stub.__new__(stub)


def _stub_attribute(cls, attr):
    path = next(
        (vars(k)["_stub_path"] for k in cls.__mro__ if "_stub_path" in vars(k)), None
    )
    if path is None or attr.startswith("__"):
        raise AttributeError(attr)
    return _stub(f"{path}.{attr}")


def _stub_class_of(obj):
    cls = obj if _is_a(obj, type) else type(obj)
    if _is_a(cls, _StubMeta) and "_stub_path" in vars(cls):
        return cls
    return None


class _MissingModuleStubFinder:
    def __init__(self, tracer):
        self.tracer = tracer

    def find_spec(self, fullname, path, target=None):
        parent = fullname.rpartition(".")[0]
        submodule_of_real_package = parent and parent not in self.tracer.stubbed
        if submodule_of_real_package:
            return None
        frame = sys._getframe(1)
        while frame is not None and frame.f_code.co_filename.startswith(
            "<frozen importlib"
        ):
            frame = frame.f_back
        imported_by_snippet = frame is not None and self.tracer.in_snippet(
            frame.f_code.co_filename
        )
        if not imported_by_snippet:
            return None
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


def _case_top_level_module_names(case_dir):
    for entry in os.scandir(case_dir):
        if entry.is_file() and entry.name.endswith(".py"):
            yield entry.name.removesuffix(".py")
        elif entry.is_dir() and os.path.isfile(os.path.join(entry.path, "__init__.py")):
            yield entry.name


def _run_snippet_as_main(case_dir, tracer):
    main_path = os.path.join(case_dir, "main.py")
    with open(main_path, encoding="utf-8") as f:
        code = compile(f.read(), main_path, "exec")
    os.chdir(case_dir)
    sys.path.insert(0, case_dir)
    sys.argv = [main_path]
    sys.meta_path.append(_MissingModuleStubFinder(tracer))
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
        name for name in _case_top_level_module_names(case_dir) if name in sys.modules
    )
    if shadowed:
        error = (
            f"snippet modules have the names of loaded modules: {', '.join(shadowed)}"
        )
    else:
        error = _run_snippet_as_main(case_dir, tracer)
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


def trace(case_dir, graph=None, timeout=TIMEOUT_SECONDS):
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
            CHILD_PROCESS_FLAG,
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
    path = Path(case_dir) / "requires-python"
    if not path.is_file():
        return None
    version = path.read_text(encoding="utf-8").strip()
    if sys.version_info >= tuple(int(part) for part in version.split(".")):
        return None
    return f"needs Python {version}"


def validate(case_dir):
    case_dir = Path(case_dir)
    for required in ("main.py", "callgraph.json"):
        if not (case_dir / required).is_file():
            return [f"{required} not found"]
    try:
        graph = load_ground_truth(case_dir)
    except ValueError as exc:
        return [f"bad callgraph.json: {exc}"]
    return compare(trace(case_dir, graph), graph)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
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
    if sys.argv[1:2] == [CHILD_PROCESS_FLAG]:
        _run_child(*sys.argv[2:5])
    else:
        sys.exit(main())
