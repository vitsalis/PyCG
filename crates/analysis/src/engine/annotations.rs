use indexmap::IndexMap;
use pycg_solver::{NodeId, ObjId};
use pycg_stubs::DefinitionKind;
use rustc_hash::{FxHashMap, FxHashSet};

use crate::builder::calls::Shape;
use crate::engine::containers::ContainerOrigin;
use crate::engine::hierarchy::{LookupAttr, LookupKey, Unless};
use crate::engine::objects::{Kind, Object};
use crate::engine::outside_types::{TypeContext, TypeOrigin};
use crate::engine::rules::{Rule, RuleId};
use crate::engine::symbols::Sym;
use crate::engine::trace::Trace;
use crate::engine::{Graph, State};
use crate::model::{BUILTIN_MODULE, site_name};
use crate::models::builtin_kind;

const UNIONS: &[&str] = &["Optional", "Union"];
const FIRST_ARGUMENT: &[&str] = &[
    "Annotated",
    "Required",
    "NotRequired",
    "ReadOnly",
    "Final",
    "ClassVar",
];
const CLASSES: &[&str] = &["type", "Type"];
const CONTAINERS: &[(&str, &str)] = &[
    ("list", "list"),
    ("List", "list"),
    ("Sequence", "list"),
    ("MutableSequence", "list"),
    ("Iterable", "list"),
    ("Iterator", "list"),
    ("Collection", "list"),
    ("Reversible", "list"),
    ("Generator", "list"),
    ("deque", "collections.deque"),
    ("Deque", "collections.deque"),
    ("OrderedDict", "collections.OrderedDict"),
    ("DefaultDict", "collections.defaultdict"),
    ("defaultdict", "collections.defaultdict"),
    ("set", "set"),
    ("Set", "set"),
    ("frozenset", "set"),
    ("FrozenSet", "set"),
    ("AbstractSet", "set"),
    ("MutableSet", "set"),
    ("tuple", "tuple"),
    ("Tuple", "tuple"),
    ("dict", "dict"),
    ("Dict", "dict"),
    ("Mapping", "dict"),
    ("MutableMapping", "dict"),
];
const TYPES_SAYING_NOTHING: &[&str] = &["builtins.object"];
const TYPE_MODULES: &[&str] = &["typing.", "typing_extensions."];
const BUILTIN_OBJECT: &str = "<builtin>.object";
const DATACLASS_DECORATORS: &[&str] = &["dataclasses.dataclass", "dataclasses.dataclass.wrap"];
const DATACLASS_BASES: &[&str] = &["typing.NamedTuple", "typing_extensions.NamedTuple"];
const STRUCTURE_BASES: &[&str] = &["ctypes.Structure", "ctypes.Union"];
const SIMPLE_NATIVE: &[(&str, &str)] = &[
    ("ctypes.c_byte", "int"),
    ("ctypes.c_ubyte", "int"),
    ("ctypes.c_short", "int"),
    ("ctypes.c_ushort", "int"),
    ("ctypes.c_int", "int"),
    ("ctypes.c_uint", "int"),
    ("ctypes.c_long", "int"),
    ("ctypes.c_ulong", "int"),
    ("ctypes.c_longlong", "int"),
    ("ctypes.c_ulonglong", "int"),
    ("ctypes.c_size_t", "int"),
    ("ctypes.c_ssize_t", "int"),
    ("ctypes.c_int8", "int"),
    ("ctypes.c_uint8", "int"),
    ("ctypes.c_int16", "int"),
    ("ctypes.c_uint16", "int"),
    ("ctypes.c_int32", "int"),
    ("ctypes.c_uint32", "int"),
    ("ctypes.c_int64", "int"),
    ("ctypes.c_uint64", "int"),
    ("ctypes.c_float", "float"),
    ("ctypes.c_double", "float"),
    ("ctypes.c_longdouble", "float"),
    ("ctypes.c_bool", "bool"),
    ("ctypes.c_char", "bytes"),
    ("ctypes.c_char_p", "bytes"),
    ("ctypes.c_wchar", "str"),
    ("ctypes.c_wchar_p", "str"),
    ("ctypes.c_void_p", "int"),
];
const EXTERNAL_KINDS: &[Kind] = &[Kind::External];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct Owner {
    pub(crate) object: ObjId,
    pub(crate) name: Sym,
}

