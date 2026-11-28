use pycg_solver::{Attached, KindMask, NodeId, ObjId, Rules, WatchId};

use crate::engine::annotations::AnnotationRule;
use crate::engine::attributes::{
    ANALYSED_METHODS, AccessId, AccessorsId, DeliveriesId, HookCallsId, HooksId, WritesId,
};
use crate::engine::builtin_rules::DynamicId;
use crate::engine::builtin_rules::PropertyRule;
use crate::engine::containers::ContainerRule;
use crate::engine::containers::IterationId;
use crate::engine::hierarchy::{BindsId, Unless, UnlessId};
use crate::engine::library::LibraryRule;
use crate::engine::narrowing::ClassTestRule;
use crate::engine::objects::{Kind, kinds_mask};
use crate::engine::outside_calls::PlanId;
use crate::engine::outside_results::OutsideResultRule;
use crate::engine::outside_types::OutsideRule;
use crate::engine::patterns::PatternRule;
use crate::engine::protocols::ProtocolRule;
use crate::engine::reflection::{DefaultAction, GetmembersId};
use crate::engine::semantics::{CallId, ReturnedId, SharedId};
use crate::engine::symbols::Sym;
use crate::engine::{Graph, OrderedMap, State};

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
    Binds(BindsId),
    Shared(SharedId),
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
        unless: UnlessId,
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
    AnalysedHook {
        call: CallId,
    },
    InitStatementClass {
        class: ObjId,
        call: CallId,
    },
    StatementNew {
        meta: ObjId,
        call: CallId,
    },
    StatementMade,
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
    SpecialMethodOf {
        method: Sym,
        forwarded: CallId,
        dst: NodeId,
        caller: Sym,
        site: Sym,
    },
    CallProtocol {
        plan: PlanId,
        caller: Sym,
        site: Sym,
    },
    SequenceLength {
        caller: Sym,
        site: Sym,
    },
    Reversed {
        call: CallId,
        dst: NodeId,
        result: ObjId,
        iteration: IterationId,
    },
    ReversedSequence {
        object: ObjId,
        call: CallId,
        result: ObjId,
        items: NodeId,
    },
    ReverseSequence {
        object: ObjId,
        methods: NodeId,
        implicit: CallId,
        reversing: Option<NodeId>,
    },
    WhenDefaultMemberOnType {
        object: ObjId,
        name: Sym,
        action: DefaultAction,
        result: Option<NodeId>,
    },
    RunDefaultAction {
        object: ObjId,
        action: DefaultAction,
        result: Option<NodeId>,
    },
    NamespaceElement {
        object: ObjId,
        container: ObjId,
        unknown: NodeId,
    },
    AddNamespace {
        dst: NodeId,
    },
    MembersOf {
        access: GetmembersId,
        dst: NodeId,
    },
    LoadMember {
        object: ObjId,
        access: GetmembersId,
        values: NodeId,
    },
    MemberField {
        object: ObjId,
        values: NodeId,
    },
    MetaclassProtocol {
        class: ObjId,
        name: Sym,
        implicit: CallId,
        unless: UnlessId,
    },
    CallEach {
        call: CallId,
    },
    ImplicitMethod {
        field: NodeId,
        kind: Sym,
        site: Sym,
    },
    PropertyReceiver {
        rule: PropertyRule,
        dst: Option<NodeId>,
    },
    DerivedProperty {
        rule: PropertyRule,
        property: ObjId,
        dst: Option<NodeId>,
    },
    BindClass {
        method: ObjId,
        dst: NodeId,
    },
    BindType {
        method: ObjId,
        dst: NodeId,
    },
    BindTo {
        owner: ObjId,
        dst: NodeId,
    },
    LoadByPattern(DynamicId),
    SuperClass {
        object: NodeId,
        call: CallId,
        explicit: bool,
    },
    SuperAfterOutside {
        class: ObjId,
        dst: NodeId,
    },
    SuperObject {
        class: ObjId,
        dst: NodeId,
    },
    SuperGiven {
        class: ObjId,
        dst: NodeId,
    },
    SuperAcceptedBy {
        class: ObjId,
        given: NodeId,
        dst: NodeId,
    },
    TypeBases {
        call: CallId,
        made: [NodeId; 3],
    },
    TypeBase {
        call: CallId,
        made: [NodeId; 3],
    },
    CallTypeMetaclass {
        call: CallId,
    },
    SuperMetaclass {
        sup: ObjId,
        load: AccessId,
    },
    Container(ContainerRule),
    Protocol(Box<ProtocolRule>),
    Pattern(PatternRule),
    Outside(Box<OutsideRule>),
    Annotation(Box<AnnotationRule>),
    OutsideResult(Box<OutsideResultRule>),
    Library(LibraryRule),
    ClassTest(Box<ClassTestRule>),
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
const PROPERTY_KINDS: &[Kind] = &[Kind::Wrapper, Kind::Instance];
const PATTERN_KINDS: &[Kind] = &[Kind::Pattern];
const CONTAINER_KINDS: &[Kind] = &[Kind::Container];
const OWNER_OR_INSTANCE_KINDS: &[Kind] = &[Kind::Class, Kind::Instance];
const OWNER_KINDS: &[Kind] = &[Kind::Class, Kind::External];
const CALLED_BACK_KINDS: &[Kind] = &[Kind::Function, Kind::BoundMethod, Kind::Instance];
const SPECIAL_METHOD_KINDS: &[Kind] = &[Kind::Instance, Kind::Typed];

