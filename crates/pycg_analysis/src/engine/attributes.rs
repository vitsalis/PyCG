use pycg_solver::{NodeId, ObjId};
use rustc_hash::FxHashMap;

use crate::engine::hierarchy::{LookupAttr, LookupKey, Namespace, Unless};
use crate::engine::objects::{Kind, Literal, Object};
use crate::engine::rules::{Rule, WaitingRule};
use crate::engine::semantics::{CallId, Role, SiteKey};
use crate::engine::symbols::Sym;
use crate::engine::trace::Trace;
use crate::engine::{Graph, OrderedMap, OrderedSet, State, not_ported};

pub const ANALYSED_METHODS: &[Kind] = &[
    Kind::Function,
    Kind::BoundMethod,
    Kind::Instance,
    Kind::Wrapper,
    Kind::Class,
];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct AccessId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct HooksId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct AccessorsId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct WritesId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct HookCallsId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct DeliveriesId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum AccessKind {
    Load,
    Store,
    Delete,
}

impl AccessKind {
    pub fn name(self) -> &'static str {
        match self {
            AccessKind::Load => "Load",
            AccessKind::Store => "Store",
            AccessKind::Delete => "Delete",
        }
    }
}

pub struct Access {
    pub kind: AccessKind,
    pub attr: Sym,
    pub caller: Sym,
    pub site: Sym,
    pub dst: Option<NodeId>,
    pub src: Option<NodeId>,
    accessor_calls: FxHashMap<Option<Sym>, CallId>,
    named_call: Option<CallId>,
    hook_calls: FxHashMap<Option<NodeId>, CallId>,
}

pub type AccessorEntry = (NodeId, AccessId, bool, u32);

#[derive(Default)]
pub struct AccessorHooks {
    lookups: OrderedSet<NodeId>,
    receivers: OrderedMap<AccessorEntry, Vec<ObjId>>,
    callers: OrderedSet<Option<Sym>>,
    pub results_of: OrderedSet<NodeId>,
    saturated: bool,
}

pub struct Accessors {
    pub call: CallId,
    pub analysed_only: bool,
    width: u32,
    receivers: Vec<ObjId>,
    methods: Vec<ObjId>,
}

#[derive(Default)]
pub struct FieldWrites {
    pub writes: OrderedSet<(NodeId, NodeId)>,
    written: bool,
    saturated: bool,
}

pub struct HookCalls {
    found: NodeId,
    pub calls: Vec<CallId>,
    hooks: Vec<ObjId>,
    saw_opaque: bool,
}

pub struct Deliveries {
    pub receiver: ObjId,
    hook: Option<Sym>,
    pub loads: Vec<AccessId>,
}

impl<T: Trace> State<T> {
    fn new_access(
        &mut self,
        kind: AccessKind,
        attr: &str,
        dst: Option<NodeId>,
        src: Option<NodeId>,
        caller: &str,
        site: &str,
    ) -> AccessId {
        let id = AccessId(u32::try_from(self.accesses.len()).expect("fewer than 2^32 accesses"));
        let access = Access {
            kind,
            attr: self.symbols.intern(attr),
            caller: self.symbols.intern(caller),
            site: self.symbols.intern(site),
            dst,
            src,
            accessor_calls: FxHashMap::default(),
            named_call: None,
            hook_calls: FxHashMap::default(),
        };
        self.accesses.push(access);
        id
    }

    pub(super) fn access(&self, id: AccessId) -> &Access {
        &self.accesses[id.0 as usize]
    }

    pub(super) fn access_result(&self, id: AccessId) -> Option<NodeId> {
        self.access(id).dst
    }

    pub(super) fn add_load(
        &mut self,
        graph: &mut Graph,
        base: NodeId,
        attr: &str,
        dst: NodeId,
        caller: &str,
        site: &str,
    ) {
        let access = self.new_access(AccessKind::Load, attr, Some(dst), None, caller, site);
        let rule = self.rule(Rule::Access(access));
        self.attach(graph, base, rule);
    }

    pub(super) fn add_store(
        &mut self,
        graph: &mut Graph,
        base: NodeId,
        attr: &str,
        src: Option<NodeId>,
        caller: &str,
        site: &str,
    ) {
        let name = self.symbols.intern(attr);
        self.pattern_store_name(name);
        let access = self.new_access(AccessKind::Store, attr, None, src, caller, site);
        let rule = self.rule(Rule::Access(access));
        self.attach(graph, base, rule);
    }

