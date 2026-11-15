"""Statements and expressions that the interpreter turns into calls of
special methods: operators, conversions to `str`, `with`, `raise`, `except`.

`Protocols` is part of `Analysis` (see semantics.py), whose objects, nodes
and constraints it uses. The special methods are found and called like any
method; calls of methods outside the analysed modules give no edges, because
they are not call expressions (micro-benchmark/README.md).
"""

from .builtin_models import CONTAINER_CLASSES
from .containers import hashes_keys, is_dict
from .model import (
    Class,
    Const,
    Container,
    Coroutine,
    External,
    Generator,
    Instance,
    Typed,
)
from .outside import REFLECTED_COMPARISONS
from .solver import Each

# The special methods that a conversion to str calls, in order, each with
# the methods whose definition in an analysed class makes Python skip it:
# object.__format__ calls str(), and object.__str__ calls repr().
CONVERSIONS = {
    "str": (("__str__", ()), ("__repr__", ("__str__",))),
    "repr": (("__repr__", ()),),
    "format": (
        ("__format__", ()),
        ("__str__", ("__format__",)),
        ("__repr__", ("__format__", "__str__")),
    ),
}


# The builtin containers whose str(), repr() and format() call repr() of
# their elements: they define neither __str__ nor __format__.
_REPR_CONTAINERS = frozenset({"list", "tuple", "set", "frozenset", "dict"})

# The conversions of `%` formatting on a str: `%s` converts with str, `%r`
# and `%a` with repr, the others take numbers (see `_percent_fields`).
PERCENT_CONVERSIONS = {
    "s": "str",
    "r": "repr",
    "a": "repr",
    **dict.fromkeys("diouxXeEfFgGc"),
}
# The largest width and precision in digits that Python accepts, for str and
# bytes formats: PY_SSIZE_T_MAX and INT_MAX. PY_SSIZE_T_MAX depends on the
# platform; the analysis takes that of a 64-bit Python, so that it gives one
# result everywhere. A 32-bit Python also rejects the widths from 2**31 on,
# where the analysis converts: an edge too many, not one missed.
_PERCENT_BOUNDS = {"width": 2**63 - 1, "precision": 2**31 - 1}
# On bytes, `%r` and `%a` convert with repr; `%s` and `%b` call `__bytes__`,
# which the analysis does not model.
_BYTES_PERCENT_CONVERSIONS = {
    **dict.fromkeys(PERCENT_CONVERSIONS),
    "b": None,
    "r": "repr",
    "a": "repr",
}


# Special methods whose implementation in `object` calls another one where
# the class does not define them.
FALLBACKS = {"__ne__": "__eq__"}

# The comparisons, and those of them that test equality. The others order.
COMPARISON_METHODS = frozenset(
    {"__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__"}
)
EQUALITIES = frozenset({"__eq__", "__ne__"})

# The families of builtin containers whose comparisons compare elements,
# by kind: two containers compare their elements only within one family, as
# in CPython (a list never with a tuple or a deque; a set with a frozenset).
# Every dict, also one of `collections`, is of the family "dict".
_FAMILIES = {
    "list": "list",
    "tuple": "tuple",
    "collections.deque": "deque",
    "set": "set",
    "frozenset": "set",
}


def comparison_family(container):
    """The comparison family of `container` (see `_FAMILIES`), or None."""
    family = _FAMILIES.get(container.kind)
    if family is None and is_dict(container):
        family = "dict"
    return family


