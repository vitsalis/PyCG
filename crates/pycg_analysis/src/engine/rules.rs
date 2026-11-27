use pycg_solver::{KindMask, NodeId, ObjId, Rules, WatchId};

use crate::engine::attributes::{
    ANALYSED_METHODS, AccessId, AccessorsId, DeliveriesId, HookCallsId, HooksId, WritesId,
};
use crate::engine::hierarchy::Unless;
use crate::engine::objects::{Kind, kinds_mask};
use crate::engine::outside_calls::PlanId;
use crate::engine::semantics::{CallId, ReturnedId};
use crate::engine::symbols::Sym;
use crate::engine::trace::{RuleInfo, Trace};
use crate::engine::{Graph, OrderedMap, State, not_ported};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct RuleId(u32);

impl RuleId {
    pub(crate) const PLACEHOLDER: RuleId = RuleId(u32::MAX);

    fn index(self) -> usize {
        self.0 as usize
    }
}

#[derive(Clone, Debug)]
pub(crate) enum Rule {
    Call(CallId),
    Bases {
        class: ObjId,
        index: u32,
    },
    Bind {
        receiver: Option<ObjId>,
        dst: NodeId,
        instance: bool,
    },
    KeywordCandidate {
        class: ObjId,
    },
    MemberOfMetaclass {
        class: ObjId,
        attr: Sym,
        dst: NodeId,
    },
    BindFallback {
        receiver: ObjId,
        dst: NodeId,
    },
    WrapFallback {
        dst: NodeId,
    },
    PythonNew {
        class: ObjId,
        call: CallId,
    },
    PythonInstance {
        call: CallId,
    },
    New {
        class: ObjId,
        call: CallId,
    },
    ReturnedOfClass(ReturnedId),
    ReturnedByItsNew(ReturnedId),
    ReturnedRelease(ReturnedId),
    ReturnedByNew(ReturnedId),
    TypeMethod {
        object: ObjId,
        name: Sym,
        implicit: CallId,
        unless: Unless,
    },
    SetName {
        class: ObjId,
        name: Sym,
        caller: Sym,
        site: Sym,
    },
    CallMetaclass {
        class: ObjId,
    },
    AddInexact {
        dst: NodeId,
    },
    Access(AccessId),
    Deliver {
        receiver: ObjId,
        load: AccessId,
        hook: Option<Sym>,
    },
    Deliveries(DeliveriesId),
    AccessorHooks(HooksId),
    Accessors {
        id: AccessorsId,
        analysed_only: bool,
    },
    FieldWrites(WritesId),
    HookCalls(HookCallsId),
    Itself {
        object: ObjId,
        dst: NodeId,
    },
    ClassGet {
        call: CallId,
    },
    ClassAttribute {
        class: ObjId,
        load: AccessId,
    },
    ModuleGetattr {
        module: ObjId,
        attr: Sym,
        load: AccessId,
    },
    StorePast {
        src: NodeId,
        field: NodeId,
    },
    DeliverStore {
        object: ObjId,
        store: AccessId,
    },
    DeliverDelete {
        object: ObjId,
        delete: AccessId,
    },
    CallBackObject {
        callback: CallId,
    },
    CallProtocol {
        plan: PlanId,
        call: CallId,
    },
    MetaclassProtocol {
        class: ObjId,
        name: Sym,
        implicit: CallId,
        unless: Unless,
    },
    CallEach {
        call: CallId,
    },
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub(crate) enum WaitingRule {
    CallDunder {
        name: Sym,
        call: CallId,
        dst: Option<NodeId>,
        unless: Unless,
    },
    DeliverLoad(AccessId),
    CallHook {
        hook: Sym,
        call: CallId,
    },
    FoundStore(AccessId),
}

const SET_NAME_KINDS: &[Kind] = &[Kind::Instance, Kind::Class];
const CLASS_KINDS: &[Kind] = &[Kind::Class];
const CALLED_BACK_KINDS: &[Kind] = &[Kind::Function, Kind::BoundMethod, Kind::Instance];

impl Rule {
    fn key(&self) -> &'static str {
        match self {
            Rule::Call(_) => "Call",
            Rule::Bases { .. } => "_Bases",
            Rule::Bind { .. } => "_Bind",
            Rule::KeywordCandidate { .. } => "Each:Hierarchy._keyword_candidate",
            Rule::MemberOfMetaclass { .. } => "Each:Hierarchy._member_of_metaclass",
            Rule::BindFallback { .. } => "Each:Hierarchy._bind_fallback",
            Rule::WrapFallback { .. } => "Each:Hierarchy._wrap_fallback",
            Rule::PythonNew { .. } => "Each:Analysis._python_new",
            Rule::PythonInstance { .. } => "Each:Analysis._python_instance",
            Rule::New { .. } => "Each:Analysis._new",
            Rule::ReturnedOfClass(_) => "Each:_Returned.of_class",
            Rule::ReturnedByItsNew(_) => "Each:_Returned.by_its_new",
            Rule::ReturnedRelease(_) => "Each:_Returned.release",
            Rule::ReturnedByNew(_) => "Each:_Returned.by_new",
            Rule::TypeMethod { .. } => "Each:Analysis._type_method",
            Rule::SetName { .. } => "Each:Analysis._set_name",
            Rule::CallMetaclass { .. } => "Each:Analysis._call_metaclass",
            Rule::AddInexact { .. } => "Each:Containers._add_inexact",
            Rule::Access(_) => "Access",
            Rule::Deliver { .. } => "_Deliver",
            Rule::Deliveries(_) => "_Deliveries",
            Rule::AccessorHooks(_) => "_AccessorHooks",
            Rule::Accessors { .. } => "_Accessors",
            Rule::FieldWrites(_) => "_FieldWrites",
            Rule::HookCalls(_) => "_HookCalls",
            Rule::Itself { .. } => "Each:Attributes._itself",
            Rule::ClassGet { .. } => "Each:Attributes._class_get",
            Rule::ClassAttribute { .. } => "Each:Attributes._class_attribute",
            Rule::ModuleGetattr { .. } => "Each:Attributes._module_getattr",
            Rule::StorePast { .. } => "Each:Attributes._store_past",
            Rule::DeliverStore { .. } => "Each:Attributes._deliver_store",
            Rule::DeliverDelete { .. } => "Each:Attributes._deliver_delete",
            Rule::CallBackObject { .. } => "Each:Analysis._call_back_object",
            Rule::CallProtocol { .. } => "Each:Outside._call_protocol",
            Rule::MetaclassProtocol { .. } => "Each:Outside._metaclass_protocol",
            Rule::CallEach { .. } => "Each:Analysis.call",
        }
    }