    pub(super) fn add_delete(
        &mut self,
        graph: &mut Graph,
        base: NodeId,
        attr: &str,
        caller: &str,
        site: &str,
    ) {
        let access = self.new_access(AccessKind::Delete, attr, None, None, caller, site);
        let rule = self.rule(Rule::Access(access));
        self.attach(graph, base, rule);
    }

    fn pattern_store_name(&mut self, name: Sym) {
        if !self.store_names.insert(name) {
            return;
        }
        if !self.pattern_states.is_empty() {
            not_ported("patterns: a stored name");
        }
    }

    fn pattern_class_store(&mut self, class: ObjId, name: Sym) {
        if !self
            .class_store_names
            .entry(class)
            .or_default()
            .insert(name)
        {
            return;
        }
        if !self.pattern_states.is_empty() {
            not_ported("patterns: a name stored on a class");
        }
    }

    fn named_call(&mut self, graph: &mut Graph, id: AccessId) -> CallId {
        if let Some(call) = self.access(id).named_call {
            return call;
        }
        let access = self.access(id);
        let (kind, attr, caller, site, dst) = (
            access.kind,
            access.attr,
            access.caller,
            access.site,
            access.dst,
        );
        let name = self.attr_constant(graph, attr);
        let key = SiteKey {
            caller,
            site,
            role: Role::Getattr(kind, attr),
            implicit: true,
        };
        let call = self.site_call(graph, key, &[Some(name)], dst, None);
        self.accesses[id.0 as usize].named_call = Some(call);
        call
    }

    fn hook_call(&mut self, graph: &mut Graph, id: AccessId, dst: Option<NodeId>) -> CallId {
        if let Some(&call) = self.access(id).hook_calls.get(&dst) {
            return call;
        }
        let access = self.access(id);
        let (kind, attr, caller, site, src) = (
            access.kind,
            access.attr,
            access.caller,
            access.site,
            access.src,
        );
        let name = self.attr_constant(graph, attr);
        let mut args = vec![Some(name)];
        if kind == AccessKind::Store {
            args.push(src);
        }
        let key = SiteKey {
            caller,
            site,
            role: Role::Hook(kind, attr),
            implicit: true,
        };
        let call = self.site_call(graph, key, &args, dst, None);
        self.accesses[id.0 as usize].hook_calls.insert(dst, call);
        call
    }

    fn accessor_call(&mut self, graph: &mut Graph, id: AccessId, caller: Option<Sym>) -> CallId {
        if let Some(&call) = self.access(id).accessor_calls.get(&caller) {
            return call;
        }
        let access = self.access(id);
        let (kind, attr, own, site, src, dst) = (
            access.kind,
            access.attr,
            access.caller,
            access.site,
            access.src,
            access.dst,
        );
        let args: Vec<Option<NodeId>> = if kind == AccessKind::Store {
            vec![src]
        } else {
            Vec::new()
        };
        let key = SiteKey {
            caller: caller.unwrap_or(own),
            site,
            role: Role::Accessor(kind, attr),
            implicit: true,
        };
        let call = self.site_call(graph, key, &args, dst, None);
        self.accesses[id.0 as usize]
            .accessor_calls
            .insert(caller, call);
        call
    }

    fn attr_constant(&mut self, graph: &mut Graph, attr: Sym) -> NodeId {
        let literal = Literal::Str(self.symbols.text(attr).chars().map(u32::from).collect());
        let named = self.const_object(graph, &literal);
        self.constant(graph, named)
    }

    pub(super) fn apply_access(&mut self, graph: &mut Graph, object: ObjId, id: AccessId) {
        let access = self.access(id);
        let (kind, attr) = (access.kind, access.attr);
        match kind {
            AccessKind::Load => self.load(graph, object, attr, id),
            AccessKind::Store => {
                let src = self.access(id).src;
                self.store(graph, object, attr, src, id);
            }
            AccessKind::Delete => self.delete(graph, object, attr, id),
        }
    }

