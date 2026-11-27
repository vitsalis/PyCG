use num_bigint::BigInt;
use pycg_solver::{NodeId, ObjId};

use pycg_stubs::DefinitionKind;

use crate::engine::outside_calls::TypedResult;
use rustc_hash::FxHashSet;

use crate::builder::calls::{Call as BuilderCall, ClassStatement as BuilderClassStatement};
use crate::engine::attributes::AccessKind;
use crate::engine::containers::{ContainerOrigin, IterationRoleId};
use crate::engine::hierarchy::{LookupAttr, LookupKey, Unless};
use crate::engine::objects::{Literal, Object};
use crate::engine::symbols::Sym;
use crate::engine::trace::Trace;
use crate::engine::{Graph, MethodKind, OrderedSet, Rule, RuleId, State, WaitingRule, not_ported};
use crate::models::RETURNED_DECORATOR;

pub const RECEIVERS_PER_CALL_MAX: usize = 3;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct CallId(u32);

impl CallId {
    pub fn index(self) -> usize {
        self.0 as usize
    }
}

pub type Receivers = Vec<ObjId>;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct GroupId(pub(super) u32);

#[derive(Clone, Debug)]
pub enum Prefix {
    Receivers(Receivers),
    Group(GroupId),
}

pub struct BoundGroup {
    pub callee: ObjId,
    pub call: CallId,
    pub unknown: bool,
    receivers: OrderedSet<Receivers>,
    observers: Vec<(CallId, Vec<TypedResult>)>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct ReturnedId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct SharedId(u32);

impl SharedId {
    fn index(self) -> usize {
        self.0 as usize
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum SharedRule {
    PythonNew { class: ObjId },
    New { class: ObjId },
    OfClass,
    PythonInstance,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum SharedItem {
    Call(CallId),
    Returned(ReturnedId),
}

impl SharedRule {
    fn gives_dst(self) -> bool {
        !matches!(self, SharedRule::OfClass)
    }

    pub(crate) fn captured(self) -> Vec<ObjId> {
        match self {
            SharedRule::PythonNew { class } | SharedRule::New { class } => vec![class],
            SharedRule::OfClass | SharedRule::PythonInstance => Vec::new(),
        }
    }

    pub(crate) fn each(self, item: SharedItem) -> Rule {
        match (self, item) {
            (SharedRule::PythonNew { class }, SharedItem::Call(call)) => {
                Rule::PythonNew { class, call }
            }
            (SharedRule::New { class }, SharedItem::Call(call)) => Rule::New { class, call },
            (SharedRule::OfClass, SharedItem::Returned(returned)) => {
                Rule::ReturnedOfClass(returned)
            }
            (SharedRule::PythonInstance, SharedItem::Call(call)) => Rule::PythonInstance { call },
            _ => unreachable!("a shared rule and an item of its kind"),
        }
    }
}

pub struct Shared {
    rule: SharedRule,
    items: Vec<SharedItem>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Role {
    SetName(Sym),
    Getattr(AccessKind, Sym),
    Hook(AccessKind, Sym),
    Accessor(AccessKind, Sym),
    ClassGet(Sym),
    ModuleGetattr(Sym),
    Protocol(Sym),
    Property(AccessKind, Sym),
    NamedLoad,
    Hash,
    HashEq,
    Subscript(Sym),
    SubscriptFactory,
    Iterate(IterationRoleId),
    Index(IterationRoleId),
    Callable(IterationRoleId),
    Map(u32, bool),
    Filter,
    Reversed,
    ReversedLen,
    ReversedItem,
    Operator(Sym, bool),
    Compare(Sym),
    Truth,
    Convert(Sym),
    Format,
    Await,
    Enter,
    Exit,
    Raise,
    Special(Sym),
    TypeMetaclass,
    CallBack,
    Key,
    SequenceKey,
    LibraryKey(Sym),
    MergeKey(Sym),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct SiteKey {
    pub caller: Sym,
    pub site: Sym,
    pub role: Role,
    pub implicit: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Origin {
    Call(CallId),
    InitSubclass(Sym),
    ClassStatement(Sym),
    Prepare(Sym),
    Site(SiteKey),
}

pub struct ClassStatement {
    name: Sym,
    bases: Vec<Option<NodeId>>,
    namespace: Vec<(Sym, NodeId)>,
    keywords: Vec<(Sym, Option<NodeId>)>,
    double_star: Vec<Option<NodeId>>,
    caller: Sym,
    site: Sym,
}

pub enum StatementCall {
    Waiting(ClassStatement),
    Made { call: CallId, prepare: CallId },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Construct {
    Call,
    Decorator,
    Named(&'static str),
    Role(Role),
}

pub struct Returned {
    pub call: CallId,
    pub class: ObjId,
    returned: FxHashSet<ObjId>,
    sees: bool,
    pub dst: Option<NodeId>,
    dsts: Vec<NodeId>,
    held: Vec<ObjId>,
    another: bool,
}

#[derive(Clone)]
pub struct Call {
    pub caller: Sym,
    pub args: Vec<Option<NodeId>>,
    pub keywords: Vec<(Sym, Option<NodeId>)>,
    pub dst: Option<NodeId>,
    pub site: Sym,
    pub origin: Origin,
    pub star: Vec<(Option<NodeId>, bool)>,
    pub double_star: Vec<Option<NodeId>>,
    pub implicit: bool,
    pub decorator: bool,
    pub applies: bool,
    pub rule: RuleId,
}

impl<T: Trace> State<T> {
    pub(super) fn new_call(&mut self, mut call: Call, origin: Option<Origin>) -> CallId {
        let id = CallId(u32::try_from(self.calls.len()).expect("fewer than 2^32 calls"));
        call.origin = origin.unwrap_or(Origin::Call(id));
        self.calls.push(call);
        self.calls[id.index()].rule = self.rule(Rule::Call(id));
        id
    }

    pub(super) fn add_call(&mut self, graph: &mut Graph, new: &BuilderCall<'_>) {
        let caller = self.symbols.intern(new.caller);
        let site = self.symbols.intern(new.site);
        if !new.decorator {
            self.call_expressions.push((caller, site, new.callee));
        }
        let Some(callee) = new.callee else {
            return;
        };
        let keywords = new
            .keywords
            .iter()
            .map(|(name, value)| (self.symbols.intern(name), *value))
            .collect();
        let call = Call {
            caller,
            args: new.args.to_vec(),
            keywords,
            dst: new.dst,
            site,
            origin: Origin::Call(CallId(0)),
            star: new.star.to_vec(),
            double_star: new.double_star.to_vec(),
            implicit: false,
            decorator: new.decorator,
            applies: new.applies,
            rule: RuleId::PLACEHOLDER,
        };
        let call = self.new_call(call, None);
        let rule = self.calls[call.index()].rule;
        self.attach(graph, callee, rule);
    }

    pub(super) fn call(&mut self, graph: &mut Graph, object: ObjId, call: CallId) {
        if let Some(&group) = self.groups.get(&call) {
            assert_eq!(
                self.group_records[group.0 as usize].callee, object,
                "a group calls its callee"
            );
        }
        match self.objects.get(object) {
            Object::Function(_) => {
                if !self.returns_argument(graph, object, call) {
                    self.call_function(graph, object, call, None);
                }
            }
            Object::UnknownExternal(_) => self.outside_result(graph, call),
            &Object::ReturnsArgument { name, analysed } => {
                self.model_edge(name, analysed, call);
                self.return_argument(graph, &RETURNED_DECORATOR, name, analysed, call);
            }
            &Object::BoundMethod { receiver, function } => {
                self.call_bound(graph, function, vec![receiver], call);
            }
            Object::Class(_) => self.instantiate(graph, object, call),
            Object::Instance { .. } => {
                let dst = self.calls[call.index()].dst;
                self.call_dunder(graph, object, "__call__", call, dst, Unless::Nothing);
            }
            Object::External(_) => self.call_external(graph, object, call),
            &Object::Wrapper { kind, .. } => {
                if self.symbols.text(kind) == "staticmethod" {
                    let name = self.symbols.intern("__func__");
                    let func = self.field(graph, object, name);
                    let callee = self.callee(graph, call);
                    self.add_edge(graph, func, callee);
                }
            }
            Object::BuiltinMethod { .. } => self.call_builtin_method(graph, object, call),
            Object::Typed { .. } => self.call_typed(graph, object, call),
            Object::Closure { .. } => self.call_closure(graph, object, call),
            Object::Super { .. } => {}
            Object::Saturated
            | Object::Module(_)
            | Object::Fallback { .. }
            | Object::Const { .. }
            | Object::Container(_)
            | Object::Generator { .. }
            | Object::Coroutine { .. }
            | Object::Pattern { .. } => {}
        }
    }

    pub(super) fn outside_result(&mut self, graph: &mut Graph, call: CallId) {
        let Call {
            dst,
            decorator,
            ref args,
            ..
        } = self.calls[call.index()];
        let Some(dst) = dst else {
            return;
        };
        let last = args.last().copied();
        let unknown = self.unknown_external;
        self.add_object(graph, dst, unknown);
        if decorator && let Some(Some(decorated)) = last {
            self.add_edge(graph, decorated, dst);
        }
    }

    pub(super) fn call_bound(
        &mut self,
        graph: &mut Graph,
        callee: ObjId,
        receivers: Receivers,
        call: CallId,
    ) {
        assert!(
            !self.groups.contains_key(&call),
            "a group call is not bound again"
        );
        let (base, prefix) = self.prefix_receivers(call);
        let mut receivers = receivers;
        receivers.extend(prefix);
        receivers.truncate(RECEIVERS_PER_CALL_MAX);
        if matches!(self.objects.get(callee), Object::Function(_)) {
            let rest = self.prefixed_call(graph, base, receivers[1..].to_vec());
            self.call_function(graph, callee, rest, Some(receivers[0]));
            return;
        }
        if self.bound_in_group(callee) {
            let group = self.bound_group(graph, base, callee, &receivers);
            self.group_add(graph, group, receivers);
        } else {
            let prefixed = self.prefixed_call(graph, base, receivers);
            self.call(graph, callee, prefixed);
        }
    }

    pub(super) fn prefix_receivers(&self, call: CallId) -> (CallId, Receivers) {
        match self.prefixes.get(&call) {
            None => (call, Vec::new()),
            Some((base, Prefix::Receivers(receivers))) => (*base, receivers.clone()),
            Some((_, Prefix::Group(_))) => panic!("the call of a group has no receivers"),
        }
    }

    fn bound_group(
        &mut self,
        graph: &mut Graph,
        base: CallId,
        callee: ObjId,
        receivers: &[ObjId],
    ) -> GroupId {
        let unknown = self.unknown_class(receivers[0]);
        let key = (base, callee, receivers.len(), unknown);
        let groups = self.bound_groups.get(&key).cloned().unwrap_or_default();
        for &group in &groups {
            if self.group_records[group.0 as usize]
                .receivers
                .contains(receivers)
            {
                return group;
            }
        }
        if let Some(&last) = groups.last() {
            let cap = graph.cap();
            let held = self.group_records[last.0 as usize].receivers.len();
            if cap.is_none_or(|cap| held < cap as usize) {
                return last;
            }
        }
        let mut args: Vec<Option<NodeId>> = receivers
            .iter()
            .map(|_| Some(self.node(graph, None)))
            .collect();
        let template = self.calls[base.index()].clone();
        args.extend(template.args.iter().copied());
        let origin = template.origin;
        let call = self.new_call(Call { args, ..template }, Some(origin));
        let group = GroupId(u32::try_from(self.group_records.len()).expect("fewer groups"));
        self.group_records.push(BoundGroup {
            callee,
            call,
            unknown,
            receivers: OrderedSet::default(),
            observers: Vec::new(),
        });
        self.bound_groups.entry(key).or_default().push(group);
        self.groups.insert(call, group);
        self.prefixes.insert(call, (base, Prefix::Group(group)));
        self.call(graph, callee, call);
        group
    }

    fn group_add(&mut self, graph: &mut Graph, group: GroupId, receivers: Receivers) {
        if !self.group_records[group.0 as usize]
            .receivers
            .insert(receivers.clone())
        {
            return;
        }
        let call = self.group_records[group.0 as usize].call;
        let nodes = self.calls[call.index()].args.clone();
        for (&receiver, node) in receivers.iter().zip(nodes) {
            let constant = self.constant(graph, receiver);
            self.add_edge(graph, constant, node.expect("a receiver node"));
        }
        let observers = self.group_records[group.0 as usize].observers.clone();
        for (call, typed) in observers {
            self.add_results_of(graph, call, &typed, &receivers);
        }
    }

    pub(super) fn group_observe(&mut self, group: GroupId, call: CallId, typed: Vec<TypedResult>) {
        let found = &mut self.group_records[group.0 as usize];
        assert!(
            found.receivers.is_empty(),
            "a group is observed before it has receivers"
        );
        found.observers.push((call, typed));
    }

    fn prefixed_call(&mut self, graph: &mut Graph, base: CallId, receivers: Receivers) -> CallId {
        if receivers.is_empty() {
            return base;
        }
        let key = (base, receivers);
        if let Some(&call) = self.receiver_calls.get(&key) {
            return call;
        }
        let (base, receivers) = key;
        let mut args: Vec<Option<NodeId>> = receivers
            .iter()
            .map(|&receiver| Some(self.constant(graph, receiver)))
            .collect();
        let template = self.calls[base.index()].clone();
        args.extend(template.args.iter().copied());
        let call = self.new_call(
            Call { args, ..template },
            Some(self.calls[base.index()].origin),
        );
        self.receiver_calls.insert((base, receivers.clone()), call);
        self.prefixes
            .insert(call, (base, Prefix::Receivers(receivers)));
        call
    }

    fn call_function(
        &mut self,
        graph: &mut Graph,
        function: ObjId,
        call: CallId,
        receiver: Option<ObjId>,
    ) {
        if !self.may_bind(function, call, receiver) {
            return;
        }
        let name = self.objects.function(function).name;
        self.add_call_edge(call, name);
        if self.calls[call.index()].caller != name {
            self.called.insert(function);
        }
        self.function_result(graph, function, call, receiver);
    }

    fn function_result(
        &mut self,
        graph: &mut Graph,
        function: ObjId,
        call: CallId,
        receiver: Option<ObjId>,
    ) {
        self.bind_arguments(graph, function, call, receiver);
        let Some(dst) = self.calls[call.index()].dst else {
            return;
        };
        let made = self.objects.function(function);
        if made.yield_node.is_some() {
            let generator = self.generator(graph, function);
            self.add_object(graph, dst, generator);
        } else if made.is_async {
            let coroutine = self.coroutine(graph, function);
            self.add_object(graph, dst, coroutine);
        } else {
            let returned = made.return_node.expect("an analysed function returns");
            self.add_edge(graph, returned, dst);
        }
    }

    fn generator(&mut self, graph: &mut Graph, function: ObjId) -> ObjId {
        if let Some(&generator) = self.generators.get(&function) {
            return generator;
        }
        let generator = self.new_object(
            graph,
            Object::Generator {
                function,
                exact: true,
            },
        );
        self.generators.insert(function, generator);
        generator
    }

    fn coroutine(&mut self, graph: &mut Graph, function: ObjId) -> ObjId {
        if let Some(&coroutine) = self.coroutines.get(&function) {
            return coroutine;
        }
        let coroutine = self.new_object(
            graph,
            Object::Coroutine {
                function,
                exact: true,
            },
        );
        self.coroutines.insert(function, coroutine);
        coroutine
    }

    fn may_bind(&self, function: ObjId, call: CallId, receiver: Option<ObjId>) -> bool {
        let made = self.objects.function(function);
        let details = &self.calls[call.index()];
        if !details.star.is_empty() || !details.double_star.is_empty() || made.decorated {
            return true;
        }
        let base = self.prefixes.get(&call).map_or(call, |(base, _)| *base);
        let root = self.roots.get(&base).copied().unwrap_or(base);
        if self.calls[root.index()].implicit {
            return true;
        }
        let given = details.args.len() + usize::from(receiver.is_some());
        let keywords: Vec<&str> = details
            .keywords
            .iter()
            .map(|&(name, _)| self.symbols.text(name))
            .collect();
        let optional: Vec<&str> = made
            .optional
            .iter()
            .map(|&name| self.symbols.text(name))
            .collect();
        made.signature.binds(given, &keywords, &optional)
    }

    pub(super) fn add_call_edge(&mut self, call: CallId, callee: Sym) {
        let details = &self.calls[call.index()];
        let construct = match details.origin {
            Origin::Call(origin) if self.calls[origin.index()].decorator => Construct::Decorator,
            Origin::Call(_) => Construct::Call,
            Origin::InitSubclass(_) => Construct::Named("init_subclass"),
            Origin::ClassStatement(_) => Construct::Named("class statement"),
            Origin::Prepare(_) => Construct::Named("prepare"),
            Origin::Site(key) => Construct::Role(key.role),
        };
        let key = (details.caller, details.site, construct);
        self.site_edges.entry(key).or_default().insert(callee);
    }

    pub(super) fn callee(&mut self, graph: &mut Graph, call: CallId) -> NodeId {
        if let Some(&node) = self.callees.get(&call) {
            return node;
        }
        let node = self.node(graph, None);
        let rule = self.calls[call.index()].rule;
        self.attach(graph, node, rule);
        self.callees.insert(call, node);
        node
    }

    pub(super) fn instance(&mut self, graph: &mut Graph, class: ObjId, call: CallId) -> ObjId {
        let origin = self.calls[call.index()].origin;
        if let Some(&instance) = self.instances.get(&(class, Some(origin))) {
            return instance;
        }
        let site = self.calls[call.index()].site;
        let instance = self.new_object(graph, Object::Instance { class, site });
        self.instances.insert((class, Some(origin)), instance);
        let instances = self.objects.class(class).instances;
        self.add_object(graph, instances, instance);
        instance
    }

    pub(super) fn abstract_instance(&mut self, graph: &mut Graph, class: ObjId) -> ObjId {
        if let Some(&instance) = self.instances.get(&(class, None)) {
            return instance;
        }
        let site = self.symbols.intern("<object>");
        let instance = self.new_object(graph, Object::Instance { class, site });
        self.instances.insert((class, None), instance);
        let instances = self.objects.class(class).instances;
        self.add_object(graph, instances, instance);
        instance
    }

    pub(super) fn bound_method(
        &mut self,
        graph: &mut Graph,
        receiver: ObjId,
        function: ObjId,
    ) -> ObjId {
        if let Some(&method) = self.bound_methods.get(&(receiver, function)) {
            return method;
        }
        let method = self.new_object(graph, Object::BoundMethod { receiver, function });
        self.bound_methods.insert((receiver, function), method);
        method
    }

    pub(super) fn fallback_object(&mut self, graph: &mut Graph, method: ObjId) -> ObjId {
        if let Some(&fallback) = self.fallbacks.get(&method) {
            return fallback;
        }
        let fallback = self.new_object(graph, Object::Fallback { method });
        self.fallbacks.insert(method, fallback);
        fallback
    }

    pub(super) fn instantiate(&mut self, graph: &mut Graph, class: ObjId, call: CallId) {
        let default = self.python_method(graph, class, "__new__");
        self.share(
            graph,
            default,
            SharedRule::PythonNew { class },
            SharedItem::Call(call),
        );
        let new = self.implicit_call(graph, class, "__new__", call, None, Unless::Nothing);
        if !self.new_results.contains_key(&new) {
            self.class_instances.entry(class).or_default();
            let id =
                ReturnedId(u32::try_from(self.returned.len()).expect("fewer than 2^32 results"));
            self.returned.push(Returned {
                call,
                class,
                returned: FxHashSet::default(),
                sees: false,
                dst: None,
                dsts: Vec::new(),
                held: Vec::new(),
                another: false,
            });
            self.new_results.insert(new, id);
            let found =
                self.lookup_name(graph, class, "__new__", Some(class), None, Unless::Nothing);
            self.share(
                graph,
                found,
                SharedRule::New { class },
                SharedItem::Call(new),
            );
            let instances = self.objects.class(class).instances;
            self.share(
                graph,
                instances,
                SharedRule::OfClass,
                SharedItem::Returned(id),
            );
        }
        if let Some(dst) = self.calls[call.index()].dst {
            let id = self.new_results[&new];
            self.returned_add_dst(graph, id, dst);
        }
    }

    pub(super) fn python_new(&mut self, graph: &mut Graph, class: ObjId, call: CallId) {
        let instantiable = self.objects.class(class).instantiable;
        self.share(
            graph,
            instantiable,
            SharedRule::PythonInstance,
            SharedItem::Call(call),
        );
    }

    fn share(&mut self, graph: &mut Graph, node: NodeId, rule: SharedRule, item: SharedItem) {
        let key = (node, rule);
        let Some(&shared) = self.shared_by_key.get(&key) else {
            let shared =
                SharedId(u32::try_from(self.shared.len()).expect("fewer than 2^32 shared records"));
            self.shared.push(Shared {
                rule,
                items: vec![item],
            });
            self.shared_by_key.insert(key, shared);
            let id = self.rule(Rule::Shared(shared));
            self.attach(graph, node, id);
            return;
        };
        self.shared[shared.index()].items.push(item);
        let each = self.rule(rule.each(item));
        self.apply_now(graph, node, each);
    }

    pub(super) fn shared_results(&self, shared: SharedId) -> Vec<NodeId> {
        let found = &self.shared[shared.index()];
        if !found.rule.gives_dst() {
            return Vec::new();
        }
        found
            .items
            .iter()
            .filter_map(|item| match *item {
                SharedItem::Call(call) => self.calls[call.index()].dst,
                SharedItem::Returned(_) => None,
            })
            .collect()
    }

    pub(super) fn shared_captured(&self, shared: SharedId) -> Vec<ObjId> {
        self.shared[shared.index()].rule.captured()
    }

    pub(super) fn shared_items(&self, shared: SharedId) -> (SharedRule, Vec<SharedItem>) {
        let found = &self.shared[shared.index()];
        (found.rule, found.items.clone())
    }

    pub(super) fn python_instance(&mut self, graph: &mut Graph, class: ObjId, call: CallId) {
        let instance = self.instance(graph, class, call);
        if let Some(dst) = self.calls[call.index()].dst {
            self.add_object(graph, dst, instance);
        }
        self.call_dunder(graph, instance, "__init__", call, None, Unless::Nothing);
    }

    pub(super) fn call_new(
        &mut self,
        graph: &mut Graph,
        method: ObjId,
        class: ObjId,
        call: CallId,
    ) {
        if self.objects.is_external(method) {
            return;
        }
        let id = self.new_results[&call];
        let dst = self.calls[call.index()].dst.expect("the result of __new__");
        self.returned_start(graph, id, dst);
        self.call_bound(graph, method, vec![class], call);
    }

    fn returned_add_dst(&mut self, graph: &mut Graph, id: ReturnedId, dst: NodeId) {
        let returned = &mut self.returned[id.0 as usize];
        if returned.dsts.contains(&dst) {
            return;
        }
        returned.dsts.push(dst);
        if let Some(own) = returned.dst {
            self.add_edge(graph, own, dst);
        }
    }

    fn returned_start(&mut self, graph: &mut Graph, id: ReturnedId, new: NodeId) {
        if self.returned[id.0 as usize].dst.is_some() {
            return;
        }
        let own = self.node(graph, None);
        self.returned[id.0 as usize].dst = Some(own);
        for dst in self.returned[id.0 as usize].dsts.clone() {
            self.add_edge(graph, own, dst);
        }
        let rule = self.rule(Rule::ReturnedByItsNew(id));
        self.attach(graph, new, rule);
        let release = self.rule(Rule::ReturnedRelease(id));
        let class = self.returned[id.0 as usize].class;
        let another = self.lookup_name(
            graph,
            class,
            "__new__",
            None,
            None,
            Unless::NewGivesTheClass,
        );
        self.attach(graph, another, release);
        let rule = self.rule(Rule::ReturnedByNew(id));
        self.attach(graph, own, rule);
    }

    pub(super) fn returned_by_its_new(&mut self, graph: &mut Graph, id: ReturnedId, object: ObjId) {
        let returned = &self.returned[id.0 as usize];
        let other = match self.objects.get(object) {
            &Object::Instance { class, .. } => class != returned.class,
            _ => false,
        };
        if other && !returned.another {
            self.returned[id.0 as usize].held.push(object);
        } else {
            let dst = returned.dst.expect("a started result");
            self.add_object(graph, dst, object);
        }
    }

    pub(super) fn returned_release(&mut self, graph: &mut Graph, id: ReturnedId) {
        let returned = &mut self.returned[id.0 as usize];
        returned.another = true;
        let held = std::mem::take(&mut returned.held);
        let dst = returned.dst.expect("a started result");
        for object in held {
            self.add_object(graph, dst, object);
        }
    }

    pub(super) fn returned_by_new(&mut self, graph: &mut Graph, id: ReturnedId, object: ObjId) {
        let returned = &mut self.returned[id.0 as usize];
        returned.returned.insert(object);
        let class = returned.class;
        if returned.sees && self.class_instances[&class].contains(&object) {
            self.returned_initialise(graph, id, object);
        }
    }

    pub(super) fn returned_of_class(&mut self, graph: &mut Graph, id: ReturnedId, object: ObjId) {
        let returned = &mut self.returned[id.0 as usize];
        returned.sees = true;
        let class = returned.class;
        let seen = returned.returned.contains(&object);
        self.class_instances
            .get_mut(&class)
            .expect("the instances of a class")
            .insert(object);
        if seen {
            self.returned_initialise(graph, id, object);
        }
    }

    fn returned_initialise(&mut self, graph: &mut Graph, id: ReturnedId, object: ObjId) {
        let call = self.returned[id.0 as usize].call;
        self.call_dunder(graph, object, "__init__", call, None, Unless::Nothing);
    }

    pub(super) fn returned_results(&self, id: ReturnedId) -> Option<NodeId> {
        self.returned[id.0 as usize].dst
    }

    pub(super) fn call_dunder(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        name: &str,
        call: CallId,
        dst: Option<NodeId>,
        unless: Unless,
    ) {
        let name = self.symbols.intern(name);
        if let &Object::Instance { class, .. } = self.objects.get(object) {
            let rule = WaitingRule::CallDunder {
                name,
                call,
                dst,
                unless: unless.clone(),
            };
            let key = LookupKey {
                attr: LookupAttr::Name(name),
                receiver: Some(object),
                after: None,
                unless,
            };
            self.later(graph, class, key, rule);
        } else {
            self.call_dunder_now(graph, object, name, call, dst, unless);
        }
    }

    pub(super) fn call_dunder_now(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        name: Sym,
        call: CallId,
        dst: Option<NodeId>,
        unless: Unless,
    ) {
        let text = self.symbols.text(name).to_string();
        let implicit = self.implicit_call(graph, object, &text, call, dst, unless.clone());
        let owners = self.dunder_owners.entry(implicit).or_default();
        if !owners.insert(object) {
            return;
        }
        let types = match self.objects.get(object) {
            &Object::Instance { class, .. } => self.constant(graph, class),
            Object::Class(class) => class.metaclass,
            _ => panic!("a special method is called on an instance or a class"),
        };
        let rule = self.rule(Rule::TypeMethod {
            object,
            name,
            implicit,
            unless,
        });
        self.attach(graph, types, rule);
    }

    pub(super) fn type_method(
        &mut self,
        graph: &mut Graph,
        class: ObjId,
        object: ObjId,
        name: Sym,
        implicit: CallId,
        unless: Unless,
    ) {
        let rule = self.calls[implicit.index()].rule;
        if self.objects.is_class(class) {
            let key = LookupKey {
                attr: LookupAttr::Name(name),
                receiver: Some(object),
                after: None,
                unless,
            };
            let found = self.lookup(graph, class, key);
            self.attach(graph, found, rule);
            return;
        }
        let method = self.node(graph, None);
        let class_name = self.object_name(class);
        for definition in self.stub_definitions(class).unwrap_or_default().iter() {
            if definition.kind == DefinitionKind::Class {
                self.stub_member(graph, object, &definition.path, &class_name, name, method);
            }
        }
        self.attach(graph, method, rule);
    }

    pub(super) fn implicit_call(
        &mut self,
        graph: &mut Graph,
        owner: ObjId,
        name: &str,
        call: CallId,
        dst: Option<NodeId>,
        unless: Unless,
    ) -> CallId {
        let (base, receivers) = self.prefix_receivers(call);
        let root = self.roots.get(&base).copied().unwrap_or(base);
        let typed = match self.objects.get(owner) {
            Object::Instance { .. } => None,
            _ => Some(owner),
        };
        let key = (typed, self.symbols.intern(name), root, unless);
        let template = match self.dunder_calls.get(&key) {
            Some(&template) => template,
            None => {
                let node = self.node(graph, None);
                let mut details = self.calls[base.index()].clone();
                details.dst = Some(node);
                let origin = details.origin;
                let template = self.new_call(details, Some(origin));
                self.dunder_calls.insert(key, template);
                self.roots.insert(template, root);
                template
            }
        };
        let (found, given) = (&self.calls[template.index()], &self.calls[base.index()]);
        assert!(
            found.args == given.args
                && found.keywords == given.keywords
                && found.star == given.star
                && found.double_star == given.double_star,
            "a special method call keeps the arguments of its base"
        );
        let implicit = self.prefixed_call(graph, template, receivers);
        if let Some(dst) = dst {
            let own = self.calls[implicit.index()]
                .dst
                .expect("an implicit call has a result");
            self.add_edge(graph, own, dst);
        }
        implicit
    }

    pub(super) fn site_call(
        &mut self,
        graph: &mut Graph,
        key: SiteKey,
        args: &[Option<NodeId>],
        dst: Option<NodeId>,
        rest: Option<NodeId>,
    ) -> CallId {
        let call = match self.site_calls.get(&key) {
            Some(&call) => call,
            None => {
                let nodes: Vec<Option<NodeId>> =
                    args.iter().map(|_| Some(self.node(graph, None))).collect();
                let star = match rest {
                    None => Vec::new(),
                    Some(_) => vec![(None, true), (Some(self.node(graph, None)), false)],
                };
                let result = self.node(graph, None);
                let details = Call {
                    caller: key.caller,
                    args: nodes,
                    keywords: Vec::new(),
                    dst: Some(result),
                    site: key.site,
                    origin: Origin::Site(key),
                    star,
                    double_star: Vec::new(),
                    implicit: key.implicit,
                    decorator: false,
                    applies: false,
                    rule: RuleId::PLACEHOLDER,
                };
                let call = self.new_call(details, Some(Origin::Site(key)));
                self.site_calls.insert(key, call);
                call
            }
        };
        let details = self.calls[call.index()].clone();
        assert_eq!(args.len(), details.args.len(), "{key:?} with another arity");
        assert_eq!(
            rest.is_none(),
            details.star.is_empty(),
            "{key:?} with another arity"
        );
        for (value, node) in args.iter().zip(&details.args) {
            if let (Some(value), Some(node)) = (value, node) {
                self.add_edge(graph, *value, *node);
            }
        }
        if let Some(rest) = rest {
            let node = details.star[1].0.expect("the rest of a site call");
            self.add_edge(graph, rest, node);
        }
        if let Some(dst) = dst {
            let own = details.dst.expect("a site call has a result");
            self.add_edge(graph, own, dst);
        }
        call
    }

    pub(super) fn add_init_subclass(
        &mut self,
        graph: &mut Graph,
        class: ObjId,
        keywords: &[(Box<str>, Option<NodeId>)],
        double_star: &[Option<NodeId>],
        caller: &str,
        site: &str,
    ) {
        let caller = self.symbols.intern(caller);
        let site = self.symbols.intern(site);
        let keywords = keywords
            .iter()
            .map(|(name, value)| (self.symbols.intern(name), *value))
            .collect();
        let details = Call {
            caller,
            args: Vec::new(),
            keywords,
            dst: None,
            site,
            origin: Origin::InitSubclass(site),
            star: Vec::new(),
            double_star: double_star.to_vec(),
            implicit: true,
            decorator: false,
            applies: false,
            rule: RuleId::PLACEHOLDER,
        };
        let call = self.new_call(details, Some(Origin::InitSubclass(site)));
        let found = self.lookup_name(
            graph,
            class,
            "__init_subclass__",
            Some(class),
            Some(class),
            Unless::Nothing,
        );
        let rule = self.calls[call.index()].rule;
        self.attach(graph, found, rule);
    }

    pub(super) fn add_set_name(
        &mut self,
        graph: &mut Graph,
        value: NodeId,
        class: ObjId,
        name: &str,
        caller: &str,
        site: &str,
    ) {
        let name = self.symbols.intern(name);
        let caller = self.symbols.intern(caller);
        let site = self.symbols.intern(site);
        let rule = self.rule(Rule::SetName {
            class,
            name,
            caller,
            site,
        });
        self.attach(graph, value, rule);
    }

    pub(super) fn set_name(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        class: ObjId,
        name: Sym,
        caller: Sym,
        site: Sym,
    ) {
        let owner = self.constant(graph, class);
        let literal = crate::engine::objects::Literal::Str(
            self.symbols.text(name).chars().map(u32::from).collect(),
        );
        let named = self.const_object(graph, &literal);
        let named = self.constant(graph, named);
        let key = SiteKey {
            caller,
            site,
            role: Role::SetName(name),
            implicit: true,
        };
        let call = self.site_call(graph, key, &[Some(owner), Some(named)], None, None);
        self.call_dunder(graph, object, "__set_name__", call, None, Unless::Nothing);
    }

    pub(super) fn add_metaclass_call(
        &mut self,
        graph: &mut Graph,
        class: ObjId,
        statement: &BuilderClassStatement<'_>,
        caller: &str,
        site: &str,
    ) {
        let waiting = ClassStatement {
            name: self.symbols.intern(statement.name),
            bases: statement.bases.to_vec(),
            namespace: statement
                .namespace
                .iter()
                .map(|(key, value)| (self.symbols.intern(key), *value))
                .collect(),
            keywords: statement
                .keywords
                .iter()
                .map(|(name, value)| (self.symbols.intern(name), *value))
                .collect(),
            double_star: statement.double_star.to_vec(),
            caller: self.symbols.intern(caller),
            site: self.symbols.intern(site),
        };
        let replaced = self
            .statement_calls
            .insert(class, StatementCall::Waiting(waiting));
        assert!(replaced.is_none(), "one class statement per class");
        let rule = self.rule(Rule::CallMetaclass { class });
        let metaclass = self.objects.class(class).metaclass;
        self.attach(graph, metaclass, rule);
    }

    pub(super) fn call_metaclass(&mut self, graph: &mut Graph, meta: ObjId, class: ObjId) {
        let (call, prepare) = match self.statement_calls.remove(&class) {
            Some(StatementCall::Waiting(statement)) => {
                let (call, prepare) = self.statement_call(graph, &statement);
                self.statement_calls
                    .insert(class, StatementCall::Made { call, prepare });
                if self.made_classes.contains(&class) {
                    self.call_dunder(graph, class, "__init__", call, None, Unless::Nothing);
                }
                (call, prepare)
            }
            Some(StatementCall::Made { call, prepare }) => {
                self.statement_calls
                    .insert(class, StatementCall::Made { call, prepare });
                (call, prepare)
            }
            None => unreachable!("a metaclass call has its class statement"),
        };
        let found = self.lookup_name(
            graph,
            meta,
            "__prepare__",
            Some(meta),
            None,
            Unless::Nothing,
        );
        let rule = self.rule(Rule::AnalysedHook { call: prepare });
        self.attach(graph, found, rule);
        let python = self.python_method(graph, meta, "__new__");
        let rule = self.rule(Rule::InitStatementClass { class, call });
        self.attach(graph, python, rule);
        let found = self.lookup_name(graph, meta, "__new__", Some(meta), None, Unless::Nothing);
        let rule = self.rule(Rule::StatementNew { meta, call });
        self.attach(graph, found, rule);
    }

    fn statement_call(
        &mut self,
        graph: &mut Graph,
        statement: &ClassStatement,
    ) -> (CallId, CallId) {
        let site = statement.site;
        let origin = ContainerOrigin::ClassStatement(site);
        let length = u32::try_from(statement.bases.len()).expect("fewer than 2^32 bases");
        let members = self.container_at(graph, "tuple", origin, site, Some(length), false);
        for (index, base) in statement.bases.iter().enumerate() {
            if let Some(base) = *base {
                let element = self.element(graph, members, &Literal::Int(BigInt::from(index)));
                self.add_edge(graph, base, element);
            }
        }
        let body = self.container_at(graph, "dict", origin, site, None, false);
        for &(key, value) in &statement.namespace {
            let key = self.string_const(graph, key);
            let key = self.constant(graph, key);
            self.write_keyed(graph, body, Some(key), Some(value));
        }
        let name = self.string_const(graph, statement.name);
        let args = vec![
            Some(self.constant(graph, name)),
            Some(self.constant(graph, members)),
            Some(self.constant(graph, body)),
        ];
        let details = Call {
            caller: statement.caller,
            args: args.clone(),
            keywords: statement.keywords.clone(),
            dst: None,
            site,
            origin: Origin::ClassStatement(site),
            star: Vec::new(),
            double_star: statement.double_star.clone(),
            implicit: true,
            decorator: false,
            applies: false,
            rule: RuleId::PLACEHOLDER,
        };
        let call = self.new_call(details, Some(Origin::ClassStatement(site)));
        let details = Call {
            caller: statement.caller,
            args: args[..2].to_vec(),
            keywords: statement.keywords.clone(),
            dst: None,
            site,
            origin: Origin::Prepare(site),
            star: Vec::new(),
            double_star: statement.double_star.clone(),
            implicit: true,
            decorator: false,
            applies: false,
            rule: RuleId::PLACEHOLDER,
        };
        let prepare = self.new_call(details, Some(Origin::Prepare(site)));
        (call, prepare)
    }

    fn string_const(&mut self, graph: &mut Graph, text: Sym) -> ObjId {
        let literal = Literal::Str(self.symbols.text(text).chars().map(u32::from).collect());
        self.const_object(graph, &literal)
    }

    pub(super) fn analysed_hook(&mut self, graph: &mut Graph, object: ObjId, call: CallId) {
        if !matches!(
            self.objects.get(object),
            Object::External(_) | Object::UnknownExternal(_)
        ) {
            self.call(graph, object, call);
        }
    }

    pub(super) fn statement_new(
        &mut self,
        graph: &mut Graph,
        method: ObjId,
        meta: ObjId,
        call: CallId,
    ) {
        if matches!(
            self.objects.get(method),
            Object::External(_) | Object::UnknownExternal(_)
        ) {
            return;
        }
        self.call_bound(graph, method, vec![meta], call);
        if matches!(self.objects.get(method), Object::Function(_))
            && self.statement_news.insert(method)
        {
            let returned = self
                .objects
                .function(method)
                .return_node
                .expect("an analysed function returns");
            let rule = self.rule(Rule::StatementMade);
            self.attach(graph, returned, rule);
        }
    }

    pub(super) fn statement_made(&mut self, graph: &mut Graph, class: ObjId) {
        self.made_classes.insert(class);
        if let Some(&StatementCall::Made { call, .. }) = self.statement_calls.get(&class) {
            self.call_dunder(graph, class, "__init__", call, None, Unless::Nothing);
        }
    }

    pub(super) fn add_method(
        &mut self,
        graph: &mut Graph,
        class: ObjId,
        name: &str,
        function: ObjId,
        kind: Option<MethodKind>,
    ) {
        if kind == Some(MethodKind::StaticMethod) {
            return;
        }
        let made = self.objects.function(function);
        let receiver = match made.signature.positional.first() {
            Some(first) => {
                let first = self.symbols.intern(first);
                self.objects.function(function).parameter(first)
            }
            None if made.varargs.is_some() => not_ported("containers: a receiver in varargs"),
            None => return,
        };
        let source = if kind == Some(MethodKind::ClassMethod) {
            self.family(graph, class)
        } else {
            self.objects.class(class).instances
        };
        let name = self.symbols.intern(name);
        self.receivers
            .push((receiver, source, function, class, name));
    }
}