    fn each(&self) -> bool {
        !matches!(
            self,
            Rule::Call(_)
                | Rule::Bases { .. }
                | Rule::Bind { .. }
                | Rule::Access(_)
                | Rule::Deliver { .. }
                | Rule::Deliveries(_)
                | Rule::AccessorHooks(_)
                | Rule::Accessors { .. }
                | Rule::FieldWrites(_)
                | Rule::HookCalls(_)
        )
    }

    fn kinds(&self) -> Option<&'static [Kind]> {
        match self {
            Rule::SetName { .. } => Some(SET_NAME_KINDS),
            Rule::CallMetaclass { .. } => Some(CLASS_KINDS),
            Rule::CallBackObject { .. } => Some(CALLED_BACK_KINDS),
            Rule::CallProtocol { .. } => Some(SET_NAME_KINDS),
            Rule::ClassGet { .. }
            | Rule::Accessors {
                analysed_only: true,
                ..
            } => Some(ANALYSED_METHODS),
            _ => None,
        }
    }

    fn captured(&self) -> Vec<ObjId> {
        match *self {
            Rule::Bases { class, .. }
            | Rule::KeywordCandidate { class }
            | Rule::MemberOfMetaclass { class, .. }
            | Rule::PythonNew { class, .. }
            | Rule::New { class, .. }
            | Rule::SetName { class, .. }
            | Rule::CallMetaclass { class } => vec![class],
            Rule::Bind { receiver, .. } => receiver.into_iter().collect(),
            Rule::BindFallback { receiver, .. } => vec![receiver],
            Rule::TypeMethod { object, .. }
            | Rule::Itself { object, .. }
            | Rule::DeliverStore { object, .. }
            | Rule::DeliverDelete { object, .. } => vec![object],
            Rule::ClassAttribute { class, .. } | Rule::MetaclassProtocol { class, .. } => {
                vec![class]
            }
            Rule::CallBackObject { .. } | Rule::CallProtocol { .. } | Rule::CallEach { .. } => {
                Vec::new()
            }
            Rule::ModuleGetattr { module, .. } => vec![module],
            Rule::Deliver { receiver, .. } => vec![receiver],
            Rule::Access(_)
            | Rule::Deliveries(_)
            | Rule::AccessorHooks(_)
            | Rule::Accessors { .. }
            | Rule::FieldWrites(_)
            | Rule::HookCalls(_)
            | Rule::ClassGet { .. }
            | Rule::StorePast { .. } => Vec::new(),
            Rule::Call(_)
            | Rule::WrapFallback { .. }
            | Rule::PythonInstance { .. }
            | Rule::ReturnedOfClass(_)
            | Rule::ReturnedByItsNew(_)
            | Rule::ReturnedRelease(_)
            | Rule::ReturnedByNew(_)
            | Rule::AddInexact { .. } => Vec::new(),
        }
    }
}

