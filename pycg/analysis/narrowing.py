import ast

from .annotations import CLASS, INSTANCE
from .flow import UNKNOWN
from .hierarchy import BUILTIN_TYPE, MAY_DERIVE, MAY_LACK, NOT_NOMINAL
from .model import (
    Class,
    Const,
    Container,
    Coroutine,
    External,
    Generator,
    Instance,
    Pattern,
    Typed,
)
from .outside import outside_name
from .solver import Each

CLASS_TESTS = {"isinstance": False, "issubclass": True}

TYPE_PATH = "builtins.type"
COROUTINE_PATH = "types.CoroutineType"

CLASS_PREDICATES = {"inspect.iscoroutine": COROUTINE_PATH}

ANALYSED, EXACTLY, BELOW = "analysed", "exactly", "below"

UNKNOWN_CLASS = (None, None)


class ClassTestBuilder:
    def class_test(self, node, args):
        if node.keywords or not node.args or len(node.args) != len(args):
            return
        tested = self._tested_classes(node, args)
        subject = node.args[0]
        if tested is None or not isinstance(subject, ast.Name):
            return
        name = self._scope.mangle(subject.id)
        scope = self.scopes.resolve(self._scope, name)
        if scope is not self._scope or not self.scopes.tracked(scope, name):
            return
        classes, as_class = tested
        definition = self._flow.definition(name)
        self._class_tests_by_call[node] = (
            name,
            definition,
            args[0],
            classes,
            as_class,
        )

    def _tested_classes(self, node, args):
        if len(args) == 2 and _names_classes(node.args[1]):
            for checker, as_class in CLASS_TESTS.items():
                if self._is_builtin_reference(node.func, checker):
                    return args[1], as_class
        if len(args) == 1:
            path = CLASS_PREDICATES.get(self._imported_function(node.func))
            if path is not None:
                tested = self.analysis.constant(self.analysis.external(path))
                return tested, False
        return None

    def _imported_function(self, func):
        if isinstance(func, ast.Name):
            return self._import_of(func.id)
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            module = self._import_of(func.value.id)
            if module is not None:
                return f"{module}.{func.attr}"
        return None

    def _import_of(self, name):
        name = self._scope.mangle(name)
        return self.scopes.imported(self.scopes.resolve(self._scope, name), name)

    def narrow(self, test, holds, state=None):
        match test:
            case ast.UnaryOp(op=ast.Not()):
                self.narrow(test.operand, not holds, state)
            case ast.BoolOp(op=ast.And()) if holds:
                for value in test.values:
                    self.narrow(value, True, state)
            case ast.BoolOp(op=ast.Or()) if not holds:
                for value in test.values:
                    self.narrow(value, False, state)
            case ast.Call() if test in self._class_tests_by_call:
                name, tested, _, _, _ = self._class_tests_by_call[test]
                node = self._narrowed_node(test, holds)
                if holds:
                    definition = (node, False, UNKNOWN, None)
                else:
                    definition = (node, False, tested[2] or UNKNOWN, tested[3])
                self._flow.narrow(name, tested, definition, state)

    def _narrowed_node(self, test, holds):
        key = (test, holds)
        if key not in self._narrowed_nodes:
            _, _, value, classes, as_class = self._class_tests_by_call[test]
            narrowed = self.analysis.node()
            if value is not None:
                self.analysis.class_filter(value, classes, narrowed, as_class, holds)
            if holds and classes is not None:
                owner = (self.module, self._site(test))
                self.analysis.tested_classes(classes, narrowed, as_class, owner)
            self._narrowed_nodes[key] = narrowed
        return self._narrowed_nodes[key]


def _names_classes(node):
    if isinstance(node, ast.Tuple):
        return all(map(_names_classes, node.elts))
    while isinstance(node, ast.Attribute):
        node = node.value
    return isinstance(node, ast.Name)


class _Filter:
    __slots__ = (
        "source",
        "dst",
        "holds",
        "as_class",
        "groups",
        "passed",
        "alternatives",
        "all",
    )

    def __init__(self, source, dst, holds, as_class):
        self.source = source
        self.dst = dst
        self.holds = holds
        self.as_class = as_class
        self.groups = {}
        self.passed = set()
        self.alternatives = []
        self.all = False


class _Alternative:
    __slots__ = ("length", "classes", "open", "passed", "covered")

    def __init__(self, length):
        self.length = length
        self.classes = [{} for _ in range(length)]
        self.open = set()
        self.passed = {}
        self.covered = {}


