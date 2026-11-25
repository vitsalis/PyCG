import ast
import string

from .attributes import Load
from .model import Const, Container, Instance, Module, Pattern, Typed
from .protocols import PERCENT_CONVERSIONS, percent_spans
from .solver import Each


class PatternBuilder:
    def string_pattern(self, node):
        affixes = pattern_affixes(node)
        if affixes is None:
            return None
        return self.analysis.constant(self.analysis.pattern(*affixes))


def pattern_affixes(node):
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
    return prefix, suffix


def _parts(node):
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
    def pattern(self, prefix, suffix, case=None, exact=True):
        key = (prefix, suffix, case, exact)
        if key not in self._patterns:
            self._patterns[key] = Pattern(prefix, suffix, case, exact)
            self._pattern_states[self._patterns[key]] = _PatternState()
        return self._patterns[key]

    def _rule_case(self, call, receiver, args, case):
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
        added = False
        pending = self._pattern_operands[self._completed_pattern_operands :]
        for operand, result in pending:
            if not self.solver.objects(operand):
                self.add_object(result, self.unknown_external)
                added = True
        self._completed_pattern_operands = len(self._pattern_operands)
        return added

    def load_by_pattern(self, pattern, access):
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
        state = self._pattern_states[pattern]
        if state.watching:
            return
        state.watching = True
        for cls in self.classes:
            names = set(cls.defines) | self._class_store_names.get(cls, set())
            for name in sorted(names):
                self._pattern_class_name(pattern, cls, name)

    def _pattern_class_name(self, pattern, cls, name):
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
        stored = self._class_store_names.setdefault(cls, set())
        if name in stored:
            return
        stored.add(name)
        for pattern, state in list(self._pattern_states.items()):
            if state.watching:
                self._pattern_class_name(pattern, cls, name)

    def pattern_store_name(self, name):
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
        for module in self.modules.values():
            self._module_names[module] = sorted(module.fields)


_TYPED_CLASSES_KEEPING_PATTERNS = ("builtins.str", "builtins.bytes")


def _certain_operand(obj):
    if isinstance(obj, (Const, Pattern, Container)):
        return not _inexact(obj)
    return isinstance(obj, Typed) and obj.cls in _TYPED_CLASSES_KEEPING_PATTERNS


def _inexact(obj):
    return isinstance(obj, (Const, Pattern, Container)) and not obj.exact


class _PatternState:
    __slots__ = ("targets", "candidates", "watching", "class_names", "class_seen")

    def __init__(self):
        self.targets = {}
        self.candidates = {}
        self.watching = False
        self.class_names = {}
        self.class_seen = {}
