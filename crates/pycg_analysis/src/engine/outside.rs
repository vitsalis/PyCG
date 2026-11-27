use std::rc::Rc;

use pycg_solver::{NodeId, ObjId};
use pycg_stubs::{Decorator, Definition, DefinitionKind, Entry};

use crate::engine::objects::Object;
use crate::engine::symbols::Sym;
use crate::engine::trace::Trace;
use crate::engine::{EXTERNAL_STEPS_PAST_ROOT_MAX, Graph, State, not_ported};
use crate::model::BUILTIN_MODULE;
use crate::models::CONCRETE_CLASSES;

pub const STUB_BUILTINS: &str = "builtins";
const OBJECT: &str = "builtins.object";
const BUILTIN_TYPE_PATH: &str = "builtins.type";
const BUILTIN_PROTOCOLS: &[&str] = &[
    "typing.Iterable",
    "typing.Iterator",
    "typing.Collection",
    "typing.Container",
    "typing.Sized",
    "typing.Hashable",
    "typing.Reversible",
];
const MRO_ENTRIES: &[(&str, &str)] = &[
    ("typing.NamedTuple", "builtins.tuple"),
    ("typing.TypedDict", "builtins.dict"),
    ("typing_extensions.TypedDict", "builtins.dict"),
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum OutsideGives {
    Default,
    Override,
    Inherited,
}

pub fn stub_path(name: &str) -> String {
    if name == BUILTIN_MODULE || name.starts_with(&format!("{BUILTIN_MODULE}.")) {
        return format!("{STUB_BUILTINS}{}", &name[BUILTIN_MODULE.len()..]);
    }
    name.to_string()
}

pub fn outside_name(path: &str) -> String {
    if path == STUB_BUILTINS || path.starts_with(&format!("{STUB_BUILTINS}.")) {
        return format!("{BUILTIN_MODULE}{}", &path[STUB_BUILTINS.len()..]);
    }
    path.to_string()
}

impl<T: Trace> State<T> {
    pub(super) fn stub_definitions(&mut self, external: ObjId) -> Option<Rc<[Definition]>> {
        let (name, unknown) = match self.objects.get(external) {
            Object::External(found) => (found.name, false),
            Object::UnknownExternal(found) => (found.name, true),
            _ => panic!("object {external:?} is not an outside value"),
        };
        if let Some(found) = self.stub_definitions.get(&name) {
            return found.clone();
        }
        let mut result = None;
        if !unknown {
            let mut path = stub_path(self.symbols.text(name));
            for &(concrete, class) in CONCRETE_CLASSES {
                if path == concrete || path.starts_with(&format!("{concrete}.")) {
                    path = format!("{class}{}", &path[concrete.len()..]);
                }
            }
            let top = path.split('.').next().unwrap_or(&path).to_string();
            if self.stubs.module(&top).is_some() {
                result = Some(Rc::from(self.stubs.find(&path)));
            }
        }
        self.stub_definitions.insert(name, result.clone());
        result
    }

    pub(super) fn outside_member(&mut self, external: ObjId, name: Sym) -> OutsideGives {
        let Some(definitions) = self.stub_definitions(external) else {
            return OutsideGives::Override;
        };
        let name = self.symbols.text(name).to_string();
        let mut default = false;
        let mut overrides = false;
        for definition in definitions.iter() {
            if definition.kind != DefinitionKind::Class {
                continue;
            }
            for path in self.stubs.mro(&definition.path).iter() {
                if &**path == BUILTIN_TYPE_PATH {
                    default = true;
                    break;
                }
                if &**path == OBJECT {
                    break;
                }
                if self
                    .stubs
                    .member(path, &name)
                    .iter()
                    .any(|member| member.owner.as_deref() == Some(&**path))
                {
                    overrides = true;
                    break;
                }
            }
        }
        if overrides {
            OutsideGives::Override
        } else if default {
            OutsideGives::Default
        } else {
            OutsideGives::Inherited
        }
    }

    pub(super) fn same_class(&mut self, graph: &mut Graph, object: ObjId) -> ObjId {
        match self.objects.get(object) {
            Object::External(external) if external.inexact => {
                let name = self.symbols.text(external.name).to_string();
                let steps = external.steps;
                self.external(graph, &name, steps, false)
            }
            _ => object,
        }
    }

    pub(super) fn mro_entry(&mut self, graph: &mut Graph, base: ObjId) -> ObjId {
        let base_name = self.external_name(base);
        for definition in self.stub_definitions(base).unwrap_or_default().iter() {
            if let Some(&(_, replaced)) = MRO_ENTRIES
                .iter()
                .find(|&&(path, _)| path == &*definition.path)
            {
                let name = outside_name(&self.stubs.public_name(replaced));
                return self.external(graph, &name, 0, false);
            }
            if let Some(abc) = self.stubs.abc_name(&definition.path)
                && *abc != *base_name
            {
                return self.external(graph, &abc, 0, false);
            }
        }
        base
    }

    pub(super) fn stub_member(
        &mut self,
        graph: &mut Graph,
        receiver: ObjId,
        class: &str,
        prefix: &str,
        attr: Sym,
        dst: NodeId,
    ) {
        let attr = self.symbols.text(attr).to_string();
        for definition in self.stubs.member(class, &attr).iter() {
            let name = format!("{prefix}.{attr}");
            match definition.kind {
                DefinitionKind::Function => {
                    let method = self.external(graph, &name, 1, false);
                    match self.decorator(definition) {
                        Some(Decorator::StaticMethod) => self.add_object(graph, dst, method),
                        Some(Decorator::ClassMethod) => {
                            let owner = self.class_object(graph, receiver);
                            let bound = self.bound_method(graph, owner, method);
                            self.add_object(graph, dst, bound);
                        }
                        None => {
                            let bound = self.bound_method(graph, receiver, method);
                            self.add_object(graph, dst, bound);
                        }
                    }
                }
                DefinitionKind::Class => {
                    let external = self.external(graph, &name, 1, false);
                    self.add_object(graph, dst, external);
                }
                _ => not_ported("outside types: the type of a stub member"),
            }
        }
    }

    fn decorator(&self, definition: &Definition) -> Option<Decorator> {
        match definition.entry.map(|entry| self.stubs.entry(entry)) {
            Some(Entry::Function(function)) => function.decorator,
            _ => None,
        }
    }

    fn class_object(&mut self, graph: &mut Graph, object: ObjId) -> ObjId {
        match self.objects.get(object) {
            Object::Class(_) | Object::External(_) | Object::UnknownExternal(_) => object,
            &Object::Instance { class, .. } => class,
            Object::Const { value, exact } => {
                let name = format!(
                    "{BUILTIN_MODULE}.{}",
                    crate::model::constant_type_name(&value.view())
                );
                let inexact = !exact;
                self.external(graph, &name, 0, inexact)
            }
            _ => not_ported("the class of a builtin value"),
        }
    }

    pub(super) fn outside_base_member(
        &mut self,
        graph: &mut Graph,
        base: ObjId,
        attr: Sym,
        receiver: Option<ObjId>,
        dst: NodeId,
    ) -> bool {
        let mut found = false;
        let text = self.symbols.text(attr).to_string();
        let definitions = self.stub_definitions(base).expect("stub definitions");
        for definition in definitions.iter() {
            if definition.kind != DefinitionKind::Class {
                continue;
            }
            let members = self.stubs.member(&definition.path, &text);
            for member in members.iter() {
                if member.owner.as_deref() != Some(OBJECT) {
                    found = true;
                    self.deliver_base_member(graph, member, base, attr, receiver, dst);
                }
            }
            let class_receiver = receiver.filter(|&receiver| self.objects.is_class(receiver));
            if members.is_empty()
                && let Some(receiver) = class_receiver
            {
                for member in self.stubs.metaclass_member(&definition.path, &text).iter() {
                    if member.kind == DefinitionKind::Function {
                        found = true;
                        let method = self.base_member_external(graph, base, attr);
                        let bound = self.bound_method(graph, receiver, method);
                        self.add_object(graph, dst, bound);
                    }
                }
            }
        }
        found
    }

    pub(super) fn object_member(
        &mut self,
        graph: &mut Graph,
        classes: &[ObjId],
        attr: Sym,
        receiver: Option<ObjId>,
        dst: NodeId,
    ) -> bool {
        let text = self.symbols.text(attr).to_string();
        let members = self.stubs.member(OBJECT, &text);
        if members.is_empty() {
            return false;
        }
        let mut through = None;
        for &base in classes {
            if self.objects.is_external(base) && self.stub_definitions(base).is_some() {
                through = Some(base);
                break;
            }
        }
        let through = match through {
            Some(through) => through,
            None => {
                let name = outside_name(OBJECT);
                self.external(graph, &name, 0, false)
            }
        };
        for member in members.iter() {
            self.deliver_base_member(graph, member, through, attr, receiver, dst);
        }
        true
    }

    fn deliver_base_member(
        &mut self,
        graph: &mut Graph,
        member: &Definition,
        base: ObjId,
        attr: Sym,
        receiver: Option<ObjId>,
        dst: NodeId,
    ) {
        let instance_class = receiver.and_then(|receiver| match self.objects.get(receiver) {
            &Object::Instance { class, .. } => Some(class),
            _ => None,
        });
        let instance = instance_class.is_some();
        match member.kind {
            DefinitionKind::Function => {
                let method = self.base_member_external(graph, base, attr);
                let decorator = self.decorator(member);
                if decorator == Some(Decorator::ClassMethod) {
                    let owner = instance_class
                        .or(receiver)
                        .expect("a class method has a receiver");
                    let bound = self.bound_method(graph, owner, method);
                    self.add_object(graph, dst, bound);
                } else if instance && decorator != Some(Decorator::StaticMethod) {
                    let receiver = receiver.expect("an instance receiver");
                    let bound = self.bound_method(graph, receiver, method);
                    self.add_object(graph, dst, bound);
                } else {
                    self.add_object(graph, dst, method);
                }
            }
            DefinitionKind::Class => {
                let external = self.base_member_external(graph, base, attr);
                self.add_object(graph, dst, external);
            }
            DefinitionKind::Variable => not_ported("outside types: the type of a base member"),
            _ if instance => not_ported("outside types: the type of a base member"),
            _ => {}
        }
    }

    fn base_member_external(&mut self, graph: &mut Graph, base: ObjId, attr: Sym) -> ObjId {
        let found = self.objects.external(base).expect("an outside base");
        if found.steps > EXTERNAL_STEPS_PAST_ROOT_MAX {
            return self.unknown_external;
        }
        let name = format!(
            "{}.{}",
            self.symbols.text(found.name),
            self.symbols.text(attr)
        );
        let steps = found.steps + 1;
        self.external(graph, &name, steps, false)
    }

    pub(super) fn external_attribute(
        &mut self,
        graph: &mut Graph,
        external: ObjId,
        attr: Sym,
        dst: NodeId,
    ) {
        let found = self.objects.external(external).expect("an outside value");
        let name = self.symbols.text(found.name).to_string();
        let steps = found.steps;
        let past_root = crate::model::steps_past_root(&name, steps as usize);
        let bounded =
            steps < EXTERNAL_STEPS_PAST_ROOT_MAX && !past_root.contains(&self.symbols.text(attr));
        if self.stub_definitions(external).is_some() {
            not_ported("outside attributes");
        }
        if bounded {
            let attribute = format!("{name}.{}", self.symbols.text(attr));
            let steps = if self.external_modules.contains(&attribute) || name == BUILTIN_MODULE {
                0
            } else {
                steps + 1
            };
            let external = self.external(graph, &attribute, steps, false);
            self.add_object(graph, dst, external);
        } else {
            let unknown = self.unknown_external;
            self.add_object(graph, dst, unknown);
        }
    }

    pub(super) fn add_external_module(&mut self, name: &str) {
        let parts: Vec<&str> = name.split('.').collect();
        for end in 2..=parts.len() {
            self.external_modules.insert(parts[..end].join("."));
        }
    }

    pub(super) fn add_outside_base(&mut self, graph: &mut Graph, class: ObjId, base: ObjId) {
        for definition in self.stub_definitions(base).unwrap_or_default().iter() {
            if definition.kind != DefinitionKind::Class {
                continue;
            }
            let through = self.stubs.abstract_reach(&definition.path);
            for path in self.stubs.mro(&definition.path).iter() {
                if !self.stubs.is_abstract(path) {
                    continue;
                }
                if BUILTIN_PROTOCOLS.contains(&&**path) && !through.contains(path) {
                    continue;
                }
                let below = self.classes_below.entry(path.to_string()).or_default();
                if !below.insert(class) {
                    continue;
                }
                for as_class in [false, true] {
                    if let Some(&node) = self.below_nodes.get(&(path.to_string(), as_class)) {
                        let source = if as_class {
                            self.family(graph, class)
                        } else {
                            self.objects.class(class).instances
                        };
                        self.add_edge(graph, source, node);
                    }
                }
            }
        }
    }

    pub(super) fn imported_value(&mut self, graph: &mut Graph, name: &str) -> NodeId {
        let external = self.external(graph, name, 0, false);
        let definitions = self.stub_definitions(external).unwrap_or_default();
        if definitions.iter().all(named) {
            return self.constant(graph, external);
        }
        not_ported("outside types: an imported variable")
    }
}

fn named(definition: &Definition) -> bool {
    if matches!(
        definition.kind,
        DefinitionKind::Module | DefinitionKind::Class | DefinitionKind::Function
    ) {
        return true;
    }
    let module = definition
        .path
        .split('.')
        .next()
        .unwrap_or(&definition.path);
    module == "typing" || module == "typing_extensions"
}
