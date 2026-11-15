"""Annotations as declared values.

A parameter annotated with a class holds an instance of that class or of a
subclass (scope rule B2 of the macro-benchmark: the package values for a
role are those its annotation names). So each annotated parameter holds,
always, every instance of each analysed class that its annotation names,
and of its subclasses (`C.instances`); `type[C]` names the classes
themselves; one level of a standard container or iterable (`list[C]`,
`Sequence[C]`, `tuple[C, ...]`, `dict[K, C]`) is a container that holds
them; `Optional`, unions and `Annotated` name what their arguments name. A
class of the stubs gives a typed outside value of it (macro scope rule B4,
see outside.py), or the class for `type[C]`; an abstract one that is not a
protocol of the builtin types also gives the instances (for `type[C]`, the
classes) of every analysed class whose MRO reaches it through the stub MROs
(`below_outside`; not structural fit). An annotation that names
nothing else (`object`, `Any`, a bare `Callable`, a type variable, outside
code without stubs) gives nothing.

The builder reads annotations from the AST (`AnnotationBuilder`): a name or
an attribute is loaded as any expression is (`annotation_name`), so imports
and aliases resolve, and a name that an import under `if TYPE_CHECKING:`
would bind resolves as that import would (the builder's `type_only_names`);
a string is parsed; a union or a subscript becomes a `TypeForm`, an object that flows
like any value. A type alias (`T = A | B` at module or class level,
`T: TypeAlias = ...`, `type T = ...`) binds its `TypeForm` too, so an
annotation that names it reads it. What the type constructors are
(`typing.Optional`, `list`, `collections.abc.Sequence`) is decided at solve
time from the outside name that the subscripted value holds
(`Annotations`).

An annotated assignment (`x: T = v`, `self.a: T = v`) stores what `T` names
as well as `v` (`declared`); an annotation without a value binds nothing and
names nothing.

Class-level annotations of a dataclass-like class (decorated with
`dataclasses.dataclass`, or a subclass of `typing.NamedTuple`) are the
parameters of the `__init__` that the library generates, which initialises
every instance: the fields of every instance hold the annotated values. A
`TypedDict` value is a dict, so its class-level annotations name nothing.

A module's own stub (`x.pyi` beside `x.py`, `OwnStub`) gives the annotations
that the source leaves out: a parameter, a class attribute or a module
variable without an annotation takes the annotations of the same name in the
stub, read as if they were written in the source. Every definition of the
name in the stub counts (the overloads of a function, the branches of an
`if`). A name in a stub annotation resolves as Python resolves it in the
stub (class body, module, builtins), and each of its bindings there
contributes: an import, what a type-only import of it binds, without loads;
a class statement, the source's class definitions of the same qualified
name; any other binding, nothing. Nothing else of the stub is used.
"""

import ast

from .builtin_models import RETURNS_ARGUMENT, builtin_kind
from .model import Class, External, ReturnsArgument, TypeForm
from .scopes import CLASS as CLASS_SCOPE
from .scopes import FUNCTION, MODULE, mangle
from .solver import Each

# How the annotation of a parameter names its values: as instances (which
# may be in one container), as elements of a container (instances only),
# or as classes.
INSTANCE, ELEMENT, CLASS = "instance", "element", "class"

# Type constructors by the last part of their outside name.
UNIONS = frozenset({"Optional", "Union"})
FIRST_ARGUMENT = frozenset(
    {"Annotated", "Required", "NotRequired", "ReadOnly", "Final", "ClassVar"}
)
CLASSES = frozenset({"type", "Type"})
CONTAINERS = {
    **dict.fromkeys(
        (
            "list",
            "List",
            "Sequence",
            "MutableSequence",
            "Iterable",
            "Iterator",
            "Collection",
            "Reversible",
            "Generator",
        ),
        "list",
    ),
    **dict.fromkeys(("deque", "Deque"), "collections.deque"),
    "OrderedDict": "collections.OrderedDict",
    **dict.fromkeys(("DefaultDict", "defaultdict"), "collections.defaultdict"),
    **dict.fromkeys(
        ("set", "Set", "frozenset", "FrozenSet", "AbstractSet", "MutableSet"), "set"
    ),
    **dict.fromkeys(("tuple", "Tuple"), "tuple"),
    **dict.fromkeys(
        (
            "dict",
            "Dict",
            "Mapping",
            "MutableMapping",
        ),
        "dict",
    ),
}
# Which arguments name the elements: a generator's yield type, a mapping's
# values, every position of a tuple.
_ELEMENTS = {"list": slice(0, 1), "set": slice(0, 1), "tuple": slice(0, None)}