#[derive(Clone, Debug)]
pub(crate) enum AnnotationRule {
    AnnotatedObject {
        dst: NodeId,
        shape: Shape,
        owner: Owner,
    },
    AnnotatedSubscript {
        form: ObjId,
        dst: NodeId,
        shape: Shape,
        owner: Owner,
    },
    StubBase {
        class: ObjId,
    },
    TypeOperand {
        form: ObjId,
        gate: NodeId,
    },
    DataclassDecorator {
        class: ObjId,
    },
    DataclassBase {
        class: ObjId,
    },
    StructureBase {
        class: ObjId,
        fields: Box<[(Sym, Option<NodeId>)]>,
    },
    NativeField {
        native: NodeId,
    },
    FieldValues {
        name: Sym,
        values: NodeId,
    },
    NameLookup {
        attr: Sym,
        dst: NodeId,
    },
    DefinedName {
        dst: NodeId,
    },
}

impl AnnotationRule {
    pub(crate) fn key(&self) -> &'static str {
        match self {
            AnnotationRule::AnnotatedObject { .. } => "Each:Annotations._annotated_object",
            AnnotationRule::AnnotatedSubscript { .. } => "Each:Annotations._annotated_subscript",
            AnnotationRule::StubBase { .. } => "Each:Annotations._stub_base",
            AnnotationRule::TypeOperand { .. } => "Each:Annotations._type_operand",
            AnnotationRule::DataclassDecorator { .. } => "Each:Annotations._dataclass_decorator",
            AnnotationRule::DataclassBase { .. } => "Each:Annotations._dataclass_base",
            AnnotationRule::StructureBase { .. } => "Each:Annotations._structure_base",
            AnnotationRule::NativeField { .. } => "Each:Annotations._native_field",
            AnnotationRule::FieldValues { .. } => "Each:Annotations._field_values",
            AnnotationRule::NameLookup { .. } => "Each:Attributes._name_lookup",
            AnnotationRule::DefinedName { .. } => "Each:Attributes._defined_name",
        }
    }

    pub(crate) fn kinds(&self) -> Option<&'static [Kind]> {
        match self {
            AnnotationRule::StubBase { .. } => Some(EXTERNAL_KINDS),
            _ => None,
        }
    }

    pub(crate) fn captured(&self) -> Vec<ObjId> {
        match *self {
            AnnotationRule::AnnotatedSubscript { form, .. }
            | AnnotationRule::TypeOperand { form, .. } => vec![form],
            AnnotationRule::StubBase { class }
            | AnnotationRule::DataclassDecorator { class }
            | AnnotationRule::DataclassBase { class }
            | AnnotationRule::StructureBase { class, .. } => vec![class],
            AnnotationRule::AnnotatedObject { .. }
            | AnnotationRule::NativeField { .. }
            | AnnotationRule::FieldValues { .. }
            | AnnotationRule::NameLookup { .. }
            | AnnotationRule::DefinedName { .. } => Vec::new(),
        }
    }

    pub(crate) fn results(&self) -> Vec<NodeId> {
        match *self {
            AnnotationRule::AnnotatedObject { dst, .. }
            | AnnotationRule::AnnotatedSubscript { dst, .. }
            | AnnotationRule::NameLookup { dst, .. }
            | AnnotationRule::DefinedName { dst } => vec![dst],
            AnnotationRule::TypeOperand { gate, .. } => vec![gate],
            AnnotationRule::NativeField { native } => vec![native],
            AnnotationRule::StubBase { .. }
            | AnnotationRule::DataclassDecorator { .. }
            | AnnotationRule::DataclassBase { .. }
            | AnnotationRule::StructureBase { .. }
            | AnnotationRule::FieldValues { .. } => Vec::new(),
        }
    }
}

#[derive(Default)]
pub(crate) struct Annotations {
    type_forms: FxHashMap<(Sym, Sym), ObjId>,
    annotated: FxHashSet<(NodeId, NodeId, &'static str)>,
    pub(crate) of_objects: FxHashMap<ObjId, IndexMap<Sym, NodeId>>,
    dataclass_like_classes: FxHashSet<ObjId>,
    structure_classes: FxHashSet<ObjId>,
}

fn constructor_kind(constructor: &str) -> Option<&'static str> {
    CONTAINERS
        .iter()
        .find(|&&(name, _)| name == constructor)
        .map(|&(_, kind)| kind)
}