class Protocols:
    def add_operator(
        self, left, right, method, reflected, inplace, dst, caller, site, unary=False
    ):
        """dst ⊇ the result of an operator. `method` is the special method of
        the left operand (`__add__`) and `reflected` that of the right one
        (`__radd__`), or None. `left op= right` (`inplace`) calls
        `__iadd__`, and `__add__` where no `__iadd__` is defined; `!=`
        calls `__eq__` where no `__ne__` is (see `FALLBACKS`). Either
        operand may be None if it is not tracked; a `unary` operator has no
        right operand. `dst` may be None."""
        operation = _Operator(
            self, left, right, method, reflected, inplace, dst, unary, caller, site
        )
        # `in` searches generators and externals too (see `_contains`).
        if method == "__contains__":
            kinds = (Instance, Class, Container, Generator, External, Typed)
        else:
            kinds = (Instance, Class, Container, Typed)
        # The result of an operator on the saturated value is saturated; a
        # membership test gives a bool.
        results = (dst,) if method != "__contains__" else ()
        for node, is_left in ((left, True), (right, False)):
            if node is not None:
                operand = Each(
                    self._operand, operation, is_left, kinds=kinds, results=results
                )
                self.solver.attach(node, operand)

    def _operand(self, obj, operation, is_left):
        if operation.method == "__contains__":
            if is_left:
                self._contains(obj, operation)
            return
        if isinstance(obj, Container) and operation.method in COMPARISON_METHODS:
            operation.comparison().arrive(obj, is_left)
        if isinstance(obj, (Instance, Class)):
            # A class's special methods are its metaclass's.
            name = operation.method if is_left else operation.reflected
            if name is None:
                return
            call = operation.call(is_left)
            unless = ()
            if is_left and operation.inplace:
                # `a += b` falls back to `__add__` where no `__iadd__` is.
                inplace = "__i" + name[2:]
                self.call_dunder(obj, inplace, call, operation.dst)
                unless = (inplace,)
            self.call_dunder(obj, name, call, operation.dst, unless)
            if name in FALLBACKS:
                # object.__ne__ calls __eq__.
                fallback = FALLBACKS[name]
                self.call_dunder(obj, fallback, call, operation.dst, (name,))
        elif isinstance(obj, Container) and obj.kind not in CONTAINER_CLASSES:
            self.combine(obj, operation, is_left)
        elif isinstance(obj, (Typed, Container)):
            # A typed value, or a container of `collections`: what the
            # method of its class in the stubs returns (`Counter.__add__`).
            name = operation.method if is_left else operation.reflected
            if name is not None:
                origin = (operation.caller, operation.site, "operator", is_left)
                self.typed_special(obj, name, operation.dst, origin)

    def _contains(self, obj, operation):
        """`value in obj`. An instance whose class defines `__contains__`
        answers alone, and so does a class whose metaclass does. Anything
        else is searched: Python compares the value with each element
        (iterating an instance through `__iter__` or `__getitem__`), so the
        value's `__eq__` may run, and that of each element the analysis
        tracks. The value is compared whatever the analysis knows of the
        elements: some values (None, numbers, bytes) have no object, so an
        empty node is not an empty container; so `in` on `[]` compares too.
        An instance or class is searched once its type may leave
        `__contains__` to Python or an external class, whose `__contains__`
        may compare too (see `python_method`). A limit: an `in` whose
        container never holds an object compares nothing."""
        if isinstance(obj, (Instance, Class)):
            call = operation.call(True)
            self.call_dunder(obj, "__contains__", call, operation.dst)
            operation.membership().apply(obj)
            types = self._types(obj)
            self.solver.attach(types, Each(self._searched_type, operation))
        elif isinstance(obj, (Container, Generator, External, Typed)):
            operation.membership().apply(obj)
            self._compare_value(operation)
            if isinstance(obj, Container) and hashes_keys(obj):
                self._hash_value(operation)

    def compare_member(self, element, operation, elements):
        """`value in container` found `element` while iterating: Python
        compares the element with the value, so the `__eq__` of the element
        may run."""
        if isinstance(element, (Instance, Class)):
            call = operation.compare_call("element", operation.right)
            self.call_dunder(element, "__eq__", call, None)

    def _compare_value(self, operation):
        """Compare the value of `in`, once, with the elements: its `__eq__`
        may run, reflected. The elements are those of every container that
        reaches `in`, including those that arrive after the comparison."""
        key = (operation, "compare value")
        if operation.right is not None and key not in self._subscriptions:
            self._subscriptions.add(key)
            operation.membership()
            call = operation.compare_call("value", operation.elements)
            compare = Each(self._call_eq, call)
            self.solver.attach(operation.right, compare)

    def _hash_value(self, operation):
        """`value in d` hashes the value, once, for the sets and dicts `d`
        that the container of `operation` holds."""
        key = (operation, "hash value")
        if operation.right is not None and key not in self._subscriptions:
            self._subscriptions.add(key)
            self.add_hash(operation.right, operation.caller, operation.site)

    def _searched_type(self, cls, operation):
        """`in` searches the objects of the class `cls` where Python's own
        `__contains__` or an outside class's may run for them; an outside
        class (a metaclass) may compare."""
        if not isinstance(cls, Class):
            self._compare_value(operation)
        elif cls not in operation.classes:
            operation.classes.add(cls)
            python = self.python_method(cls, "__contains__")
            self.solver.attach(python, Each(self._python_contains, operation))

    def _python_contains(self, python, operation):
        """Python's own `__contains__`, or an external class's, may run for
        the container of `operation`: compare its value."""
        self._compare_value(operation)

    def compare_containers(self, items, method, call, kind="compare"):
        """The containers in the node `items` compare their elements with
        each other, family by family (see `_ElementComparison`), for the
        comparison `method`: the items of `sorted`, `min` and `max`."""
        comparison = _ElementComparison(self, method, call, kind)
        for is_left in (True, False):
            arrive = Each(comparison.arrive, is_left, kinds=(Container,))
            self.solver.attach(items, arrive)

    def _call_eq(self, value, call):
        if isinstance(value, (Instance, Class)):
            self.call_dunder(value, "__eq__", call, None)

    def add_conversion(self, value, kind, caller, site, spec=None):
        """`str(value)`, `repr(value)` or `format(value, spec)` (`kind`), and
        the same conversions in f-strings and `print`. `__format__` gets
        `spec` (None if it is not tracked); the methods it falls back to get
        no arguments."""
        call = self.site_call(caller, site, ("convert", kind))
        formatted = call
        if kind == "format":
            formatted = self.site_call(caller, site, ("format",), [spec])
        for name, unless in CONVERSIONS[kind]:
            implicit = formatted if name == "__format__" else call
            self.add_special_call(value, name, implicit, unless)
        # A builtin container converts what its repr() reaches with repr():
        # the conversion gathers that in one node, which `__repr__` is called on.
        reached = self.node()
        each = Each(
            self._convert_container,
            reached,
            caller,
            site,
            kinds=(Container,),
            results=(reached,),
        )
        self.solver.attach(value, each)

    def _convert_container(self, container, reached, caller, site):
        """The conversion of a builtin container is its repr(): `reached`
        gets what that reaches, and on the first container the conversion
        calls `__repr__` on `reached`, once."""
        if container.kind not in _REPR_CONTAINERS:
            return
        key = (reached, "convert elements")
        if key not in self._subscriptions:
            self._subscriptions.add(key)
            call = self.site_call(caller, site, ("convert", "repr"))
            self.add_special_call(reached, "__repr__", call)
        self.add_edge(self.repr_reach(container), reached)

    def repr_reach(self, container):
        """The node, one per builtin container, with what its repr() reaches:
        its elements (the keys and values of a dict) and, through one
        constraint on each, what the repr() of the builtin containers among
        them reaches. A container that holds itself adds an edge to itself."""
        if container.repr_reach is None:
            node = container.repr_reach = self.node()
            parts = [self.every(container)]
            if container.kind == "dict":
                parts.append(self.keys(container))
            for part in parts:
                self.add_edge(part, node)
                nested = Each(
                    self._reach_nested, node, kinds=(Container,), results=(node,)
                )
                self.solver.attach(part, nested)
        return container.repr_reach

    def _reach_nested(self, nested, node):
        if nested.kind in _REPR_CONTAINERS:
            self.add_edge(self.repr_reach(nested), node)

    def add_truth(self, value, caller, site):
        """Python tests the truth of `value` (a condition, an operand of
        `not`, `and`, `or`, a result that a comparison uses): `__bool__`,
        else `__len__`."""
        call = self.site_call(caller, site, ("truth",))
        self.add_special_call(value, "__bool__", call)
        self.add_special_call(value, "__len__", call, ("__bool__",))

    def add_percent(self, fmt, value, caller, site):
        """`fmt % value` and `fmt %= value`: for each str constant that
        `fmt` holds, each of its conversions converts the item it takes."""
        each = Each(self._percent_format, value, caller, site, kinds=(Const,))
        self.solver.attach(fmt, each)

    def _percent_format(self, fmt, value, caller, site):
        """`fmt` is a str or bytes constant: each of its fields (position or
        mapping key, conversion) converts the item it takes, an element of
        a tuple, a value of a dict, or the value itself where it is the
        only item."""
        if isinstance(fmt.value, str):
            fields = _percent_fields(fmt.value, PERCENT_CONVERSIONS)
        elif isinstance(fmt.value, bytes):
            # Each byte is one character; the keys are bytes.
            text = fmt.value.decode("latin-1")
            fields = [
                (key if isinstance(key, int) else key.encode("latin-1"), kind)
                for key, kind in _percent_fields(text, _BYTES_PERCENT_CONVERSIONS)
            ]
        else:
            return
        if any(kind for _, kind in fields):
            self.solver.attach(value, Each(self._percent, fields, caller, site))

    def _percent(self, obj, fields, caller, site):
        """The items of `fmt % obj`, field by field until Python rejects
        one: the elements of a tuple, which has no keys; else `obj` itself,
        which goes to what the format takes first, so only a field at
        position 0 converts it (a `*` width or `%d` there takes it, and a
        later field lacks its argument), and for a dict the values of the
        named fields, after which a field without a key has no argument; a
        number conversion rejects a dict."""
        if isinstance(obj, Container) and obj.kind == "tuple":
            for key, kind in fields:
                if not isinstance(key, int):
                    return
                if kind is not None:
                    self.add_conversion(self.element(obj, key), kind, caller, site)
            return
        whole = isinstance(obj, (Instance, Class, Container))
        mapping = isinstance(obj, Container) and is_dict(obj)
        named = False
        for key, kind in fields:
            if not isinstance(key, int):
                if not mapping:
                    return
                named = True
                item = self.element(obj, key)
            elif named or key != 0 or (kind is None and mapping):
                # No argument, or a dict that a number conversion takes.
                return
            elif whole:
                item = self.constant(obj)
            else:
                continue
            if kind is not None:
                self.add_conversion(item, kind, caller, site)

    def add_special_call(self, value, name, call, unless=()):
        """Call the special method `name` of each object that `value` holds
        with the implicit call `call` (`len(x)` calls `__len__`); with
        `unless`, only where Python falls back to it. Instances and classes
        have special methods (see `call_dunder`); the other objects are
        builtin or outside values, whose special methods give no edges."""
        receivers = (Instance, Class)
        each = Each(self.call_dunder, name, call, None, unless, kinds=receivers)
        self.solver.attach(value, each)

    def add_await(self, value, dst, caller, site):
        """`dst ⊇ await value`: what `value.__await__()` finishes with. A
        coroutine finishes with what its function returns, and so does a
        generator; an instance's `__await__` is called (implicitly, from the
        scope of the await) and the generators it returns finish with what
        their functions return, and an instance whose class defines no
        `__await__` is itself; an outside value is itself."""
        iterator = self.node()
        self.solver.attach(iterator, Each(self._finished, dst, results=(dst,)))
        call = self.site_call(caller, site, ("await",))
        each = Each(self._await, call, iterator, dst, results=(dst,))
        self.solver.attach(value, each)

    def _await(self, obj, call, iterator, dst):
        if isinstance(obj, (Instance, Class)):
            self.call_dunder(obj, "__await__", call, iterator)
            # An object whose type defines no __await__ is itself: an
            # outside call that gives its awaited value at the call
            # (`wait_for`) is awaited again.
            each = Each(self._await_type, obj, dst, results=(dst,))
            self.solver.attach(self._types(obj), each)
        elif isinstance(obj, (External, Typed, Container)):
            # What an outside call gives is already what awaiting it gives
            # (see *Typed outside values* in the design).
            self.add_object(dst, obj)
        else:
            self._finished(obj, dst)

    def _await_type(self, cls, obj, dst):
        """`await obj` gives `obj` itself where its type `cls` defines no
        `__await__`: an outside class, or one where Python's own may run."""
        if isinstance(cls, Class):
            python = self.python_method(cls, "__await__")
            self.solver.attach(
                python, Each(self._awaited_itself, obj, dst, results=(dst,))
            )
        else:
            self.add_object(dst, obj)

    def _awaited_itself(self, python, obj, dst):
        self.add_object(dst, obj)

    def _finished(self, obj, dst):
        """What awaiting the coroutine or generator `obj` gives."""
        if isinstance(obj, (Coroutine, Generator)):
            self.add_edge(obj.function.return_node, dst)

    def add_with(self, manager, dst, caller, site, is_async=False):
        """`with manager as target`: call `__enter__` and `__exit__` of each
        instance that `manager` holds (`__aenter__` and `__aexit__` for
        `async with`, which awaits what both return, used or not); `dst`
        (None if there is no target) gets the result of `__enter__`. An
        external gives an external result. `__exit__` gets exception
        arguments that the analysis does not track."""
        enter = self.site_call(caller, site, ("enter",))
        leave = self.site_call(caller, site, ("exit",), [None, None, None])
        names = ("__aenter__", "__aexit__") if is_async else ("__enter__", "__exit__")
        exited = None
        if is_async:
            entered, dst = dst, self.node()
            if entered is None:
                entered = self.node()
            self.add_await(dst, entered, caller, site)
            exited = self.node()
            self.add_await(exited, self.node(), caller, site)
        each = Each(self._with, dst, exited, enter, leave, names, results=(dst,))
        self.solver.attach(manager, each)

    def _with(self, obj, dst, exited, enter, leave, names):
        if isinstance(obj, (Instance, Class)):
            self.call_dunder(obj, names[0], enter, dst)
            self.call_dunder(obj, names[1], leave, exited)
        elif isinstance(obj, Typed):
            origin = (enter.caller, enter.site, "enter")
            self.typed_special(obj, names[0], dst, origin)
        elif isinstance(obj, External) and dst is not None:
            self.add_object(dst, obj)

    def add_raise(self, exception, caller, site):
        """`raise exception`: a class is instantiated, as by a call without
        arguments."""
        call = self.site_call(caller, site, ("raise",), implicit=False)
        self.solver.attach(exception, Each(self._raise, call, kinds=(Class,)))

    def _raise(self, cls, call):
        self.instantiate(cls, call)

    def add_handler(self, types, dst):
        """`except types as name`: `dst` gets every instance of the classes
        that `types` holds, and of their subclasses, that the analysis
        creates, whether or not it is raised; for an outside class, an
        instance of it (a typed value if the stubs describe it)."""
        self.solver.attach(types, Each(self._handler, dst, results=(dst,)))

    def _handler(self, obj, dst):
        match obj:
            case Class():
                self.add_edge(obj.instances, dst)
            case External():
                # An instance of the outside class: typed if the stubs
                # describe it, else named like the class.
                for value in self.outside_instance_of(obj):
                    self.add_object(dst, value)
            case Container():
                # Once per tuple: a tuple of classes can contain itself.
                if (obj, dst) not in self._handlers:
                    self._handlers.add((obj, dst))
                    each = Each(self._handler, dst, results=(dst,))
                    self.solver.attach(self.every(obj), each)