# The protocols that the builtin types implement (`list`, `str`, `dict`,
# `tuple`, ...), by stub definition path; the names of `collections.abc` are
# the same definitions. A client most likely passes a builtin value where
# one is annotated, so they name no analysed class below them.
BUILTIN_PROTOCOLS = frozenset(
    f"typing.{name}"
    for name in (
        "Iterable",
        "Iterator",
        "Collection",
        "Container",
        "Sized",
        "Hashable",
        "Reversible",
    )
)

DATACLASS = "dataclasses.dataclass"
# `dataclass` itself, and the decorator that `dataclass(frozen=True)`
# returns (see `RETURNS_ARGUMENT`).
DATACLASS_DECORATORS = frozenset({DATACLASS, RETURNS_ARGUMENT[DATACLASS][2]})
DATACLASS_BASES = frozenset(
    f"{module}.{name}"
    for module in ("typing", "typing_extensions")
    for name in ("NamedTuple",)
)


# The kinds of parameters by which a stub's parameter annotates one of the
# source: a named one (positional or keyword), `*args` or `**kwargs`.
NAMED, VARARG, KWARG = "named", "*", "**"


# How the stub binds a name in one of its scopes: a class (with its path),
# an import (with the dotted name it imports), or anything else.
STUB_CLASS, STUB_IMPORT, STUB_OTHER = "class", "import", "other"


class OwnStub:
    """The annotations of a module's own stub, the file `x.pyi` beside the
    module's `x.py`. A definition is known by its path from the module
    (`("C", "m")` for the method `m` of the class `C`): `parameters` maps
    (path, name, kind) to the annotations of a parameter, `variables` the
    path of a class attribute or module variable to its annotations, and
    `names` (scope path, name) to each way the stub binds the name in that
    scope (`STUB_CLASS` with the class's path, `STUB_IMPORT` with the dotted
    name, or `STUB_OTHER`). Names are as Python stores them: `__x` in the
    class `C` is `_C__x`. Every definition of a name counts: the overloads of
    a function and those in each branch of an `if` or a `try` (`if
    TYPE_CHECKING:` too). `absolute` gives the absolute module of a relative
    import."""

    def __init__(self, tree, absolute):
        self.parameters = {}
        self.variables = {}
        self.names = {}
        self._absolute = absolute
        pending = [(tree.body, ())]
        while pending:
            statements, path = pending.pop()
            for statement in statements:
                self._definition(statement, path, pending)

    def _bind(self, path, name, how, target=None):
        key = (path, _stored(path, name))
        self.names.setdefault(key, {})[(how, target)] = None

    def _definition(self, statement, path, pending):
        match statement:
            case ast.FunctionDef() | ast.AsyncFunctionDef():
                self._bind(path, statement.name, STUB_OTHER)
                function = (*path, statement.name)
                arguments = statement.args
                named = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
                kinds = [(arg, NAMED) for arg in named]
                kinds += [(arguments.vararg, VARARG), (arguments.kwarg, KWARG)]
                for arg, kind in kinds:
                    if arg is not None and arg.annotation is not None:
                        key = (function, arg.arg, kind)
                        self.parameters.setdefault(key, []).append(arg.annotation)
            case ast.ClassDef():
                cls = (*path, statement.name)
                self._bind(path, statement.name, STUB_CLASS, cls)
                pending.append((statement.body, cls))
            case ast.AnnAssign(target=ast.Name() as target):
                self._bind(path, target.id, STUB_OTHER)
                key = (*path, _stored(path, target.id))
                self.variables.setdefault(key, []).append(statement.annotation)
            case ast.Import() | ast.ImportFrom():
                private = path[-1] if path else None
                imports = imported_names([statement], self._absolute, private)
                for name, target in imports:
                    self._bind(path, name, STUB_IMPORT, target)
            case ast.Assign() | ast.AugAssign() | ast.TypeAlias():
                targets = getattr(statement, "targets", None) or [
                    getattr(statement, "target", None) or statement.name
                ]
                for name in _target_names(targets):
                    self._bind(path, name, STUB_OTHER)
            case ast.If() | ast.Try() | ast.TryStar():
                for field in ("body", "orelse", "finalbody"):
                    pending.append((getattr(statement, field, ()), path))
                for handler in getattr(statement, "handlers", ()):
                    pending.append((handler.body, path))