impl<T: Trace> State<T> {
    pub(super) fn rule(&mut self, rule: Rule) -> RuleId {
        let id = RuleId(u32::try_from(self.rules.len()).expect("fewer than 2^32 rules"));
        let key = match rule {
            Rule::Call(call) => {
                format!("Call:{}", self.symbols.text(self.calls[call.index()].site))
            }
            Rule::Access(access) => self.access(access).kind.name().to_string(),
            _ => rule.key().to_string(),
        };
        let captured = match rule {
            Rule::Deliveries(id) => vec![self.deliveries_receiver(id)],
            _ => rule.captured(),
        };
        self.trace.rule(
            id,
            &RuleInfo {
                key: &key,
                kinds: rule.kinds(),
                each: rule.each(),
                captured: &captured,
            },
        );
        self.rules.push(rule);
        id
    }

    fn results(&self, rule: &Rule) -> Vec<NodeId> {
        match *rule {
            Rule::Call(call)
            | Rule::PythonNew { call, .. }
            | Rule::PythonInstance { call }
            | Rule::New { call, .. } => self.calls[call.index()].dst.into_iter().collect(),
            Rule::TypeMethod { implicit, .. } => {
                self.calls[implicit.index()].dst.into_iter().collect()
            }
            Rule::Bind { dst, .. }
            | Rule::MemberOfMetaclass { dst, .. }
            | Rule::BindFallback { dst, .. }
            | Rule::WrapFallback { dst }
            | Rule::AddInexact { dst } => vec![dst],
            Rule::ReturnedByItsNew(id) | Rule::ReturnedRelease(id) => {
                self.returned_results(id).into_iter().collect()
            }
            Rule::Access(access)
            | Rule::Deliver { load: access, .. }
            | Rule::ClassAttribute { load: access, .. }
            | Rule::ModuleGetattr { load: access, .. } => {
                self.access_result(access).into_iter().collect()
            }
            Rule::Deliveries(id) => self.deliveries_results(id),
            Rule::AccessorHooks(id) => self.hooks_results(id),
            Rule::Accessors { id, .. } => self.accessors_results(id),
            Rule::FieldWrites(id) => self.writes_results(id),
            Rule::HookCalls(id) => self.hook_calls_results(id),
            Rule::Itself { dst, .. } => vec![dst],
            Rule::ClassGet { call } => self.calls[call.index()].dst.into_iter().collect(),
            Rule::StorePast { field, .. } => vec![field],
            Rule::DeliverStore { .. }
            | Rule::DeliverDelete { .. }
            | Rule::CallBackObject { .. }
            | Rule::CallProtocol { .. } => Vec::new(),
            Rule::MetaclassProtocol { implicit: call, .. } | Rule::CallEach { call } => {
                self.calls[call.index()].dst.into_iter().collect()
            }
            Rule::Bases { .. }
            | Rule::KeywordCandidate { .. }
            | Rule::ReturnedOfClass(_)
            | Rule::ReturnedByNew(_)
            | Rule::SetName { .. }
            | Rule::CallMetaclass { .. } => Vec::new(),
        }
    }

