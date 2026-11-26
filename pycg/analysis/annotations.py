import ast

from .builtin_models import RETURNS_ARGUMENT, builtin_kind
from .model import (
    BUILTIN_MODULE,
    Class,
    External,
    ReturnsArgument,
    TypeForm,
    UnknownExternal,
)
from .scopes import CLASS as CLASS_SCOPE
from .scopes import FUNCTION, MODULE, mangle
from .solver import Each

INSTANCE, ELEMENT, CLASS = "instance", "element", "class"

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
_ELEMENTS = {"list": slice(0, 1), "set": slice(0, 1), "tuple": slice(0, None)}

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

BUILTIN_OBJECT = f"{BUILTIN_MODULE}.object"

DATACLASS = "dataclasses.dataclass"
DATACLASS_DECORATORS = frozenset({DATACLASS, RETURNS_ARGUMENT[DATACLASS][2]})
DATACLASS_BASES = frozenset(
    f"{module}.{name}"
    for module in ("typing", "typing_extensions")
    for name in ("NamedTuple",)
)


NAMED, VARARG, KWARG = "named", "*", "**"


STUB_CLASS, STUB_IMPORT, STUB_ALIAS, STUB_OTHER = "class", "import", "alias", "other"


class OwnStub:
    def __init__(self, tree, absolute):
        self.parameters = {}
        self.variables = {}
        self.names = {}
        self.bases = {}
        self._absolute = absolute
        self._function_aliases = []
        pending = [(tree.body, ())]
        while pending:
            statements, path = pending.pop()
            for statement in statements:
                self._definition(statement, path, pending)
        copied = True
        while copied:
            copied = False
            for path, name, source in self._function_aliases:
                for key, annotations in list(self.parameters.items()):
                    function, arg, kind = key
                    if function != (*path, source):
                        continue
                    known = self.parameters.setdefault(((*path, name), arg, kind), [])
                    added = [a for a in annotations if a not in known]
                    known.extend(added)
                    copied = copied or bool(added)

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
                bases = self.bases.setdefault(cls, [])
                for base in statement.bases:
                    while isinstance(base, ast.Subscript):
                        base = base.value
                    if isinstance(base, (ast.Name, ast.Attribute)):
                        bases.append(base)
                pending.append((statement.body, cls))
            case ast.Assign(targets=[ast.Name() as target], value=value) if (
                _alias_value(value)
            ):
                self._bind(path, target.id, STUB_ALIAS, value)
                if isinstance(value, ast.Name):
                    self._function_aliases.append((path, target.id, value.id))
            case ast.AnnAssign(target=ast.Name() as target, value=value) if (
                value is not None and _type_alias(statement.annotation)
            ):
                self._bind(path, target.id, STUB_ALIAS, value)
            case ast.TypeAlias(name=ast.Name() as target, value=value):
                self._bind(path, target.id, STUB_ALIAS, value)
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


def _alias_value(value):
    if isinstance(value, ast.BinOp):
        return isinstance(value.op, ast.BitOr)
    return isinstance(value, (ast.Name, ast.Attribute, ast.Subscript))


def _type_alias(annotation):
    match annotation:
        case ast.Name(id="TypeAlias") | ast.Attribute(attr="TypeAlias"):
            return True
    return False


def _stored(path, name):
    return mangle(path[-1] if path else None, name)