def _stored(path, name):
    """`name` as the stub's scope of path `path` stores it."""
    return mangle(path[-1] if path else None, name)


def _target_names(targets):
    """The names that the assignment targets `targets` bind: names, also
    inside tuples, lists and starred targets; not the names that an
    attribute or a subscript target reads."""
    pending = list(targets)
    while pending:
        target = pending.pop()
        match target:
            case ast.Name():
                yield target.id
            case ast.Tuple() | ast.List():
                pending.extend(target.elts)
            case ast.Starred():
                pending.append(target.value)


def imported_names(statements, absolute, private_class=None):
    """The names that the imports in `statements` would bind, also in their
    nested blocks, with the dotted names that they would import: pairs
    `(name, target)`. `absolute` gives the absolute name of the module of a
    `from` import (the builder's `_absolute_module_name`). In the class
    named `private_class`, a private name is mangled, as Python does: `from
    m import __x` imports `m._Class__x`, and `import __m` and `from __m
    import x` import from `_Class__m` (a dotted module name is not
    mangled)."""
    stack = list(statements)
    while stack:
        statement = stack.pop()
        match statement:
            case ast.Import():
                for alias in statement.names:
                    module = mangle(private_class, alias.name)
                    if alias.asname:
                        yield alias.asname, module
                    else:
                        # `import a.b` binds `a` to the module `a`.
                        yield alias.name.partition(".")[0], module.partition(".")[0]
            case ast.ImportFrom():
                module = statement.module
                if module is not None:
                    module = mangle(private_class, module)
                holder = absolute(module, statement.level)
                for alias in statement.names:
                    if alias.name != "*":
                        member = mangle(private_class, alias.name)
                        target = f"{holder}.{member}" if holder else member
                        yield alias.asname or alias.name, target
            case ast.If() | ast.Try() | ast.TryStar() | ast.With():
                for field in ("body", "orelse", "finalbody"):
                    stack.extend(getattr(statement, field, ()))
                for handler in getattr(statement, "handlers", ()):
                    stack.extend(handler.body)