    fn apply_one(&mut self, graph: &mut Graph, rule: &Rule, object: ObjId) {
        match *rule {
            Rule::Call(call) => self.call(graph, object, call),
            Rule::Bases { class, index } => self.add_base(graph, object, class, index),
            Rule::Bind {
                receiver,
                dst,
                instance,
            } => self.bind(graph, object, receiver, dst, Some(instance)),
            Rule::KeywordCandidate { class } => self.keyword_candidate(graph, object, class),
            Rule::MemberOfMetaclass { class, attr, dst } => {
                self.member_of_metaclass(graph, object, class, attr, dst)
            }
            Rule::BindFallback { receiver, dst } => {
                self.bind_fallback(graph, object, receiver, dst)
            }
            Rule::WrapFallback { dst } => self.wrap_fallback(graph, object, dst),
            Rule::PythonNew { class, call } => self.python_new(graph, class, call),
            Rule::PythonInstance { call } => self.python_instance(graph, object, call),
            Rule::New { class, call } => self.call_new(graph, object, class, call),
            Rule::ReturnedOfClass(id) => self.returned_of_class(graph, id, object),
            Rule::ReturnedByItsNew(id) => self.returned_by_its_new(graph, id, object),
            Rule::ReturnedRelease(id) => self.returned_release(graph, id),
            Rule::ReturnedByNew(id) => self.returned_by_new(graph, id, object),
            Rule::TypeMethod {
                object: owner,
                name,
                implicit,
                ref unless,
            } => self.type_method(graph, object, owner, name, implicit, unless.clone()),
            Rule::SetName {
                class,
                name,
                caller,
                site,
            } => self.set_name(graph, object, class, name, caller, site),
            Rule::CallMetaclass { .. } => not_ported("containers: the call of a metaclass"),
            Rule::AddInexact { dst } => {
                let inexact = self.inexact_object(graph, object);
                self.add_object(graph, dst, inexact);
            }
            Rule::Access(access) => self.apply_access(graph, object, access),
            Rule::Deliver {
                receiver,
                load,
                hook,
            } => self.deliver(graph, object, receiver, load, hook),
            Rule::Deliveries(id) => self.deliveries_apply(graph, id, &[object]),
            Rule::AccessorHooks(id) => self.hooks_apply(graph, id, object),
            Rule::Accessors { id, .. } => self.accessors_apply(graph, id, object),
            Rule::FieldWrites(id) => self.writes_apply(graph, id),
            Rule::HookCalls(id) => self.hook_calls_apply(graph, id, object),
            Rule::Itself { object: owner, dst } => self.itself(graph, owner, dst),
            Rule::ClassGet { call } => self.class_get(graph, object, call),
            Rule::ClassAttribute { class, load } => {
                self.class_attribute(graph, object, class, load)
            }
            Rule::ModuleGetattr { module, attr, load } => {
                self.module_getattr(graph, object, module, attr, load)
            }
            Rule::StorePast { src, field } => self.store_past(graph, object, src, field),
            Rule::DeliverStore {
                object: owner,
                store,
            } => self.deliver_store(graph, object, owner, store),
            Rule::DeliverDelete {
                object: owner,
                delete,
            } => self.deliver_delete(graph, object, owner, delete),
            Rule::CallBackObject { callback } => self.call(graph, object, callback),
            Rule::CallProtocol { plan, call } => self.call_protocol(graph, object, plan, call),
            Rule::MetaclassProtocol {
                class,
                name,
                implicit,
                ref unless,
            } => self.metaclass_protocol(graph, object, class, name, implicit, unless.clone()),
            Rule::CallEach { call } => self.call(graph, object, call),
        }
    }

