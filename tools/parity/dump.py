import argparse
import ast
import copy
import functools
import hashlib
import importlib.util
import inspect
import json
import os
import resource
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import FunctionType, MethodType

DESCRIPTION = """\
Writes the parity dumps of the Python engine (docs/rust/PLAN.md, section 3).

    dump.py input --checkout PATH --out DIR --package ROOT ENTRY...
        one input: D1.jsonl to D5.jsonl, D6.json and modules.tsv in DIR;
        modules.tsv has each module built, in build order, and its file
        relative to the checkout, from which pycg_dump d1 writes D1
    dump.py oracle --checkout PATH --out DIR [--set micro|macro]... [--name INPUT]...
        every input of the sets for hash seeds 0 and 1, in DIR/seed-<s>/<input>/,
        then checks that both seeds give the same D1 to D6, byte for byte
    dump.py key --checkout PATH
        the key of an oracle run: the git objects of KEYED_PATHS at HEAD (the
        engine, this harness, the micro cases and the runner that lists the
        inputs) and the inputs key, which pins the Python image by its digest
        and the macro projects

The engine is not changed: this process wraps its methods while it runs.
"""

DUMPS = ("D1", "D2", "D3", "D4", "D5", "D6")
MODULES = "modules.tsv"
SEEDS = (0, 1)
KEYED_PATHS = (
    "pycg",
    "tools/parity",
    "evaluation/micro-benchmark/snippets",
    "evaluation/common/run.py",
)
SETS = ("micro", "macro")
INTERPRETER_FLAGS_ISOLATED = ("-S", "-s", "-P", "-B")
STUB_METHODS = (
    "module",
    "find",
    "attribute",
    "metaclass_member",
    "metaclass",
    "member",
    "definition",
    "mro",
    "abstract",
    "abstract_reach",
    "abc_name",
    "public_name",
)
SOLVER_CALLS = (
    "constant",
    "add_object",
    "add_edge",
    "attach",
    "apply_now",
    "follower",
    "objects",
    "holds",
    "is_saturated",
)
SOLVER_ANSWERS = frozenset({"constant", "follower", "objects", "holds", "is_saturated"})
ENTRIES = "entries.txt"
BUILDER_IMPORT_CALLS = ("handle_import", "locate")
BUILDER_TABLES = (
    "iterated_expressions",
    "literal_imports",
    "none_arguments",
    "none_keywords",
    "read_namespaces",
    "zero_argument_super",
)
BUILDER_FIELDS = {
    "Module": ("defines",),
    "Function": (
        "decorated",
        "lineno",
        "col_offset",
        "end_lineno",
        "end_col_offset",
        "is_async",
        "annotations",
        "passthrough",
    ),
    "Class": (
        "lineno",
        "end_lineno",
        "allocator",
        "slots",
        "bound",
        "defines",
        "annotations",
    ),
}