    fn descriptor(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        receiver: ObjId,
        method: &str,
        hook: Option<Sym>,
        access: AccessId,
    ) -> bool {
        if self.wrapper_kind_is(object, "property") {
            let accessor = self.symbols.intern(self.property_accessor(method));
            let accessor = self.field(graph, object, accessor);
            self.call_accessor(graph, (accessor, access, false, 1), receiver, hook);
            return true;
        }
        let &Object::Instance { class, .. } = self.objects.get(object) else {
            return false;
        };
        if self.access(access).kind == AccessKind::Load {
            let dst = self.access(access).dst.expect("a load has a result");
            if self.descriptors_itself.insert((object, dst)) {
                let itself = self.lookup_name(
                    graph,
                    class,
                    "__get__",
                    None,
                    None,
                    Unless::DescriptorItself,
                );
                let rule = self.rule(Rule::Itself { object, dst });
                self.attach(graph, itself, rule);
            }
        }
        let receiver_class = match self.objects.get(receiver) {
            &Object::Instance { class, .. } => class,
            _ => panic!("a descriptor of an instance"),
        };
        let prefix = if method == "__get__" {
            vec![receiver, receiver_class]
        } else {
            vec![receiver]
        };
        let found = self.lookup_name(graph, class, method, Some(object), None, Unless::Nothing);
        let width = u32::try_from(prefix.len()).expect("a short prefix");
        self.call_accessor(graph, (found, access, true, width), receiver, hook);
        true
    }

    pub(super) fn itself(&mut self, graph: &mut Graph, object: ObjId, dst: NodeId) {
        self.add_object(graph, dst, object);
    }

    pub(super) fn class_attribute(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        class: ObjId,
        load: AccessId,
    ) {
        let dst = self.access(load).dst.expect("a load has a result");
        match self.objects.get(object) {
            &Object::Fallback { method } => {
                let call = self.named_call(graph, load);
                self.call(graph, method, call);
                return;
            }
            Object::Instance { .. } => {}
            _ => {
                self.add_object(graph, dst, object);
                return;
            }
        }
        let &Object::Instance { class: owner, .. } = self.objects.get(object) else {
            panic!("an instance")
        };
        let get = self.python_method(graph, owner, "__get__");
        let rule = self.rule(Rule::Itself { object, dst });
        self.attach(graph, get, rule);
        let access = self.access(load);
        let (attr, caller, site) = (access.attr, access.caller, access.site);
        let owner_node = self.constant(graph, class);
        let key = SiteKey {
            caller,
            site,
            role: Role::ClassGet(attr),
            implicit: true,
        };
        let call = self.site_call(graph, key, &[None, Some(owner_node)], Some(dst), None);
        let found = self.lookup_name(graph, owner, "__get__", Some(object), None, Unless::Nothing);
        let rule = self.rule(Rule::ClassGet { call });
        self.attach(graph, found, rule);
    }

    pub(super) fn class_get(&mut self, graph: &mut Graph, method: ObjId, call: CallId) {
        if let &Object::BoundMethod { function, .. } = self.objects.get(method)
            && self.is_property_method(function)
        {
            return;
        }
        self.call(graph, method, call);
    }

    fn is_property_method(&self, function: ObjId) -> bool {
        self.objects.external(function).is_some_and(|external| {
            matches!(self.objects.get(function), Object::External(_))
                && self
                    .symbols
                    .text(external.name)
                    .starts_with("<builtin>.property.")
        })
    }

    fn call_accessor(
        &mut self,
        graph: &mut Graph,
        entry: AccessorEntry,
        receiver: ObjId,
        hook: Option<Sym>,
    ) {
        let (accessor, access, analysed_only, width) = entry;
        let Some(hook) = hook else {
            let accessors = self.accessors_of(graph, None, accessor, access, analysed_only, width);
            self.accessors_add(graph, accessors, receiver);
            return;
        };
        let entry = (accessor, access, analysed_only, width);
        let &Object::Instance { class, .. } = self.objects.get(receiver) else {
            panic!("an accessor of an instance")
        };
        let hook_text = self.symbols.text(hook).to_string();
        let python_hook = self.python_method(graph, class, &hook_text);
        let found = self.lookup_name(
            graph,
            class,
            &hook_text,
            Some(receiver),
            None,
            Unless::Nothing,
        );
        let mut hooks = self.hooks_of(graph, python_hook, (class, hook, None));
        if !self.accessor_hooks[hooks.0 as usize]
            .receivers
            .contains_key(&entry)
            && (self.is_saturated(graph, python_hook) || self.is_saturated(graph, found))
        {
            hooks = self.hooks_of(graph, python_hook, (class, hook, Some(entry)));
        }
        if self.accessor_hooks[hooks.0 as usize].lookups.insert(found) {
            let rule = self.accessor_hook_rules[&hooks];
            self.attach(graph, found, rule);
        }
        self.hooks_add(graph, hooks, entry, receiver);
    }

