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
from .solver import Constraint, Each

CONVERSIONS = {
    "str": (("__str__", ()), ("__repr__", ("__str__",))),
    "repr": (("__repr__", ()),),
    "format": (
        ("__format__", ()),
        ("__str__", ("__format__",)),
        ("__repr__", ("__format__", "__str__")),
    ),
}


_REPR_CONTAINERS = frozenset({"list", "tuple", "set", "frozenset", "dict"})

PERCENT_CONVERSIONS = {
    "s": "str",
    "r": "repr",
    "a": "repr",
    **dict.fromkeys("diouxXeEfFgGc"),
}
_PERCENT_DIGITS_MAX_BY_PART = {"width": 2**63 - 1, "precision": 2**31 - 1}
_BYTES_PERCENT_CONVERSIONS = {
    **dict.fromkeys(PERCENT_CONVERSIONS),
    "b": None,
    "r": "repr",
    "a": "repr",
}


FALLBACK_BY_SPECIAL_METHOD = {"__ne__": "__eq__"}

COMPARISON_METHODS = frozenset(
    {"__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__"}
)
EQUALITIES = frozenset({"__eq__", "__ne__"})

_COMPARISON_FAMILY_BY_KIND = {
    "list": "list",
    "tuple": "tuple",
    "collections.deque": "deque",
    "set": "set",
    "frozenset": "set",
}


_OPERAND_KINDS = {
    (membership, constants): (
        Instance,
        Class,
        Container,
        *((Generator, External) if membership else ()),
        Typed,
        *((Const,) if constants else ()),
    )
    for membership in (False, True)
    for constants in (False, True)
}


def comparison_family(container):
    family = _COMPARISON_FAMILY_BY_KIND.get(container.kind)
    if family is None and is_dict(container):
        family = "dict"
    return family


class Protocols:
    def add_operator(
        self,
        left,
        right,
        method,
        reflected,
        inplace,
        dst,
        caller,
        site,
        unary=False,
        constants=False,
        extra=(),
    ):
        operation = _Operator(
            self,
            left,
            right,
            method,
            reflected,
            inplace,
            dst,
            unary,
            caller,
            site,
            extra,
        )
        kinds = _OPERAND_KINDS[method == "__contains__", constants]
        for node, is_left in ((left, True), (right, False)):
            if node is not None:
                self.solver.attach(node, _Operand(operation, is_left, kinds))

    def _operand(self, obj, operation, is_left):
        if isinstance(obj, Const):
            obj = self.string_constant_value(obj)
            if obj is None:
                return
        if operation.method == "__contains__":
            if is_left:
                self._contains(obj, operation)
            return
        if isinstance(obj, Container) and operation.method in COMPARISON_METHODS:
            operation.comparison().arrive(obj, is_left)
        if isinstance(obj, (Instance, Class)):
            name = operation.method if is_left else operation.reflected
            call = operation.call(is_left)
            unless = ()
            if is_left and operation.inplace:
                inplace = "__i" + name[2:]
                self.call_dunder(obj, inplace, call, operation.dst)
                unless = (inplace,)
            self.call_dunder(obj, name, call, operation.dst, unless)
            if name in FALLBACK_BY_SPECIAL_METHOD:
                fallback = FALLBACK_BY_SPECIAL_METHOD[name]
                self.call_dunder(obj, fallback, call, operation.dst, (name,))
        elif isinstance(obj, Container) and obj.kind not in CONTAINER_CLASSES:
            self.combine(obj, operation, is_left)
        else:
            name = operation.method if is_left else operation.reflected
            origin = (operation.caller, operation.site, "operator", is_left)
            self.typed_special(obj, name, operation.dst, origin)

    def _contains(self, obj, operation):
        if isinstance(obj, (Instance, Class)):
            call = operation.call(True)
            self.call_dunder(obj, "__contains__", call, operation.dst)
            operation.membership().apply(obj)
            types = self._types(obj)
            self.solver.attach(types, Each(self._searched_type, operation))
        else:
            operation.membership().apply(obj)
            self._compare_value(operation)
            if isinstance(obj, Container) and hashes_keys(obj):
                self._hash_value(operation)

    def compare_member(self, element, operation, elements):
        if isinstance(element, (Instance, Class)):
            call = operation.compare_call("element", operation.right)
            self.call_dunder(element, "__eq__", call, None)

    def _compare_value(self, operation):
        key = (operation, "compare value")
        if operation.right is not None and key not in self._subscriptions:
            self._subscriptions.add(key)
            operation.membership()
            call = operation.compare_call("value", operation.elements)
            compare = Each(self._call_eq, call)
            self.solver.attach(operation.right, compare)

    def _hash_value(self, operation):
        key = (operation, "hash value")
        if operation.right is not None and key not in self._subscriptions:
            self._subscriptions.add(key)
            self.add_hash(operation.right, operation.caller, operation.site)

    def _searched_type(self, cls, operation):
        if not isinstance(cls, Class):
            self._compare_value(operation)
        elif operation.classes is None or cls not in operation.classes:
            if operation.classes is None:
                operation.classes = set()
            operation.classes.add(cls)
            python = self.python_method(cls, "__contains__")
            self.solver.attach(python, Each(self._python_contains, operation))

    def _python_contains(self, python, operation):
        self._compare_value(operation)

    def compare_containers(self, items, method, call, kind="compare"):
        comparison = _ElementComparison(self, method, call, kind)
        for is_left in (True, False):
            arrive = Each(comparison.arrive, is_left, kinds=(Container,))
            self.solver.attach(items, arrive)

    def _call_eq(self, value, call):
        if isinstance(value, (Instance, Class)):
            self.call_dunder(value, "__eq__", call, None)

    def add_conversion(self, value, kind, caller, site, spec=None):
        call = self.site_call(caller, site, ("convert", kind))
        formatted = call
        if kind == "format":
            formatted = self.site_call(caller, site, ("format",), [spec])
        for name, unless in CONVERSIONS[kind]:
            implicit = formatted if name == "__format__" else call
            self.add_special_call(value, name, implicit, unless)
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
        if container.kind not in _REPR_CONTAINERS:
            return
        key = (reached, "convert elements")
        if key not in self._subscriptions:
            self._subscriptions.add(key)
            call = self.site_call(caller, site, ("convert", "repr"))
            self.add_special_call(reached, "__repr__", call)
        self.add_edge(self.repr_reach(container), reached)

    def repr_reach(self, container):
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
        call = self.site_call(caller, site, ("truth",))
        self.add_special_call(value, "__bool__", call)
        self.add_special_call(value, "__len__", call, ("__bool__",))

    def add_percent(self, fmt, value, caller, site):
        each = Each(self._percent_format, value, caller, site, kinds=(Const,))
        self.solver.attach(fmt, each)

    def _percent_format(self, fmt, value, caller, site):
        if isinstance(fmt.value, str):
            fields = _percent_fields(fmt.value, PERCENT_CONVERSIONS)
        elif isinstance(fmt.value, bytes):
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
                return
            elif whole:
                item = self.constant(obj)
            else:
                continue
            if kind is not None:
                self.add_conversion(item, kind, caller, site)

    def add_special_call(self, value, name, call, unless=()):
        receivers = (Instance, Class)
        each = Each(self.call_dunder, name, call, None, unless, kinds=receivers)
        self.solver.attach(value, each)

    def add_await(self, value, dst, caller, site):
        iterator = self.node()
        self.solver.attach(iterator, Each(self._finished, dst, results=(dst,)))
        call = self.site_call(caller, site, ("await",))
        each = Each(self._await, call, iterator, dst, results=(dst,))
        self.solver.attach(value, each)

    def _await(self, obj, call, iterator, dst):
        if isinstance(obj, (Instance, Class)):
            self.call_dunder(obj, "__await__", call, iterator)
            each = Each(self._await_type, obj, dst, results=(dst,))
            self.solver.attach(self._types(obj), each)
        elif isinstance(obj, (External, Typed, Container)):
            self.add_object(dst, obj)
        else:
            self._finished(obj, dst)

    def _await_type(self, cls, obj, dst):
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
        if isinstance(obj, (Coroutine, Generator)):
            self.add_edge(obj.function.return_node, dst)

    def add_with(self, manager, dst, caller, site, is_async=False):
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
        call = self.site_call(caller, site, ("raise",), implicit=False)
        self.solver.attach(exception, Each(self._raise, call, kinds=(Class,)))

    def _raise(self, cls, call):
        self.instantiate(cls, call)

    def add_handler(self, types, dst):
        self.solver.attach(types, Each(self._handler, dst, results=(dst,)))

    def _handler(self, obj, dst):
        match obj:
            case Class():
                self.add_edge(obj.instances, dst)
            case External():
                for value in self.outside_instance_of(obj):
                    self.add_object(dst, value)
            case Container():
                if (obj, dst) not in self._handlers:
                    self._handlers.add((obj, dst))
                    each = Each(self._handler, dst, results=(dst,))
                    self.solver.attach(self.every(obj), each)


