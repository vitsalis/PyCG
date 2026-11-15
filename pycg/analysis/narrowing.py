"""Class tests: what `isinstance(x, C)` and `issubclass(x, C)` tell about a
local name in the branches of the test (see *Class tests* in the design).

The builder (`ClassTestBuilder`) records each test it evaluates: the name,
the definition of it that the test read, the node of its value there, and
the node of the classes. At the start of each branch of the test, it gives
the name a narrowed definition, which the flow state keeps beside the
definitions (`State.narrowed`), so only the reads in the branch see it.

At solve time (`ClassTests`), the narrowed node holds the values of the name
that may pass the test there (a filter, below), and, where the test holds,
what an annotation that names the classes names (annotations.py).

The filter keeps the values in groups by what the analysis knows of their
class (`_class_key`), decides each pair of a group and a tested class once
both have arrived, and only ever lets values through. A decision on an
analysed class waits for its hierarchy, as a lookup does
(`Hierarchy.relation`). A tested class whose instance check may not follow
its MROs, anything else that the class expression holds, and a class
expression, or a position of a tuple of classes, that holds nothing at a
fixpoint (`complete_class_tests`) let every value through.
"""

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

# The builtins that test the class of their first argument, and whether
# that argument is a class (`issubclass`).
CLASS_TESTS = {"isinstance": False, "issubclass": True}

TYPE_PATH = "builtins.type"
COROUTINE_PATH = "types.CoroutineType"

# What the analysis knows of the class of a value (see `_class_key`): an
# analysed class, by its hierarchy; exactly a class of the stubs; a class of
# the stubs or a subclass of it.
ANALYSED, EXACTLY, BELOW = "analysed", "exactly", "below"

# The group of the values whose class the analysis does not know (a
# function, a container of an annotation, an outside value without a type).
UNKNOWN_CLASS = (None, None)


class ClassTestBuilder:
    """The part of the builder that records class tests and gives their
    branches the narrowed definitions (see the module docstring)."""

    def class_test(self, node, args):
        """Record the call `node` of `isinstance` or `issubclass`, whose
        evaluated positional arguments are `args`, if it tests a name that
        the current scope follows by definition against classes written as
        a name, an attribute path or a tuple display of those."""
        if node.keywords or len(node.args) != 2 or len(args) != 2:
            return
        subject, classes = node.args
        if not isinstance(subject, ast.Name) or not _names_classes(classes):
            return
        checker = next(
            (n for n in CLASS_TESTS if self._is_builtin_reference(node.func, n)),
            None,
        )
        if checker is None:
            return
        name = self._scope.mangle(subject.id)
        scope = self.scopes.resolve(self._scope, name)
        if scope is not self._scope or not self.scopes.tracked(scope, name):
            return
        tested = self._flow.definition(name)
        self._class_tests[node] = (name, tested, args[0], args[1], CLASS_TESTS[checker])

    def narrow(self, test, holds, state=None):
        """Give the names that the condition `test` tests their narrowed
        definitions in the branch where `test` is true (if `holds`) or
        false, which starts at `state` (by default the current one): under
        `not`, `and` where it is true, `or` where it is false."""
        match test:
            case ast.UnaryOp(op=ast.Not()):
                self.narrow(test.operand, not holds, state)
            case ast.BoolOp(op=ast.And()) if holds:
                for value in test.values:
                    self.narrow(value, True, state)
            case ast.BoolOp(op=ast.Or()) if not holds:
                for value in test.values:
                    self.narrow(value, False, state)
            case ast.Call() if test in self._class_tests:
                name, tested, _, _, _ = self._class_tests[test]
                node = self._narrowed_node(test, holds)
                if holds:
                    definition = (node, False, UNKNOWN, None)
                else:
                    # A part of what the name held: its truth and values.
                    definition = (node, False, tested[2] or UNKNOWN, tested[3])
                self._flow.narrow(name, tested, definition, state)

    def _narrowed_node(self, test, holds):
        """The node of the name that the class test `test` tests, in the
        branch where it holds (if `holds`) or fails: one per test and
        branch."""
        key = (test, holds)
        if key not in self._narrowed_nodes:
            _, _, value, classes, as_class = self._class_tests[test]
            narrowed = self.analysis.node()
            if value is not None:
                self.analysis.class_filter(value, classes, narrowed, as_class, holds)
            if holds and classes is not None:
                owner = (self.module, self._site(test))
                self.analysis.tested_classes(classes, narrowed, as_class, owner)
            self._narrowed_nodes[key] = narrowed
        return self._narrowed_nodes[key]


def _names_classes(node):
    """Whether the expression `node` is a name, an attribute path or a
    tuple display of those."""
    if isinstance(node, ast.Tuple):
        return all(map(_names_classes, node.elts))
    while isinstance(node, ast.Attribute):
        node = node.value
    return isinstance(node, ast.Name)


class _Filter:
    """The values of the node `source` that may pass a class test go to
    `dst`, in the branch where the test holds (`holds`) or where it fails;
    the values are classes for `issubclass` (`as_class`). The values are
    kept in groups by what the analysis knows of their class (`groups`, see
    `_class_key`), and a group passes or not as a whole: `passed` holds the
    groups that pass. `alternatives` are the values of the class expression
    seen so far, and `all` is true once every value passes."""

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
    """One value of the class expression: one class, or a tuple of `length`
    classes. `classes` holds the classes that may stand at each position,
    as the keys of a dict (in the order they arrive, each found in one
    step), `open` the positions that every value passes, `passed` maps a
    group of values to the other positions that it passes, where the test
    fails, and `covered` to how many positions it passes in all."""

    __slots__ = ("length", "classes", "open", "passed", "covered")

    def __init__(self, length):
        self.length = length
        self.classes = [{} for _ in range(length)]
        self.open = set()
        self.passed = {}
        self.covered = {}