    fn hooks_of(
        &mut self,
        graph: &mut Graph,
        python_hook: NodeId,
        key: (ObjId, Sym, Option<AccessorEntry>),
    ) -> HooksId {
        if let Some(&hooks) = self.accessor_hooks_by_key.get(&key) {
            return hooks;
        }
        let hooks = HooksId(u32::try_from(self.accessor_hooks.len()).expect("fewer hooks"));
        self.accessor_hooks.push(AccessorHooks::default());
        self.accessor_hooks_by_key.insert(key, hooks);
        let rule = self.rule(Rule::AccessorHooks(hooks));
        self.accessor_hook_rules.insert(hooks, rule);
        self.attach(graph, python_hook, rule);
        hooks
    }

    fn hooks_add(
        &mut self,
        graph: &mut Graph,
        hooks: HooksId,
        entry: AccessorEntry,
        receiver: ObjId,
    ) {
        let found = &mut self.accessor_hooks[hooks.0 as usize];
        if !found.receivers.contains_key(&entry) {
            found.receivers.insert(entry, Vec::new());
            let result = self.access(entry.1).dst;
            if let Some(result) = result {
                let found = &mut self.accessor_hooks[hooks.0 as usize];
                if found.results_of.insert(result) && found.saturated {
                    let saturated = self.saturated;
                    self.add_object(graph, result, saturated);
                }
            }
        }
        self.accessor_hooks[hooks.0 as usize]
            .receivers
            .get_mut(&entry)
            .expect("an entry")
            .push(receiver);
        let callers: Vec<Option<Sym>> = self.accessor_hooks[hooks.0 as usize]
            .callers
            .iter()
            .copied()
            .collect();
        for caller in callers {
            let (accessor, access, analysed_only, width) = entry;
            let accessors =
                self.accessors_of(graph, caller, accessor, access, analysed_only, width);
            self.accessors_add(graph, accessors, receiver);
        }
    }

    pub(super) fn hooks_apply(&mut self, graph: &mut Graph, hooks: HooksId, hook: ObjId) {
        let function = match self.objects.get(hook) {
            &Object::BoundMethod { function, .. } => function,
            _ => hook,
        };
        let caller = match self.objects.get(function) {
            Object::Function(function) => Some(function.name),
            _ => None,
        };
        if !self.accessor_hooks[hooks.0 as usize].callers.insert(caller) {
            return;
        }
        let entries: Vec<(AccessorEntry, Vec<ObjId>)> = self.accessor_hooks[hooks.0 as usize]
            .receivers
            .iter()
            .map(|(entry, receivers)| (*entry, receivers.clone()))
            .collect();
        for ((accessor, access, analysed_only, width), receivers) in entries {
            let accessors =
                self.accessors_of(graph, caller, accessor, access, analysed_only, width);
            for receiver in receivers {
                self.accessors_add(graph, accessors, receiver);
            }
        }
    }

    pub(super) fn hooks_saturate(&mut self, hooks: HooksId) {
        self.accessor_hooks[hooks.0 as usize].saturated = true;
    }

    pub(super) fn hooks_results(&self, hooks: HooksId) -> Vec<NodeId> {
        self.accessor_hooks[hooks.0 as usize]
            .results_of
            .iter()
            .copied()
            .collect()
    }

    fn accessors_of(
        &mut self,
        graph: &mut Graph,
        caller: Option<Sym>,
        accessor: NodeId,
        access: AccessId,
        analysed_only: bool,
        width: u32,
    ) -> AccessorsId {
        let call = self.accessor_call(graph, access, caller);
        let key = (accessor, call, analysed_only, width);
        if let Some(&accessors) = self.accessor_receivers.get(&key) {
            return accessors;
        }
        let accessors = AccessorsId(u32::try_from(self.accessors.len()).expect("fewer accessors"));
        self.accessors.push(Accessors {
            call,
            analysed_only,
            width,
            receivers: Vec::new(),
            methods: Vec::new(),
        });
        self.accessor_receivers.insert(key, accessors);
        let rule = self.rule(Rule::Accessors {
            id: accessors,
            analysed_only,
        });
        self.attach(graph, accessor, rule);
        accessors
    }