class ClassTests:
    def tested_classes(self, classes, dst, as_class, owner):
        key = (classes, dst, as_class)
        if key in self._tested_classes:
            return
        self._tested_classes.add(key)
        self.annotated(classes, dst, CLASS if as_class else INSTANCE, owner)
        each = Each(self._tested_tuple, dst, as_class, owner, results=(dst,))
        self.solver.attach(classes, each)

    def _tested_tuple(self, obj, dst, as_class, owner):
        if isinstance(obj, Container) and obj.kind == "tuple":
            self.tested_classes(self.every(obj), dst, as_class, owner)

    def class_filter(self, source, classes, dst, as_class, holds):
        record = _Filter(source, dst, holds, as_class)
        if classes is None:
            self._pass_all(record)
            return
        self._subscribe(classes, record, None, None, self._alternative)
        self.solver.attach(source, Each(self._value, record, results=(dst,)))

    def _subscribe(self, node, record, alternative, index, function):
        key = (node, record, alternative, index)
        if key in self._class_filters:
            return
        self._class_filters[key] = None
        if alternative is None:
            each = Each(function, record, results=(record.dst,))
        else:
            each = Each(function, record, alternative, index, results=(record.dst,))
        self.solver.attach(node, each)

    def complete_class_tests(self):
        added = False
        keys = list(self._class_filters)
        pending = keys[self._completed_class_filters :]
        self._completed_class_filters = len(keys)
        for node, record, alternative, index in pending:
            if not self.solver.objects(node):
                if alternative is None:
                    added = self._pass_all(record) or added
                else:
                    added = self._open(record, alternative, index) or added
        return added

    def _alternative(self, value, record):
        if isinstance(value, Container) and value.kind == "tuple":
            if value.length == 0:
                if not record.holds:
                    self._pass_all(record)
            elif value.length is None:
                alternative = self._new_alternative(record, 1)
                self._tuple_at(value, record, alternative, 0)
            else:
                alternative = self._new_alternative(record, value.length)
                for index in range(value.length):
                    node = self.element(value, index)
                    self._position(node, record, alternative, index)
        else:
            alternative = self._new_alternative(record, 1)
            self._tested_class(value, record, alternative, 0)

    def _tuple_at(self, value, record, alternative, index):
        if not record.holds:
            self._open(record, alternative, index)
        elif value.length is None:
            self._position(self.every(value), record, alternative, index)
        else:
            for position in range(value.length):
                node = self.element(value, position)
                self._position(node, record, alternative, index)

    def _new_alternative(self, record, length):
        alternative = _Alternative(length)
        record.alternatives.append(alternative)
        return alternative

    def _position(self, node, record, alternative, index):
        self._subscribe(node, record, alternative, index, self._position_class)

    def _position_class(self, value, record, alternative, index):
        if record.all and record.holds and not isinstance(value, (Class, Container)):
            return
        if isinstance(value, Container) and value.kind == "tuple":
            self._tuple_at(value, record, alternative, index)
        else:
            self._tested_class(value, record, alternative, index)

    def _tested_class(self, cls, record, alternative, index):
        classes = alternative.classes[index]
        if cls in classes:
            return
        if isinstance(cls, Class):
            metaclass = Each(
                self._metaclass, record, alternative, index, results=(record.dst,)
            )
            self.solver.attach(cls.metaclass, metaclass)
            bases = Each(
                self._not_nominal, record, alternative, index, results=(record.dst,)
            )
            self.solver.attach(self.relation(cls, None, NOT_NOMINAL), bases)
        elif not (
            isinstance(cls, External) and not cls.inexact and self.nominal_outside(cls)
        ):
            self._open(record, alternative, index)
            return
        classes[cls] = None
        for key in list(record.groups):
            self._decide_remembered(key, cls, record, alternative, index)

    def _metaclass(self, meta, record, alternative, index):
        if not (isinstance(meta, External) and meta.name == BUILTIN_TYPE):
            self._open(record, alternative, index)

    def _not_nominal(self, _marker, record, alternative, index):
        self._open(record, alternative, index)

    def _value(self, obj, record):
        if record.all:
            return
        key = self._class_key(obj, record.as_class)
        if key in record.passed:
            self.add_object(record.dst, obj)
            return
        group = record.groups.get(key)
        if group is not None:
            group.append(obj)
            return
        record.groups[key] = [obj]
        for alternative in list(record.alternatives):
            if not record.holds:
                self._passes_at(key, record, alternative, None)
            for index, classes in enumerate(alternative.classes):
                for cls in list(classes):
                    self.solver.revisit(
                        self._decide_class, cls, key, record, alternative, index
                    )

    def _decide_remembered(self, key, cls, record, alternative, index):
        if key[0] == ANALYSED:
            self.solver.revisit(
                self._decide_known, key[1], key, cls, record, alternative, index
            )
        else:
            self._decide(key, cls, record, alternative, index)

    def _decide_known(self, _known, key, cls, record, alternative, index):
        self._decide(key, cls, record, alternative, index)

    def _decide_class(self, cls, key, record, alternative, index):
        self._decide(key, cls, record, alternative, index)

    def _decide(self, key, cls, record, alternative, index):
        if record.all or key in record.passed:
            return
        kind, known = key
        if kind is None:
            if record.holds:
                self._pass_group(key, record)
            else:
                self._passes_at(key, record, alternative, index)
            return
        if kind == ANALYSED:
            if record.holds and isinstance(cls, Class):
                return
            relation = MAY_DERIVE if record.holds else MAY_LACK
            each = Each(
                self._related, record, key, alternative, index, results=(record.dst,)
            )
            self.solver.attach(self.relation(known, cls, relation), each)
            return
        if record.holds:
            if self._may_be(kind, known, cls):
                self._pass_group(key, record)
        elif not self._certainly(kind, known, cls):
            self._passes_at(key, record, alternative, index)

    def _related(self, _marker, record, key, alternative, index):
        if record.holds:
            self._pass_group(key, record)
        else:
            self._passes_at(key, record, alternative, index)

    def _class_key(self, obj, as_class):
        if as_class:
            if isinstance(obj, Class):
                return ANALYSED, obj
            if isinstance(obj, External) and obj.inexact:
                return UNKNOWN_CLASS
            paths = _stub_classes(self, obj)
            return (EXACTLY, paths) if paths else UNKNOWN_CLASS
        if isinstance(obj, Instance):
            return ANALYSED, obj.cls
        if isinstance(obj, Const) and obj.exact:
            return EXACTLY, (f"builtins.{obj.type_name}",)
        if isinstance(obj, Pattern) and obj.exact:
            return EXACTLY, ("builtins.str",)
        if isinstance(obj, (Container, Generator)) and obj.exact:
            return EXACTLY, (self.kind_class(obj.kind)[0],)
        if isinstance(obj, Coroutine) and obj.exact:
            return EXACTLY, (COROUTINE_PATH,)
        if isinstance(obj, Typed):
            return BELOW, (obj.cls,)
        if isinstance(obj, Class) or _stub_classes(self, obj):
            return BELOW, (TYPE_PATH,)
        return UNKNOWN_CLASS

    def _may_be(self, kind, paths, cls):
        if isinstance(cls, Class):
            return kind == BELOW
        tested = self._stub_names(cls)
        if any(tested & self._ancestor_names(path) for path in paths):
            return True
        if kind == BELOW:
            names = {self._public(path) for path in paths}
            return any(
                names & self._ancestor_names(path) for path in _stub_classes(self, cls)
            )
        return False

    def _certainly(self, kind, paths, cls):
        if isinstance(cls, Class):
            return False
        tested = self._stub_names(cls)
        return any(tested & self._ancestor_names(path) for path in paths)

    def _stub_names(self, cls):
        return {self._public(path) for path in _stub_classes(self, cls)}

    def _ancestor_names(self, path):
        if path not in self._stub_ancestors:
            self._stub_ancestors[path] = frozenset(
                self._public(ancestor) for ancestor in self.stubs.mro(path)
            )
        return self._stub_ancestors[path]

    def _public(self, path):
        return outside_name(self.stubs.public_name(path))

    def _passes_at(self, key, record, alternative, index):
        if key not in alternative.covered:
            alternative.passed[key] = set()
            alternative.covered[key] = len(alternative.open)
        passed = alternative.passed[key]
        if index is not None and index not in passed and index not in alternative.open:
            passed.add(index)
            alternative.covered[key] += 1
        if alternative.covered[key] == alternative.length:
            self._pass_group(key, record)

    def _pass_group(self, key, record):
        if key in record.passed:
            return
        record.passed.add(key)
        for obj in record.groups.get(key, ()):
            self.solver.revisit(self._pass_value, obj, record)

    def _pass_value(self, obj, record):
        self.add_object(record.dst, obj)

    def _open(self, record, alternative, index):
        if record.holds:
            return self._pass_all(record)
        if index in alternative.open:
            return False
        alternative.open.add(index)
        for key, passed in alternative.passed.items():
            if index not in passed:
                alternative.covered[key] += 1
        for key in list(record.groups):
            self._passes_at(key, record, alternative, None)
        return True

    def _pass_all(self, record):
        if record.all:
            return False
        record.all = True
        self.add_edge(record.source, record.dst)
        return True


def _stub_classes(analysis, obj):
    if not isinstance(obj, External):
        return ()
    return tuple(
        definition.path
        for definition in analysis.stub_definitions(obj) or ()
        if definition.kind == "class"
    )
