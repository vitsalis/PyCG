import random
from dataclasses import dataclass, field, replace

MODULES_MAX = 5
DEFINITIONS_PER_MODULE_MAX = 5
IMPORTS_PER_MODULE_MAX = 3
STATEMENTS_PER_BLOCK_MAX = 4
BLOCK_DEPTH_MAX = 3
EXPRESSION_DEPTH_MAX = 3
BASES_PER_CLASS_MAX = 3
METHODS_PER_CLASS_MAX = 5
ARGUMENTS_PER_CALL_MAX = 3
ELEMENTS_PER_CONTAINER_MAX = 3
PARAMETERS_PER_KIND_MAX = 2
CASES_PER_MATCH_MAX = 3
PATTERN_DEPTH_MAX = 2

PACKAGE = "pkg"
HEADER = ("import asyncio", "import contextlib", "import functools")
METHOD_NAMES = ("run", "get", "put", "close")
ATTRIBUTE_NAMES = ("value", "data", "handler")
KEYWORD_NAMES = ("key", "value", "default", "handler")
CONTAINER_METHODS = (
    "append",
    "extend",
    "pop",
    "get",
    "items",
    "keys",
    "values",
    "setdefault",
    "update",
    "add",
    "copy",
)
CONSTANTS = ("0", "1", "2.5", "'k'", "'run'", "b'x'", "None", "True")
BUILTIN_CLASSES = ("int", "str", "list", "dict", "tuple", "object")
EXCEPTIONS = ("Exception", "ValueError", "KeyError", "TypeError")
FUNCTION_KINDS = ("plain", "generator", "async", "async_generator")
ASYNC_KINDS = ("async", "async_generator")
YIELDING_KINDS = ("generator", "async_generator")
DEFINITION_KINDS = (
    "function",
    "function",
    "decorator",
    "factory",
    "class",
    "class",
    "diamond",
    "value",
)
METHOD_KINDS = (
    "init",
    "method",
    "method",
    "property",
    "static",
    "class",
    "call",
    "getattr",
    "getitem",
    "iter",
    "context",
    "async",
)


@dataclass
class Exports:
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    factories: list[str] = field(default_factory=list)

    def names(self):
        return [
            *self.functions,
            *self.classes,
            *self.values,
            *self.decorators,
            *self.factories,
        ]

    def callables(self):
        return [*self.functions, *self.classes, *self.decorators, *self.factories]

    def qualified(self, prefix):
        return Exports(
            *([f"{prefix}.{name}" for name in names] for names in self.lists())
        )

    def lists(self):
        return (
            self.functions,
            self.classes,
            self.values,
            self.decorators,
            self.factories,
        )

    def merge(self, other):
        for mine, theirs in zip(self.lists(), other.lists()):
            mine.extend(theirs)


@dataclass
class Module:
    name: str
    package: bool
    definitions: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)
    exports: Exports = field(default_factory=Exports)

    def path(self):
        parts = self.name.split(".")
        if self.package:
            return "/".join([*parts, "__init__.py"])
        return "/".join(parts) + ".py"

    def parent(self):
        parts = self.name.split(".")
        return parts if self.package else parts[:-1]


@dataclass
class Scope:
    variables: list[str] = field(default_factory=list)
    globals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Context:
    refs: Exports
    scope: Scope
    module_values: tuple[str, ...]
    outer: tuple[str, ...] = ()
    enclosing: tuple[str, ...] = ()
    kind: str = "module"
    loop: bool = False
    owner: str | None = None
    depth: int = 0
    cleanup: bool = False

    def visible(self):
        return [
            *self.refs.names(),
            *self.outer,
            *self.scope.variables,
            *self.scope.globals,
        ]

    def function(self):
        return self.kind in FUNCTION_KINDS