def _target_names(targets):
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
    def annotation(self, expression, origin=None):
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
        if self._stub_scope_path_being_read is not None:
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
                    self.analysis.add_name_lookup(base, attr, value)
                    return value
                site = self._annotation_site(expression, origin)
                self.analysis.add_load(base, attr, value, self._caller, site)
                return value
        return None

    def _annotation_variable(self, name):
        name = self._scope.mangle(name)
        scope = self.scopes.resolve(self._scope, name)
        if scope.kind == CLASS_SCOPE and scope is not self._scope:
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
        target = None
        scope = self._scope
        while scope is not None and target is None:
            target = self.type_only_names.get(f"{scope.name}.{scope.mangle(name)}")
            scope = scope.parent
        if target is None:
            return None
        return self._imported(target)

    def _imported(self, target):
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
        if isinstance(value, ast.Subscript):
            operator = "[]"
        elif isinstance(value, ast.BinOp) and isinstance(value.op, ast.BitOr):
            operator = "|"
        else:
            return None
        self.annotation(value)
        form = self.analysis.type_form(operator, (), self._site(value))
        gate = self.analysis.node()
        self.analysis.gate_type_form(form, gate)
        return gate

    def declared(self, annotation, target):
        if annotation is None:
            return None
        node = self.analysis.node()
        position = f"{target.lineno}:{target.col_offset}"
        owner = (self.module, position)
        self.analysis.annotated(annotation, node, INSTANCE, owner)
        return node

    def parameter_annotations(self, function, arguments, scope):
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
        if scope not in self._source_annotated_names_by_scope:
            names = set()
            pending = list(scope.node.body)
            while pending:
                node = pending.pop()
                match node:
                    case ast.AnnAssign(target=ast.Name(id=name)):
                        names.add(scope.mangle(name))
                if not isinstance(node, _NESTED_SCOPES):
                    pending.extend(ast.iter_child_nodes(node))
            self._source_annotated_names_by_scope[scope] = names
        return self._source_annotated_names_by_scope[scope]

    def _stub_annotation(self, annotations, scope):
        if not annotations:
            return None
        self._stub_scope_path_being_read = scope
        try:
            origin = f"{self.module.name}:stub"
            return self._join([self.annotation(a, origin) for a in annotations])
        finally:
            self._stub_scope_path_being_read = None

    def _stub_name(self, expression):
        attributes = []
        while isinstance(expression, ast.Attribute):
            attributes.append(expression.attr)
            expression = expression.value
        if not isinstance(expression, ast.Name):
            return None
        scope = self._stub_scope_path_being_read
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
                elif how == STUB_ALIAS and not attributes:
                    contributions.append(self._stub_alias(path, target))
            return self._join(contributions)
        if attributes:
            return None
        return self.builtin_name(name)

    def _stub_alias(self, path, value):
        node = self._stub_aliases.get(value)
        if node is None:
            node = self._stub_aliases[value] = self.analysis.node()
            reading = self._stub_scope_path_being_read
            self._stub_scope_path_being_read = path
            try:
                read = self.annotation(value, f"{self.module.name}:stub")
            finally:
                self._stub_scope_path_being_read = reading
            if read is not None:
                self.analysis.add_edge(read, node)
        return node

    def source_classes(self, path):
        if path not in self._source_classes_by_stub_path:
            self._source_classes_by_stub_path[path] = self.analysis.node()
        return self._source_classes_by_stub_path[path]

    def defined_class(self, scope, cls):
        if self.own_stub is not None:
            path = _stub_path(scope)
            if path is not None:
                self.analysis.add_object(self.source_classes(path), cls)
                bases = self.own_stub.bases.get(path)
                node = self._stub_annotation(bases, path[:-1])
                if node is not None:
                    self.analysis.add_stub_bases(cls, node)