impl<T: Trace> State<T> {
    fn annotation_rule(&mut self, rule: AnnotationRule) -> RuleId {
        self.rule(Rule::Annotation(rule))
    }

    pub(super) fn type_form(
        &mut self,
        graph: &mut Graph,
        operator: &str,
        parts: &[Option<NodeId>],
        site: &str,
    ) -> ObjId {
        let key = (self.symbols.intern(operator), self.symbols.intern(site));
        if let Some(&form) = self.annotations.type_forms.get(&key) {
            return form;
        }
        let name = format!("type{operator}@{}", site_name(site));
        let name = self.symbols.intern(&name);
        let form = self.new_object(
            graph,
            Object::TypeForm {
                operator: key.0,
                parts: parts.into(),
                name,
            },
        );
        self.annotations.type_forms.insert(key, form);
        form
    }

    pub(super) fn bind_annotations(&mut self, graph: &mut Graph, function: ObjId) {
        let annotations = self
            .annotations
            .of_objects
            .get(&function)
            .expect("a function with annotations")
            .clone();
        for (name, annotation) in annotations {
            let made = self.objects.function(function);
            let text = self.symbols.text(name);
            let dst = if made.signature.vararg.as_deref() == Some(text) {
                let varargs = made.varargs.expect("a function with varargs");
                self.unknown(graph, varargs)
            } else if made.signature.kwarg.as_deref() == Some(text) {
                let varkeywords = made.varkeywords.expect("a function with varkeywords");
                self.unknown(graph, varkeywords)
            } else {
                made.parameter(name)
            };
            let owner = Owner {
                object: function,
                name,
            };
            self.annotated(graph, Some(annotation), dst, Shape::Instance, owner);
        }
    }

    pub(super) fn annotated(
        &mut self,
        graph: &mut Graph,
        node: Option<NodeId>,
        dst: NodeId,
        shape: Shape,
        owner: Owner,
    ) {
        let Some(node) = node else {
            return;
        };
        if !self.annotations.annotated.insert((node, dst, shape.name())) {
            return;
        }
        let rule = self.annotation_rule(AnnotationRule::AnnotatedObject { dst, shape, owner });
        self.attach(graph, node, rule);
    }

    fn type_form_parts(&self, form: ObjId) -> (Sym, Box<[Option<NodeId>]>) {
        match self.objects.get(form) {
            Object::TypeForm {
                operator, parts, ..
            } => (*operator, parts.clone()),
            _ => panic!("a type form"),
        }
    }

    fn annotated_object(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        dst: NodeId,
        shape: Shape,
        owner: Owner,
    ) {
        match self.objects.get(object) {
            Object::Class(class) => {
                let instances = class.instances;
                let source = if shape == Shape::Class {
                    self.family(graph, object)
                } else {
                    instances
                };
                self.add_edge(graph, source, dst);
            }
            Object::TypeForm { .. } => {
                let (operator, parts) = self.type_form_parts(object);
                match self.symbols.text(operator) {
                    "|" => {
                        for part in parts.iter() {
                            self.annotated(graph, *part, dst, shape, owner);
                        }
                    }
                    "[]" => {
                        if let Some(Some(base)) = parts.first() {
                            let rule = self.annotation_rule(AnnotationRule::AnnotatedSubscript {
                                form: object,
                                dst,
                                shape,
                                owner,
                            });
                            self.attach(graph, *base, rule);
                        }
                    }
                    _ => {}
                }
            }
            Object::External(_) | Object::UnknownExternal(_) => {
                self.annotated_outside(graph, object, dst, shape == Shape::Class, owner);
                self.below_outside(graph, object, dst, shape == Shape::Class);
            }
            _ => {}
        }
    }