class _Operator:
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
        "extra",
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
        extra=(),
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
        self._calls = None
        self._membership = None
        self._compare_calls = None
        self.elements = None
        self.classes = None
        self._comparison = None
        self.extra = extra

    def membership(self):
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
        if self._comparison is None:
            analysis = self.analysis
            comparison = _ElementComparison(analysis, self.method, self, "compare")
            self._comparison = comparison
        return self._comparison

    def compare_call(self, side, other):
        if self._compare_calls is None:
            self._compare_calls = {}
        if side not in self._compare_calls:
            call = self.analysis.site_call(
                self.caller, self.site, ("compare", side), [other]
            )
            self._compare_calls[side] = (other, call)
        compared, call = self._compare_calls[side]
        assert compared is other, f"`in` at {self.site} compares another node"
        return call

    def call(self, is_left):
        if self._calls is None:
            self._calls = {}
        if is_left not in self._calls:
            if self.unary:
                args = []
            else:
                args = [self.right if is_left else self.left, *self.extra]
            role = ("operator", self.method, is_left)
            self._calls[is_left] = self.analysis.site_call(
                self.caller, self.site, role, args
            )
        return self._calls[is_left]


class _Operand(Constraint):
    __slots__ = ("operation", "is_left", "kinds")

    def __init__(self, operation, is_left, kinds):
        self.operation = operation
        self.is_left = is_left
        self.kinds = kinds

    def apply(self, obj):
        if isinstance(obj, self.kinds):
            self.operation.analysis._operand(obj, self.operation, self.is_left)

    def results(self):
        if self.operation.method == "__contains__":
            return ()
        return (self.operation.dst,)


class _ElementComparison:
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
    spans, _ = percent_spans(text, conversions)
    return [(key, kind) for _, _, key, kind in spans if kind != "%"]


def percent_spans(text, conversions):
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
                value = value * 10 + "0123456789".index(text[index])
                if value > _PERCENT_DIGITS_MAX_BY_PART[part]:
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
