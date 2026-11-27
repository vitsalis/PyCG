use std::collections::VecDeque;

use pycg_solver::{NodeId, ObjId};
use pycg_stubs::mro::{exhaustive_order, linearizations};
use pycg_stubs::{DefinitionKind, Entry, class_names};
use rustc_hash::FxHashSet;

use crate::builder::calls::{Allocator, NewClass};
use crate::engine::objects::{Class, Object};
use crate::engine::outside::{OutsideGives, outside_name};
use crate::engine::symbols::Sym;
use crate::engine::trace::Trace;
use crate::engine::{Graph, OrderedMap, OrderedSet, Rule, State, WaitingRule};
use crate::model::BUILTIN_MODULE;
use crate::models::{DEFINES_MARKERS, TUPLE_STORAGE};

pub const HIERARCHIES_PER_CLASS_MAX: u64 = 8;

const BUILTIN_OBJECT: &str = "<builtin>.object";
const BUILTIN_TYPE: &str = "<builtin>.type";
const BUILTIN_PROPERTY: &str = "<builtin>.property";
const OBJECT_PATH: &str = "builtins.object";
const BUILTIN_STUBS: &str = "builtins.";
const ABC_META: &str = "abc.ABCMeta";
const MODULES_OF_ABCS: &[&str] = &["abc", "typing", "typing_extensions", "_collections_abc"];
const GENERIC_CLASSES: &[&str] = &["typing.Generic", "typing_extensions.Generic"];
const FINAL_BUILTIN_METHODS: &[&str] = &["__iter__", "__contains__"];
const STR_DEFINED_BEYOND_STUBS: &[&str] = &["builtins.str", "builtins.bytes", "builtins.bytearray"];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum LookupAttr {
    Name(Sym),
    Object(ObjId),
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum Unless {
    Nothing,
    Explicit,
    PythonsOwn,
    DescriptorItself,
    DefaultMember,
    NewGivesTheClass,
    DescriptorDecides,
    DataDescriptor,
    MayDerive,
    MayLack,
    MayLackMethod,
    NotNominal,
    Names(Box<[Sym]>),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct BindsId(u32);

pub(crate) struct Binds {
    instance: bool,
    receivers: OrderedMap<NodeId, Option<ObjId>>,
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct LookupKey {
    pub attr: LookupAttr,
    pub receiver: Option<ObjId>,
    pub after: Option<ObjId>,
    pub unless: Unless,
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub(super) enum BaseOrder {
    Nothing,
    Class(String, u32),
    External(u32, String),
}

type Shape = (bool, Vec<Vec<ObjId>>);

impl<T: Trace> State<T> {
    pub(super) fn new_class(&mut self, graph: &mut Graph, new: &NewClass<'_>) -> ObjId {
        let instances = self.node(graph, None);
        let metaclass = self.node(graph, None);
        let instantiable = self.node(graph, None);
        let index = u32::try_from(self.classes.len()).expect("fewer than 2^32 classes");
        let mut ancestry: Vec<NodeId> = new.base_nodes.iter().flatten().copied().collect();
        ancestry.extend(new.metaclass);
        ancestry.push(metaclass);
        let class = Class {
            name: self.symbols.intern(new.name),
            module: self.symbols.intern(new.module),
            defines: new
                .defines
                .iter()
                .map(|name| self.symbols.intern(name))
                .collect(),
            bound: FxHashSet::default(),
            slots: FxHashSet::default(),
            bases: vec![OrderedSet::default(); new.base_nodes.len()],
            mros: Vec::new(),
            ancestors: FxHashSet::default(),
            exhaustive: false,
            ready: false,
            forced: false,
            index,
            subclasses: OrderedSet::default(),
            lookups: OrderedMap::default(),
            instances,
            metaclass,
            instantiable,
            keyword: new.metaclass.map(|_| OrderedSet::default()),
            metaclasses: OrderedSet::default(),
            metaclass_candidate_of: OrderedSet::default(),
            metaclass_users: OrderedSet::default(),
            protocol: new.protocol,
            abstract_methods: new
                .abstract_methods
                .iter()
                .map(|name| self.symbols.intern(name))
                .collect(),
            uses_namespace: new.uses_namespace,
            stored_names_outside_body: FxHashSet::default(),
            concrete: false,
            ancestry,
            unknown: false,
            allocator: None,
            lineno: None,
            end_lineno: None,
        };
        let id = self.new_object(graph, Object::Class(Box::new(class)));
        self.objects.class_mut(id).set_mros(vec![vec![id]]);
        self.classes.push(id);
        if let Some(keyword) = new.metaclass {
            let rule = self.rule(Rule::KeywordCandidate { class: id });
            self.attach(graph, keyword, rule);
        }
        for (index, node) in new.base_nodes.iter().enumerate() {
            match node {
                None => {
                    self.objects.class_mut(id).bases[index].insert(None);
                }
                Some(node) => {
                    let rule = self.rule(Rule::Bases {
                        class: id,
                        index: u32::try_from(index).expect("fewer than 2^32 bases"),
                    });
                    self.attach(graph, *node, rule);
                }
            }
        }
        self.update_mros(graph, id);
        id
    }

    pub(super) fn lookup(&mut self, graph: &mut Graph, class: ObjId, key: LookupKey) -> NodeId {
        if let Some(&node) = self.objects.class(class).lookups.get(&key) {
            return node;
        }
        let watched = (class, key.attr, key.after, key.unless.clone());
        let instance = key
            .receiver
            .is_some_and(|receiver| matches!(self.objects.get(receiver), Object::Instance { .. }));
        let node = if instance && !self.watches.contains_key(&watched) {
            let watch = graph.watch();
            self.watches.insert(watched, watch);
            self.witness(graph, watch)
        } else {
            self.node(graph, None)
        };
        self.objects
            .class_mut(class)
            .lookups
            .insert(key.clone(), node);
        let found = self.objects.class(class);
        if found.ready || found.unknown {
            self.walk_mro(graph, class, &key, node);
        }
        node
    }

    pub(super) fn lookup_name(
        &mut self,
        graph: &mut Graph,
        class: ObjId,
        attr: &str,
        receiver: Option<ObjId>,
        after: Option<ObjId>,
        unless: Unless,
    ) -> NodeId {
        let attr = LookupAttr::Name(self.symbols.intern(attr));
        let key = LookupKey {
            attr,
            receiver,
            after,
            unless,
        };
        self.lookup(graph, class, key)
    }

    pub(super) fn later(
        &mut self,
        graph: &mut Graph,
        class: ObjId,
        key: LookupKey,
        rule: WaitingRule,
    ) {
        let receiver = key.receiver.expect("a waiting rule has a receiver");
        let LookupKey {
            attr,
            after,
            unless,
            ..
        } = key;
        let LookupAttr::Name(attr) = attr else {
            panic!("a waiting rule looks up a name")
        };
        let watched = (class, LookupAttr::Name(attr), after, unless.clone());
        if !self.watches.contains_key(&watched) {
            let key = LookupKey {
                attr: LookupAttr::Name(attr),
                receiver: Some(receiver),
                after,
                unless,
            };
            self.lookup(graph, class, key);
        }
        let watch = self.watches[&watched];
        if graph.is_waiting(watch) {
            self.waiting
                .entry(watch)
                .or_default()
                .push((rule, receiver));
        } else {
            self.run_waiting(graph, rule, receiver);
        }
    }

    pub(super) fn python_method(&mut self, graph: &mut Graph, class: ObjId, name: &str) -> NodeId {
        self.lookup_name(graph, class, name, None, None, Unless::PythonsOwn)
    }

    fn new_may_give_another(&mut self, class: ObjId) -> bool {
        let found = self.objects.class(class);
        if found.exhaustive {
            return true;
        }
        let new = self.symbols.intern("__new__");
        for mro in found.mros.clone() {
            for base in mro {
                if self.objects.is_external(base) {
                    if !self.allocates_with_object(&[base]) {
                        return true;
                    }
                    continue;
                }
                let base = self.objects.class(base);
                if base.uses_namespace {
                    return true;
                }
                if !base.defines.contains(&new) {
                    continue;
                }
                match base.allocator {
                    None => return true,
                    Some(Allocator::Object) => break,
                    Some(Allocator::Super) => {}
                }
            }
        }
        false
    }

    fn may_give_itself(&mut self, class: ObjId, name: Sym) -> bool {
        let found = self.objects.class(class);
        if found.exhaustive {
            return !found.defines.contains(&name);
        }
        for mro in found.mros.clone() {
            let mut stopped = false;
            for base in mro {
                if let Object::Class(base) = self.objects.get(base) {
                    if base.defines.contains(&name) {
                        stopped = true;
                        break;
                    }
                } else if self.is_property(base) {
                    stopped = true;
                    break;
                } else if self.outside_member(base, name) != OutsideGives::Inherited {
                    return true;
                }
            }
            if !stopped {
                return true;
            }
        }
        false
    }

    fn may_write_field(&mut self, class: ObjId, name: Sym) -> bool {
        let found = self.objects.class(class);
        if found.unknown || found.exhaustive {
            return true;
        }
        for mro in found.mros.clone() {
            let mut stopped = false;
            for base in mro {
                if let Object::Class(base) = self.objects.get(base) {
                    if base.slots.contains(&name) {
                        return true;
                    }
                    if base.bound.contains(&name) {
                        stopped = true;
                        break;
                    }
                } else if self.outside_member(base, name) != OutsideGives::Inherited {
                    return true;
                }
            }
            if !stopped {
                return true;
            }
        }
        false
    }

    fn is_data_descriptor_class(&mut self, class: ObjId) -> bool {
        let found = self.objects.class(class);
        if found.unknown || found.exhaustive {
            return false;
        }
        let set = self.symbols.intern("__set__");
        let delete = self.symbols.intern("__delete__");
        for mro in found.mros.clone() {
            let mut stopped = false;
            for base in mro {
                if let Object::Class(base) = self.objects.get(base) {
                    if base.bound.contains(&set) || base.bound.contains(&delete) {
                        stopped = true;
                        break;
                    }
                } else if self.is_property(base) {
                    stopped = true;
                    break;
                } else {
                    if self.stub_definitions(base).is_none() {
                        return false;
                    }
                    if self.outside_member(base, set) == OutsideGives::Override
                        || self.outside_member(base, delete) == OutsideGives::Override
                    {
                        stopped = true;
                        break;
                    }
                }
            }
            if !stopped {
                return false;
            }
        }
        true
    }

    fn default_may_answer(&mut self, class: ObjId, name: Sym) -> bool {
        let found = self.objects.class(class);
        if found.exhaustive {
            return !found.defines.contains(&name);
        }
        let mros = found.mros.clone();
        mros.iter().any(|mro| self.default_first(mro, name))
    }

    fn default_first(&mut self, mro: &[ObjId], name: Sym) -> bool {
        for &base in mro {
            if let Object::Class(base) = self.objects.get(base) {
                if base.defines.contains(&name) {
                    return false;
                }
            } else {
                let found = self.outside_member(base, name);
                if found != OutsideGives::Inherited {
                    return found == OutsideGives::Default;
                }
            }
        }
        true
    }

    fn may_relate(&mut self, class: ObjId, other: LookupAttr, relation: &Unless) -> bool {
        let found = self.objects.class(class);
        let exhaustive = found.exhaustive;
        let mros = found.mros.clone();
        if *relation == Unless::MayLackMethod {
            let LookupAttr::Name(other) = other else {
                panic!("a method relation names a method")
            };
            if exhaustive {
                return !self.objects.class(class).defines.contains(&other);
            }
            return !mros.iter().all(|mro| self.defines_method(mro, other));
        }
        if *relation == Unless::NotNominal {
            return mros
                .iter()
                .flatten()
                .any(|&base| self.objects.is_external(base) && !self.nominal_outside(base));
        }
        let LookupAttr::Object(other) = other else {
            panic!("a relation names a class")
        };
        if self
            .objects
            .external(other)
            .is_some_and(|external| self.symbols.text(external.name) == BUILTIN_OBJECT)
        {
            return *relation == Unless::MayDerive;
        }
        if *relation == Unless::MayDerive {
            return mros.iter().any(|mro| self.derives_in(mro, other, true));
        }
        if exhaustive {
            return other != class;
        }
        mros.iter().any(|mro| !self.derives_in(mro, other, false))
    }

    fn nominal_outside(&mut self, external: ObjId) -> bool {
        let name = self.external_name(external);
        if GENERIC_CLASSES.contains(&name.as_str()) {
            return true;
        }
        let paths: Vec<Box<str>> = self
            .stub_definitions(external)
            .unwrap_or_default()
            .iter()
            .filter(|definition| definition.kind == DefinitionKind::Class)
            .map(|definition| definition.path.clone())
            .collect();
        !paths.is_empty() && paths.iter().all(|path| self.nominal_stub_class(path))
    }

    fn derives_in(&mut self, mro: &[ObjId], other: ObjId, unknown: bool) -> bool {
        if self.objects.is_class(other) {
            return mro.contains(&other);
        }
        let mut names = FxHashSet::default();
        for definition in self.stub_definitions(other).unwrap_or_default().iter() {
            if definition.kind == DefinitionKind::Class {
                names.insert(outside_name(&self.stubs.public_name(&definition.path)));
            }
        }
        for &base in mro {
            if self.objects.is_external(base) {
                if self.stub_definitions(base).is_none() {
                    if unknown {
                        return true;
                    }
                } else if self
                    .outside_ancestors(base)
                    .iter()
                    .any(|ancestor| names.contains(ancestor))
                {
                    return true;
                }
            }
        }
        false
    }

    pub(super) fn walk_mro(
        &mut self,
        graph: &mut Graph,
        class: ObjId,
        key: &LookupKey,
        dst: NodeId,
    ) {
        if self.objects.class(class).unknown {
            let saturated = self.saturated;
            self.add_object(graph, dst, saturated);
            return;
        }
        let explicit = key.unless == Unless::Explicit;
        let unless = if explicit {
            Unless::Nothing
        } else {
            key.unless.clone()
        };
        let after = key.after;
        let receiver = key.receiver;
        let attr_name = |state: &State<T>| match key.attr {
            LookupAttr::Name(name) => state.symbols.text(name).to_string(),
            LookupAttr::Object(_) => panic!("a lookup of a name"),
        };
        let name_sym = match key.attr {
            LookupAttr::Name(name) => Some(name),
            LookupAttr::Object(_) => None,
        };
        match &unless {
            Unless::DescriptorItself => {
                let name = name_sym.expect("a name");
                if self.may_give_itself(class, name) {
                    let text = format!("{BUILTIN_OBJECT}.{}", attr_name(self));
                    let external = self.external(graph, &text, 1, false);
                    self.add_object(graph, dst, external);
                }
                return;
            }
            Unless::DescriptorDecides => {
                if self.may_write_field(class, name_sym.expect("a name")) {
                    let external =
                        self.external(graph, &format!("{BUILTIN_OBJECT}.__dict__"), 1, false);
                    self.add_object(graph, dst, external);
                }
                return;
            }
            Unless::DataDescriptor => {
                if !self.is_data_descriptor_class(class) {
                    let external =
                        self.external(graph, &format!("{BUILTIN_OBJECT}.__dict__"), 1, false);
                    self.add_object(graph, dst, external);
                }
                return;
            }
            Unless::PythonsOwn => {
                if self.python_may_define(class, name_sym.expect("a name")) {
                    let text = format!("{BUILTIN_OBJECT}.{}", attr_name(self));
                    let external = self.external(graph, &text, 1, false);
                    self.add_object(graph, dst, external);
                }
                return;
            }
            Unless::NewGivesTheClass => {
                if self.new_may_give_another(class) {
                    let text = format!("{BUILTIN_OBJECT}.{}", attr_name(self));
                    let external = self.external(graph, &text, 1, false);
                    self.add_object(graph, dst, external);
                }
                return;
            }
            Unless::DefaultMember => {
                if self.default_may_answer(class, name_sym.expect("a name")) {
                    let text = format!("{BUILTIN_OBJECT}.{}", attr_name(self));
                    let external = self.external(graph, &text, 1, false);
                    self.add_object(graph, dst, external);
                }
                return;
            }
            Unless::MayDerive | Unless::MayLack | Unless::MayLackMethod | Unless::NotNominal => {
                if self.may_relate(class, key.attr, &unless) {
                    let external = self.external(graph, BUILTIN_OBJECT, 0, false);
                    self.add_object(graph, dst, external);
                }
                return;
            }
            Unless::Nothing | Unless::Explicit | Unless::Names(_) => {}
        }
        let attr = name_sym.expect("a lookup of a name");
        let names: Vec<Sym> = match &unless {
            Unless::Names(names) => names.to_vec(),
            _ => Vec::new(),
        };
        let through_class = explicit && receiver == Some(class) && after.is_none();
        let found = self.objects.class(class);
        if found.exhaustive {
            let order = found.mros[0].clone();
            let defines = found.defines.contains(&attr);
            let walked = LookupKey {
                attr: key.attr,
                receiver,
                after,
                unless: unless.clone(),
            };
            self.walk_exhaustive(graph, class, &order, &walked, dst);
            if (after.is_some() && names.is_empty()) || (explicit && !defines) {
                let found = self.object_member(graph, &order, attr, receiver, dst);
                if !found && through_class {
                    self.metaclass_member(graph, class, attr, dst);
                }
            }
            return;
        }
        for mro in found.mros.clone() {
            let mut mro = mro;
            if let Some(after) = after {
                let Some(position) = mro.iter().position(|&base| base == after) else {
                    continue;
                };
                mro = mro[position + 1..].to_vec();
            }
            if !names.is_empty() && (self.defines(&mro, &names) || !self.defines(&mro, &[attr])) {
                continue;
            }
            let mut found = self.walk_classes(graph, &mro, attr, receiver, dst, true);
            if !found && (explicit || (after.is_some() && names.is_empty())) {
                found = self.object_member(graph, &mro, attr, receiver, dst);
            }
            if !found && through_class {
                self.metaclass_member(graph, class, attr, dst);
            }
            if !found && after.is_none() && names.is_empty() {
                self.fallback(graph, &mro, attr, receiver, dst);
            }
        }
    }

    fn metaclass_member(&mut self, graph: &mut Graph, class: ObjId, attr: Sym, dst: NodeId) {
        let metaclass = self.objects.class(class).metaclass;
        if !self.metaclass_members.insert((metaclass, attr, dst)) {
            return;
        }
        let rule = self.rule(Rule::MemberOfMetaclass { class, attr, dst });
        self.attach(graph, metaclass, rule);
    }

    pub(super) fn member_of_metaclass(
        &mut self,
        graph: &mut Graph,
        meta: ObjId,
        class: ObjId,
        attr: Sym,
        dst: NodeId,
    ) {
        if self.objects.is_class(meta) {
            let key = LookupKey {
                attr: LookupAttr::Name(attr),
                receiver: Some(class),
                after: None,
                unless: Unless::Explicit,
            };
            let found = self.lookup(graph, meta, key);
            self.add_edge(graph, found, dst);
            return;
        }
        let meta_name = self.object_name(meta);
        for definition in self.stub_definitions(meta).unwrap_or_default().iter() {
            if definition.kind == DefinitionKind::Class {
                self.stub_member(graph, class, &definition.path, &meta_name, attr, dst);
            }
        }
    }

    fn walk_exhaustive(
        &mut self,
        graph: &mut Graph,
        class: ObjId,
        classes: &[ObjId],
        key: &LookupKey,
        dst: NodeId,
    ) {
        let LookupAttr::Name(attr) = key.attr else {
            panic!("an exhaustive walk looks up a name")
        };
        let (receiver, after) = (key.receiver, key.after);
        let names: Vec<Sym> = match &key.unless {
            Unless::Names(names) => names.to_vec(),
            Unless::Nothing => Vec::new(),
            other => panic!("an exhaustive walk with {other:?}"),
        };
        let unless = &names[..];
        let found = self.objects.class(class);
        let mut order = found.mros[0].clone();
        let defines = found.defines.contains(&attr);
        let mut classes = classes.to_vec();
        let mut searched_by_all = vec![class];
        if let Some(after) = after {
            if !order.contains(&after) {
                return;
            }
            classes.retain(|&base| base != after && base != class);
            order.retain(|&base| base != after && base != class);
            searched_by_all = Vec::new();
        }
        if !unless.is_empty()
            && (self.defines(&searched_by_all, unless) || !self.defines(&order, &[attr]))
        {
            return;
        }
        self.walk_classes(graph, &classes, attr, receiver, dst, false);
        if after.is_none() && unless.is_empty() && !defines {
            for base in classes {
                self.fallback_to(graph, base, attr, receiver, dst);
            }
        }
    }

    fn fallback(
        &mut self,
        graph: &mut Graph,
        mro: &[ObjId],
        attr: Sym,
        receiver: Option<ObjId>,
        dst: NodeId,
    ) {
        for &base in mro {
            if self.fallback_to(graph, base, attr, receiver, dst) {
                return;
            }
        }
    }

    fn fallback_to(
        &mut self,
        graph: &mut Graph,
        base: ObjId,
        attr: Sym,
        receiver: Option<ObjId>,
        dst: NodeId,
    ) -> bool {
        let getattr = self.symbols.intern("__getattr__");
        let Object::Class(found) = self.objects.get(base) else {
            return false;
        };
        if !found.defines.contains(&getattr) {
            return false;
        }
        let instance = match receiver.map(|receiver| self.objects.get(receiver)) {
            Some(Object::Instance { .. }) => true,
            Some(Object::Class(receiver)) => !receiver.ancestors.contains(&base),
            _ => false,
        };
        if instance && attr != getattr {
            if let Some(&watch) = self.watch_of_witness.get(&dst)
                && graph.is_waiting(watch)
            {
                graph.wake(self, watch);
            }
            let field = self.field(graph, base, getattr);
            let receiver = receiver.expect("an instance receiver");
            if self.fallback_binds.insert((field, receiver, dst)) {
                let rule = self.rule(Rule::BindFallback { receiver, dst });
                self.attach(graph, field, rule);
            }
        }
        true
    }

    pub(super) fn bind_fallback(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        receiver: ObjId,
        dst: NodeId,
    ) {
        let node = match self.fallback_nodes.get(&(receiver, dst)) {
            Some(&node) => node,
            None => {
                let node = self.node(graph, None);
                let rule = self.rule(Rule::WrapFallback { dst });
                self.attach(graph, node, rule);
                self.fallback_nodes.insert((receiver, dst), node);
                node
            }
        };
        self.bind(graph, object, Some(receiver), node, Some(true));
    }

    pub(super) fn wrap_fallback(&mut self, graph: &mut Graph, method: ObjId, dst: NodeId) {
        let fallback = self.fallback_object(graph, method);
        self.add_object(graph, dst, fallback);
    }

    fn walk_classes(
        &mut self,
        graph: &mut Graph,
        classes: &[ObjId],
        attr: Sym,
        receiver: Option<ObjId>,
        dst: NodeId,
        first_only: bool,
    ) -> bool {
        let mut found = false;
        for &base in classes {
            let defines = if self.objects.is_external(base) {
                if self.stub_definitions(base).is_some() {
                    self.outside_base_member(graph, base, attr, receiver, dst)
                } else {
                    self.external_attribute(graph, base, attr, dst);
                    true
                }
            } else {
                let field = self.field(graph, base, attr);
                let instance = match receiver.map(|receiver| self.objects.get(receiver)) {
                    Some(Object::Instance { .. }) => true,
                    Some(Object::Class(receiver)) => !receiver.ancestors.contains(&base),
                    _ => false,
                };
                self.bind_field(graph, field, receiver, dst, instance);
                self.objects.class(base).defines.contains(&attr)
            };
            found = found || defines;
            if defines && first_only {
                break;
            }
        }
        found
    }

    fn bind_field(
        &mut self,
        graph: &mut Graph,
        field: NodeId,
        receiver: Option<ObjId>,
        dst: NodeId,
        instance: bool,
    ) {
        let binds = match self.field_binds.get(&(field, instance)) {
            Some(&binds) => binds,
            None => {
                let binds = BindsId(
                    u32::try_from(self.binds.len()).expect("fewer than 2^32 field bindings"),
                );
                self.binds.push(Binds {
                    instance,
                    receivers: OrderedMap::default(),
                });
                self.field_binds.insert((field, instance), binds);
                let rule = self.rule(Rule::Binds(binds));
                self.attach(graph, field, rule);
                binds
            }
        };
        let receivers = &mut self.binds[binds.0 as usize].receivers;
        if let Some(&known) = receivers.get(&dst) {
            assert_eq!(known, receiver, "a lookup node belongs to one receiver");
            return;
        }
        receivers.insert(dst, receiver);
        let rule = self.rule(Rule::Bind {
            receiver,
            dst,
            instance,
        });
        self.apply_now(graph, field, rule);
    }

    pub(super) fn binds_results(&self, binds: BindsId) -> Vec<NodeId> {
        self.binds[binds.0 as usize]
            .receivers
            .keys()
            .copied()
            .collect()
    }

    pub(super) fn binds_apply(&mut self, graph: &mut Graph, binds: BindsId, object: ObjId) {
        let found = &self.binds[binds.0 as usize];
        let instance = found.instance;
        let receivers: Vec<(NodeId, Option<ObjId>)> = found
            .receivers
            .iter()
            .map(|(&dst, &receiver)| (dst, receiver))
            .collect();
        for (dst, receiver) in receivers {
            if receiver.is_some_and(|receiver| self.opaque(receiver)) {
                let saturated = self.saturated;
                self.add_object(graph, dst, saturated);
            } else {
                self.bind(graph, object, receiver, dst, Some(instance));
            }
        }
    }

    pub(super) fn bind(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        receiver: Option<ObjId>,
        dst: NodeId,
        instance: Option<bool>,
    ) {
        let instance = instance.unwrap_or_else(|| {
            receiver.is_some_and(|receiver| {
                matches!(self.objects.get(receiver), Object::Instance { .. })
            })
        });
        match self.objects.get(object) {
            Object::Function(_) if instance => {
                let receiver = receiver.expect("an instance receiver");
                let method = self.bound_method(graph, receiver, object);
                self.add_object(graph, dst, method);
            }
            &Object::Wrapper { kind, .. } if self.symbols.text(kind) == "staticmethod" => {
                let name = self.symbols.intern("__func__");
                let func = self.field(graph, object, name);
                self.add_edge(graph, func, dst);
            }
            &Object::Wrapper { kind, .. } if self.symbols.text(kind) == "classmethod" => {
                let receiver = receiver.expect("a class method has a receiver");
                let owner = match self.objects.get(receiver) {
                    &Object::Instance { class, .. } => class,
                    _ => receiver,
                };
                let name = self.symbols.intern("__func__");
                let func = self.field(graph, object, name);
                let rule = self.rule(Rule::BindTo { owner, dst });
                self.attach(graph, func, rule);
            }
            _ => self.add_object(graph, dst, object),
        }
    }

    pub(super) fn keyword_candidate(&mut self, graph: &mut Graph, object: ObjId, class: ObjId) {
        let candidate = match self.objects.get(object) {
            Object::Class(_) | Object::External(_) => Some(self.same_class(graph, object)),
            _ => None,
        };
        let keyword = self
            .objects
            .class_mut(class)
            .keyword
            .as_mut()
            .expect("a class with a metaclass keyword");
        if !keyword.insert(candidate) {
            return;
        }
        if let Some(candidate) = candidate
            && self.objects.is_class(candidate)
        {
            self.objects
                .class_mut(candidate)
                .metaclass_candidate_of
                .insert(class);
        }
        self.update_mros(graph, class);
    }

    fn decide_metaclasses(&mut self, graph: &mut Graph, class: ObjId) -> bool {
        let found = self.objects.class(class);
        let keyword: Vec<Option<ObjId>> = match &found.keyword {
            None => vec![None],
            Some(keyword) => keyword.iter().copied().collect(),
        };
        let bases: Vec<Vec<Option<ObjId>>> = found
            .bases
            .iter()
            .map(|candidates| candidates.iter().copied().collect())
            .collect();
        let type_ = self.external(graph, BUILTIN_TYPE, 0, false);
        let mut slots: Vec<Vec<ObjId>> =
            vec![keyword.iter().map(|meta| meta.unwrap_or(type_)).collect()];
        for candidates in bases {
            let mut slot = Vec::new();
            for base in candidates {
                slot.extend(self.base_metaclasses(graph, base));
            }
            slots.push(slot);
        }
        let mut added = false;
        for index in 0..slots.len() {
            for &meta in &slots[index] {
                if self.objects.class(class).metaclasses.contains(&meta)
                    || matches!(self.objects.get(meta), Object::Class(meta) if !meta.ready)
                {
                    continue;
                }
                let mut accepted = true;
                for (other_index, other) in slots.iter().enumerate() {
                    if other_index == index {
                        continue;
                    }
                    if !other.iter().any(|&o| self.derives(meta, o)) {
                        accepted = false;
                        break;
                    }
                }
                if accepted {
                    self.objects.class_mut(class).metaclasses.insert(meta);
                    let node = self.objects.class(class).metaclass;
                    self.add_object(graph, node, meta);
                    if self.objects.is_class(meta) {
                        let instances = self.objects.class(meta).instances;
                        self.add_object(graph, instances, class);
                        self.objects.class_mut(meta).metaclass_users.insert(class);
                    }
                    added = true;
                }
            }
        }
        self.decide_concrete(graph, class);
        added
    }

    fn decide_concrete(&mut self, graph: &mut Graph, class: ObjId) {
        if !self.objects.class(class).concrete && self.concrete(class) {
            self.objects.class_mut(class).concrete = true;
            let instantiable = self.objects.class(class).instantiable;
            self.add_object(graph, instantiable, class);
        }
        let found = self.objects.class(class);
        if found.concrete {
            let mros = found.mros.clone();
            if !mros.iter().all(|mro| self.derives_from_type(mro)) {
                self.abstract_instance(graph, class);
            }
        }
    }

    pub(super) fn class_attribute_stored(&mut self, graph: &mut Graph, class: ObjId, name: Sym) {
        if !self
            .objects
            .class_mut(class)
            .stored_names_outside_body
            .insert(name)
        {
            return;
        }
        let mut pending = vec![class];
        let mut seen = FxHashSet::default();
        while let Some(current) = pending.pop() {
            if !seen.insert(current) {
                continue;
            }
            let found = self.objects.class(current);
            if found.ready && !found.unknown {
                self.decide_concrete(graph, current);
            }
            pending.extend(self.objects.class(current).subclasses.iter().copied());
        }
    }

    fn concrete(&mut self, class: ObjId) -> bool {
        let found = self.objects.class(class);
        let init = self.symbols.intern("__init__");
        if found.protocol
            && !found.mros.iter().any(|mro| {
                mro.iter().any(|&base| {
                    matches!(self.objects.get(base), Object::Class(base)
                        if base.defines.contains(&init) || base.uses_namespace)
                })
            })
        {
            return false;
        }
        !self.abstract_by_abc(class)
    }

    fn abstract_by_abc(&mut self, class: ObjId) -> bool {
        if !self.made_by_abc(class) {
            return false;
        }
        let found = self.objects.class(class);
        let exhaustive = found.exhaustive;
        let mros = found.mros.clone();
        mros.iter()
            .all(|mro| self.allocates_with_object(mro) && self.has_abstract_name(mro, exhaustive))
    }

    fn made_by_abc(&mut self, class: ObjId) -> bool {
        if self.objects.is_external(class) {
            for definition in self.stub_definitions(class).unwrap_or_default().iter() {
                if definition.kind == DefinitionKind::Class {
                    let path = self.stubs.metaclass(&definition.path);
                    return self
                        .stubs
                        .mro(&path)
                        .iter()
                        .any(|owner| &**owner == ABC_META)
                        || &*path == ABC_META;
                }
            }
            return false;
        }
        let metaclasses: Vec<ObjId> = self
            .objects
            .class(class)
            .metaclasses
            .iter()
            .copied()
            .collect();
        if metaclasses.is_empty() {
            return false;
        }
        for meta in metaclasses {
            if self.objects.is_external(meta) {
                if !(self.external_name(meta) == ABC_META
                    || self.outside_ancestors(meta).contains(ABC_META))
                {
                    return false;
                }
            } else {
                let found = self.objects.class(meta);
                if found.exhaustive {
                    return false;
                }
                let mros = found.mros.clone();
                for mro in mros {
                    let mut any = false;
                    for base in mro {
                        if self.objects.is_external(base)
                            && (self.external_name(base) == ABC_META
                                || self.outside_ancestors(base).contains(ABC_META))
                        {
                            any = true;
                            break;
                        }
                    }
                    if !any {
                        return false;
                    }
                }
            }
        }
        true
    }

    fn allocates_with_object(&mut self, mro: &[ObjId]) -> bool {
        for &base in mro {
            if !self.objects.is_external(base) {
                continue;
            }
            let Some(definitions) = self.stub_definitions(base) else {
                return false;
            };
            for definition in definitions.iter() {
                if definition.kind != DefinitionKind::Class {
                    continue;
                }
                if self
                    .stubs
                    .mro(&definition.path)
                    .iter()
                    .any(|path| path.starts_with(BUILTIN_STUBS) && &**path != OBJECT_PATH)
                {
                    return false;
                }
                for member in self.stubs.member(&definition.path, "__new__").iter() {
                    if member.owner.as_deref() != Some(OBJECT_PATH) {
                        return false;
                    }
                }
            }
        }
        true
    }

    fn has_abstract_name(&mut self, mro: &[ObjId], exhaustive: bool) -> bool {
        let mut abstract_names: FxHashSet<String> = FxHashSet::default();
        let mut concrete_names: FxHashSet<String> = FxHashSet::default();
        for &base in mro {
            let analysed =
                matches!(self.objects.get(base), Object::Class(found) if !found.uses_namespace);
            let outside = !analysed
                && matches!(self.objects.get(base), Object::External(_))
                && self
                    .stub_definitions(base)
                    .is_some_and(|definitions| !definitions.is_empty());
            let names: Vec<(String, bool)> = if analysed {
                let made = self.made_by_abc(base);
                let found = self.objects.class(base);
                found
                    .defines
                    .union(&found.stored_names_outside_body)
                    .map(|&name| {
                        (
                            self.symbols.text(name).to_string(),
                            made && found.abstract_methods.contains(&name)
                                && !found.stored_names_outside_body.contains(&name),
                        )
                    })
                    .collect()
            } else if outside {
                let made = self.made_by_abc(base);
                self.stub_abstract_names(base)
                    .into_iter()
                    .map(|(name, is_abstract)| (name, made && is_abstract))
                    .collect()
            } else if exhaustive {
                return false;
            } else {
                break;
            };
            for (name, is_abstract) in names {
                if exhaustive
                    || (!abstract_names.contains(&name) && !concrete_names.contains(&name))
                {
                    if is_abstract {
                        abstract_names.insert(name);
                    } else {
                        concrete_names.insert(name);
                    }
                }
            }
        }
        abstract_names
            .iter()
            .any(|name| !concrete_names.contains(name))
    }

    fn stub_abstract_names(&mut self, external: ObjId) -> Vec<(String, bool)> {
        let mut names: OrderedMap<String, bool> = OrderedMap::default();
        let definitions = self.stub_definitions(external).expect("stub definitions");
        for definition in definitions.iter() {
            if definition.kind != DefinitionKind::Class {
                continue;
            }
            for owner in self.stubs.mro(&definition.path).iter() {
                let Some(found) = self.stubs.definition(owner) else {
                    continue;
                };
                let Some(entry) = found.entry else {
                    continue;
                };
                let Entry::Class(entry) = self.stubs.entry(entry) else {
                    continue;
                };
                let members: Vec<(String, bool)> = entry
                    .members
                    .iter()
                    .map(|(name, &member)| {
                        (name.to_string(), self.stubs.entry(member).is_abstract())
                    })
                    .collect();
                for (name, is_abstract) in members {
                    names.entry(name).or_insert(is_abstract);
                }
            }
        }
        names.into_iter().collect()
    }

    fn base_metaclasses(&mut self, graph: &mut Graph, base: Option<ObjId>) -> Vec<ObjId> {
        if let Some(base) = base {
            if self.objects.is_class(base) {
                return self
                    .objects
                    .class(base)
                    .metaclasses
                    .iter()
                    .copied()
                    .collect();
            }
            if self.objects.is_external(base) {
                for definition in self.stub_definitions(base).unwrap_or_default().iter() {
                    if definition.kind == DefinitionKind::Class {
                        let path = self.stubs.metaclass(&definition.path);
                        let name = outside_name(&self.stubs.public_name(&path));
                        return vec![self.external(graph, &name, 0, false)];
                    }
                }
            }
        }
        vec![self.external(graph, BUILTIN_TYPE, 0, false)]
    }

    fn derives(&mut self, meta: ObjId, other: ObjId) -> bool {
        if meta == other || self.object_name(other) == BUILTIN_TYPE {
            return true;
        }
        if self.objects.is_class(meta) {
            let mros = self.objects.class(meta).mros.clone();
            return mros.iter().any(|mro| self.named(other, mro));
        }
        if self.objects.is_external(other) {
            let name = self.external_name(other);
            return self.outside_ancestors(meta).contains(&name);
        }
        false
    }

    pub(super) fn derives_from_type(&mut self, mro: &[ObjId]) -> bool {
        mro.iter().any(|&base| {
            self.objects.is_external(base)
                && (self.external_name(base) == BUILTIN_TYPE
                    || self.outside_ancestors(base).contains(BUILTIN_TYPE))
        })
    }

    pub(super) fn outside_ancestors(&mut self, external: ObjId) -> FxHashSet<String> {
        let mut names = FxHashSet::default();
        for definition in self.stub_definitions(external).unwrap_or_default().iter() {
            if definition.kind == DefinitionKind::Class {
                for path in self.stubs.mro(&definition.path).iter() {
                    names.insert(outside_name(&self.stubs.public_name(path)));
                }
            }
        }
        names
    }

    pub(super) fn add_base(&mut self, graph: &mut Graph, base: ObjId, class: ObjId, index: u32) {
        let base = match self.objects.get(base) {
            Object::External(external) if self.symbols.text(external.name) == BUILTIN_OBJECT => {
                None
            }
            Object::Class(_) if base != class => Some(base),
            Object::External(_) => {
                let same = self.same_class(graph, base);
                Some(self.mro_entry(graph, same))
            }
            _ => return,
        };
        let candidates = &mut self.objects.class_mut(class).bases[index as usize];
        if !candidates.insert(base) {
            return;
        }
        match base {
            Some(base) if self.objects.is_class(base) => {
                self.objects.class_mut(base).subclasses.insert(class);
                if let Some(&listed) = self.namespace_nodes.get(&(base, Namespace::Subclasses)) {
                    self.add_object(graph, listed, class);
                }
                let instances = self.objects.class(class).instances;
                let base_instances = self.objects.class(base).instances;
                self.add_edge(graph, instances, base_instances);
                if let Some(&family) = self.families.get(&base) {
                    let own = self.family(graph, class);
                    self.add_edge(graph, own, family);
                }
                self.members_base(graph, base, class);
            }
            Some(base) => self.add_outside_base(graph, class, base),
            None => {}
        }
        self.update_mros(graph, class);
    }

    pub(super) fn decide_hierarchies(&mut self, graph: &mut Graph) -> bool {
        let waiting: Vec<ObjId> = self
            .classes
            .iter()
            .copied()
            .filter(|&class| {
                let found = self.objects.class(class);
                !found.ready && !found.unknown
            })
            .collect();
        if waiting.is_empty() {
            return false;
        }
        for &class in &waiting {
            let found = self.objects.class_mut(class);
            for candidates in &mut found.bases {
                if candidates.is_empty() {
                    candidates.insert(None);
                }
            }
            if let Some(keyword) = &mut found.keyword
                && keyword.is_empty()
            {
                keyword.insert(None);
            }
        }
        for &class in &waiting {
            self.update_mros(graph, class);
        }
        let cycles: Vec<ObjId> = waiting
            .into_iter()
            .filter(|&class| !self.objects.class(class).ready)
            .collect();
        for &class in &cycles {
            self.objects.class_mut(class).forced = true;
        }
        for class in cycles {
            self.update_mros(graph, class);
        }
        true
    }

    fn update_mros(&mut self, graph: &mut Graph, start: ObjId) {
        let mut queue = VecDeque::from([start]);
        while let Some(class) = queue.pop_front() {
            let found = self.objects.class(class);
            if found.unknown {
                continue;
            }
            if !found.ready {
                if !self.resolved(class) {
                    continue;
                }
                let (mros, exhaustive) = self.compute_mros(class);
                let found = self.objects.class_mut(class);
                found.ready = true;
                found.set_mros(mros);
                found.exhaustive = exhaustive;
                let lookups: Vec<(LookupKey, NodeId)> = found
                    .lookups
                    .iter()
                    .map(|(key, &node)| (key.clone(), node))
                    .collect();
                for (key, node) in lookups {
                    self.walk_mro(graph, class, &key, node);
                }
                self.decide_metaclasses(graph, class);
                let found = self.objects.class(class);
                queue.extend(found.subclasses.iter().copied());
                queue.extend(found.metaclass_candidate_of.iter().copied());
                continue;
            }
            let (mros, exhaustive) = self.compute_mros(class);
            if shape(&mros, exhaustive) == shape(&found.mros, found.exhaustive) {
                if self.decide_metaclasses(graph, class) {
                    queue.extend(self.objects.class(class).subclasses.iter().copied());
                }
                continue;
            }
            let new = if found.exhaustive && exhaustive {
                let walked: FxHashSet<ObjId> = found.mros[0].iter().copied().collect();
                Some(
                    mros[0]
                        .iter()
                        .copied()
                        .filter(|base| !walked.contains(base))
                        .collect::<Vec<_>>(),
                )
            } else {
                None
            };
            let found = self.objects.class_mut(class);
            found.set_mros(mros);
            found.exhaustive = exhaustive;
            let lookups: Vec<(LookupKey, NodeId)> = found
                .lookups
                .iter()
                .map(|(key, &node)| (key.clone(), node))
                .collect();
            for (key, node) in lookups {
                match &new {
                    Some(new) if key.after.is_none() && key.unless == Unless::Nothing => {
                        self.walk_exhaustive(graph, class, new, &key, node);
                    }
                    _ => self.walk_mro(graph, class, &key, node),
                }
            }
            self.decide_metaclasses(graph, class);
            let found = self.objects.class(class);
            queue.extend(found.subclasses.iter().copied());
            queue.extend(found.metaclass_candidate_of.iter().copied());
            queue.extend(found.metaclass_users.iter().copied());
        }
    }

    fn compute_mros(&self, class: ObjId) -> (Vec<Vec<ObjId>>, bool) {
        let found = self.objects.class(class);
        let slots: Vec<Vec<Option<ObjId>>> = found
            .bases
            .iter()
            .map(|candidates| {
                let mut slot: Vec<Option<ObjId>> = candidates
                    .iter()
                    .copied()
                    .filter(|&base| match base {
                        Some(base) => {
                            found.forced
                                || !self.objects.is_class(base)
                                || self.objects.class(base).ready
                        }
                        None => true,
                    })
                    .collect();
                slot.sort_by_cached_key(|&base| self.base_order(base));
                slot
            })
            .collect();
        let exhaustive = found.forced
            || slots.iter().flatten().flatten().any(|&base| {
                matches!(self.objects.get(base), Object::Class(base)
                    if base.exhaustive || base.ancestors.contains(&class))
            });
        let mros_of = |base: Option<&ObjId>| -> Vec<Vec<ObjId>> {
            match base {
                None => vec![Vec::new()],
                Some(&base) => match self.objects.get(base) {
                    Object::Class(base) => base.mros.clone(),
                    _ => vec![vec![base]],
                },
            }
        };
        if !exhaustive
            && let Some(mut mros) =
                linearizations(&class, &slots, mros_of, HIERARCHIES_PER_CLASS_MAX)
        {
            mros.sort_by_cached_key(|mro| {
                mro.iter()
                    .map(|&base| self.base_order(Some(base)))
                    .collect::<Vec<_>>()
            });
            return (mros, false);
        }
        (vec![exhaustive_order(&class, &slots, mros_of)], true)
    }

    pub(super) fn base_order(&self, base: Option<ObjId>) -> BaseOrder {
        let Some(base) = base else {
            return BaseOrder::Nothing;
        };
        match self.objects.get(base) {
            Object::Class(class) => {
                BaseOrder::Class(self.symbols.text(class.module).to_string(), class.index)
            }
            Object::External(external) | Object::UnknownExternal(external) => {
                BaseOrder::External(external.steps, self.symbols.text(external.name).to_string())
            }
            _ => panic!("a base is a class or an outside value"),
        }
    }

    pub(super) fn class_mro(&self, class: ObjId) -> Vec<ObjId> {
        let found = self.objects.class(class);
        if found.exhaustive {
            let mut rest: Vec<ObjId> = found.mros[0][1..].to_vec();
            rest.sort_by_cached_key(|&base| self.base_order(Some(base)));
            let mut mro = vec![class];
            mro.extend(rest);
            return mro;
        }
        let mut mro: OrderedSet<ObjId> = OrderedSet::default();
        for each in &found.mros {
            mro.extend(each.iter().copied());
        }
        mro.into_iter().collect()
    }

    fn resolved(&self, class: ObjId) -> bool {
        let found = self.objects.class(class);
        if found.forced {
            return true;
        }
        found
            .bases
            .iter()
            .chain(found.keyword.iter())
            .all(|candidates| {
                candidates.iter().any(|&base| match base {
                    Some(base) => !self.objects.is_class(base) || self.objects.class(base).ready,
                    None => true,
                })
            })
    }

    pub(super) fn opaque(&self, object: ObjId) -> bool {
        let object = match self.objects.get(object) {
            Object::Fallback { method } => *method,
            _ => object,
        };
        let class = match self.objects.get(object) {
            Object::Instance { class, .. } => *class,
            _ => object,
        };
        match self.objects.get(class) {
            Object::Saturated => true,
            Object::Class(class) => class.unknown,
            _ => false,
        }
    }

    pub(super) fn unknown_classes(&mut self, graph: &mut Graph) -> (bool, Vec<ObjId>) {
        let mut unknown = Vec::new();
        if !graph.has_absorbed() {
            return (false, unknown);
        }
        let mut added = false;
        let mut changed = true;
        while changed {
            changed = false;
            for class in self.classes.clone() {
                let found = self.objects.class(class);
                if found.unknown {
                    continue;
                }
                let ancestry = found.ancestry.clone();
                let mut opaque = false;
                for node in ancestry {
                    let held = self.objects_of(graph, node);
                    if held.iter().any(|&object| {
                        object == self.saturated
                            || matches!(self.objects.get(object), Object::Class(c) if c.unknown)
                    }) {
                        opaque = true;
                        break;
                    }
                }
                if !opaque {
                    continue;
                }
                let lookups: Vec<NodeId> = self
                    .objects
                    .class(class)
                    .lookups
                    .values()
                    .copied()
                    .collect();
                for &node in &lookups {
                    if let Some(&watch) = self.watch_of_witness.get(&node)
                        && graph.is_waiting(watch)
                    {
                        graph.wake(self, watch);
                    }
                }
                self.objects.class_mut(class).unknown = true;
                changed = true;
                unknown.push(class);
                graph.enable_opacity();
                let lookups: Vec<NodeId> = self
                    .objects
                    .class(class)
                    .lookups
                    .values()
                    .copied()
                    .collect();
                let saturated = self.saturated;
                for node in lookups {
                    self.add_object(graph, node, saturated);
                    added = true;
                }
            }
        }
        (added, unknown)
    }

    fn python_may_define(&self, class: ObjId, name: Sym) -> bool {
        let found = self.objects.class(class);
        if found.exhaustive {
            return !found.defines.contains(&name);
        }
        for mro in &found.mros {
            let definer = mro.iter().find(|&&base| match self.objects.get(base) {
                Object::Class(base) => base.defines.contains(&name),
                _ => true,
            });
            if !definer.is_some_and(|&definer| self.objects.is_class(definer)) {
                return true;
            }
        }
        false
    }

    fn is_property(&self, object: ObjId) -> bool {
        self.objects
            .external(object)
            .is_some_and(|external| self.symbols.text(external.name) == BUILTIN_PROPERTY)
    }

    fn defines_method(&mut self, classes: &[ObjId], name: Sym) -> bool {
        let text = self.symbols.text(name).to_string();
        classes.iter().any(|&base| match self.objects.get(base) {
            Object::Class(base) => base.defines.contains(&name),
            Object::External(external) => {
                let external = self.symbols.text(external.name).to_string();
                self.outside_defines(&external, &text)
            }
            _ => false,
        })
    }

    fn defines(&mut self, classes: &[ObjId], names: &[Sym]) -> bool {
        let texts: Vec<String> = names
            .iter()
            .map(|&name| self.symbols.text(name).to_string())
            .collect();
        let marked: Vec<&str> = texts
            .iter()
            .filter_map(|name| {
                DEFINES_MARKERS
                    .iter()
                    .find(|&&(marker, _)| marker == name)
                    .map(|&(_, method)| method)
            })
            .collect();
        let marked_syms: Vec<Sym> = marked
            .iter()
            .map(|name| self.symbols.intern(name))
            .collect();
        for &base in classes {
            match self.objects.get(base) {
                Object::Class(found) => {
                    if names
                        .iter()
                        .chain(&marked_syms)
                        .any(|name| found.defines.contains(name))
                    {
                        return true;
                    }
                }
                _ => {
                    let base_name = self.object_name(base);
                    let finals: Vec<&String> = texts
                        .iter()
                        .filter(|name| FINAL_BUILTIN_METHODS.contains(&name.as_str()))
                        .collect();
                    if finals
                        .iter()
                        .any(|name| self.builtin_defines(&base_name, name))
                    {
                        return true;
                    }
                    if marked
                        .iter()
                        .any(|name| self.outside_defines(&base_name, name))
                    {
                        return true;
                    }
                    if texts.iter().any(|name| name == TUPLE_STORAGE)
                        && self.derives_from_tuple(&base_name)
                    {
                        return true;
                    }
                    if texts.iter().any(|name| name == "__str__")
                        && self.outside_defines_str(&base_name)
                    {
                        return true;
                    }
                }
            }
        }
        false
    }

    fn outside_defines_str(&mut self, name: &str) -> bool {
        if self.outside_defines(name, "__str__") {
            return true;
        }
        let path = builtins_path(name);
        self.stubs.find(&path).iter().any(|definition| {
            definition.kind == DefinitionKind::Class
                && self
                    .stubs
                    .mro(&definition.path)
                    .iter()
                    .any(|owner| STR_DEFINED_BEYOND_STUBS.contains(&&**owner))
        })
    }

    fn derives_from_tuple(&mut self, name: &str) -> bool {
        let path = builtins_path(name);
        self.stubs.find(&path).iter().any(|definition| {
            definition.kind == DefinitionKind::Class
                && self
                    .stubs
                    .mro(&definition.path)
                    .iter()
                    .any(|owner| &**owner == "builtins.tuple")
        })
    }

    fn outside_defines(&mut self, name: &str, attr: &str) -> bool {
        let path = builtins_path(name);
        self.stubs.find(&path).iter().any(|definition| {
            definition.kind == DefinitionKind::Class
                && self
                    .stubs
                    .member(&definition.path, attr)
                    .iter()
                    .any(|member| member.owner.as_deref() != Some(OBJECT_PATH))
        })
    }

    fn builtin_defines(&mut self, name: &str, attr: &str) -> bool {
        let Some(rest) = name.strip_prefix(&format!("{BUILTIN_MODULE}.")) else {
            return false;
        };
        let path = format!("builtins.{rest}");
        let Some(definition) = self.stubs.definition(&path) else {
            return false;
        };
        if definition.kind != DefinitionKind::Class {
            return false;
        }
        self.stubs
            .member(&path, attr)
            .iter()
            .any(|member| member.owner.as_deref() != Some(OBJECT_PATH))
    }

    fn nominal_stub_class(&mut self, path: &str) -> bool {
        let mro = self.stubs.mro(path);
        for owner in mro.iter() {
            let definition = self.stubs.definition(owner);
            if let Some(Entry::Class(entry)) = definition
                .and_then(|definition| definition.entry)
                .map(|entry| self.stubs.entry(entry))
                && let Some(meta) = &entry.metaclass
                && class_names(meta) != ["builtins.type"]
            {
                return false;
            }
        }
        for owner in mro.iter() {
            let definition = self.stubs.definition(owner);
            let Some(Entry::Class(entry)) = definition
                .filter(|definition| definition.kind == DefinitionKind::Class)
                .and_then(|definition| definition.entry)
                .map(|entry| self.stubs.entry(entry))
            else {
                panic!("{owner} is not a class of the stubs")
            };
            if entry.protocol || entry.type_check_only {
                return false;
            }
            if owner.starts_with("builtins.") || entry.final_ {
                return true;
            }
            let module = owner.split('.').next().unwrap_or(owner);
            if MODULES_OF_ABCS.contains(&module) || self.stubs.is_abstract(owner) {
                return false;
            }
        }
        panic!("{path} has no builtin class in its stub order")
    }

    fn named(&self, other: ObjId, mro: &[ObjId]) -> bool {
        if self.objects.is_class(other) {
            return mro.contains(&other);
        }
        let name = self.object_name(other);
        mro.iter()
            .any(|&base| self.objects.is_external(base) && self.object_name(base) == name)
    }

    pub(super) fn external_name(&self, external: ObjId) -> String {
        let found = self.objects.external(external).expect("an outside value");
        self.symbols.text(found.name).to_string()
    }

    pub(super) fn family(&mut self, graph: &mut Graph, class: ObjId) -> NodeId {
        if let Some(&node) = self.families.get(&class) {
            return node;
        }
        let mut made = Vec::new();
        let mut pending = vec![class];
        while let Some(member) = pending.pop() {
            if self.families.contains_key(&member) {
                continue;
            }
            let node = self.node(graph, None);
            self.families.insert(member, node);
            self.add_object(graph, node, member);
            made.push(member);
            pending.extend(self.objects.class(member).subclasses.iter().copied());
        }
        for member in made {
            let subclasses: Vec<ObjId> = self
                .objects
                .class(member)
                .subclasses
                .iter()
                .copied()
                .collect();
            for subclass in subclasses {
                let source = self.families[&subclass];
                let target = self.families[&member];
                self.add_edge(graph, source, target);
            }
        }
        self.families[&class]
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Namespace {
    Names,
    Subclasses,
    Members,
}

fn shape(mros: &[Vec<ObjId>], exhaustive: bool) -> Shape {
    let mut sorted: Vec<Vec<ObjId>> = if exhaustive {
        let mut only = mros[0].clone();
        only.sort_unstable();
        only.dedup();
        vec![only]
    } else {
        let mut all = mros.to_vec();
        all.sort_unstable();
        all.dedup();
        all
    };
    sorted.shrink_to_fit();
    (exhaustive, sorted)
}

fn builtins_path(name: &str) -> String {
    match name.strip_prefix(&format!("{BUILTIN_MODULE}.")) {
        Some(rest) => format!("builtins.{rest}"),
        None => name.to_string(),
    }
}