    fn annotated_subscript(
        &mut self,
        graph: &mut Graph,
        base: ObjId,
        form: ObjId,
        dst: NodeId,
        shape: Shape,
        owner: Owner,
    ) {
        let (_, parts) = self.type_form_parts(form);
        let arguments = &parts[1..];
        match self.objects.get(base) {
            Object::Class(_) | Object::TypeForm { .. } => {
                let constant = self.constant(graph, base);
                self.annotated(graph, Some(constant), dst, shape, owner);
                return;
            }
            Object::External(_) | Object::UnknownExternal(_) => {}
            _ => return,
        }
        let name = self.external_name(base);
        let constructor = name.rsplit_once('.').map_or(&*name, |(_, last)| last);
        let kind = constructor_kind(constructor);
        if UNIONS.contains(&constructor) {
            for argument in arguments {
                self.annotated(graph, *argument, dst, shape, owner);
            }
        } else if FIRST_ARGUMENT.contains(&constructor) {
            if let Some(&argument) = arguments.first() {
                self.annotated(graph, argument, dst, shape, owner);
            }
        } else if CLASSES.contains(&constructor) && shape == Shape::Instance {
            if let Some(&argument) = arguments.first() {
                self.annotated(graph, argument, dst, Shape::Class, owner);
            }
        } else if let Some(kind) = kind
            && shape == Shape::Instance
        {
            let site = self.owner_site(owner);
            let site = self.symbols.intern(&site);
            let container = self.container_at(
                graph,
                kind,
                ContainerOrigin::Annotation(owner.object, owner.name),
                site,
                None,
                false,
            );
            self.add_object(graph, dst, container);
            self.below_outside(graph, base, dst, false);
            let elements: &[Option<NodeId>] = match builtin_kind(kind) {
                "dict" => &arguments[arguments.len().saturating_sub(1)..],
                "tuple" => arguments,
                "list" | "set" => &arguments[..arguments.len().min(1)],
                other => panic!("no elements of an annotated {other}"),
            };
            for &argument in elements {
                let unknown = self.unknown(graph, container);
                self.annotated(graph, argument, unknown, Shape::Element, owner);
            }
        } else if kind.is_some() && shape == Shape::Class {
            self.annotated_outside(graph, base, dst, true, owner);
            self.below_outside(graph, base, dst, true);
        } else if kind.is_none() {
            self.annotated_outside(graph, base, dst, shape == Shape::Class, owner);
            self.below_outside(graph, base, dst, shape == Shape::Class);
        }
    }

    fn owner_site(&self, owner: Owner) -> String {
        let definition = self.objects.name(owner.object, &self.symbols);
        format!("{definition}.{}:annotation", self.symbols.text(owner.name))
    }

    pub(super) fn owner_text(&self, owner: Owner) -> String {
        let kind = self.objects.get(owner.object).kind().name();
        let definition = self.objects.name(owner.object, &self.symbols);
        let name = self.symbols.text(owner.name);
        assert!(
            !name.contains(['\'', '"', '\\']) && name.chars().all(|c| !c.is_control()),
            "an annotation owner's name prints as itself"
        );
        format!("(<{kind} {definition}>, '{name}')")
    }

    fn annotated_outside(
        &mut self,
        graph: &mut Graph,
        external: ObjId,
        dst: NodeId,
        as_class: bool,
        owner: Owner,
    ) {
        let definitions = self.stub_definitions(external).unwrap_or_default();
        for definition in definitions.iter() {
            if definition.kind != DefinitionKind::Class
                || TYPES_SAYING_NOTHING.contains(&&*definition.path)
            {
                continue;
            }
            let module = definition
                .path
                .split('.')
                .next()
                .unwrap_or(&definition.path);
            if module == "typing" || module == "typing_extensions" {
                continue;
            }
            if as_class {
                self.add_object(graph, dst, external);
            } else {
                let context = TypeContext {
                    call: None,
                    receiver: None,
                    binding: None,
                    origin: TypeOrigin::Annotation(owner),
                    deferred: false,
                };
                self.add_instance(graph, &definition.path, &[], dst, &context, &[]);
            }
        }
    }

    fn below_outside(&mut self, graph: &mut Graph, external: ObjId, dst: NodeId, as_class: bool) {
        let definitions = self.stub_definitions(external).unwrap_or_default();
        for definition in definitions.iter() {
            if definition.kind == DefinitionKind::Class && self.stubs.is_abstract(&definition.path)
            {
                let node = self.below_node(graph, &definition.path, as_class);
                self.add_edge(graph, node, dst);
            }
        }
    }