    pub(super) fn accessors_results(&self, accessors: AccessorsId) -> Vec<NodeId> {
        let call = self.accessors[accessors.0 as usize].call;
        self.calls[call.index()].dst.into_iter().collect()
    }

    fn accessor_prefix(&self, receiver: ObjId, width: u32) -> Vec<ObjId> {
        if width == 2 {
            let &Object::Instance { class, .. } = self.objects.get(receiver) else {
                panic!("a prefix of two has an instance")
            };
            vec![receiver, class]
        } else {
            vec![receiver]
        }
    }

    pub(super) fn accessors_apply(
        &mut self,
        graph: &mut Graph,
        accessors: AccessorsId,
        method: ObjId,
    ) {
        let found = &self.accessors[accessors.0 as usize];
        if found.analysed_only
            && self.objects.get(method).kind().mask()
                & crate::engine::objects::kinds_mask(ANALYSED_METHODS)
                == 0
        {
            return;
        }
        let (call, width) = (found.call, found.width);
        self.accessors[accessors.0 as usize].methods.push(method);
        let receivers = self.accessors[accessors.0 as usize].receivers.clone();
        for receiver in receivers {
            let prefix = self.accessor_prefix(receiver, width);
            self.call_bound(graph, method, prefix, call);
        }
    }

    fn accessors_add(&mut self, graph: &mut Graph, accessors: AccessorsId, receiver: ObjId) {
        let found = &mut self.accessors[accessors.0 as usize];
        found.receivers.push(receiver);
        let (call, width) = (found.call, found.width);
        let methods = found.methods.clone();
        let prefix = self.accessor_prefix(receiver, width);
        for method in methods {
            self.call_bound(graph, method, prefix.clone(), call);
        }
    }

    pub(super) fn module_getattr(
        &mut self,
        graph: &mut Graph,
        function: ObjId,
        module: ObjId,
        attr: Sym,
        load: AccessId,
    ) {
        let Object::Module(found) = self.objects.get(module) else {
            panic!("a module")
        };
        if found.defines.contains(&attr) {
            return;
        }
        let name = self.attr_constant(graph, attr);
        let access = self.access(load);
        let (caller, site, dst) = (access.caller, access.site, access.dst);
        let key = SiteKey {
            caller,
            site,
            role: Role::ModuleGetattr(attr),
            implicit: true,
        };
        let call = self.site_call(graph, key, &[Some(name)], dst, None);
        self.call(graph, function, call);
    }

    fn load(&mut self, graph: &mut Graph, object: ObjId, attr: Sym, load: AccessId) {
        let dst = self.access(load).dst.expect("a load has a result");
        match self.objects.get(object) {
            Object::Module(_) => {
                let field = self.field(graph, object, attr);
                self.add_edge(graph, field, dst);
                let getattr = self.symbols.intern("__getattr__");
                let getattr = self.field(graph, object, getattr);
                let rule = self.rule(Rule::ModuleGetattr {
                    module: object,
                    attr,
                    load,
                });
                self.attach(graph, getattr, rule);
            }
            Object::Function(_) => {
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
                let rule = self.rule(Rule::ClassAttribute {
                    class: object,
                    load,
                });
                self.attach(graph, found, rule);
                if self.symbols.text(attr) == "__dict__" {
                    not_ported("reflection: the namespace of a class");
                }
            }
            &Object::Instance { class, .. } => {
                self.read_field(graph, object, attr, dst);
                let key = LookupKey {
                    attr: LookupAttr::Name(attr),
                    receiver: Some(object),
                    after: None,
                    unless: Unless::Explicit,
                };
                self.later(graph, class, key, WaitingRule::DeliverLoad(load));
                let hook = self.symbols.intern("__getattribute__");
                let call = self.hook_call(graph, load, Some(dst));
                let key = LookupKey {
                    attr: LookupAttr::Name(hook),
                    receiver: Some(object),
                    after: None,
                    unless: Unless::Nothing,
                };
                self.later(graph, class, key, WaitingRule::CallHook { hook, call });
            }
            Object::External(_) | Object::UnknownExternal(_) => {
                self.external_attribute(graph, object, attr, dst)
            }
            &Object::BoundMethod { function, .. } => {
                let field = self.field(graph, function, attr);
                self.add_edge(graph, field, dst);
            }
            Object::Wrapper { .. }
            | Object::Container(_)
            | Object::Generator { .. }
            | Object::Const { .. } => {
                let type_name = self.object_type_name(object);
                self.load_builtin_attribute(graph, object, &type_name, attr, dst);
            }
            Object::BuiltinMethod { .. } => {}
            Object::Coroutine { .. } => {
                let name = format!("types.CoroutineType.{}", self.symbols.text(attr));
                let external = self.external(graph, &name, 2, false);
                self.add_object(graph, dst, external);
            }
            Object::Saturated | Object::Fallback { .. } => {}
        }
    }