class ClassTests:
    """The part of `Analysis` that reads the classes of a class test and
    filters the values of the name (see the module docstring)."""

    def tested_classes(self, classes, dst, as_class, owner):
        """dst ⊇ what an annotation names (the classes, if `as_class`) for
        each class that the node `classes` holds, and for each element of
        a tuple of classes that it holds. `owner` keys the containers that
        an annotation makes."""
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
        """dst ⊇ the values of `source` that may pass the test of the
        classes in the node `classes` (None if it has no value), in the
        branch where the test holds (if `holds`) or fails.

        Cost of one test of t classes on v values of c known classes: one
        dict operation per value, and one decision per pair of a class of
        the values and a tested class, v + c*t. A decision on an analysed
        class reads a node of its hierarchy that every test shares
        (`Hierarchy.relation`)."""
        record = _Filter(source, dst, holds, as_class)
        if classes is None:
            self._pass_all(record)
            return
        self._subscribe(classes, record, None, None, self._alternative)
        self.solver.attach(source, Each(self._value, record, results=(dst,)))

    def _subscribe(self, node, record, alternative, index, function):
        """Subscribe `function` to the class values that `node` holds, at
        most once per (node, filter, alternative, position): a tuple that
        contains itself, or tuples that share their elements, subscribe each
        node once. The completion reads the same table."""
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
        """At a fixpoint: a class expression, or a position of a tuple of
        classes, that holds nothing lets every value pass. Return whether
        anything was added."""
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

    # The values of the class expression

    def _alternative(self, value, record):
        if isinstance(value, Container) and value.kind == "tuple":
            if value.length == 0:
                # `isinstance(x, ())` is false: every value passes where it
                # fails, none where it holds.
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
        """A tuple of classes stands at the position `index`. Where the test
        holds, a value passes if it may pass one of its elements; where it
        fails, the elements are not known one by one: every value passes."""
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
            # Every value passes already, which is all that a value that
            # is not a class can add where the test holds (see `_open`).
            # A class still goes on: its metaclass and its hierarchy may
            # saturate the result. A hub of values at a position of many
            # tests ends here (hypothesis: 5.8 of 7.2 million values).
            return
        if isinstance(value, Container) and value.kind == "tuple":
            self._tuple_at(value, record, alternative, index)
        else:
            self._tested_class(value, record, alternative, index)

    def _tested_class(self, cls, record, alternative, index):
        """The class `cls` may stand at the position `index`. Only a class
        whose instance check follows its MROs filters: one whose metaclass
        may define `__instancecheck__` (an ABC, a protocol) lets every value
        pass, and so does anything that is not a class."""
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

    # The values of the name

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
        """Decide a group seen before for a new class; not the group of the
        instances of an analysed class that has become unknown (see
        `Hierarchy.unknown_classes`)."""
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
        """Whether the group of values `key` may pass the class `cls` at the
        position `index`: it may be an instance (a subclass, for
        `issubclass`) of it, where the test holds; it may not be, where it
        fails."""
        if record.all or key in record.passed:
            return
        kind, known = key
        if kind is None:
            # Nothing is known of their class: they may be instances of
            # `cls`, and may not.
            if record.holds:
                self._pass_group(key, record)
            else:
                self._passes_at(key, record, alternative, index)
            return
        if kind == ANALYSED:
            if record.holds and isinstance(cls, Class):
                # What the test adds holds every instance that may pass.
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
        """What the analysis knows of the class of the value `obj` (the
        value itself, for `issubclass`): `(ANALYSED, class)`, `(EXACTLY,
        stub paths)` or `(BELOW, stub paths)`; `UNKNOWN_CLASS` if
        nothing."""
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
        """Whether a value whose class is known as `kind` and `paths` may
        be an instance of `cls`, which is not analysed or not tested
        against an analysed class."""
        if isinstance(cls, Class):
            # An outside class may have an analysed subclass.
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
        """Whether a value whose class is known as `kind` and `paths` is
        certainly an instance of the outside class `cls`."""
        if isinstance(cls, Class):
            return False
        tested = self._stub_names(cls)
        return any(tested & self._ancestor_names(path) for path in paths)

    def _stub_names(self, cls):
        return {self._public(path) for path in _stub_classes(self, cls)}

    def _ancestor_names(self, path):
        """The public names of the classes of the stub MRO of `path`."""
        if path not in self._stub_ancestors:
            self._stub_ancestors[path] = frozenset(
                self._public(ancestor) for ancestor in self.stubs.mro(path)
            )
        return self._stub_ancestors[path]

    def _public(self, path):
        return outside_name(self.stubs.public_name(path))

    # Passing

    def _passes_at(self, key, record, alternative, index):
        """Where the test fails, the group `key` may pass the position
        `index` of `alternative` (None: only the open ones); it passes once
        it may pass every position. Each position counts once."""
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
        """The values of the group `key` pass, now and when they arrive."""
        if key in record.passed:
            return
        record.passed.add(key)
        for obj in record.groups.get(key, ()):
            self.solver.revisit(self._pass_value, obj, record)

    def _pass_value(self, obj, record):
        self.add_object(record.dst, obj)

    def _open(self, record, alternative, index):
        """Every value passes the position `index` of `alternative`. Return
        whether that is new."""
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
        """Every value passes. Return whether that is new."""
        if record.all:
            return False
        record.all = True
        self.add_edge(record.source, record.dst)
        return True


def _stub_classes(analysis, obj):
    """The stub paths of the classes that the outside value `obj` names, or
    an empty tuple."""
    if not isinstance(obj, External):
        return ()
    return tuple(
        definition.path
        for definition in analysis.stub_definitions(obj) or ()
        if definition.kind == "class"
    )