    fn below_node(&mut self, graph: &mut Graph, path: &str, as_class: bool) -> NodeId {
        let key = (path.to_string(), as_class);
        if let Some(&node) = self.below_nodes.get(&key) {
            return node;
        }
        let node = self.node(graph, None);
        self.below_nodes.insert(key, node);
        let classes: Vec<ObjId> = self
            .classes_below
            .get(path)
            .into_iter()
            .flatten()
            .copied()
            .collect();
        for class in classes {
            let source = if as_class {
                self.family(graph, class)
            } else {
                self.objects.class(class).instances
            };
            self.add_edge(graph, source, node);
        }
        node
    }

    pub(super) fn add_stub_bases(&mut self, graph: &mut Graph, class: ObjId, node: NodeId) {
        let rule = self.annotation_rule(AnnotationRule::StubBase { class });
        self.attach(graph, node, rule);
    }

    pub(super) fn gate_type_form(&mut self, graph: &mut Graph, form: ObjId, gate: NodeId) {
        let (operator, parts) = self.type_form_parts(form);
        let operands = if self.symbols.text(operator) == "[]" {
            &parts[..parts.len().min(1)]
        } else {
            &parts[..]
        };
        for node in operands.iter().flatten() {
            let rule = self.annotation_rule(AnnotationRule::TypeOperand { form, gate });
            self.attach(graph, *node, rule);
        }
    }

    fn may_be_type(&mut self, object: ObjId) -> bool {
        match self.objects.get(object) {
            Object::Class(_) | Object::TypeForm { .. } => true,
            Object::External(_) | Object::UnknownExternal(_) => {
                let name = self.external_name(object);
                if TYPE_MODULES.iter().any(|module| name.starts_with(module)) {
                    return true;
                }
                self.stub_definitions(object)
                    .unwrap_or_default()
                    .iter()
                    .any(|definition| definition.kind == DefinitionKind::Class)
            }
            _ => false,
        }
    }

    pub(super) fn add_name_lookup(
        &mut self,
        graph: &mut Graph,
        base: NodeId,
        attr: Sym,
        dst: NodeId,
    ) {
        let rule = self.annotation_rule(AnnotationRule::NameLookup { attr, dst });
        self.attach(graph, base, rule);
    }

    pub(super) fn add_annotated_class(
        &mut self,
        graph: &mut Graph,
        class: ObjId,
        decorators: &[NodeId],
        bases: &[NodeId],
    ) {
        for &node in decorators {
            let rule = self.annotation_rule(AnnotationRule::DataclassDecorator { class });
            self.attach(graph, node, rule);
        }
        for &node in bases {
            let rule = self.annotation_rule(AnnotationRule::DataclassBase { class });
            self.attach(graph, node, rule);
        }
    }

    pub(super) fn add_structure_class(
        &mut self,
        graph: &mut Graph,
        class: ObjId,
        fields: Box<[(Sym, Option<NodeId>)]>,
        bases: &[NodeId],
    ) {
        for &node in bases {
            let rule = self.annotation_rule(AnnotationRule::StructureBase {
                class,
                fields: fields.clone(),
            });
            self.attach(graph, node, rule);
        }
    }

    fn dataclass_like(&mut self, graph: &mut Graph, class: ObjId) {
        if !self.annotations.dataclass_like_classes.insert(class) {
            return;
        }
        let annotations = self
            .annotations
            .of_objects
            .get(&class)
            .expect("a dataclass-like class has annotations")
            .clone();
        for (name, annotation) in annotations {
            let values = self.node(graph, None);
            let owner = Owner {
                object: class,
                name,
            };
            self.annotated(graph, Some(annotation), values, Shape::Instance, owner);
            let rule = self.annotation_rule(AnnotationRule::FieldValues { name, values });
            let instances = self.objects.class(class).instances;
            self.attach(graph, instances, rule);
        }
    }