    fn store(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        attr: Sym,
        src: Option<NodeId>,
        store: AccessId,
    ) {
        let src = src.expect("a store has a value");
        let kind = self.objects.get(object).kind();
        if matches!(kind, Kind::Module | Kind::Function | Kind::Class) {
            let field = self.field(graph, object, attr);
            self.add_edge(graph, src, field);
        }
        if matches!(kind, Kind::Class | Kind::Instance) {
            self.stored_name(graph, object, attr);
        }
        if kind == Kind::Class {
            self.pattern_class_store(object, attr);
            self.class_attribute_stored(graph, object, attr);
        }
        if let &Object::Instance { class, .. } = self.objects.get(object) {
            self.store_field(graph, object, class, attr, src);
            let key = LookupKey {
                attr: LookupAttr::Name(attr),
                receiver: Some(object),
                after: None,
                unless: Unless::Nothing,
            };
            self.later(graph, class, key, WaitingRule::FoundStore(store));
            let hook = self.symbols.intern("__setattr__");
            let call = self.hook_call(graph, store, None);
            let key = LookupKey {
                attr: LookupAttr::Name(hook),
                receiver: Some(object),
                after: None,
                unless: Unless::Nothing,
            };
            self.later(graph, class, key, WaitingRule::CallHook { hook, call });
        }
    }

    fn stored_name(&mut self, graph: &mut Graph, object: ObjId, name: Sym) {
        let names = self.namespace_names(graph, object);
        let literal = Literal::Str(self.symbols.text(name).chars().map(u32::from).collect());
        let named = self.const_object(graph, &literal);
        self.add_object(graph, names, named);
    }

    fn namespace_names(&mut self, graph: &mut Graph, object: ObjId) -> NodeId {
        if let Some(&node) = self.namespace_nodes.get(&(object, Namespace::Names)) {
            return node;
        }
        let node = self.node(graph, None);
        self.namespace_nodes
            .insert((object, Namespace::Names), node);
        if let Object::Class(class) = self.objects.get(object) {
            let mut names: Vec<String> = class
                .defines
                .iter()
                .map(|&name| self.symbols.text(name).to_string())
                .collect();
            names.sort_unstable();
            for name in names {
                let literal = Literal::Str(name.chars().map(u32::from).collect());
                let named = self.const_object(graph, &literal);
                self.add_object(graph, node, named);
            }
        }
        node
    }

    fn store_field(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        class: ObjId,
        attr: Sym,
        src: NodeId,
    ) {
        let field = self.field(graph, object, attr);
        let text = self.symbols.text(attr).to_string();
        let written = self.lookup_name(graph, class, &text, None, None, Unless::DescriptorDecides);
        self.write_field_once(graph, written, src, field);
    }

    fn write_field_once(&mut self, graph: &mut Graph, written: NodeId, src: NodeId, field: NodeId) {
        let writes = match self.field_writes.get(&written) {
            Some(&writes) => writes,
            None => {
                let writes = WritesId(u32::try_from(self.writes.len()).expect("fewer writes"));
                self.writes.push(FieldWrites::default());
                self.field_writes.insert(written, writes);
                let rule = self.rule(Rule::FieldWrites(writes));
                self.attach(graph, written, rule);
                writes
            }
        };
        let found = &mut self.writes[writes.0 as usize];
        if !found.writes.insert((src, field)) {
            return;
        }
        if found.saturated {
            let saturated = self.saturated;
            self.add_object(graph, field, saturated);
        } else if found.written {
            self.add_edge(graph, src, field);
        }
    }

    pub(super) fn writes_apply(&mut self, graph: &mut Graph, writes: WritesId) {
        let found = &mut self.writes[writes.0 as usize];
        if found.written {
            return;
        }
        found.written = true;
        let pairs: Vec<(NodeId, NodeId)> = found.writes.iter().copied().collect();
        for (src, field) in pairs {
            self.add_edge(graph, src, field);
        }
    }

    pub(super) fn writes_saturate(&mut self, writes: WritesId) {
        self.writes[writes.0 as usize].saturated = true;
    }