def canonical_line(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"


class Names:
    def __init__(self, model, solver, semantics):
        self.model = model
        self.solver = solver
        self.semantics = semantics
        self.context = "<program>"
        self._node_names = {}
        self._label_counts = {}
        self._context_counts = {}
        self._object_names = {}
        self._object_counts = {}
        self._other_names = {}
        self._other_counts = {}

    def new_node(self, node):
        label = getattr(node, "label", None)
        if label is not None:
            count = self._label_counts.get(label, 0) + 1
            self._label_counts[label] = count
            name = label if count == 1 else f"{label}~{count}"
        else:
            count = self._context_counts.get(self.context, 0) + 1
            self._context_counts[self.context] = count
            name = f"{self.context}#{count}"
        self._node_names[node] = name
        return name

    def node(self, node):
        name = self._node_names.get(node)
        if name is None:
            name = self.new_node(node)
        return name

    def new_object(self, obj):
        key = f"{type(obj).__name__}:{obj.name}"
        count = self._object_counts.get(key, 0) + 1
        self._object_counts[key] = count
        name = key if count == 1 else f"{key}~{count}"
        self._object_names[obj] = name
        return name

    def object(self, obj):
        name = self._object_names.get(obj)
        if name is None:
            name = self.new_object(obj)
        return name

    def other(self, value, key):
        name = self._other_names.get(value)
        if name is None:
            count = self._other_counts.get(key, 0) + 1
            self._other_counts[key] = count
            name = key if count == 1 else f"{key}~{count}"
            self._other_names[value] = name
        return name

    def nodes(self):
        return self._node_names

    def canon(self, value):
        if value is None or isinstance(value, (bool, str)):
            return value
        if isinstance(value, int):
            return value if abs(value) < 1 << 53 else {"int": str(value)}
        if isinstance(value, float):
            return {"float": repr(value)}
        if isinstance(value, (bytes, bytearray)):
            return {"bytes": bytes(value).hex()}
        if isinstance(value, complex):
            return {"complex": repr(value)}
        if value is Ellipsis:
            return {"ellipsis": True}
        if isinstance(value, (self.solver.Node, self.solver.Constant)):
            return {"node": self.node(value)}
        if isinstance(value, self.model.Object):
            return {"object": self.object(value)}
        if isinstance(value, ast.AST):
            return {"ast": ast_position(value)}
        if isinstance(value, (tuple, list)):
            return [self.canon(item) for item in value]
        if isinstance(value, (set, frozenset)):
            items = [self.canon(item) for item in value]
            return {"set": sorted(items, key=canonical_line)}
        if isinstance(value, dict):
            return {"dict": [[self.canon(k), self.canon(v)] for k, v in value.items()]}
        if isinstance(value, (FunctionType, MethodType, functools.partial)):
            function = getattr(value, "__func__", value)
            function = getattr(function, "func", function)
            return {"function": getattr(function, "__qualname__", repr(function))}
        if isinstance(value, type):
            return {"type": value.__qualname__}
        if isinstance(value, self.semantics.Call):
            return {"call": self.other(value, f"Call:{value.site}")}
        if isinstance(value, self.solver.Constraint):
            return {"constraint": self.constraint(value)}
        if isinstance(value, self.model.Signature):
            return {
                "signature": {
                    "positional": list(value.positional),
                    "positional_only_count": value.positional_only_count,
                    "keyword_only": list(value.keyword_only),
                    "vararg": value.vararg,
                    "kwarg": value.kwarg,
                }
            }
        if hasattr(value, "kind") and hasattr(value, "local_name"):
            return {"scope": f"{value.kind}:{value.name}"}
        return {"value": self.other(value, type(value).__qualname__)}

    def constraint(self, constraint):
        if isinstance(constraint, self.solver.Each):
            rule = getattr(constraint.function, "__wrapped__", constraint.function)
            key = f"Each:{rule.__qualname__}"
        elif isinstance(constraint, self.semantics.Call):
            key = f"Call:{constraint.site}"
        else:
            key = type(constraint).__qualname__
        return self.other(constraint, key)


def ast_position(node):
    position = [type(node).__name__]
    if hasattr(node, "lineno"):
        position += [
            node.lineno,
            node.col_offset,
            getattr(node, "end_lineno", None),
            getattr(node, "end_col_offset", None),
        ]
    return position


def identifier_fields(node):
    found = {}
    if isinstance(node, ast.Constant):
        return found
    for field, value in ast.iter_fields(node):
        if field == "type_comment":
            continue
        if isinstance(value, str):
            found[field] = value
        elif (
            isinstance(value, list)
            and value
            and all(isinstance(item, str) for item in value)
        ):
            found[field] = value
    return found


class Writer:
    def __init__(self, path):
        self.file = open(path, "w", encoding="utf-8")

    def write(self, record):
        self.file.write(canonical_line(record))

    def close(self):
        self.file.close()


class Recorder:
    def __init__(self, out, checkout):
        from pycg.analysis import (
            builder,
            imports,
            model,
            program,
            scopes,
            semantics,
            solver,
            stubs,
        )

        self.builder = builder
        self.imports = imports
        self.model = model
        self.program = program
        self.scopes = scopes
        self.semantics = semantics
        self.solver = solver
        self.stubs = stubs
        self.names = Names(model, solver, semantics)
        self.out = Path(out)
        self.writers = {
            dump: Writer(self.out / f"{dump}.jsonl") for dump in DUMPS if dump != "D6"
        }
        self.inside_solver = False
        self.building = None
        self.builder_depth = 0
        self.first_rounds = {}
        self.round = 0
        self.analysis = None
        self.scopes_by_module = {}
        self.checkout = os.path.realpath(checkout)
        self.module_files = []
        self.stub_depth = 0
        self.witness_of_watch = {}
        self.declared = {}
        self.built_objects = []

    def close(self):
        for writer in self.writers.values():
            writer.close()
        lines = "".join(f"{name}\t{path}\n" for name, path in self.module_files)
        (self.out / MODULES).write_text(lines, encoding="utf-8")

    def install(self):
        self._install_names()
        self._install_program()
        self._install_stubs()
        self._install_solver()
        self._install_constraints()
        self._install_builder_calls()
        self._guard_builder_writes()

    def _install_names(self):
        names = self.names
        solver = self.solver
        recorder = self

        def wrap_init(cls, after):
            original = cls.__init__

            @functools.wraps(original)
            def init(self, *args, **kwargs):
                original(self, *args, **kwargs)
                after(self)

            cls.__init__ = init

        def new_node(node):
            name = names.new_node(node)
            if not recorder.inside_solver:
                record = {"op": "node", "node": name}
                if node.label is not None:
                    record["named"] = True
                if type(node) is solver.Witness:
                    record["witness"] = True
                recorder.writers["D3"].write(record)

        def new_witness(witness):
            recorder.witness_of_watch[witness.watch] = names.node(witness)

        def new_object(obj):
            names.new_object(obj)
            if recorder.building is not None and type(obj).__name__ in BUILDER_FIELDS:
                recorder.built_objects.append(obj)

        wrap_init(solver.Node, new_node)
        wrap_init(solver.Witness, new_witness)
        wrap_init(solver.Constant, names.new_node)
        wrap_init(self.model.Object, new_object)
        wrap_init(self.model.Const, names.new_object)
        wrap_init(self.semantics.Call, names.constraint)

        def recorded_each(each):
            names.constraint(each)
            each.function = recorder.applying(each.function, each)

        wrap_init(solver.Each, recorded_each)

    def _install_program(self):
        recorder = self
        Program = self.program.Program
        original_build = Program._build
        original_analyse_scopes = self.builder.analyse_scopes

        def build(program, name, path):
            recorder.names.context = name
            recorder.building = name
            recorder.analysis = program.analysis
            recorder.tables_before = {
                table: copy.copy(getattr(program.analysis, table))
                for table in BUILDER_TABLES
            }
            try:
                return original_build(program, name, path)
            finally:
                recorder.write_builder_fields(program, name)
                recorder.building = None
                recorder.names.context = "<program>"
                recorder.write_module(program, name, path)

        def analyse_scopes(tree, module_name):
            found = original_analyse_scopes(tree, module_name)
            recorder.scopes_by_module.setdefault(module_name, found)
            return found

        Program._build = build
        self.builder.analyse_scopes = analyse_scopes
        original_solve = self.semantics.Analysis.solve

        def solve(analysis):
            recorder.names.context = "<solve>"
            return original_solve(analysis)

        self.semantics.Analysis.solve = solve

    def write_builder_fields(self, program, name):
        built, self.built_objects = self.built_objects, []
        source = program.modules.get(name)
        if source is None or source.status == "failed":
            return
        tables = {}
        for table, before in self.tables_before.items():
            now = getattr(program.analysis, table)
            if isinstance(now, dict):
                added = {key: value for key, value in now.items() if key not in before}
            else:
                added = {item for item in now if item not in before}
            tables[table] = self.names.canon(added)
        self.writers["D4"].write({"module": name, "tables": tables})
        module = program.analysis.modules.get(name)
        if module is not None and module not in built:
            built.insert(0, module)
        for obj in built:
            fields = BUILDER_FIELDS[type(obj).__name__]
            self.writers["D4"].write(
                {
                    "module": name,
                    "object": self.names.canon(obj),
                    "fields": {
                        field: self.names.canon(getattr(obj, field)) for field in fields
                    },
                }
            )

    def _guard_builder_writes(self):
        recorder = self
        for type_name, fields in BUILDER_FIELDS.items():
            cls = getattr(self.model, type_name)
            original = cls.__setattr__

            def guarded(obj, field, value, _original=original, _fields=fields):
                if recorder.building is not None and not recorder.builder_depth:
                    assert field in _fields, (
                        f"the builder writes {type(obj).__name__}.{field}, "
                        "which BUILDER_FIELDS does not record"
                    )
                _original(obj, field, value)

            cls.__setattr__ = guarded

    def write_module(self, program, name, path):
        relative = os.path.relpath(os.path.realpath(path), self.checkout)
        assert "\t" not in relative and "\n" not in relative, relative
        self.module_files.append((name, relative))
        module = program.modules[name]
        writer = self.writers["D1"]
        writer.write({"module": name, "status": module.status, "cause": module.cause})
        if module.status == "failed":
            return
        source, _ = self.program._read(path)
        tree, _ = self.program._parse(source, path)
        for node in ast.walk(tree):
            if hasattr(node, "lineno"):
                record = {"module": name, "position": ast_position(node)}
                identifiers = identifier_fields(node)
                if identifiers:
                    record["identifiers"] = identifiers
                writer.write(record)
        found = self.scopes_by_module.pop(name, None)
        if found is not None:
            self.write_scopes(name, found)

    def write_scopes(self, module_name, found):
        writer = self.writers["D1"]
        canon = self.names.canon
        for scope in found.scopes:
            node = scope.node
            writer.write(
                {
                    "module": module_name,
                    "scope": {
                        "kind": scope.kind,
                        "name": scope.name,
                        "local_name": scope.local_name,
                        "private_class": scope.private_class,
                        "position": ast_position(node),
                        "parent": None if scope.parent is None else scope.parent.name,
                        "generator": scope.generator,
                        "asynchronous": scope.asynchronous,
                        "star_import": scope.star_import,
                        "dynamic": scope.dynamic,
                        "bound": list(scope.bound),
                        "defined": list(scope.defined),
                        "globals": sorted(scope.globals),
                        "nonlocals": sorted(scope.nonlocals),
                        "rebound": sorted(scope.rebound),
                        "shared": sorted(scope.shared),
                        "imports": canon(scope.imports),
                        "definitions": canon(scope.definitions),
                        "reads": {
                            read: found.resolve(scope, read).name
                            for read in sorted(scope.reads)
                        },
                    },
                }
            )
        for loop, bindings in found._loops.items():
            writer.write(
                {
                    "module": module_name,
                    "loop": ast_position(loop),
                    "bindings": canon(bindings),
                }
            )
        writer.write(
            {
                "module": module_name,
                "unread_lazy": sorted(
                    ast_position(alias) for alias in found.unread_lazy
                ),
            }
        )

    def _install_stubs(self):
        recorder = self
        Stubs = self.stubs.Stubs
        writer = self.writers["D2"]
        stub_answer = self.stub_answer

        for method_name in STUB_METHODS:
            original = getattr(Stubs, method_name)

            def wrapped(stubs, *args, _original=original, _name=method_name):
                recorder.stub_depth += 1
                try:
                    answer = _original(stubs, *args)
                finally:
                    recorder.stub_depth -= 1
                if recorder.stub_depth == 0:
                    writer.write(
                        {
                            "call": _name,
                            "args": stub_answer(args),
                            "answer": stub_answer(answer, _name),
                        }
                    )
                return answer

            functools.update_wrapper(wrapped, original)
            setattr(Stubs, method_name, wrapped)

    def stub_answer(self, value, method=None):
        if method == "module" and value is not None:
            return {"names": sorted(value["names"]), "all": value.get("all")}
        if value is None or isinstance(value, (bool, int, str)):
            return value
        if isinstance(value, self.stubs.Definition):
            return {"kind": value.kind, "path": value.path, "owner": value.owner}
        if isinstance(value, (list, tuple)):
            return [self.stub_answer(item) for item in value]
        if isinstance(value, (set, frozenset)):
            items = [self.stub_answer(item) for item in value]
            return sorted(items, key=canonical_line)
        raise TypeError(f"no canonical form for the stub answer {value!r}")

    def _install_solver(self):
        recorder = self
        Solver = self.solver.Solver
        writer = self.writers["D3"]
        canon = self.names.canon

        for method_name in SOLVER_CALLS:
            original = getattr(Solver, method_name)
            answers = method_name in SOLVER_ANSWERS

            def wrapped(
                solver, *args, _original=original, _name=method_name, _answers=answers
            ):
                if recorder.inside_solver:
                    return _original(solver, *args)
                recorder.declare(_name, args)
                record = {"op": _name, "args": canon(args)}
                if not _answers:
                    writer.write(record)
                recorder.inside_solver = True
                try:
                    answer = _original(solver, *args)
                finally:
                    recorder.inside_solver = False
                if _answers:
                    record["answer"] = canon(answer)
                    writer.write(record)
                return answer

            functools.update_wrapper(wrapped, original)
            setattr(Solver, method_name, wrapped)

        original_wake = self.solver.Watch.wake

        def wake(watch):
            writer.write({"op": "wake", "node": recorder.witness_of_watch[watch]})
            with recorder.rules():
                answer = original_wake(watch)
            writer.write({"op": "woken"})
            return answer

        self.solver.Watch.wake = wake

        original_init = Solver.__init__

        def init(solver, saturated, cap=None):
            writer.write({"op": "solver", "cap": cap})
            original_init(solver, saturated, cap)

        Solver.__init__ = init
        original_solve = Solver.solve
        original_fire = Solver._fire

        def solve(solver):
            writer.write({"op": "solve"})
            between = solver.between_rounds
            if between is not None and not getattr(between, "recorded", False):

                def between_rounds():
                    writer.write({"op": "between_rounds"})
                    unknown_before = recorder.unknown_classes()
                    with recorder.rules():
                        answer = between()
                    unknown = [
                        recorder.names.object(cls)
                        for cls in recorder.unknown_classes()
                        if cls not in unknown_before
                    ]
                    writer.write(
                        {
                            "op": "between_rounds_done",
                            "answer": answer,
                            "unknown": unknown,
                        }
                    )
                    return answer

                between_rounds.recorded = True
                solver.between_rounds = between_rounds
            recorder.inside_solver = True
            try:
                return original_solve(solver)
            finally:
                recorder.inside_solver = False
                writer.write({"op": "solved", "phase": solver.phase})

        def fire(solver):
            recorder.note_first_rounds(solver)
            recorder.round += 1
            writer.write({"op": "fire", "phase": solver.phase})
            return original_fire(solver)

        Solver.solve = solve
        Solver._fire = fire

    def unknown_classes(self):
        if self.analysis is None:
            return {}
        return {cls: None for cls in self.analysis.classes if cls.unknown}

    def declare(self, operation, args):
        if operation in ("constant", "add_object"):
            self.declare_object(args[-1])
        elif operation in ("attach", "apply_now"):
            self.declare_constraint(args[1])

    def declare_object(self, obj):
        if obj in self.declared or not isinstance(obj, self.model.Object):
            return
        self.declared[obj] = None
        types = [
            cls.__name__
            for cls in type(obj).__mro__
            if issubclass(cls, self.model.Object)
        ]
        self.writers["D3"].write(
            {
                "op": "object",
                "object": self.names.object(obj),
                "types": types,
                "opacity": self.opacity(obj),
            }
        )

    def opacity(self, obj):
        model = self.model
        if type(obj) is model.Fallback:
            obj = obj.method
        cls = obj.cls if type(obj) is model.Instance else obj
        if type(cls) is model.Saturated:
            return "saturated"
        if type(cls) is model.Class:
            self.declare_object(cls)
            return self.names.object(cls)
        return None

    def declare_constraint(self, constraint):
        if constraint in self.declared:
            return
        self.declared[constraint] = None
        captured = [
            obj for obj in constraint.captured() if isinstance(obj, self.model.Object)
        ]
        for obj in captured:
            self.declare_object(obj)
        kinds = constraint.kinds
        mode = "each" if isinstance(constraint, self.solver.Each) else "list"
        self.writers["D3"].write(
            {
                "op": "constraint",
                "constraint": self.names.constraint(constraint),
                "kinds": None if kinds is None else [k.__name__ for k in kinds],
                "mode": mode,
                "captured": [self.names.object(obj) for obj in captured],
            }
        )

    def note_first_rounds(self, solver):
        analysis = self.analysis
        if analysis is None:
            return
        first = self.first_rounds
        for node in analysis.named_nodes:
            for obj in solver.objects.__wrapped__(solver, node):
                key = (self.names.node(node), self.names.object(obj))
                if key not in first:
                    first[key] = self.round

    def rules(self):
        recorder = self

        class Rules:
            def __enter__(self):
                self.saved = recorder.inside_solver
                recorder.inside_solver = False

            def __exit__(self, *error):
                recorder.inside_solver = self.saved

        return Rules()

    def applying(self, function, constraint):
        recorder = self
        writer = self.writers["D3"]
        canon = self.names.canon
        number = self.names.constraint(constraint)

        @functools.wraps(function)
        def applied(*args):
            if not recorder.inside_solver:
                return function(*args)
            obj = args[1] if constraint.owner is not None else args[0]
            recorder.declare_constraint(constraint)
            writer.write({"op": "apply", "constraint": number, "objects": [canon(obj)]})
            with recorder.rules():
                answer = function(*args)
            writer.write({"op": "applied"})
            return answer

        return applied

    def _install_constraints(self):
        solver = self.solver
        writer = self.writers["D3"]
        canon = self.names.canon
        recorder = self
        pending = [solver.Constraint]
        seen = set()
        while pending:
            cls = pending.pop()
            if cls in seen:
                continue
            seen.add(cls)
            pending.extend(cls.__subclasses__())
            if cls is solver.Each:
                continue
            own = vars(cls)
            for method_name in ("apply_each", "apply"):
                if method_name not in own:
                    continue
                if method_name == "apply" and cls is solver.Constraint:
                    continue
                original = own[method_name]

                def wrapped(constraint, objects, _original=original, _name=method_name):
                    if not recorder.inside_solver:
                        return _original(constraint, objects)
                    listed = [objects] if _name == "apply" else list(objects)
                    recorder.declare_constraint(constraint)
                    writer.write(
                        {
                            "op": "apply",
                            "constraint": recorder.names.constraint(constraint),
                            "objects": [canon(obj) for obj in listed],
                        }
                    )
                    with recorder.rules():
                        answer = _original(
                            constraint, objects if _name == "apply" else listed
                        )
                    writer.write({"op": "applied"})
                    return answer

                functools.update_wrapper(wrapped, original)
                setattr(cls, method_name, wrapped)
            if "saturate" in own or cls is solver.Constraint:
                original = own.get("saturate", solver.Constraint.saturate)

                def saturate(constraint, solver_, _original=original):
                    if not recorder.inside_solver:
                        return _original(constraint, solver_)
                    recorder.declare_constraint(constraint)
                    writer.write(
                        {
                            "op": "saturate",
                            "constraint": recorder.names.constraint(constraint),
                        }
                    )
                    with recorder.rules():
                        answer = _original(constraint, solver_)
                    writer.write({"op": "saturated"})
                    return answer

                functools.update_wrapper(saturate, original)
                cls.saturate = saturate

    def _install_builder_calls(self):
        recorder = self
        Analysis = self.semantics.Analysis
        writer = self.writers["D4"]
        canon = self.names.canon
        methods = {}
        for owner in reversed(Analysis.__mro__):
            for method_name, value in vars(owner).items():
                if isinstance(value, FunctionType) and not method_name.startswith("__"):
                    methods[method_name] = value
        for method_name, original in methods.items():
            signature = inspect.signature(original)
            receiver = next(iter(signature.parameters))

            def wrapped(
                analysis,
                *args,
                _original=original,
                _name=method_name,
                _signature=signature,
                _self=receiver,
                **kw,
            ):
                if recorder.building is None or recorder.builder_depth:
                    recorder.builder_depth += 1
                    try:
                        return _original(analysis, *args, **kw)
                    finally:
                        recorder.builder_depth -= 1
                recorder.builder_depth += 1
                try:
                    answer = _original(analysis, *args, **kw)
                finally:
                    recorder.builder_depth -= 1
                bound = _signature.bind(analysis, *args, **kw)
                bound.apply_defaults()
                writer.write(
                    {
                        "module": recorder.building,
                        "call": _name,
                        "arguments": {
                            parameter: canon(value)
                            for parameter, value in bound.arguments.items()
                            if parameter != _self
                        },
                        "answer": canon(answer),
                    }
                )
                return answer

            functools.update_wrapper(wrapped, original)
            setattr(Analysis, method_name, wrapped)
        self._install_import_calls()

    def _install_import_calls(self):
        recorder = self
        manager = self.imports.ImportManager
        writer = self.writers["D4"]
        canon = self.names.canon
        for method_name in BUILDER_IMPORT_CALLS:
            original = getattr(manager, method_name)
            signature = inspect.signature(original)
            receiver = next(iter(signature.parameters))

            def wrapped(
                imports,
                *args,
                _original=original,
                _name=method_name,
                _signature=signature,
                _self=receiver,
                **kw,
            ):
                answer = _original(imports, *args, **kw)
                if recorder.building is None or recorder.builder_depth:
                    return answer
                bound = _signature.bind(imports, *args, **kw)
                bound.apply_defaults()
                writer.write(
                    {
                        "module": recorder.building,
                        "call": f"imports.{_name}",
                        "arguments": {
                            parameter: canon(value)
                            for parameter, value in bound.arguments.items()
                            if parameter != _self
                        },
                        "answer": canon(answer),
                    }
                )
                return answer

            functools.update_wrapper(wrapped, original)
            setattr(manager, method_name, wrapped)

    def finish(self, generator):
        self.inside_solver = True
        solver = generator.program.analysis.solver
        self.note_first_rounds(solver)
        objects = solver.objects.__wrapped__
        writer = self.writers["D3"]
        for node, name in list(self.names.nodes().items()):
            if isinstance(node, self.solver.Constant):
                continue
            held = objects(solver, node)
            writer.write(
                {
                    "op": "final",
                    "node": name,
                    "objects": [self.names.object(obj) for obj in held],
                    "saturated": solver.is_saturated.__wrapped__(solver, node),
                }
            )
        writer.write(
            {
                "op": "absorbed",
                "objects": sorted(self.names.object(o) for o in solver.absorbed()),
            }
        )
        for (node, obj), number in sorted(self.first_rounds.items()):
            writer.write({"op": "first", "node": node, "object": obj, "round": number})
        writer.write({"op": "work", "rounds": solver.phase, "work": solver.work})
        points_to = generator.output_points_to()
        for label, held in points_to.items():
            self.writers["D5"].write({"node": label, "objects": held})


def dump_input(checkout, out, entry_points, package, cap=None):
    sys.path.insert(0, os.path.abspath(checkout))
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    from pycg.formats import dumps
    from pycg.pycg import CallGraphGenerator

    recorder = Recorder(out, checkout)
    recorder.install()
    generator = (
        CallGraphGenerator(entry_points, package)
        if cap is None
        else CallGraphGenerator(entry_points, package, cap)
    )
    try:
        generator.analyze()
        entries = sorted(generator.program._entry_module_names)
        (out / ENTRIES).write_text("".join(f"{name}\n" for name in entries))
        recorder.finish(generator)
        document = dumps(generator.document())
    except (Exception, SystemExit) as error:
        (out / "error.txt").write_text(f"{type(error).__name__}: {error}\n")
        return 1
    finally:
        recorder.close()
    (out / "D6.json").write_text(document, encoding="utf-8")
    return 0


def load_runner(checkout):
    path = Path(checkout) / "evaluation" / "common" / "run.py"
    spec = importlib.util.spec_from_file_location("evaluation_run", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs(checkout, sets):
    runner = load_runner(checkout)
    jobs = []
    for name in sets:
        found, _ = runner.micro_jobs() if name == "micro" else runner.macro_jobs()
        jobs.extend(found)
    return jobs


def run_input(checkout, job, directory, seed):
    command = [
        sys.executable,
        *INTERPRETER_FLAGS_ISOLATED,
        str(Path(__file__).resolve()),
        "input",
        "--checkout",
        str(checkout),
        "--out",
        str(directory),
        "--package",
        os.path.realpath(job.package),
        *(os.path.realpath(path) for path in job.entry_points),
    ]
    done = subprocess.run(
        command,
        env={"PYTHONHASHSEED": str(seed)},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if done.returncode != 0 and not (directory / "error.txt").exists():
        directory.mkdir(parents=True, exist_ok=True)
        tail = (done.stderr.strip().splitlines() or [""])[-1]
        (directory / "error.txt").write_text(f"exit {done.returncode}: {tail}\n")
    return done.returncode


def differing_dumps(first, second):
    found = []
    for dump in DUMPS:
        name = f"{dump}.json" if dump == "D6" else f"{dump}.jsonl"
        left, right = first / name, second / name
        if (
            not (left.exists() and right.exists())
            or left.read_bytes() != right.read_bytes()
        ):
            found.append(dump)
    return found


def oracle(checkout, out, sets, workers, names=()):
    checkout = Path(checkout).resolve()
    out = Path(out).resolve()
    jobs = inputs(checkout, sets)
    if names:
        jobs = [job for job in jobs if job.key in names]
        missing = set(names) - {job.key for job in jobs}
        if missing:
            print(f"parity-oracle: no input {', '.join(sorted(missing))}")
            return 2
    tasks = [(job, seed) for job in jobs for seed in SEEDS]

    def both_seeds(job):
        return [
            run_input(checkout, job, out / f"seed-{seed}" / job.key, seed)
            for seed in SEEDS
        ]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        codes = [code for pair in pool.map(both_seeds, jobs) for code in pair]
    failed = sum(1 for code in codes if code)
    different = []
    for job in jobs:
        directories = [out / f"seed-{seed}" / job.key for seed in SEEDS]
        if not any((directory / "error.txt").exists() for directory in directories):
            dumps = differing_dumps(*directories)
            if dumps:
                different.append((job.key, dumps))
    peak_mib = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
    print(
        f"parity-oracle: {len(jobs)} inputs, {failed} failed runs, "
        f"{len(different)} with differing dumps across seeds, "
        f"largest run {peak_mib:.0f} MiB"
    )
    for (job, seed), code in zip(tasks, codes):
        if code:
            error = out / f"seed-{seed}" / job.key / "error.txt"
            print(f"  {job.key} (seed {seed}): {error.read_text().strip()}")
    for key, dumps in different:
        print(f"  {key}: seeds 0 and 1 differ in {', '.join(dumps)}")
    return 1 if different or failed else 0


def git_object(checkout, path):
    done = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", f"HEAD:{path}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def key(checkout):
    sys.path.insert(0, str(Path(checkout) / "tools"))
    from inputs_key import inputs_key

    parts = [f"{path} {git_object(checkout, path)}" for path in KEYED_PATHS]
    parts.append(f"inputs {inputs_key(Path(checkout))}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("input", help="dump one input")
    one.add_argument("--checkout", type=Path, required=True)
    one.add_argument("--out", type=Path, required=True)
    one.add_argument("--package", required=True)
    one.add_argument("--cap", type=int, help="objects per node, for tests")
    one.add_argument("entry_points", nargs="+")
    every = commands.add_parser("oracle", help="dump every input for both seeds")
    every.add_argument("--checkout", type=Path, required=True)
    every.add_argument("--out", type=Path, required=True)
    every.add_argument("--set", choices=SETS, action="append")
    every.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    every.add_argument(
        "--name", action="append", help="only this input, e.g. macro/h11"
    )
    keyed = commands.add_parser("key", help="print the key of an oracle run")
    keyed.add_argument("--checkout", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "input":
        return dump_input(
            args.checkout, args.out, args.entry_points, args.package, args.cap
        )
    if args.command == "oracle":
        sets = args.set or list(SETS)
        return oracle(args.checkout, args.out, sets, args.jobs, args.name or ())
    print(key(args.checkout))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
