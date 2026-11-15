"""Names built from a constant part and another value (patterns).

A str that the code builds from a constant and another value is a pattern,
its constant prefix and suffix: `"visit_" + kind`, `"visit_%s" % kind`,
`"visit_{}".format(kind)`, `f"visit_{kind}"`, and the same with a constant
suffix. A pattern needs a non-empty constant part. The builder finds these
forms in the AST (`PatternBuilder`) and gives the expression the `Pattern`
of its prefix and suffix, which flows like a str constant. A pattern of
`+` or `%` with an operand that is not certainly a plain str (or int,
bytes, exact container) also gives the unnamed external, a value of any
class (`add_pattern_operand`). `lower()`,
`upper()` and `casefold()` of a pattern give the pattern of the converted
prefix and suffix, which matches no ASCII name that the conversion changes
(`_rule_case`).

`getattr(x, name)` and `hasattr(x, name)` with a pattern load every
attribute of `x` whose name matches it (`Patterns`): on an instance, the
names that the class bodies of its MRO define or that stores assign on
those classes (an ordinary load: MRO, descriptors, properties), and the
names that stores assign anywhere, as fields of the instance only; on a
module, its fields. Each side subscribes to the other, so a base or a name
that appears later is found. A name that the object does not define is not
loaded, so `__getattr__` is not called by a pattern. `setattr` and `delattr`
with a pattern store and delete no known name. A dict read with a pattern
key gets the entries whose str key matches it (containers.py).
"""

import ast
import string

from .attributes import Load
from .model import Const, Container, Instance, Module, Pattern, Typed
from .protocols import PERCENT_CONVERSIONS, percent_spans
from .solver import Each


class PatternBuilder:
    """The part of the builder that finds the str forms that are patterns
    (see the module docstring)."""

    def string_pattern(self, node):
        """The node of the pattern that the expression `node` builds, or
        None."""
        parts = _parts(node)
        if parts is None:
            return None
        merged = []
        for part in parts:
            if isinstance(part, str) and merged and isinstance(merged[-1], str):
                merged[-1] += part
            else:
                merged.append(part)
        prefix = merged.pop(0) if merged and isinstance(merged[0], str) else ""
        suffix = merged.pop() if merged and isinstance(merged[-1], str) else ""
        if not merged or not (prefix or suffix):
            return None
        return self.analysis.constant(self.analysis.pattern(prefix, suffix))


def _parts(node):
    """The parts of the str that `node` builds: str for a constant part, an
    expression for a value converted by `str()`, None for a value converted
    otherwise; or None if `node` is not such a form."""
    match node:
        case ast.BinOp(op=ast.Add()):
            items = []
            while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                items.append(node.right)
                node = node.left
            items.append(node)
            parts = []
            for item in reversed(items):
                if isinstance(item, ast.Constant):
                    if not isinstance(item.value, str):
                        return None
                    parts.append(item.value)
                elif isinstance(item, ast.JoinedStr):
                    parts.extend(_fstring_parts(item))
                else:
                    parts.append(item)
            return parts
        case ast.BinOp(op=ast.Mod(), left=ast.Constant(value=str() as text)):
            return _percent_parts(text)
        case ast.JoinedStr():
            return _fstring_parts(node)
        case ast.Call(
            func=ast.Attribute(value=ast.Constant(value=str() as text), attr="format")
        ):
            return _format_parts(text, node.args, node.keywords)
    return None


def _fstring_parts(node):
    parts = []
    for value in node.values:
        if isinstance(value, ast.Constant):
            parts.append(value.value)
        elif value.conversion == -1 and value.format_spec is None:
            parts.append(value.value)
        else:
            parts.append(None)
    return parts


def _percent_parts(text):
    """The parts of `text % value`: the literal text, `%` for `%%`, and
    None for each other field; or None if `text` has no field to format,
    or if Python rejects a field (see `percent_spans`), so that no pattern
    is made of a format that the analysis cannot read with certainty."""
    spans, accepted = percent_spans(text, PERCENT_CONVERSIONS)
    if not accepted or all(kind == "%" for _, _, _, kind in spans):
        return None
    parts, start = [], 0
    for begin, end, _, kind in spans:
        parts.append(text[start:begin])
        parts.append("%" if kind == "%" else None)
        start = end
    parts.append(text[start:])
    return parts