class Generator:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.counter = 0
        self.lines = []
        self.indent = 0

    def chance(self):
        return self.rng.choice((True, False))

    def count(self, maximum, minimum=0):
        return self.rng.randint(minimum, maximum)

    def fresh(self, prefix):
        self.counter += 1
        return f"{prefix}{self.counter}"

    def emit(self, line):
        self.lines.append("    " * self.indent + line)

    def program(self):
        modules = self.modules()
        for module in modules:
            self.plan(module)
        return {module.path(): self.module(module, modules) for module in modules}

    def modules(self):
        modules = [Module("main", False)]
        packages = []
        for _ in range(self.count(MODULES_MAX - 1)):
            if not packages:
                packages.append(Module(PACKAGE, True))
                modules.append(packages[-1])
                continue
            parent = self.rng.choice(packages).name
            module = Module(f"{parent}.{self.fresh('m')}", self.chance())
            modules.append(module)
            if module.package:
                packages.append(module)
        return modules

    def plan(self, module):
        for _ in range(self.count(DEFINITIONS_PER_MODULE_MAX, 1)):
            kind = self.rng.choice(DEFINITION_KINDS)
            if kind == "diamond":
                names = tuple(self.fresh("C") for _ in range(4))
                module.exports.classes.extend(names)
            elif kind == "class":
                names = (self.fresh("C"),)
                module.exports.classes.extend(names)
            elif kind == "value":
                names = (self.fresh("v"),)
                module.exports.values.extend(names)
            elif kind == "decorator":
                names = (self.fresh("deco"),)
                module.exports.decorators.extend(names)
            elif kind == "factory":
                names = (self.fresh("factory"),)
                module.exports.factories.extend(names)
            else:
                names = (self.fresh("f"),)
                module.exports.functions.extend(names)
            module.definitions.append((kind, names))

    def module(self, module, modules):
        self.lines = []
        self.indent = 0
        for line in HEADER:
            self.emit(line)
        refs = Exports()
        refs.merge(module.exports)
        others = [other for other in modules if other is not module]
        for _ in range(self.count(min(IMPORTS_PER_MODULE_MAX, len(others)))):
            refs.merge(self.import_(module, self.rng.choice(others)))
        context = Context(refs, Scope(), tuple(module.exports.values))
        for kind, names in module.definitions:
            self.definition(context, kind, names)
        self.block(context, 0)
        if module.name == "main":
            self.emit('if __name__ == "__main__":')
            self.indent += 1
            self.block(context, 1)
            self.indent -= 1
        return "\n".join(self.lines) + "\n"

    def import_(self, module, target):
        exports = target.exports
        names = exports.names()
        forms = ["import", "import as", "from", "star"]
        if not target.package and "." in target.name:
            forms.append("from package")
        if self.relative(module, target) is not None:
            forms.append("relative")
        form = self.rng.choice(forms)
        if form == "import":
            self.emit(f"import {target.name}")
            return exports.qualified(target.name)
        if form == "import as":
            alias = self.fresh("mod")
            self.emit(f"import {target.name} as {alias}")
            return exports.qualified(alias)
        if form == "from package":
            parent, _, leaf = target.name.rpartition(".")
            self.emit(f"from {parent} import {leaf}")
            return exports.qualified(leaf)
        if form == "star":
            self.emit(f"from {target.name} import *")
            return Exports(*(list(names) for names in exports.lists()))
        source = target.name if form == "from" else self.relative(module, target)
        chosen = self.rng.sample(names, self.count(len(names), 1))
        aliases = {name: self.alias(name) for name in chosen}
        imported = ", ".join(
            name if alias == name else f"{name} as {alias}"
            for name, alias in aliases.items()
        )
        self.emit(f"from {source} import {imported}")
        return Exports(
            *(
                [aliases[name] for name in names if name in aliases]
                for names in exports.lists()
            )
        )

    def alias(self, name):
        if self.chance():
            return name
        return self.fresh(name.rstrip("0123456789") + "_as")

    def relative(self, module, target):
        source = module.parent()
        parts = target.name.split(".")
        if not source or target.package:
            return None
        common = 0
        while (
            common < len(source)
            and common < len(parts) - 1
            and source[common] == parts[common]
        ):
            common += 1
        if common == 0:
            return None
        dots = "." * (len(source) - common + 1)
        return dots + ".".join(parts[common:])

    def definition(self, context, kind, names):
        if kind == "class":
            bases = self.bases(context)
            self.class_(context, names[0], bases, 0)
        elif kind == "diamond":
            top, left, right, bottom = names
            self.class_(context, top, [], 0)
            self.class_(context, left, [top], 0)
            self.class_(context, right, [top], 0)
            self.class_(context, bottom, [left, right], 0)
        elif kind == "value":
            self.emit(f"{names[0]} = {self.container(context, 1)}")
        elif kind == "decorator":
            self.decorator(context, names[0])
        elif kind == "factory":
            self.factory(context, names[0])
        else:
            kind = self.rng.choice(FUNCTION_KINDS)
            self.function(context, names[0], kind, self.decorators(context, kind))

    def bases(self, context):
        classes = context.refs.classes
        if not classes:
            return []
        count = self.count(min(BASES_PER_CLASS_MAX, len(classes)))
        return self.rng.sample(classes, count)

    def decorators(self, context, kind):
        options = [
            *(f"@{name}" for name in context.refs.decorators),
            *(
                f"@{name}({self.arguments(context, EXPRESSION_DEPTH_MAX - 1)})"
                for name in context.refs.factories
            ),
            "@functools.cache",
        ]
        if kind == "generator":
            options.append("@contextlib.contextmanager")
        count = self.count(min(2, len(options)))
        return self.rng.sample(options, count)

    def decorator(self, context, name):
        function = self.fresh("fn")
        self.emit(f"def {name}({function}):")
        self.indent += 1
        self.wrapper(context, function, Scope([function]))
        self.indent -= 1

    def factory(self, context, name):
        parameter = self.fresh("p")
        function = self.fresh("fn")
        inner = self.fresh("decorate")
        self.emit(f"def {name}({parameter}=None):")
        self.indent += 1
        self.emit(f"def {inner}({function}):")
        self.indent += 1
        self.wrapper(context, function, Scope([parameter, function]))
        self.indent -= 1
        self.emit(f"return {inner}")
        self.indent -= 1

    def wrapper(self, context, function, scope):
        wrapper = self.fresh("wrapper")
        args = self.fresh("args")
        kwargs = self.fresh("kwargs")
        if self.chance():
            self.emit(f"@functools.wraps({function})")
        self.emit(f"def {wrapper}(*{args}, **{kwargs}):")
        self.indent += 1
        inner = Context(
            context.refs,
            Scope([args, kwargs]),
            context.module_values,
            outer=(*context.outer, *scope.variables),
            enclosing=tuple(scope.variables),
            kind="plain",
        )
        self.block(inner, 1)
        self.emit(f"return {function}(*{args}, **{kwargs})")
        self.indent -= 1
        self.emit(f"return {wrapper}")

    def class_(self, context, name, bases, depth):
        for decorator in self.class_decorators(context):
            self.emit(decorator)
        self.emit(f"class {name}({', '.join(bases)}):" if bases else f"class {name}:")
        self.indent += 1
        outer = context.outer
        if context.function():
            outer = (*outer, *context.scope.variables)
        body = Context(
            context.refs,
            Scope(),
            context.module_values,
            outer=outer,
            kind="class",
        )
        self.emit(f"{self.rng.choice(ATTRIBUTE_NAMES)} = {self.expression(body, 1)}")
        kinds = self.rng.sample(METHOD_KINDS, self.count(METHODS_PER_CLASS_MAX, 1))
        for kind in kinds:
            self.method(body, name, kind, depth + 1)
        self.indent -= 1

    def class_decorators(self, context):
        options = [f"@{name}" for name in context.refs.decorators]
        return self.rng.sample(options, self.count(min(1, len(options))))

    def method(self, body, owner, kind, depth):
        method = replace(body, owner=owner, depth=depth)
        if kind == "init":
            self.function(method, "__init__", "plain", (), "self", init=True)
        elif kind == "method":
            name = self.rng.choice(METHOD_NAMES)
            self.function(method, name, self.rng.choice(FUNCTION_KINDS), (), "self")
        elif kind == "property":
            name = self.rng.choice(ATTRIBUTE_NAMES)
            self.function(method, name, "plain", ("@property",), "self")
            setter = (f"@{name}.setter",)
            self.function(method, name, "plain", setter, "self", minimum=1)
        elif kind == "static":
            name = self.rng.choice(METHOD_NAMES)
            self.function(method, name, "plain", ("@staticmethod",), None)
        elif kind == "class":
            name = self.rng.choice(METHOD_NAMES)
            self.function(method, name, "plain", ("@classmethod",), "cls")
        elif kind == "call":
            self.function(method, "__call__", "plain", (), "self")
        elif kind == "getattr":
            self.function(method, "__getattr__", "plain", (), "self", minimum=1)
        elif kind == "getitem":
            self.function(method, "__getitem__", "plain", (), "self", minimum=1)
        elif kind == "iter":
            self.function(method, "__iter__", "generator", (), "self")
        elif kind == "context":
            self.function(method, "__enter__", "plain", (), "self")
            self.function(method, "__exit__", "plain", (), "self", minimum=3)
        else:
            self.function(method, "__aenter__", "async", (), "self")
            self.function(method, "__aexit__", "async", (), "self", minimum=3)

    def function(
        self, context, name, kind, decorators, first="", init=False, minimum=0
    ):
        depth = context.depth + 1
        parameters, names = self.parameters(context, first, minimum)
        for decorator in decorators:
            self.emit(decorator)
        keyword = "async def" if kind in ASYNC_KINDS else "def"
        self.emit(f"{keyword} {name}({parameters}):")
        self.indent += 1
        outer = context.outer
        enclosing = ()
        if context.function():
            outer = (*outer, *context.scope.variables)
            enclosing = tuple(context.scope.variables)
        inner = Context(
            context.refs,
            Scope(list(names)),
            context.module_values,
            outer=outer,
            enclosing=enclosing,
            kind=kind,
            owner=context.owner,
            depth=depth,
        )
        self.declarations(inner)
        if init and self.chance():
            self.emit(f"super().__init__({self.arguments(inner, 1)})")
        if init and first:
            for attribute in self.rng.sample(ATTRIBUTE_NAMES, self.count(2, 1)):
                self.emit(f"{first}.{attribute} = {self.expression(inner, 1)}")
        self.block(inner, depth)
        if kind in YIELDING_KINDS:
            self.emit(f"yield {self.expression(inner, 1)}")
        elif not init:
            self.emit(f"return {self.expression(inner, 1)}")
        self.indent -= 1

    def declarations(self, context):
        if context.enclosing and self.chance():
            names = self.rng.sample(context.enclosing, 1)
            self.emit(f"nonlocal {', '.join(names)}")
            context.scope.globals.extend(names)
        if context.module_values and self.chance():
            names = self.rng.sample(context.module_values, 1)
            self.emit(f"global {', '.join(names)}")
            context.scope.globals.extend(names)

    def parameters(self, context, first, minimum):
        parts = [first] if first else []
        names = [first] if first else []
        count = self.count(PARAMETERS_PER_KIND_MAX + minimum, minimum)
        positional = [self.fresh("p") for _ in range(count)]
        defaults_from = self.count(count, minimum)
        for index, name in enumerate(positional):
            if index < defaults_from:
                parts.append(name)
            else:
                parts.append(f"{name}={self.expression(context, 2)}")
        names.extend(positional)
        if parts and self.chance():
            parts.append("/")
        star = self.rng.choice(("", "*", self.fresh("args")))
        keywords = []
        if star:
            keywords = [
                self.fresh("k") for _ in range(self.count(PARAMETERS_PER_KIND_MAX))
            ]
        if star == "*" and not keywords:
            keywords.append(self.fresh("k"))
        if star:
            parts.append(f"*{'' if star == '*' else star}")
        if star != "*" and star:
            names.append(star)
        for name in keywords:
            if self.chance():
                parts.append(f"{name}={self.expression(context, 2)}")
            else:
                parts.append(name)
        names.extend(keywords)
        if self.chance():
            kwargs = self.fresh("kwargs")
            parts.append(f"**{kwargs}")
            names.append(kwargs)
        return ", ".join(parts), names

    def block(self, context, depth):
        for _ in range(self.count(STATEMENTS_PER_BLOCK_MAX, 1)):
            self.statement(context, depth)

    def nested(self, context, depth):
        self.indent += 1
        self.block(context, depth + 1)
        self.indent -= 1

    def statement(self, context, depth):
        makers = [
            self.assignment,
            self.assignment,
            self.unpacking,
            self.expression_statement,
            self.expression_statement,
            self.reflection_statement,
            self.augmented,
            self.annotated,
            self.raise_,
        ]
        if context.function() and not context.cleanup:
            makers.append(self.return_)
        if context.kind in YIELDING_KINDS:
            makers.append(self.yield_)
        if context.loop and not context.cleanup:
            makers.append(self.jump)
        if depth < BLOCK_DEPTH_MAX:
            makers.extend(
                (
                    self.if_,
                    self.for_,
                    self.while_,
                    self.try_,
                    self.with_,
                    self.match,
                    self.nested_function,
                    self.nested_class,
                )
            )
        self.rng.choice(makers)(context, depth)

    def assignment(self, context, depth):
        value = self.expression(context)
        assigned = context.scope.variables + context.scope.globals
        targets = []
        new = []
        for _ in range(self.count(2, 1)):
            form = self.rng.choice(("new", "new", "old", "attribute", "subscript"))
            if form == "old" and assigned:
                targets.append(self.rng.choice(assigned))
            elif form == "attribute":
                name = self.rng.choice(context.visible())
                targets.append(f"{name}.{self.rng.choice(ATTRIBUTE_NAMES)}")
            elif form == "subscript":
                index = self.expression(context, EXPRESSION_DEPTH_MAX - 1)
                targets.append(f"{self.rng.choice(context.visible())}[{index}]")
            else:
                new.append(self.fresh("x"))
                targets.append(new[-1])
        self.emit(f"{' = '.join(targets)} = {value}")
        context.scope.variables.extend(new)

    def unpacking(self, context, depth):
        value = self.expression(context)
        target, names = self.unpacking_target()
        self.emit(f"{target} = {value}")
        context.scope.variables.extend(names)

    def unpacking_target(self):
        names = [self.fresh("x") for _ in range(self.count(3, 2))]
        form = self.rng.choice(("tuple", "starred", "nested", "list"))
        if form == "starred":
            star = self.rng.randrange(len(names))
            parts = [f"*{n}" if i == star else n for i, n in enumerate(names)]
            return ", ".join(parts), names
        if form == "nested":
            return f"({names[0]}, {names[1]}), {', '.join(names[2:]) or '_'}", names
        if form == "list":
            return f"[{', '.join(names)}]", names
        return ", ".join(names), names

    def expression_statement(self, context, depth):
        self.emit(self.rng.choice((self.call, self.method_call))(context, 1))

    def reflection_statement(self, context, depth):
        name = self.rng.choice(context.visible())
        attribute = self.attribute_name(context)
        self.emit(f"setattr({name}, {attribute}, {self.expression(context, 1)})")

    def augmented(self, context, depth):
        assigned = context.scope.variables + context.scope.globals
        if not assigned:
            self.assignment(context, depth)
            return
        operator = self.rng.choice(("+=", "|=", "-="))
        target = self.rng.choice(assigned)
        self.emit(f"{target} {operator} {self.expression(context, 1)}")

    def annotated(self, context, depth):
        name = self.fresh("x")
        annotation = self.rng.choice(
            [*context.refs.classes, *BUILTIN_CLASSES, "list[int]"]
        )
        self.emit(f"{name}: {annotation} = {self.expression(context)}")
        context.scope.variables.append(name)

    def raise_(self, context, depth):
        exception = self.rng.choice([*EXCEPTIONS, *context.refs.classes])
        cause = self.rng.choice(("", " from None", f" from {exception}()"))
        self.emit(f"raise {exception}({self.arguments(context, 2)}){cause}")

    def return_(self, context, depth):
        if context.kind == "async_generator":
            self.emit("return")
        else:
            self.emit(f"return {self.expression(context)}")

    def yield_(self, context, depth):
        forms = ["yield", "assign"]
        if context.kind == "generator":
            forms.append("from")
        form = self.rng.choice(forms)
        value = self.expression(context, 1)
        if form == "from":
            self.emit(f"yield from {value}")
        elif form == "assign":
            name = self.fresh("x")
            self.emit(f"{name} = yield {value}")
            context.scope.variables.append(name)
        else:
            self.emit(f"yield {value}")

    def jump(self, context, depth):
        self.emit(self.rng.choice(("break", "continue")))

    def if_(self, context, depth):
        self.emit(f"if {self.class_test(context, 1)}:")
        self.nested(context, depth)
        if self.chance():
            self.emit(f"elif {self.expression(context, 1)}:")
            self.nested(context, depth)
        if self.chance():
            self.emit("else:")
            self.nested(context, depth)

    def for_(self, context, depth):
        iterable = self.expression(context)
        if self.chance():
            target, names = self.unpacking_target()
        else:
            names = [self.fresh("x")]
            target = names[0]
        asynchronous = context.kind in ASYNC_KINDS and self.chance()
        keyword = "async for" if asynchronous else "for"
        self.emit(f"{keyword} {target} in {iterable}:")
        context.scope.variables.extend(names)
        self.nested(replace(context, loop=True), depth)
        if self.chance():
            self.emit("else:")
            self.nested(context, depth)

    def while_(self, context, depth):
        self.emit(f"while {self.expression(context, 1)}:")
        self.nested(replace(context, loop=True), depth)
        self.indent += 1
        self.emit("break")
        self.indent -= 1

    def try_(self, context, depth):
        self.emit("try:")
        self.nested(context, depth)
        handlers = self.count(2)
        for _ in range(handlers):
            caught = self.rng.sample(
                [*EXCEPTIONS, *context.refs.classes], self.count(2, 1)
            )
            clause = caught[0] if len(caught) == 1 else f"({', '.join(caught)})"
            if self.chance():
                name = self.fresh("error")
                self.emit(f"except {clause} as {name}:")
                context.scope.variables.append(name)
            else:
                self.emit(f"except {clause}:")
            self.nested(context, depth)
        if handlers and self.chance():
            self.emit("else:")
            self.nested(context, depth)
        if not handlers or self.chance():
            self.emit("finally:")
            self.nested(replace(context, cleanup=True), depth)

    def with_(self, context, depth):
        items = []
        names = []
        for _ in range(self.count(2, 1)):
            manager = self.expression(context, 1)
            if self.chance():
                names.append(self.fresh("x"))
                items.append(f"{manager} as {names[-1]}")
            else:
                items.append(manager)
        asynchronous = context.kind in ASYNC_KINDS and self.chance()
        keyword = "async with" if asynchronous else "with"
        self.emit(f"{keyword} {', '.join(items)}:")
        context.scope.variables.extend(names)
        self.nested(context, depth)

    def match(self, context, depth):
        self.emit(f"match {self.expression(context, 1)}:")
        self.indent += 1
        for _ in range(self.count(CASES_PER_MATCH_MAX, 1)):
            names = []
            pattern = self.pattern(context, names, 0)
            if self.chance():
                name = self.fresh("x")
                pattern = f"({pattern}) as {name}"
                names.append(name)
            context.scope.variables.extend(names)
            guard = f" if {self.expression(context, 1)}" if self.chance() else ""
            self.emit(f"case {pattern}{guard}:")
            self.nested(context, depth)
        if self.chance():
            name = self.rng.choice(("_", self.fresh("x")))
            self.emit(f"case {name}:")
            if name != "_":
                context.scope.variables.append(name)
            self.nested(context, depth)
        self.indent -= 1

    def pattern(self, context, names, depth):
        forms = ["literal", "alternatives", "class", "sequence", "mapping"]
        if depth > 0:
            forms.extend(("capture", "wildcard"))
        if depth >= PATTERN_DEPTH_MAX:
            forms = ["literal", "capture", "wildcard"]
        form = self.rng.choice(forms)
        if form == "literal":
            return self.rng.choice(("0", "'k'", "None", "True", "-1"))
        if form == "capture":
            names.append(self.fresh("x"))
            return names[-1]
        if form == "wildcard":
            return "_"
        if form == "alternatives":
            classes = [*context.refs.classes, *BUILTIN_CLASSES]
            chosen = self.rng.sample(classes, 2)
            return " | ".join(f"{name}()" for name in chosen)
        if form == "class":
            return self.class_pattern(context, names, depth)
        if form == "sequence":
            return self.sequence_pattern(context, names, depth)
        return self.mapping_pattern(context, names, depth)

    def class_pattern(self, context, names, depth):
        name = self.rng.choice([*context.refs.classes, *BUILTIN_CLASSES])
        positional = [
            self.pattern(context, names, depth + 1) for _ in range(self.count(2))
        ]
        keywords = [
            f"{keyword}={self.pattern(context, names, depth + 1)}"
            for keyword in self.rng.sample(ATTRIBUTE_NAMES, self.count(2))
        ]
        return f"{name}({', '.join(positional + keywords)})"

    def sequence_pattern(self, context, names, depth):
        parts = [self.pattern(context, names, depth + 1) for _ in range(self.count(2))]
        if self.chance():
            names.append(self.fresh("rest"))
            parts.append(f"*{names[-1]}")
        return f"[{', '.join(parts)}]"

    def mapping_pattern(self, context, names, depth):
        keys = self.rng.sample(("'k'", "'run'", "0", "None"), self.count(2))
        parts = [f"{key}: {self.pattern(context, names, depth + 1)}" for key in keys]
        if self.chance():
            names.append(self.fresh("rest"))
            parts.append(f"**{names[-1]}")
        return "{" + ", ".join(parts) + "}"

    def nested_function(self, context, depth):
        name = self.fresh("g")
        kind = self.rng.choice(FUNCTION_KINDS)
        decorators = self.decorators(context, kind)
        self.function(replace(context, loop=False, depth=depth), name, kind, decorators)
        context.scope.variables.append(name)

    def nested_class(self, context, depth):
        name = self.fresh("K")
        self.class_(context, name, self.bases(context), depth)
        context.scope.variables.append(name)

    def expression(self, context, depth=0):
        if depth >= EXPRESSION_DEPTH_MAX:
            return self.atom(context, depth)
        makers = [
            self.atom,
            self.call,
            self.call,
            self.method_call,
            self.attribute,
            self.subscript,
            self.container,
            self.comprehension,
            self.lambda_,
            self.reflection,
            self.class_test,
            self.conditional,
            self.builtin,
            self.operation,
        ]
        if context.kind in ASYNC_KINDS:
            makers.append(self.await_)
        if context.owner is not None:
            makers.append(self.super_call)
        return self.rng.choice(makers)(context, depth + 1)

    def atom(self, context, depth):
        if self.chance():
            return self.rng.choice(CONSTANTS)
        return self.name(context)

    def name(self, context):
        return self.rng.choice(context.visible())

    def callee(self, context):
        return self.rng.choice(context.refs.callables() or context.visible())

    def arguments(self, context, depth):
        parts = [
            self.expression(context, depth)
            for _ in range(self.count(ARGUMENTS_PER_CALL_MAX))
        ]
        if self.chance():
            parts.append(f"*{self.expression(context, depth)}")
        for keyword in self.rng.sample(KEYWORD_NAMES, self.count(2)):
            parts.append(f"{keyword}={self.expression(context, depth)}")
        if self.chance():
            parts.append(f"**{self.expression(context, depth)}")
        return ", ".join(parts)

    def call(self, context, depth):
        callee = self.callee(context) if self.chance() else self.name(context)
        return f"{callee}({self.arguments(context, depth)})"

    def method_call(self, context, depth):
        method = self.rng.choice((*METHOD_NAMES, *CONTAINER_METHODS))
        return f"{self.name(context)}.{method}({self.arguments(context, depth)})"

    def attribute(self, context, depth):
        attribute = self.rng.choice((*ATTRIBUTE_NAMES, *METHOD_NAMES))
        return f"{self.name(context)}.{attribute}"

    def subscript(self, context, depth):
        if self.chance():
            return f"{self.name(context)}[1:]"
        return f"{self.name(context)}[{self.expression(context, depth)}]"

    def elements(self, context, depth):
        return [
            self.expression(context, depth)
            for _ in range(self.count(ELEMENTS_PER_CONTAINER_MAX, 1))
        ]

    def container(self, context, depth):
        form = self.rng.choice(("list", "tuple", "set", "dict"))
        elements = self.elements(context, depth)
        if form != "dict" and self.chance():
            elements.append(f"*{self.expression(context, depth)}")
        if form == "list":
            return f"[{', '.join(elements)}]"
        if form == "tuple":
            return f"({', '.join(elements)},)"
        if form == "set":
            return "{" + ", ".join(elements) + "}"
        items = [f"{self.rng.choice(CONSTANTS)}: {element}" for element in elements]
        if self.chance():
            items.append(f"**{self.expression(context, depth)}")
        return "{" + ", ".join(items) + "}"

    def comprehension(self, context, depth):
        iterable = self.expression(context, depth)
        names = [self.fresh("i") for _ in range(self.count(2, 1))]
        target = ", ".join(names)
        inner = replace(context, outer=(*context.outer, *names))
        element = self.expression(inner, depth)
        condition = f" if {self.expression(inner, depth)}" if self.chance() else ""
        clause = f"for {target} in {iterable}{condition}"
        form = self.rng.choice(("list", "set", "dict", "generator"))
        if form == "list":
            return f"[{element} {clause}]"
        if form == "set":
            return "{" + f"{element} {clause}" + "}"
        if form == "dict":
            return "{" + f"{names[0]}: {element} {clause}" + "}"
        return f"({element} {clause})"

    def lambda_(self, context, depth):
        parameters, names = self.parameters(context, "", 0)
        inner = replace(context, outer=(*context.outer, *names), kind="plain")
        body = self.expression(inner, depth)
        return f"(lambda {parameters}: {body})" if parameters else f"(lambda: {body})"

    def attribute_name(self, context):
        constant = repr(self.rng.choice((*ATTRIBUTE_NAMES, *METHOD_NAMES)))
        form = self.rng.choice(("constant", "concatenated", "computed"))
        if form == "constant":
            return constant
        if form == "concatenated":
            return f"{constant[:2]}' + '{constant[2:]}"
        return self.name(context)

    def reflection(self, context, depth):
        target = self.name(context)
        attribute = self.attribute_name(context)
        form = self.rng.choice(("getattr", "default", "hasattr"))
        if form == "getattr":
            return f"getattr({target}, {attribute})"
        if form == "default":
            return f"getattr({target}, {attribute}, {self.expression(context, depth)})"
        return f"hasattr({target}, {attribute})"

    def class_test(self, context, depth):
        classes = [*context.refs.classes, *BUILTIN_CLASSES]
        chosen = self.rng.sample(classes, self.count(2, 1))
        tested = chosen[0] if len(chosen) == 1 else f"({', '.join(chosen)})"
        return f"isinstance({self.expression(context, depth)}, {tested})"

    def conditional(self, context, depth):
        then = self.expression(context, depth)
        test = self.expression(context, depth)
        otherwise = self.expression(context, depth)
        return f"({then} if {test} else {otherwise})"

    def builtin(self, context, depth):
        value = self.expression(context, depth)
        function = self.callee(context)
        forms = (
            f"len({value})",
            f"sorted({value}, key={function})",
            f"list(map({function}, {value}))",
            f"filter({function}, {value})",
            f"next(iter({value}), None)",
            f"functools.partial({function}, {value})",
            f"dict({value})",
            f"zip({value}, {self.name(context)})",
            f"enumerate({value})",
            f"type({value})",
            f"functools.reduce({function}, {value})",
            f"asyncio.run({function}({value}))",
        )
        return self.rng.choice(forms)

    def operation(self, context, depth):
        left = self.expression(context, depth)
        right = self.expression(context, depth)
        operator = self.rng.choice(("+", "|", "and", "or", "==", "in", "@"))
        return f"({left} {operator} {right})"

    def await_(self, context, depth):
        return f"(await {self.expression(context, depth)})"

    def super_call(self, context, depth):
        method = self.rng.choice((*METHOD_NAMES, "__init__", "__getattr__"))
        return f"super().{method}({self.arguments(context, depth)})"


def program(seed):
    files = Generator(seed).program()
    for path, source in files.items():
        try:
            compile(source, path, "exec", dont_inherit=True)
        except SyntaxError as error:
            error.add_note(f"generated program of seed {seed}, {path}:\n{source}")
            raise
    return files