class Annotations:
    def type_form(self, operator, parts, site):
        key = (operator, site)
        form = self._type_forms.get(key)
        if form is None:
            form = self._type_forms[key] = TypeForm(operator, tuple(parts), site)
        return form

    def bind_annotations(self, function):
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
        arguments = form.parts[1:]
        if isinstance(base, (Class, TypeForm)):
            self.annotated(self.constant(base), dst, shape, owner)
            return
        if not isinstance(base, External):
            return
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
            self.annotated_outside(base, dst, True, owner)
            self.below_outside(base, dst, True)
        elif constructor not in CONTAINERS:
            self.annotated_outside(base, dst, shape == CLASS, owner)
            self.below_outside(base, dst, shape == CLASS)

    def family(self, cls):
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
        for definition in self.stub_definitions(external) or ():
            if definition.kind == "class" and self.names_classes_below(definition.path):
                self.add_edge(self._below_node(definition.path, as_class), dst)

    def names_classes_below(self, path):
        return self.stubs.abstract(path)

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
        for definition in self.stub_definitions(base) or ():
            if definition.kind != "class":
                continue
            through = self.stubs.abstract_reach(definition.path)
            for path in self.stubs.mro(definition.path):
                if not self.names_classes_below(path):
                    continue
                if path in BUILTIN_PROTOCOLS and path not in through:
                    continue
                below = self._classes_below.setdefault(path, {})
                if cls in below:
                    continue
                below[cls] = None
                for as_class in (False, True):
                    node = self._below_nodes.get((path, as_class))
                    if node is not None:
                        self.add_edge(self._below_source(cls, as_class), node)

    def add_stub_bases(self, cls, node):
        self.solver.attach(node, Each(self._stub_base, cls, kinds=(External,)))

    def _stub_base(self, base, cls):
        if isinstance(base, UnknownExternal) or base.name == BUILTIN_OBJECT:
            return
        self.add_outside_base(cls, self.mro_entry(self.same_class(base)))

    def gate_type_form(self, form, gate):
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
        if isinstance(obj, (Class, TypeForm)):
            return True
        if not isinstance(obj, External):
            return False
        if obj.name.startswith(_TYPE_MODULES):
            return True
        definitions = self.stub_definitions(obj) or ()
        return any(definition.kind == "class" for definition in definitions)

    def add_annotated_class(self, cls, decorators, bases):
        for node in decorators:
            self.solver.attach(node, Each(self._dataclass_decorator, cls))
        for node in bases:
            self.solver.attach(node, Each(self._dataclass_base, cls))

    def add_structure_class(self, cls, fields, bases):
        for node in bases:
            self.solver.attach(node, Each(self._structure_base, cls, fields))

    def _structure_base(self, obj, cls, fields):
        if not (isinstance(obj, External) and obj.name in STRUCTURE_BASES):
            return
        if cls in self._structure_classes:
            return
        self._structure_classes.add(cls)
        for name, annotation in fields.items():
            if annotation is None:
                continue
            native = self.node()
            values = self.node()
            each = Each(self._native_field, native, results=(native,))
            self.solver.attach(annotation, each)
            self.annotated(native, values, INSTANCE, (cls, name))
            self.solver.attach(cls.instances, Each(self._field_values, name, values))

    def _native_field(self, obj, native):
        if isinstance(obj, External) and obj.name in SIMPLE_NATIVE:
            obj = self.external(f"{BUILTIN_MODULE}.{SIMPLE_NATIVE[obj.name]}")
        self.add_object(native, obj)

    def _dataclass_decorator(self, obj, cls):
        if isinstance(obj, (External, ReturnsArgument)) and (
            obj.name in DATACLASS_DECORATORS
        ):
            self._dataclass_like(cls)

    def _dataclass_base(self, obj, cls):
        if isinstance(obj, External) and obj.name in DATACLASS_BASES:
            self._dataclass_like(cls)

    def _dataclass_like(self, cls):
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


STRUCTURE_BASES = frozenset({"ctypes.Structure", "ctypes.Union"})
SIMPLE_NATIVE = {
    **{
        f"ctypes.c_{name}": "int"
        for name in (
            "byte",
            "ubyte",
            "short",
            "ushort",
            "int",
            "uint",
            "long",
            "ulong",
            "longlong",
            "ulonglong",
            "size_t",
            "ssize_t",
            "int8",
            "uint8",
            "int16",
            "uint16",
            "int32",
            "uint32",
            "int64",
            "uint64",
        )
    },
    "ctypes.c_float": "float",
    "ctypes.c_double": "float",
    "ctypes.c_longdouble": "float",
    "ctypes.c_bool": "bool",
    "ctypes.c_char": "bytes",
    "ctypes.c_char_p": "bytes",
    "ctypes.c_wchar": "str",
    "ctypes.c_wchar_p": "str",
    "ctypes.c_void_p": "int",
}


_NESTED_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _stub_path(scope):
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


_TYPE_MODULES = ("typing.", "typing_extensions.")