    pub(super) fn annotation_apply(
        &mut self,
        graph: &mut Graph,
        rule: &AnnotationRule,
        object: ObjId,
    ) {
        match *rule {
            AnnotationRule::AnnotatedObject { dst, shape, owner } => {
                self.annotated_object(graph, object, dst, shape, owner)
            }
            AnnotationRule::AnnotatedSubscript {
                form,
                dst,
                shape,
                owner,
            } => self.annotated_subscript(graph, object, form, dst, shape, owner),
            AnnotationRule::StubBase { class } => {
                if matches!(self.objects.get(object), Object::UnknownExternal(_))
                    || self.external_name(object) == BUILTIN_OBJECT
                {
                    return;
                }
                let same = self.same_class(graph, object);
                let base = self.mro_entry(graph, same);
                self.add_outside_base(graph, class, base);
            }
            AnnotationRule::TypeOperand { form, gate } => {
                if self.may_be_type(object) {
                    self.add_object(graph, gate, form);
                }
            }
            AnnotationRule::DataclassDecorator { class } => {
                let name = match self.objects.get(object) {
                    Object::External(_) | Object::UnknownExternal(_) => {
                        Some(self.external_name(object))
                    }
                    &Object::ReturnsArgument { name, .. } => {
                        Some(self.symbols.text(name).to_string())
                    }
                    _ => None,
                };
                if name.is_some_and(|name| DATACLASS_DECORATORS.contains(&&*name)) {
                    self.dataclass_like(graph, class);
                }
            }
            AnnotationRule::DataclassBase { class } => {
                let named = matches!(
                    self.objects.get(object),
                    Object::External(_) | Object::UnknownExternal(_)
                ) && DATACLASS_BASES.contains(&&*self.external_name(object));
                if named {
                    self.dataclass_like(graph, class);
                }
            }
            AnnotationRule::StructureBase { class, ref fields } => {
                let named = matches!(
                    self.objects.get(object),
                    Object::External(_) | Object::UnknownExternal(_)
                ) && STRUCTURE_BASES.contains(&&*self.external_name(object));
                if !named || !self.annotations.structure_classes.insert(class) {
                    return;
                }
                for &(name, annotation) in fields.iter() {
                    let Some(annotation) = annotation else {
                        continue;
                    };
                    let native = self.node(graph, None);
                    let values = self.node(graph, None);
                    let rule = self.annotation_rule(AnnotationRule::NativeField { native });
                    self.attach(graph, annotation, rule);
                    let owner = Owner {
                        object: class,
                        name,
                    };
                    self.annotated(graph, Some(native), values, Shape::Instance, owner);
                    let rule = self.annotation_rule(AnnotationRule::FieldValues { name, values });
                    let instances = self.objects.class(class).instances;
                    self.attach(graph, instances, rule);
                }
            }
            AnnotationRule::NativeField { native } => {
                let mut value = object;
                if matches!(
                    self.objects.get(object),
                    Object::External(_) | Object::UnknownExternal(_)
                ) {
                    let name = self.external_name(object);
                    if let Some(&(_, simple)) = SIMPLE_NATIVE.iter().find(|&&(n, _)| n == name) {
                        let builtin = format!("{BUILTIN_MODULE}.{simple}");
                        value = self.external(graph, &builtin, 0, false);
                    }
                }
                self.add_object(graph, native, value);
            }
            AnnotationRule::FieldValues { name, values } => {
                let field = self.field(graph, object, name);
                self.add_edge(graph, values, field);
                self.stored_name(graph, object, name);
            }
            AnnotationRule::NameLookup { attr, dst } => match self.objects.get(object) {
                Object::Module(_) => {
                    let field = self.field(graph, object, attr);
                    self.add_edge(graph, field, dst);
                }
                Object::Class(_) => {
                    let key = LookupKey {
                        attr: LookupAttr::Name(attr),
                        receiver: Some(object),
                        after: None,
                        unless: Unless::Explicit,
                    };
                    let found = self.lookup(graph, object, key);
                    let rule = self.annotation_rule(AnnotationRule::DefinedName { dst });
                    self.attach(graph, found, rule);
                }
                Object::External(_) | Object::UnknownExternal(_) => {
                    self.external_attribute(graph, object, attr, dst)
                }
                _ => {}
            },
            AnnotationRule::DefinedName { dst } => {
                if !matches!(self.objects.get(object), Object::Fallback { .. }) {
                    self.add_object(graph, dst, object);
                }
            }
        }
    }
}