def _format_parts(text, args, keywords):
    """The parts of `text.format(...)`: each field is another value,
    whatever it names; or None if `text` is no format string."""
    try:
        fields = list(string.Formatter().parse(text))
    except ValueError:
        return None
    parts = []
    for literal, field, _, _ in fields:
        parts.append(literal)
        if field is not None:
            parts.append(None)
    return parts


class Patterns:
    """The part of `Analysis` that loads attributes by pattern (see the
    module docstring)."""

    def pattern(self, prefix, suffix, case=None, exact=True):
        key = (prefix, suffix, case, exact)
        if key not in self._patterns:
            self._patterns[key] = Pattern(prefix, suffix, case, exact)
            self._pattern_states[self._patterns[key]] = _PatternState()
        return self._patterns[key]

    def _rule_case(self, call, receiver, args, case):
        """str.lower(), str.upper(), and str.casefold() as lower(): of a
        pattern whose constant parts are ASCII, the pattern of the converted
        parts; else a str of unknown value. The case of other characters
        depends on the Unicode database of the running Python. Of a class
        member (an enum member, whose class may define the method), also
        any value."""
        if (
            isinstance(receiver, Pattern)
            and receiver.prefix.isascii()
            and receiver.suffix.isascii()
        ):
            prefix = getattr(receiver.prefix, case)()
            suffix = getattr(receiver.suffix, case)()
            result = self.pattern(prefix, suffix, case)
        else:
            result = self.typed("builtins.str")
        if call.dst is not None:
            self.add_object(call.dst, result)
            if _inexact(receiver):
                self.add_object(call.dst, self.unknown_external)

    def add_pattern_operand(self, operand, result):
        """`result` is a pattern only where `str`'s own operation runs on
        plain strs: any other operand may be a str subclass whose
        `__radd__`, `__add__` or `__rmod__` runs and returns any value. So
        each object of the operand node `operand` that is not certainly a
        value for which `str`'s operation runs adds the unnamed external
        (`unknown_external`, a value of any class) to `result` (see
        `_certain_operand`); so does an operand that is not a node (None),
        and one that holds nothing at the fixpoint (see
        `complete_pattern_operands`). Not a str of unknown value: the
        reflected method may return any object, whose own operators a
        later `+` would call."""
        if operand is None:
            self.add_object(result, self.unknown_external)
            return
        each = Each(self._pattern_operand, result, results=(result,))
        self.solver.attach(operand, each)
        self._pattern_operands.append((operand, result))

    def _pattern_operand(self, obj, result):
        if not _certain_operand(obj):
            self.add_object(result, self.unknown_external)

    def complete_pattern_operands(self):
        """The unnamed external in the result of each pattern whose
        operand holds nothing at the fixpoint: code or values that the
        analysis does not see give it. Return whether anything was
        added."""
        added = False
        pending = self._pattern_operands[self._completed_pattern_operands :]
        for operand, result in pending:
            if not self.solver.objects(operand):
                self.add_object(result, self.unknown_external)
                added = True
        self._completed_pattern_operands = len(self._pattern_operands)
        return added

    def load_by_pattern(self, pattern, access):
        """The getattr or hasattr `access` loads by `pattern`."""
        load = Each(
            self._pattern_target,
            pattern,
            access,
            kinds=(Instance, Module),
            results=(access.dst,),
        )
        self.solver.attach(access.obj, load)

    def _pattern_target(self, obj, pattern, access):
        state = self._pattern_states[pattern]
        if access in state.targets.setdefault(obj, []):
            return
        state.targets[obj].append(access)
        if isinstance(obj, Instance):
            self._watch_classes(pattern)
            for name in sorted(self._store_names):
                self._pattern_candidate(obj, pattern, name, False)
        else:
            for name in self._module_names.get(obj, ()):
                self._pattern_candidate(obj, pattern, name, True)
        for name, full in list(state.candidates.get(obj, ())):
            self._pattern_load(access, obj, name, full)

    def _watch_classes(self, pattern):
        """Once per pattern, let the instances of each class find the names
        that the class body defines or that stores assign on the class."""
        state = self._pattern_states[pattern]
        if state.watching:
            return
        state.watching = True
        for cls in self.classes:
            names = set(cls.defines) | self._class_store_names.get(cls, set())
            for name in sorted(names):
                self._pattern_class_name(pattern, cls, name)

    def _pattern_class_name(self, pattern, cls, name):
        """`name` is defined on `cls`: if it matches, the instances of `cls`
        and its subclasses have it."""
        if pattern.matches(name) is None:
            return
        state = self._pattern_states[pattern]
        names = state.class_names.get(cls)
        if names is None:
            names = state.class_names[cls] = []
            state.class_seen[cls] = []
            watch = Each(self._pattern_class_instance, pattern, cls)
            self.solver.attach(cls.instances, watch)
        if name in names:
            return
        names.append(name)
        for instance in list(state.class_seen[cls]):
            self.solver.revisit(self._pattern_candidate, instance, pattern, name, True)

    def _pattern_class_instance(self, instance, pattern, cls):
        state = self._pattern_states[pattern]
        state.class_seen[cls].append(instance)
        for name in list(state.class_names[cls]):
            self._pattern_candidate(instance, pattern, name, True)

    def pattern_class_store(self, cls, name):
        """A store assigns `name` on the class `cls`."""
        stored = self._class_store_names.setdefault(cls, set())
        if name in stored:
            return
        stored.add(name)
        # A load may convert a pattern and make another (`_rule_case`).
        for pattern, state in list(self._pattern_states.items()):
            if state.watching:
                self._pattern_class_name(pattern, cls, name)

    def pattern_store_name(self, name):
        """A store assigns `name` on an object; instances that a pattern
        reaches may have it as a field."""
        if name in self._store_names:
            return
        self._store_names.add(name)
        for pattern, state in list(self._pattern_states.items()):
            for obj in list(state.targets):
                if isinstance(obj, Instance):
                    self.solver.revisit(
                        self._pattern_candidate, obj, pattern, name, False
                    )

    def _pattern_candidate(self, obj, pattern, name, full):
        """`obj` has the attribute `name`, through its class (`full`, an
        ordinary load) or as a field: load it for every access by
        `pattern` that reaches `obj`, if it matches."""
        if pattern.matches(name) is None:
            return
        state = self._pattern_states[pattern]
        candidates = state.candidates.setdefault(obj, {})
        if (name, full) in candidates:
            return
        candidates[(name, full)] = None
        for access in list(state.targets.get(obj, ())):
            self._pattern_load(access, obj, name, full)

    def _pattern_load(self, access, obj, name, full):
        key = (obj, name, full)
        if key in access.loaded:
            return
        access.loaded.add(key)
        if full:
            loader = access.loaders.get(name)
            if loader is None:
                call = access.call
                loader = Load(self, name, access.dst, call.caller, call.site)
                access.loaders[name] = loader
            loader.apply(obj)
        else:
            self.add_edge(self.field(obj, name), access.dst)

    def freeze_module_names(self):
        """The names of each module's fields when the solve starts: the
        names that a module binds, its submodules and what star imports
        give it."""
        for module in self.modules.values():
            self._module_names[module] = sorted(module.fields)