impl Rule {
    fn each(&self) -> bool {
        if let Rule::Container(rule) = self {
            return rule.each();
        }
        if let Rule::Protocol(rule) = self {
            return rule.each();
        }
        !matches!(
            self,
            Rule::Call(_)
                | Rule::Bases { .. }
                | Rule::Bind { .. }
                | Rule::Binds(_)
                | Rule::Shared(_)
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
            Rule::Container(rule) => rule.kinds(),
            Rule::Protocol(rule) => rule.kinds(),
            Rule::Pattern(rule) => rule.kinds(),
            Rule::Annotation(rule) => rule.kinds(),
            Rule::OutsideResult(rule) => rule.kinds(),
            Rule::Library(rule) => rule.kinds(),
            Rule::ClassTest(_) => None,
            Rule::SetName { .. } => Some(SET_NAME_KINDS),
            Rule::CallMetaclass { .. }
            | Rule::StatementMade
            | Rule::TypeBase { .. }
            | Rule::CallTypeMetaclass { .. } => Some(CLASS_KINDS),
            Rule::CallBackObject { .. } => Some(CALLED_BACK_KINDS),
            Rule::SpecialMethodOf { .. } => Some(SPECIAL_METHOD_KINDS),
            Rule::CallProtocol { .. } => Some(SET_NAME_KINDS),
            Rule::SequenceLength { .. } => Some(CONTAINER_KINDS),
            Rule::MembersOf { .. } => Some(OWNER_OR_INSTANCE_KINDS),
            Rule::PropertyReceiver { .. } => Some(PROPERTY_KINDS),
            Rule::BindClass { .. } => Some(OWNER_KINDS),
            Rule::BindType { .. } | Rule::SuperGiven { .. } => Some(SET_NAME_KINDS),
            Rule::LoadByPattern(_) => Some(PATTERN_KINDS),
            Rule::TypeBases { .. } => Some(CONTAINER_KINDS),
            Rule::SuperMetaclass { .. } => Some(CLASS_KINDS),
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
            Rule::Container(ref rule) => rule.captured(),
            Rule::Protocol(ref rule) => rule.captured(),
            Rule::Pattern(ref rule) => rule.captured(),
            Rule::Outside(_) => Vec::new(),
            Rule::Annotation(ref rule) => rule.captured(),
            Rule::OutsideResult(ref rule) => rule.captured(),
            Rule::Library(_) => Vec::new(),
            Rule::ClassTest(ref rule) => rule.captured(),
            Rule::Bases { class, .. }
            | Rule::KeywordCandidate { class }
            | Rule::MemberOfMetaclass { class, .. }
            | Rule::PythonNew { class, .. }
            | Rule::New { class, .. }
            | Rule::SetName { class, .. }
            | Rule::CallMetaclass { class }
            | Rule::InitStatementClass { class, .. } => vec![class],
            Rule::StatementNew { meta, .. } => vec![meta],
            Rule::Bind { receiver, .. } => receiver.into_iter().collect(),
            Rule::Binds(_) => Vec::new(),
            Rule::Shared(_) => {
                unreachable!("the captured objects of a shared record are kept apart")
            }
            Rule::BindFallback { receiver, .. } => vec![receiver],
            Rule::TypeMethod { object, .. }
            | Rule::Itself { object, .. }
            | Rule::DeliverStore { object, .. }
            | Rule::DeliverDelete { object, .. } => vec![object],
            Rule::ClassAttribute { class, .. } | Rule::MetaclassProtocol { class, .. } => {
                vec![class]
            }
            Rule::CallBackObject { .. }
            | Rule::SpecialMethodOf { .. }
            | Rule::CallProtocol { .. }
            | Rule::SequenceLength { .. }
            | Rule::CallEach { .. }
            | Rule::ImplicitMethod { .. }
            | Rule::PropertyReceiver { .. } => Vec::new(),
            Rule::DerivedProperty { property, .. } => vec![property],
            Rule::BindClass { method, .. } | Rule::BindType { method, .. } => vec![method],
            Rule::BindTo { owner, .. } => vec![owner],
            Rule::Reversed { result, .. } => vec![result],
            Rule::ReversedSequence { object, result, .. } => vec![object, result],
            Rule::ReverseSequence { object, .. }
            | Rule::WhenDefaultMemberOnType { object, .. }
            | Rule::RunDefaultAction { object, .. }
            | Rule::LoadMember { object, .. }
            | Rule::MemberField { object, .. } => vec![object],
            Rule::NamespaceElement {
                object, container, ..
            } => vec![object, container],
            Rule::AddNamespace { .. } | Rule::MembersOf { .. } => Vec::new(),
            Rule::SuperAfterOutside { class, .. }
            | Rule::SuperObject { class, .. }
            | Rule::SuperGiven { class, .. }
            | Rule::SuperAcceptedBy { class, .. } => vec![class],
            Rule::SuperMetaclass { sup, .. } => vec![sup],
            Rule::LoadByPattern(_)
            | Rule::SuperClass { .. }
            | Rule::AnalysedHook { .. }
            | Rule::StatementMade
            | Rule::TypeBases { .. }
            | Rule::TypeBase { .. }
            | Rule::CallTypeMetaclass { .. } => Vec::new(),
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

impl State {
    pub(super) fn rule(&mut self, rule: Rule) -> RuleId {
        if let Some(id) = self.released_rules.pop() {
            self.rules[id.index()] = rule;
            return id;
        }
        let id = RuleId(u32::try_from(self.rules.len()).expect("fewer than 2^32 rules"));
        self.rules.push(rule);
        id
    }

    pub(super) fn attach_rule(&mut self, graph: &mut Graph, node: NodeId, rule: Rule) {
        let id = self.rule(rule);
        if graph.attach(self, node, id) == Attached::Released {
            self.released_rules.push(id);
        }
    }

    fn results(&self, rule: &Rule) -> Vec<NodeId> {
        match *rule {
            Rule::Container(ref rule) => self.container_results(rule),
            Rule::Protocol(ref rule) => self.protocol_results(rule),
            Rule::Pattern(ref rule) => self.pattern_results(rule),
            Rule::Outside(ref rule) => rule.results(),
            Rule::Annotation(ref rule) => rule.results(),
            Rule::OutsideResult(ref rule) => rule.results(),
            Rule::Library(ref rule) => rule.results(),
            Rule::ClassTest(ref rule) => self.class_test_results(rule),
            Rule::Call(call)
            | Rule::PythonNew { call, .. }
            | Rule::PythonInstance { call }
            | Rule::New { call, .. } => self.calls[call.index()].dst.into_iter().collect(),
            Rule::TypeMethod { implicit, .. } => {
                self.calls[implicit.index()].dst.into_iter().collect()
            }
            Rule::Binds(binds) => self.binds_results(binds),
            Rule::Shared(shared) => self.shared_results(shared),
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
            Rule::SpecialMethodOf { dst, .. } => vec![dst],
            Rule::DeliverStore { .. }
            | Rule::DeliverDelete { .. }
            | Rule::CallBackObject { .. }
            | Rule::CallProtocol { .. } => Vec::new(),
            Rule::MetaclassProtocol { implicit: call, .. } | Rule::CallEach { call } => {
                self.calls[call.index()].dst.into_iter().collect()
            }
            Rule::ImplicitMethod { field: dst, .. }
            | Rule::BindClass { dst, .. }
            | Rule::BindType { dst, .. }
            | Rule::BindTo { dst, .. } => vec![dst],
            Rule::PropertyReceiver { dst, .. } | Rule::DerivedProperty { dst, .. } => {
                dst.into_iter().collect()
            }
            Rule::SuperClass { call, .. } => self.calls[call.index()].dst.into_iter().collect(),
            Rule::SuperAfterOutside { dst, .. }
            | Rule::SuperObject { dst, .. }
            | Rule::SuperGiven { dst, .. }
            | Rule::SuperAcceptedBy { dst, .. } => vec![dst],
            Rule::SuperMetaclass { load, .. } => self.access_result(load).into_iter().collect(),
            Rule::AnalysedHook { call } => self.calls[call.index()].dst.into_iter().collect(),
            Rule::LoadByPattern(_)
            | Rule::SequenceLength { .. }
            | Rule::InitStatementClass { .. }
            | Rule::StatementNew { .. }
            | Rule::StatementMade
            | Rule::TypeBases { .. }
            | Rule::TypeBase { .. }
            | Rule::CallTypeMetaclass { .. } => Vec::new(),
            Rule::Reversed { dst, .. } | Rule::ReversedSequence { items: dst, .. } => vec![dst],
            Rule::ReverseSequence { implicit, .. } => {
                self.calls[implicit.index()].dst.into_iter().collect()
            }
            Rule::WhenDefaultMemberOnType { result, .. }
            | Rule::RunDefaultAction { result, .. } => result.into_iter().collect(),
            Rule::NamespaceElement { unknown: dst, .. }
            | Rule::AddNamespace { dst }
            | Rule::MembersOf { dst, .. }
            | Rule::LoadMember { values: dst, .. }
            | Rule::MemberField { values: dst, .. } => vec![dst],
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
            Rule::Binds(binds) => self.binds_apply(graph, binds, object),
            Rule::Shared(shared) => {
                let (rule, items) = self.shared_items(shared);
                for item in items {
                    let each = rule.each(item);
                    self.apply_one(graph, &each, object);
                }
            }
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
                unless,
            } => {
                let unless = self.unless_of(unless);
                self.type_method(graph, object, owner, name, implicit, unless)
            }
            Rule::SetName {
                class,
                name,
                caller,
                site,
            } => self.set_name(graph, object, class, name, caller, site),
            Rule::CallMetaclass { class } => self.call_metaclass(graph, object, class),
            Rule::AnalysedHook { call } => self.analysed_hook(graph, object, call),
            Rule::InitStatementClass { class, call } => {
                self.call_dunder(graph, class, "__init__", call, None, Unless::Nothing)
            }
            Rule::StatementNew { meta, call } => self.statement_new(graph, object, meta, call),
            Rule::StatementMade => self.statement_made(graph, object),
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
            Rule::SpecialMethodOf {
                method,
                forwarded,
                dst,
                caller,
                site,
            } => self.special_method_of(graph, object, method, forwarded, dst, caller, site),
            Rule::CallProtocol { plan, caller, site } => {
                self.call_protocol(graph, object, plan, caller, site)
            }
            Rule::SequenceLength { caller, site } => {
                self.sequence_length(graph, object, caller, site)
            }
            Rule::Reversed {
                call,
                dst,
                result,
                iteration,
            } => self.reversed(graph, object, call, dst, result, iteration),
            Rule::ReversedSequence {
                object: owner,
                call,
                result,
                ..
            } => self.reversed_sequence(graph, object, owner, call, result),
            Rule::ReverseSequence {
                object: owner,
                methods,
                implicit,
                reversing,
            } => self.reverse_sequence(graph, owner, methods, implicit, reversing),
            Rule::WhenDefaultMemberOnType {
                object: owner,
                name,
                action,
                result,
            } => self.when_default_member_on_type(graph, object, owner, name, action, result),
            Rule::RunDefaultAction {
                object: owner,
                action,
                ..
            } => self.run_default_action(graph, owner, action),
            Rule::NamespaceElement {
                object: owner,
                container,
                ..
            } => self.namespace_element(graph, object, owner, container),
            Rule::AddNamespace { dst } => self.add_namespace(graph, object, dst),
            Rule::MembersOf { access, .. } => self.members_of(graph, object, access),
            Rule::LoadMember {
                object: owner,
                access,
                ..
            } => self.load_member(graph, object, owner, access),
            Rule::MemberField {
                object: owner,
                values,
            } => self.member_field(graph, object, owner, values),
            Rule::MetaclassProtocol {
                class,
                name,
                implicit,
                unless,
            } => {
                let unless = self.unless_of(unless);
                self.metaclass_protocol(graph, object, class, name, implicit, unless)
            }
            Rule::CallEach { call } => self.call(graph, object, call),
            Rule::ImplicitMethod { field, kind, site } => {
                self.implicit_method(graph, object, field, kind, site)
            }
            Rule::PropertyReceiver { rule, dst } => {
                self.property_receiver(graph, object, rule, dst)
            }
            Rule::DerivedProperty { rule, property, .. } => {
                self.run_property_rule(graph, property, rule)
            }
            Rule::BindClass { method, dst } => self.bind(graph, method, Some(object), dst, None),
            Rule::BindType { method, dst } => self.bind_type(graph, object, method, dst),
            Rule::LoadByPattern(access) => self.load_by_pattern(graph, object, access),
            Rule::SuperClass {
                object: node,
                call,
                explicit,
            } => self.super_class(graph, object, node, call, explicit),
            Rule::SuperAfterOutside { class, dst } => {
                self.super_after_outside(graph, object, class, dst)
            }
            Rule::SuperObject { class, dst } => self.super_object_rule(graph, object, class, dst),
            Rule::SuperGiven { class, dst } => self.super_given(graph, object, class, dst),
            Rule::SuperAcceptedBy { class, given, dst } => {
                self.super_accepted_by(graph, object, class, given, dst)
            }
            Rule::TypeBases { call, made } => self.type_bases(graph, object, call, made),
            Rule::TypeBase { call, made } => self.type_base(graph, object, call, made),
            Rule::CallTypeMetaclass { call } => self.call(graph, object, call),
            Rule::SuperMetaclass { sup, load } => self.super_metaclass(graph, object, sup, load),
            Rule::BindTo { owner, dst } => {
                let bound = if matches!(
                    self.objects.get(object),
                    crate::engine::objects::Object::Function(_)
                ) {
                    self.bound_method(graph, owner, object)
                } else {
                    object
                };
                self.add_object(graph, dst, bound);
            }
            Rule::Container(ref rule) => self.container_apply(graph, rule, object),
            Rule::Protocol(ref rule) => self.protocol_apply(graph, rule, object),
            Rule::Pattern(ref rule) => self.pattern_apply(graph, rule, object),
            Rule::Outside(ref rule) => self.outside_apply(graph, rule, object),
            Rule::Annotation(ref rule) => self.annotation_apply(graph, rule, object),
            Rule::OutsideResult(ref rule) => self.outside_result_apply(graph, rule, object),
            Rule::Library(rule) => self.library_apply(graph, rule, object),
            Rule::ClassTest(ref rule) => self.class_test_apply(graph, rule, object),
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

impl Rules<RuleId> for State {
    fn apply(&mut self, graph: &mut Graph, rule: RuleId, objects: &[ObjId]) {
        let found = self.rules[rule.index()].clone();
        if let Rule::Deliveries(id) = found {
            self.deliveries_apply(graph, id, objects);
            return;
        }
        if let Rule::Container(container) = &found
            && container.batches()
            && objects.len() > 1
        {
            self.container_apply_each(graph, container, objects);
            return;
        }
        if !found.each() {
            for &object in objects {
                self.apply_one(graph, &found, object);
            }
            return;
        }
        let mask = found.kinds().map(kinds_mask);
        for &object in objects {
            if let Some(mask) = mask
                && self.objects.get(object).kind().mask() & mask == 0
            {
                continue;
            }
            self.apply_one(graph, &found, object);
        }
    }

    fn saturate(&mut self, graph: &mut Graph, rule: RuleId) {
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
    }

    fn kinds(&self, rule: RuleId) -> Option<KindMask> {
        self.rules[rule.index()].kinds().map(kinds_mask)
    }

    fn captures_opaque(&self, _graph: &Graph, rule: RuleId) -> bool {
        let captured = match self.rules[rule.index()] {
            Rule::Shared(shared) => self.shared_captured(shared),
            ref rule => rule.captured(),
        };
        captured
            .into_iter()
            .any(|object| State::opaque(self, object))
    }

    fn opaque(&self, object: ObjId) -> bool {
        State::opaque(self, object)
    }

    fn between_rounds(&mut self, graph: &mut Graph) -> bool {
        self.unknown_classes(graph)
    }

    fn wake(&mut self, graph: &mut Graph, watch: WatchId) {
        let waiting = self.waiting.remove(&watch).unwrap_or_default();
        let mut receivers_by_rule: OrderedMap<u32, Vec<ObjId>> = OrderedMap::default();
        for (rule, receiver) in waiting {
            receivers_by_rule.entry(rule).or_default().push(receiver);
        }
        for (rule, receivers) in receivers_by_rule {
            let rule = self.waiting_rules[rule as usize].clone();
            for receiver in receivers {
                self.run_waiting(graph, rule.clone(), receiver);
            }
        }
    }

    fn firing(&mut self, _graph: &mut Graph) {}
}

const _: () = assert!(std::mem::size_of::<Rule>() == 24);