class _Operator:
    """An operator at `site` in the scope named `caller`. `call(is_left)`
    is the implicit call of a special method of one operand, with the other
    operand as its argument."""

    __slots__ = (
        "analysis",
        "left",
        "right",
        "method",
        "reflected",
        "inplace",
        "dst",
        "unary",
        "caller",
        "site",
        "_calls",
        "_membership",
        "_compare_calls",
        "elements",
        "classes",
        "_comparison",
    )

    def __init__(
        self,
        analysis,
        left,
        right,
        method,
        reflected,
        inplace,
        dst,
        unary,
        caller,
        site,
    ):
        self.analysis = analysis
        self.left = left
        self.right = right
        self.method = method
        self.reflected = reflected
        self.inplace = inplace
        self.dst = dst
        self.unary = unary
        self.caller = caller
        self.site = site
        self._calls = {}
        self._membership = None
        self._compare_calls = {}
        # What iterating over the container of `in` gives.
        self.elements = None
        # The classes of the instances that the container of `in` holds.
        self.classes = set()
        self._comparison = None

    def membership(self):
        """The iteration that `in` falls back to where no class of the
        container defines `__contains__`, and that builtin containers do:
        each element is compared with the value, so the `__eq__` of both
        may run."""
        if self._membership is None:
            analysis = self.analysis
            elements = self.elements = analysis.node()
            compare = Each(analysis.compare_member, self, elements)
            analysis.solver.attach(elements, compare)
            self._membership = analysis.iteration(
                elements, self.caller, self.site, ("__contains__",), "membership"
            )
        return self._membership

    def comparison(self):
        """How a comparison compares the elements of the containers of its
        two operands (see `_ElementComparison`)."""
        if self._comparison is None:
            analysis = self.analysis
            comparison = _ElementComparison(analysis, self.method, self, "compare")
            self._comparison = comparison
        return self._comparison

    def compare_call(self, side, other):
        """The implicit call of the `__eq__` of the element or of the value
        (`side`) with the node `other` (None if the value is not
        tracked)."""
        if side not in self._compare_calls:
            call = self.analysis.site_call(
                self.caller, self.site, ("compare", side), [other]
            )
            self._compare_calls[side] = (other, call)
        compared, call = self._compare_calls[side]
        # The cache keeps the first node: another would be lost.
        assert compared is other, f"`in` at {self.site} compares another node"
        return call

    def call(self, is_left):
        if is_left not in self._calls:
            if self.unary:
                args = []
            else:
                args = [self.right if is_left else self.left]
            role = ("operator", self.method, is_left)
            self._calls[is_left] = self.analysis.site_call(
                self.caller, self.site, role, args
            )
        return self._calls[is_left]