class AnnotationBuilder:
    """The part of the builder that reads annotations (see the module
    docstring)."""

    def annotation(self, expression, origin=None):
        """The node of what the annotation `expression` names, or None.
        `origin` is the site of the string that holds `expression` when it
        was parsed from a string: sites inside it are positions in it, so
        the forms of nested strings are told apart. A shape that names no
        type (a call, a lambda, a comprehension) gives nothing."""
        site = self._annotation_site(expression, origin)
        match expression:
            case ast.Constant(value=str() as text):
                try:
                    parsed = ast.parse(text.strip(), mode="eval").body
                except (SyntaxError, ValueError, RecursionError):
                    return None
                return self.annotation(parsed, site.partition("#")[0])
            case ast.Name() | ast.Attribute():
                return self.annotation_name(expression, origin)
            case ast.BinOp(op=ast.BitOr()):
                arms = []
                # A long union nests on the left: walk it without recursion.
                while isinstance(expression, ast.BinOp) and isinstance(
                    expression.op, ast.BitOr
                ):
                    arms.append(expression.right)
                    expression = expression.left
                arms.append(expression)
                parts = [self.annotation(arm, origin) for arm in reversed(arms)]
                return self._type_form("|", parts, site)
            case ast.Subscript():
                value = self.annotation(expression.value, origin)
                arguments = expression.slice
                if isinstance(arguments, ast.Tuple):
                    arguments = arguments.elts
                else:
                    arguments = [arguments]
                parts = [value] + [self.annotation(a, origin) for a in arguments]
                return self._type_form("[]", parts, site)
        return None

    def _annotation_site(self, node, origin):
        if origin is None:
            return self._site(node)
        position = f"{node.lineno}:{node.col_offset}"
        return f"{origin}/{position}#{node.end_lineno}:{node.end_col_offset}"

    def annotation_name(self, expression, origin=None):
        """The node of the name or attribute chain `expression` in an
        annotation. Annotations are not evaluated where they are written: a
        name is resolved against what its scope binds at any time (the
        variable that every definition flows into), so a class or alias
        defined later is found; and, for a name that an import under `if
        TYPE_CHECKING:` would bind (which binds nothing at run time), as
        that import would. An attribute in a string (`origin`) is looked up
        without running a hook (`add_name_lookup`), as nothing evaluates the
        string. Anything else gives nothing."""
        if self._reading_stub is not None:
            return self._stub_name(expression)
        match expression:
            case ast.Name():
                return self._join(
                    [
                        self._annotation_variable(expression.id),
                        self._type_only(expression.id),
                    ]
                )
            case ast.Attribute():
                base = self.annotation_name(expression.value, origin)
                if base is None:
                    return None
                value = self.analysis.node()
                attr = self._scope.mangle(expression.attr)
                if origin is not None:
                    # Python never evaluates a string annotation: no hook.
                    self.analysis.add_name_lookup(base, attr, value)
                    return value
                site = self._annotation_site(expression, origin)
                self.analysis.add_load(base, attr, value, self._caller, site)
                return value
        return None

    def _annotation_variable(self, name):
        """The variable that `name` reads in an annotation of the current
        scope: a class body reads its own namespace, then the module's."""
        name = self._scope.mangle(name)
        scope = self.scopes.resolve(self._scope, name)
        if scope.kind == CLASS_SCOPE and scope is not self._scope:
            # The implicit `__class__` of a function in a class.
            return self.analysis.constant(self._classes[scope])
        if self._is_builtin(scope, name):
            return self._builtin_global(name)
        value = self._variable(scope, name)
        if scope.kind == CLASS_SCOPE:
            module = self.scopes.module
            if self._is_builtin(module, name):
                return self._join([value, self._builtin_global(name)])
            return self._join([value, self._variable(module, name)])
        return value

    def _type_only(self, name):
        """The node of what a type-only import binds to `name` in the
        current scope or an enclosing one (`type_only_names`), or None."""
        target = None
        scope = self._scope
        while scope is not None and target is None:
            target = self.type_only_names.get(f"{scope.name}.{scope.mangle(name)}")
            scope = scope.parent
        if target is None:
            return None
        return self._imported(target)

    def _imported(self, target):
        """The node of what an import of the dotted name `target` would
        bind, without importing it or loading an attribute. A submodule
        `p.n` is read as the attribute `n` of its package, as `from p import
        n` reads it: what the package binds to `n`, and the submodule where
        an import of the program makes it that attribute (see
        `Program._link_submodules`)."""
        found = self.imports.locate(target)
        if found is None:
            return self.analysis.constant(self.analysis.external(target))
        module, attribute = found
        if attribute is None:
            module, _, attribute = module.rpartition(".")
            if not module:
                return self.analysis.constant(self.analysis.module(attribute))
        return self.analysis.field(self.analysis.module(module), attribute)

    def _type_form(self, operator, parts, site):
        return self.analysis.constant(self.analysis.type_form(operator, parts, site))

    def alias_form(self, value):
        """A node that gets the type form of `value` (a union or a
        subscript) once one of its operands may be a type: a name bound to
        it at module or class level (`T = A | B`) is an alias that
        annotations may name, so the builder joins this node to the value
        it binds. An ordinary subscript or `|` gets no form. Else None."""
        if isinstance(value, ast.Subscript):
            operator = "[]"
        elif isinstance(value, ast.BinOp) and isinstance(value.op, ast.BitOr):
            operator = "|"
        else:
            return None
        if self.annotation(value) is None:
            return None
        form = self.analysis.type_form(operator, (), self._site(value))
        gate = self.analysis.node()
        self.analysis.gate_type_form(form, gate)
        return gate

    def declared(self, annotation, target):
        """The node of what the annotation node `annotation` of an annotated
        assignment to `target` names, read as for a parameter; None without
        one. The containers that it makes are keyed by the target's
        position."""
        if annotation is None:
            return None
        node = self.analysis.node()
        position = f"{target.lineno}:{target.col_offset}"
        owner = (self.module, position)
        self.analysis.annotated(annotation, node, INSTANCE, owner)
        return node

    def parameter_annotations(self, function, arguments, scope):
        """Give each annotated parameter of `function` what its annotation
        names; one without an annotation, what the stub's annotations of the
        parameter of its name and kind name (see `OwnStub`)."""
        path = None
        if self.own_stub is not None and scope.kind == FUNCTION:
            path = _stub_path(scope)
        named = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
        kinds = [(arg, NAMED) for arg in named]
        kinds += [(arguments.vararg, VARARG), (arguments.kwarg, KWARG)]
        for arg, kind in kinds:
            if arg is None:
                continue
            if arg.annotation is not None:
                node = self.annotation(arg.annotation)
            elif path is not None:
                key = (path, arg.arg, kind)
                annotations = self.own_stub.parameters.get(key)
                node = self._stub_annotation(annotations, path[:-1])
            else:
                node = None
            if node is not None:
                if function.annotations is None:
                    function.annotations = {}
                function.annotations[scope.mangle(arg.arg)] = node
        if function.annotations:
            self.analysis.bind_annotations(function)

    def stub_variable(self, target):
        """The node of what the stub's annotations of the assignment
        target `target` name (see `OwnStub`), or None: the target must be a
        name that the assignment binds in a class body or the module (also
        through `global`), which no annotation of the source names there."""
        if self.own_stub is None or not isinstance(target, ast.Name):
            return None
        name = self._scope.mangle(target.id)
        scope = self.scopes.resolve(self._scope, name)
        if scope.kind not in (MODULE, CLASS_SCOPE):
            return None
        path = _stub_path(scope)
        if path is None or name in self._annotated_in(scope):
            return None
        annotations = self.own_stub.variables.get((*path, name))
        return self._stub_annotation(annotations, path)

    def _annotated_in(self, scope):
        """The names, as `scope` stores them, that an annotation of the
        source names in the module or class body `scope`, with or without a
        value, anywhere in its own statements."""
        if scope not in self._source_annotated:
            names = set()
            pending = list(scope.node.body)
            while pending:
                node = pending.pop()
                match node:
                    case ast.AnnAssign(target=ast.Name(id=name)):
                        names.add(scope.mangle(name))
                if not isinstance(node, _NESTED_SCOPES):
                    pending.extend(ast.iter_child_nodes(node))
            self._source_annotated[scope] = names
        return self._source_annotated[scope]

    def _stub_annotation(self, annotations, scope):
        """The node of what the stub's `annotations`, written in the stub's
        scope of path `scope`, name together, or None. Their sites are
        positions in the stub, apart from those of the source."""
        if not annotations:
            return None
        self._reading_stub = scope
        try:
            origin = f"{self.module.name}:stub"
            return self._join([self.annotation(a, origin) for a in annotations])
        finally:
            self._reading_stub = None

    def _stub_name(self, expression):
        """The node of the name or attribute chain `expression` in an
        annotation of the stub, resolved as Python resolves the stub: in the
        scope of the annotation (a class body), else in the module, else
        among the builtins. Each binding of the first name in the first
        scope that binds it contributes: an import, what importing its dotted
        name (with the attributes) would bind, as for a type-only import,
        without loads, so it runs no hook; a class, the source's class
        definitions of the same path (`source_classes`); anything else, nothing."""
        attributes = []
        while isinstance(expression, ast.Attribute):
            attributes.append(expression.attr)
            expression = expression.value
        if not isinstance(expression, ast.Name):
            return None
        scope = self._reading_stub
        name = _stored(scope, expression.id)
        rest = "".join(f".{_stored(scope, a)}" for a in reversed(attributes))
        for path in dict.fromkeys([scope, ()]):
            bindings = self.own_stub.names.get((path, name))
            if bindings is None:
                continue
            contributions = []
            for how, target in bindings:
                if how == STUB_IMPORT:
                    contributions.append(self._imported(target + rest))
                elif how == STUB_CLASS and not attributes:
                    contributions.append(self.source_classes(target))
            return self._join(contributions)
        if attributes:
            return None
        return self.builtin_name(name)

    def source_classes(self, path):
        """The node of the source's class definitions of path `path` (`("C",
        "Inner")`), those that a class statement makes in the module or in
        class bodies only: the class statement adds each (see the builder),
        so one defined later arrives too."""
        if path not in self._stub_classes:
            self._stub_classes[path] = self.analysis.node()
        return self._stub_classes[path]

    def defined_class(self, scope, cls):
        """The class statement of `scope` made `cls`: a class that a stub
        class of its path names (`source_classes`)."""
        if self.own_stub is not None:
            path = _stub_path(scope)
            if path is not None:
                self.analysis.add_object(self.source_classes(path), cls)