    pub(super) fn writes_results(&self, writes: WritesId) -> Vec<NodeId> {
        self.writes[writes.0 as usize]
            .writes
            .iter()
            .map(|&(_, field)| field)
            .collect()
    }

    pub(super) fn store_past(
        &mut self,
        graph: &mut Graph,
        value: ObjId,
        src: NodeId,
        field: NodeId,
    ) {
        if self.wrapper_kind_is(value, "property") {
            return;
        }
        if let &Object::Instance { class, .. } = self.objects.get(value) {
            let written =
                self.lookup_name(graph, class, "__set__", None, None, Unless::DataDescriptor);
            self.write_field_once(graph, written, src, field);
            return;
        }
        self.add_edge(graph, src, field);
    }

    pub(super) fn deliver_load(&mut self, graph: &mut Graph, object: ObjId, load: AccessId) {
        let &Object::Instance { class, .. } = self.objects.get(object) else {
            panic!("a delivery to an instance")
        };
        let key = LookupKey {
            attr: LookupAttr::Name(self.access(load).attr),
            receiver: Some(object),
            after: None,
            unless: Unless::Explicit,
        };
        let found = self.lookup(graph, class, key);
        let hook = self.symbols.intern("__getattribute__");
        self.deliver_through(graph, found, object, load, Some(hook));
    }

    fn deliver_through(
        &mut self,
        graph: &mut Graph,
        found: NodeId,
        receiver: ObjId,
        load: AccessId,
        hook: Option<Sym>,
    ) {
        let deliveries = match self.deliveries_by_lookup.get(&found) {
            Some(&deliveries) => deliveries,
            None => {
                let deliveries =
                    DeliveriesId(u32::try_from(self.deliveries.len()).expect("fewer deliveries"));
                self.deliveries.push(Deliveries {
                    receiver,
                    hook,
                    loads: Vec::new(),
                });
                self.deliveries_by_lookup.insert(found, deliveries);
                let rule = self.rule(Rule::Deliveries(deliveries));
                self.attach(graph, found, rule);
                deliveries
            }
        };
        let found_deliveries = &mut self.deliveries[deliveries.0 as usize];
        assert_eq!(
            found_deliveries.receiver, receiver,
            "one receiver per lookup"
        );
        assert_eq!(found_deliveries.hook, hook, "one hook per lookup");
        found_deliveries.loads.push(load);
        let rule = self.rule(Rule::Deliver {
            receiver,
            load,
            hook,
        });
        self.apply_now(graph, found, rule);
    }

    pub(super) fn deliveries_apply(
        &mut self,
        graph: &mut Graph,
        deliveries: DeliveriesId,
        objects: &[ObjId],
    ) {
        let found = &self.deliveries[deliveries.0 as usize];
        let (receiver, hook) = (found.receiver, found.hook);
        let loads = found.loads.clone();
        for &object in objects {
            for &load in &loads {
                self.deliver(graph, object, receiver, load, hook);
            }
        }
    }

    pub(super) fn deliveries_receiver(&self, deliveries: DeliveriesId) -> ObjId {
        self.deliveries[deliveries.0 as usize].receiver
    }

    pub(super) fn deliveries_results(&self, deliveries: DeliveriesId) -> Vec<NodeId> {
        self.deliveries[deliveries.0 as usize]
            .loads
            .iter()
            .filter_map(|&load| self.access_result(load))
            .collect()
    }

    pub(super) fn found_store(&mut self, graph: &mut Graph, object: ObjId, store: AccessId) {
        let &Object::Instance { class, .. } = self.objects.get(object) else {
            panic!("a store on an instance")
        };
        let access = self.access(store);
        let (attr, src) = (access.attr, access.src.expect("a store has a value"));
        let key = LookupKey {
            attr: LookupAttr::Name(attr),
            receiver: Some(object),
            after: None,
            unless: Unless::Nothing,
        };
        let found = self.lookup(graph, class, key);
        let field = self.field(graph, object, attr);
        let rule = self.rule(Rule::StorePast { src, field });
        self.attach(graph, found, rule);
        let rule = self.rule(Rule::DeliverStore { object, store });
        self.attach(graph, found, rule);
    }