class _ElementComparison:
    """How a comparison at the construct of `call` (its scope and site)
    compares the elements of the containers that reach its two sides
    (`arrive`), for the comparison `method`: as in CPython, only within one
    family (see `_FAMILIES`). For each family it gathers the elements of
    the containers of each side in a node (the keys and the values of a
    dict), and once both sides have a container of the family,
    compares them: their instances and classes get `__eq__`, and for an
    ordering of lists, tuples or deques also `method` (its reflection
    where no class defines it), as any pair may be the first that differs;
    sets compare as subsets, with `__eq__` only, and two dicts are not
    ordered. So the work is that of a few nodes per family, not of pairs of
    containers. Containers among the elements compare nothing (a stated
    limit: comparing them per level costs a large package a third more
    time)."""

    __slots__ = ("analysis", "method", "call", "kind", "families")

    def __init__(self, analysis, method, call, kind):
        self.analysis = analysis
        self.method = method
        self.call = call
        self.kind = kind
        self.families = {}

    def arrive(self, container, is_left):
        family = comparison_family(container)
        ordering = self.method not in EQUALITIES
        if family is None or (ordering and family == "dict"):
            return
        if family not in self.families:
            # The elements of each side, and whether it has a container.
            sides = (self.analysis.node(), self.analysis.node())
            self.families[family] = (sides, [False, False])
        sides, present = self.families[family]
        side = 0 if is_left else 1
        self.analysis.add_edge(self.analysis.every(container), sides[side])
        if is_dict(container):
            self.analysis.add_edge(self.analysis.keys(container), sides[side])
        if not present[side]:
            present[side] = True
            if all(present):
                self._join(sides, family)

    def _join(self, sides, family):
        analysis = self.analysis
        elements = analysis.node()
        plan = [("__eq__", ())]
        if self.method not in EQUALITIES and family in ("list", "tuple", "deque"):
            reflected = REFLECTED_COMPARISONS[self.method]
            plan += [(self.method, ()), (reflected, (self.method,))]
        compare = Each(
            analysis._call_protocol, plan, self.call, self.kind, kinds=(Instance, Class)
        )
        analysis.solver.attach(elements, compare)
        for node in sides:
            analysis.add_edge(node, elements)