# The builtin classes whose typed values leave a pattern alone: a typed
# value is of its declared class (a stated limit), and `str`'s own
# operation keeps the literal prefix and suffix with either (`str` has an
# `__rmod__`, which formats and so keeps them; `bytes` has none that takes
# a str). `read()` gives one of them.
_PLAIN_TYPED = ("builtins.str", "builtins.bytes")


def _certain_operand(obj):
    """Whether `str`'s own `+` or `%` runs with the operand object `obj`:
    an exact constant (a str, int or bytes written in the source), an
    exact pattern (a str that the code builds), a container of exactly its
    builtin class (none derives from str), or a typed value of a class in
    `_PLAIN_TYPED`. An inexact constant, pattern or container may be an
    enum member that overrides the operator, and an instance of an
    analysed class may derive from str; the analysis does not decide that
    here."""
    if isinstance(obj, (Const, Pattern, Container)):
        return not _inexact(obj)
    return isinstance(obj, Typed) and obj.cls in _PLAIN_TYPED


def _inexact(obj):
    """Whether `obj` is an alias of a class member (an enum member): an
    inexact constant, pattern or container, which stands for an object of
    a class that may define its own methods. A rule that makes or changes
    a pattern (the operands of `+` and `%`, the receiver of a case
    method) gives any value for it."""
    return isinstance(obj, (Const, Pattern, Container)) and not obj.exact


class _PatternState:
    """What the analysis knows of a pattern: the objects that accesses by
    the pattern reach (with the accesses) and the names that each has; the
    classes whose names match, with the instances they have seen."""

    __slots__ = ("targets", "candidates", "watching", "class_names", "class_seen")

    def __init__(self):
        self.targets = {}
        self.candidates = {}
        self.watching = False
        self.class_names = {}
        self.class_seen = {}