    pub(super) fn deliver(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        receiver: ObjId,
        load: AccessId,
        hook: Option<Sym>,
    ) {
        if let &Object::Fallback { method } = self.objects.get(object) {
            let call = self.named_call(graph, load);
            self.call(graph, method, call);
        } else if !self.descriptor(graph, object, receiver, "__get__", hook, load) {
            let dst = self.access(load).dst.expect("a load has a result");
            self.add_object(graph, dst, object);
        }
    }

    fn delete(&mut self, graph: &mut Graph, object: ObjId, attr: Sym, delete: AccessId) {
        let &Object::Instance { class, .. } = self.objects.get(object) else {
            return;
        };
        let key = LookupKey {
            attr: LookupAttr::Name(attr),
            receiver: Some(object),
            after: None,
            unless: Unless::Nothing,
        };
        let found = self.lookup(graph, class, key);
        let rule = self.rule(Rule::DeliverDelete { object, delete });
        self.attach(graph, found, rule);
        let hook = self.symbols.intern("__delattr__");
        let call = self.hook_call(graph, delete, None);
        self.call_hook(graph, object, hook, call);
    }

    pub(super) fn call_hook(
        &mut self,
        graph: &mut Graph,
        instance: ObjId,
        hook: Sym,
        call: CallId,
    ) {
        let &Object::Instance { class, .. } = self.objects.get(instance) else {
            panic!("a hook of an instance")
        };
        let key = LookupKey {
            attr: LookupAttr::Name(hook),
            receiver: Some(instance),
            after: None,
            unless: Unless::Nothing,
        };
        let found = self.lookup(graph, class, key);
        let hooks = match self.hook_calls_by_lookup.get(&found) {
            Some(&hooks) => hooks,
            None => {
                let hooks = HookCallsId(u32::try_from(self.hook_calls.len()).expect("fewer hooks"));
                self.hook_calls.push(HookCalls {
                    found,
                    calls: Vec::new(),
                    hooks: Vec::new(),
                    saw_opaque: false,
                });
                self.hook_calls_by_lookup.insert(found, hooks);
                let rule = self.rule(Rule::HookCalls(hooks));
                self.attach(graph, found, rule);
                hooks
            }
        };
        self.hook_calls_add(graph, hooks, call);
    }

    fn hook_calls_add(&mut self, graph: &mut Graph, hooks: HookCallsId, call: CallId) {
        self.hook_calls[hooks.0 as usize].calls.push(call);
        let found = self.hook_calls[hooks.0 as usize].found;
        let dst = self.calls[call.index()]
            .dst
            .expect("a hook call has a result");
        if self.is_saturated(graph, found) {
            let saturated = self.saturated;
            self.add_object(graph, dst, saturated);
            return;
        }
        let all = self.hook_calls[hooks.0 as usize].hooks.clone();
        let opacity = graph.opacity_enabled();
        let kept: Vec<ObjId> = all
            .iter()
            .copied()
            .filter(|&hook| !(opacity && self.opaque(hook)))
            .collect();
        if self.hook_calls[hooks.0 as usize].saw_opaque || kept.len() < all.len() {
            let saturated = self.saturated;
            self.add_object(graph, dst, saturated);
        }
        for hook in kept {
            self.call(graph, hook, call);
        }
    }

    pub(super) fn hook_calls_apply(&mut self, graph: &mut Graph, hooks: HookCallsId, hook: ObjId) {
        if self.objects.is_external(hook) {
            return;
        }
        self.hook_calls[hooks.0 as usize].hooks.push(hook);
        let calls = self.hook_calls[hooks.0 as usize].calls.clone();
        for call in calls {
            self.call(graph, hook, call);
        }
    }

    pub(super) fn hook_calls_saturate(&mut self, hooks: HookCallsId) {
        self.hook_calls[hooks.0 as usize].saw_opaque = true;
    }

    pub(super) fn hook_calls_results(&self, hooks: HookCallsId) -> Vec<NodeId> {
        self.hook_calls[hooks.0 as usize]
            .calls
            .iter()
            .filter_map(|&call| self.calls[call.index()].dst)
            .collect()
    }

    pub(super) fn deliver_store(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        receiver: ObjId,
        store: AccessId,
    ) {
        let hook = self.symbols.intern("__setattr__");
        self.descriptor(graph, object, receiver, "__set__", Some(hook), store);
    }

    pub(super) fn deliver_delete(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        receiver: ObjId,
        delete: AccessId,
    ) {
        let hook = self.symbols.intern("__delattr__");
        self.descriptor(graph, object, receiver, "__delete__", Some(hook), delete);
    }
}