class Annotations:
    """The part of `Analysis` that reads annotations at solve time (see the
    module docstring)."""

    def type_form(self, operator, parts, site):
        key = (operator, site)
        form = self._type_forms.get(key)
        if form is None:
            form = self._type_forms[key] = TypeForm(operator, tuple(parts), site)
        return form

    def bind_annotations(self, function):
        """Each annotated parameter of `function` holds what its annotation
        names; so do the elements of `*args` and the values of
        `**kwargs`."""
        signature = function.signature
        for name, annotation in function.annotations.items():
            if name == signature.vararg:
                dst = self.unknown(function.varargs)
            elif name == signature.kwarg:
                dst = self.unknown(function.varkeywords)
            else:
                dst = function.parameters[name]
            self.annotated(annotation, dst, INSTANCE, (function, name))

    def annotated(self, node, dst, shape, owner):
        """Add to `dst` what the annotation in `node` names, in `shape`.
        `owner` (a function and a parameter, or a class and a field) keys
        the containers that the annotation makes."""
        if node is None:
            return
        key = (node, dst, shape)
        if key not in self._annotated:
            self._annotated.add(key)
            self.solver.attach(
                node, Each(self._annotated_object, dst, shape, owner, results=(dst,))
            )

    def _annotated_object(self, obj, dst, shape, owner):
        match obj:
            case Class():
                if shape == CLASS:
                    self.add_edge(self.family(obj), dst)
                else:
                    self.add_edge(obj.instances, dst)
            case TypeForm(operator="|"):
                for part in obj.parts:
                    self.annotated(part, dst, shape, owner)
            case TypeForm(operator="[]") if obj.parts[0] is not None:
                subscript = Each(
                    self._annotated_subscript, obj, dst, shape, owner, results=(dst,)
                )
                self.solver.attach(obj.parts[0], subscript)
            case External():
                self.annotated_outside(obj, dst, shape == CLASS, owner)
                self.below_outside(obj, dst, shape == CLASS)

    def _annotated_subscript(self, base, form, dst, shape, owner):
        """`base[arguments]` in an annotation, the subscript `form`."""
        arguments = form.parts[1:]
        if isinstance(base, (Class, TypeForm)):
            # A generic analysed class: its instances; a generic alias: what
            # the alias names. The type arguments are ignored. Read once per
            # destination and shape, as any annotation is, so an alias whose
            # form subscripts itself (`type Loop[T] = Loop[T]`) ends.
            self.annotated(self.constant(base), dst, shape, owner)
            return
        if not isinstance(base, External):
            return
        # `tuple[()]` has no arguments: a container or another generic class
        # names what it names without them; a form that names what its
        # argument names (`Optional`, `type`) then names nothing.
        constructor = base.name.rpartition(".")[2]
        if constructor in UNIONS:
            for argument in arguments:
                self.annotated(argument, dst, shape, owner)
        elif constructor in FIRST_ARGUMENT:
            if arguments:
                self.annotated(arguments[0], dst, shape, owner)
        elif constructor in CLASSES and shape == INSTANCE:
            if arguments:
                self.annotated(arguments[0], dst, CLASS, owner)
        elif constructor in CONTAINERS and shape == INSTANCE:
            kind = CONTAINERS[constructor]
            container = self.container_at(kind, owner, _owner_site(owner), "annotation")
            self.add_object(dst, container)
            self.below_outside(base, dst, False)
            kind = builtin_kind(kind)
            elements = arguments[-1:] if kind == "dict" else arguments[_ELEMENTS[kind]]
            for argument in elements:
                self.annotated(argument, self.unknown(container), ELEMENT, owner)
        elif constructor in CONTAINERS and shape == CLASS:
            # `type[list[int]]`: the container class and the analysed
            # classes below it, whatever the arguments.
            self.annotated_outside(base, dst, True, owner)
            self.below_outside(base, dst, True)
        elif constructor not in CONTAINERS:
            # Another generic outside class: its instances, whatever the
            # arguments (`re.Pattern[str]`).
            self.annotated_outside(base, dst, shape == CLASS, owner)
            self.below_outside(base, dst, shape == CLASS)

    def family(self, cls):
        """A node with `cls` and its subclasses, by the class hierarchy: a
        subclass that a base expression gives later joins it (see
        `Hierarchy.add_base`). The family of each class flows into those
        of its bases; the classes below `cls` that have none yet get theirs
        from a work list, so a long chain of subclasses does not nest
        calls."""
        if cls not in self._families:
            made, pending = [], [cls]
            while pending:
                member = pending.pop()
                if member not in self._families:
                    self._families[member] = self.node()
                    self.add_object(self._families[member], member)
                    made.append(member)
                    pending.extend(member.subclasses)
            for member in made:
                for subclass in member.subclasses:
                    self.add_edge(self._families[subclass], self._families[member])
        return self._families[cls]

    def below_outside(self, external, dst, as_class):
        """dst ⊇ the instances (for `type[C]`, the classes) of every
        analysed class below the outside class `external`, whose MRO
        reaches it through the stub MROs (see `add_outside_base`), if it
        names them (`names_classes_below`)."""
        for definition in self.stub_definitions(external) or ():
            if definition.kind == "class" and self.names_classes_below(definition.path):
                self.add_edge(self._below_node(definition.path, as_class), dst)

    def names_classes_below(self, path):
        """Whether an annotation that names the stub class `path` names the
        analysed classes below it: only if the class is abstract (it cannot
        be instantiated as it is), and not one of the protocols that the
        builtin types implement. A concrete class already names a value of
        its own, an instance of it; `object` and `type` are concrete."""
        return self.stubs.abstract(path) and path not in BUILTIN_PROTOCOLS

    def _below_node(self, path, as_class):
        key = (path, as_class)
        if key not in self._below_nodes:
            node = self._below_nodes[key] = self.node()
            for cls in self._classes_below.get(path, ()):
                self.add_edge(self._below_source(cls, as_class), node)
        return self._below_nodes[key]

    def _below_source(self, cls, as_class):
        return self.family(cls) if as_class else cls.instances

    def add_outside_base(self, cls, base):
        """`cls` has the outside candidate base `base`: it is below every
        class of the stub MRO of `base`, whose nodes get its instances and
        its family (with its subclasses), as an analysed base's do (see
        `Hierarchy.add_base`). Classes are keyed by their stub definition,
        so a name of `typing` and its `collections.abc` class are one."""
        for definition in self.stub_definitions(base) or ():
            if definition.kind != "class":
                continue
            for path in self.stubs.mro(definition.path):
                if not self.names_classes_below(path):
                    continue
                below = self._classes_below.setdefault(path, {})
                if cls in below:
                    continue
                below[cls] = None
                for as_class in (False, True):
                    node = self._below_nodes.get((path, as_class))
                    if node is not None:
                        self.add_edge(self._below_source(cls, as_class), node)

    def gate_type_form(self, form, gate):
        """Add `form` to `gate` once one of its operands may be a type (see
        `AnnotationBuilder.alias_form`): the subscripted value of `X[...]`,
        or any arm of `A | B`."""
        if form.operator == "[]":
            operands = form.parts[:1]
        else:
            operands = form.parts
        for node in operands:
            if node is not None:
                self.solver.attach(
                    node, Each(self._type_operand, form, gate, results=(gate,))
                )

    def _type_operand(self, obj, form, gate):
        if self._may_be_type(obj):
            self.add_object(gate, form)

    def _may_be_type(self, obj):
        """Whether `obj` may be a type in a type expression: a class, a type
        form, a class of the stubs (`<builtin>.list`, `pathlib.Path`), or a
        name of `typing` (`typing.Optional`). The stub data decides, not the
        running Python."""
        if isinstance(obj, (Class, TypeForm)):
            return True
        if not isinstance(obj, External):
            return False
        if obj.name.startswith(_TYPE_MODULES):
            return True
        definitions = self.stub_definitions(obj) or ()
        return any(definition.kind == "class" for definition in definitions)

    def add_annotated_class(self, cls, decorators, bases):
        """`cls` has class-level annotations: if a decorator is
        `dataclasses.dataclass` or a base is `NamedTuple`,
        they are the parameters of its generated `__init__`."""
        for node in decorators:
            self.solver.attach(node, Each(self._dataclass_decorator, cls))
        for node in bases:
            self.solver.attach(node, Each(self._dataclass_base, cls))

    def _dataclass_decorator(self, obj, cls):
        if isinstance(obj, (External, ReturnsArgument)) and (
            obj.name in DATACLASS_DECORATORS
        ):
            self._dataclass_like(cls)

    def _dataclass_base(self, obj, cls):
        if isinstance(obj, External) and obj.name in DATACLASS_BASES:
            self._dataclass_like(cls)

    def _dataclass_like(self, cls):
        """The generated `__init__` initialises every instance of `cls` and
        of its subclasses: each annotated field of an instance holds what
        its annotation names."""
        if cls in self._dataclass_like_classes:
            return
        self._dataclass_like_classes.add(cls)
        for name, annotation in cls.annotations.items():
            values = self.node()
            self.annotated(annotation, values, INSTANCE, (cls, name))
            self.solver.attach(cls.instances, Each(self._field_values, name, values))

    def _field_values(self, instance, name, values):
        self.add_edge(values, self.field(instance, name))
        self.stored_name(instance, name)


# The nodes whose statements belong to a scope of their own.
_NESTED_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _stub_path(scope):
    """The path of `scope` from its module, `("C", "m")` for the method `m`
    of the class `C`, if only class bodies enclose it; else None: a stub
    defines nothing inside a function."""
    path = []
    while scope.kind != MODULE:
        path.append(scope.local_name)
        scope = scope.parent
        if scope.kind not in (MODULE, CLASS_SCOPE):
            return None
    return tuple(reversed(path))


def _owner_site(owner):
    definition, name = owner
    return f"{definition.name}.{name}:annotation"


# Outside modules whose names are types or type constructors.
# Names of these modules may be type constructs that the stubs do not
# describe as classes (`Optional`, `Union`).
_TYPE_MODULES = ("typing.", "typing_extensions.")