    pub(super) fn run_waiting(&mut self, graph: &mut Graph, rule: WaitingRule, receiver: ObjId) {
        match rule {
            WaitingRule::CallDunder {
                name,
                call,
                dst,
                unless,
            } => self.call_dunder_now(graph, receiver, name, call, dst, unless),
            WaitingRule::DeliverLoad(load) => self.deliver_load(graph, receiver, load),
            WaitingRule::CallHook { hook, call } => self.call_hook(graph, receiver, hook, call),
            WaitingRule::FoundStore(store) => self.found_store(graph, receiver, store),
        }
    }
}

impl<T: Trace> Rules<RuleId> for State<T> {
    fn apply(&mut self, graph: &mut Graph, rule: RuleId, objects: &[ObjId]) {
        let found = self.rules[rule.index()].clone();
        if let Rule::Deliveries(id) = found {
            self.trace.apply(rule, objects);
            self.deliveries_apply(graph, id, objects);
            self.trace.applied();
            return;
        }
        if !found.each() {
            self.trace.apply(rule, objects);
            for &object in objects {
                self.apply_one(graph, &found, object);
            }
            self.trace.applied();
            return;
        }
        let mask = found.kinds().map(kinds_mask);
        for &object in objects {
            if let Some(mask) = mask
                && self.objects.get(object).kind().mask() & mask == 0
            {
                continue;
            }
            self.trace.apply(rule, &[object]);
            self.apply_one(graph, &found, object);
            self.trace.applied();
        }
    }

    fn saturate(&mut self, graph: &mut Graph, rule: RuleId) {
        self.trace.saturate(rule);
        let found = self.rules[rule.index()].clone();
        match found {
            Rule::AccessorHooks(id) => self.hooks_saturate(id),
            Rule::FieldWrites(id) => self.writes_saturate(id),
            Rule::HookCalls(id) => self.hook_calls_saturate(id),
            _ => {}
        }
        let saturated = self.saturated;
        for dst in self.results(&found) {
            self.add_object(graph, dst, saturated);
        }
        self.trace.saturated();
    }

    fn kinds(&self, rule: RuleId) -> Option<KindMask> {
        self.rules[rule.index()].kinds().map(kinds_mask)
    }

    fn captures_opaque(&self, _graph: &Graph, rule: RuleId) -> bool {
        self.rules[rule.index()]
            .captured()
            .into_iter()
            .any(|object| State::opaque(self, object))
    }

    fn opaque(&self, object: ObjId) -> bool {
        State::opaque(self, object)
    }

    fn between_rounds(&mut self, graph: &mut Graph) -> bool {
        self.trace.between_rounds();
        let (answer, unknown) = self.unknown_classes(graph);
        self.trace.between_rounds_done(answer, &unknown);
        answer
    }

    fn wake(&mut self, graph: &mut Graph, watch: WatchId) {
        self.trace.wake(watch);
        let waiting = self.waiting.remove(&watch).unwrap_or_default();
        let mut receivers_by_rule: OrderedMap<WaitingRule, Vec<ObjId>> = OrderedMap::default();
        for (rule, receiver) in waiting {
            receivers_by_rule.entry(rule).or_default().push(receiver);
        }
        for (rule, receivers) in receivers_by_rule {
            for receiver in receivers {
                self.run_waiting(graph, rule.clone(), receiver);
            }
        }
        self.trace.woken();
    }

    fn firing(&mut self, graph: &mut Graph) {
        self.trace.fire(graph, &self.named_nodes);
    }
}