def _percent_fields(text, conversions):
    """The fields of `text % value`, in order, up to the first one that
    Python rejects: (position or mapping key, what `conversions` gives for
    the conversion: "str", "repr", or None for one that converts nothing)
    for each field but `%%` (see `percent_spans`)."""
    spans, _ = percent_spans(text, conversions)
    return [(key, kind) for _, _, key, kind in spans if kind != "%"]


def percent_spans(text, conversions):
    """The fields of `text % value` as Python reads them, in order, up to
    the first one that it rejects, each (start, end, position or mapping
    key, what `conversions` gives for the conversion), with `%%` as
    (start, end, None, "%"); and whether Python reads every field. A field
    is `%`, an optional key in balanced parentheses, flags, a width (digits
    or `*`), a precision (`.` with digits, `*` or nothing), one length
    modifier and the conversion. A width or precision `*` takes an item of
    its own, and is rejected in a field with a key; a width or precision in
    digits is rejected past its bound (`_PERCENT_BOUNDS`); `%` is the
    conversion of `%%` only."""
    fields, position, index, end = [], 0, 0, len(text)
    while (index := text.find("%", index)) >= 0:
        start = index
        index += 1
        if text.startswith("%", index):
            index += 1
            fields.append((start, index, None, "%"))
            continue
        key = None
        if text.startswith("(", index):
            index += 1
            opened, depth = index, 1
            while index < end and depth:
                depth += {"(": 1, ")": -1}.get(text[index], 0)
                index += 1
            if depth:
                return fields, False
            key = text[opened : index - 1]
        while index < end and text[index] in "-+ #0":
            index += 1
        stars = 0
        for part in ("width", "precision"):
            if part == "precision":
                if not text.startswith(".", index):
                    break
                index += 1
            if text.startswith("*", index):
                stars += 1
                index += 1
                continue
            value = 0
            while index < end and text[index] in "0123456789":
                # Bounded: Python rejects the field as soon as it passes.
                value = value * 10 + "0123456789".index(text[index])
                if value > _PERCENT_BOUNDS[part]:
                    return fields, False
                index += 1
        if stars and key is not None:
            return fields, False
        if index < end and text[index] in "hlL":
            index += 1
        if index == end or text[index] not in conversions:
            return fields, False
        position += stars
        kind = conversions[text[index]]
        index += 1
        fields.append((start, index, position if key is None else key, kind))
        position += 1
    return fields, True
