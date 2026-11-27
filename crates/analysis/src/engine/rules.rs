use pycg_solver::{KindMask, NodeId, ObjId, Rules, WatchId};

use crate::engine::annotations::AnnotationRule;
use crate::engine::attributes::{
    ANALYSED_METHODS, AccessId, AccessorsId, DeliveriesId, HookCallsId, HooksId, WritesId,
};
use crate::engine::builtin_rules::DynamicId;
use crate::engine::builtin_rules::PropertyRule;
use crate::engine::containers::ContainerRule;
use crate::engine::containers::IterationId;
use crate::engine::hierarchy::{BindsId, Unless};
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
use crate::engine::trace::{RuleInfo, Trace};
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
        unless: Unless,
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
    Protocol(ProtocolRule),
    Pattern(PatternRule),
    Outside(OutsideRule),
    Annotation(AnnotationRule),
    OutsideResult(OutsideResultRule),
    Library(LibraryRule),
    ClassTest(ClassTestRule),
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
    fn key(&self) -> &'static str {
        match self {
            Rule::Call(_) => "Call",
            Rule::Bases { .. } => "_Bases",
            Rule::Bind { .. } => "_Bind",
            Rule::Binds(_) => "_Binds",
            Rule::KeywordCandidate { .. } => "Each:Hierarchy._keyword_candidate",
            Rule::MemberOfMetaclass { .. } => "Each:Hierarchy._member_of_metaclass",
            Rule::BindFallback { .. } => "Each:Hierarchy._bind_fallback",
            Rule::WrapFallback { .. } => "Each:Hierarchy._wrap_fallback",
            Rule::PythonNew { .. } => "Each:Analysis._python_new",
            Rule::PythonInstance { .. } => "Each:Analysis._python_instance",
            Rule::New { .. } => "Each:Analysis._new",
            Rule::ReturnedOfClass(_) => "Each:Analysis._of_class",
            Rule::Shared(_) => "Shared",
            Rule::ReturnedByItsNew(_) => "Each:_Returned.by_its_new",
            Rule::ReturnedRelease(_) => "Each:_Returned.release",
            Rule::ReturnedByNew(_) => "Each:_Returned.by_new",
            Rule::TypeMethod { .. } => "Each:Analysis._type_method",
            Rule::SetName { .. } => "Each:Analysis._set_name",
            Rule::CallMetaclass { .. } => "Each:Analysis._call_metaclass",
            Rule::AnalysedHook { .. } => "Each:Attributes._call_analysed_hook",
            Rule::InitStatementClass { .. } => "Each:Analysis._init_statement_class",
            Rule::StatementNew { .. } => "Each:Analysis._statement_new",
            Rule::StatementMade => "Each:Analysis._statement_made",
            Rule::AddInexact { .. } => "Each:Containers._add_inexact",
            Rule::Container(rule) => rule.key(),
            Rule::Protocol(rule) => rule.key(),
            Rule::Pattern(rule) => rule.key(),
            Rule::Outside(rule) => rule.key(),
            Rule::Annotation(rule) => rule.key(),
            Rule::OutsideResult(rule) => rule.key(),
            Rule::Library(rule) => rule.key(),
            Rule::ClassTest(rule) => rule.key(),
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
            Rule::SpecialMethodOf { .. } => "Each:BuiltinRules._special_method_of",
            Rule::CallProtocol { .. } => "Each:Outside._call_protocol",
            Rule::SequenceLength { .. } => "Each:BuiltinRules._sequence_length",
            Rule::Reversed { .. } => "Each:BuiltinRules._reversed",
            Rule::ReversedSequence { .. } => "Each:BuiltinRules._reversed_sequence",
            Rule::ReverseSequence { .. } => "Each:BuiltinRules._reverse_sequence",
            Rule::WhenDefaultMemberOnType { .. } => "Each:Reflection._when_default_member_on_type",
            Rule::RunDefaultAction { .. } => "Each:Reflection._run_default_action",
            Rule::NamespaceElement { .. } => "Each:Reflection._namespace_element",
            Rule::AddNamespace { .. } => "Each:Reflection.add_namespace",
            Rule::MembersOf { .. } => "Each:Reflection._members_of",
            Rule::LoadMember { .. } => "Each:Reflection._load_member",
            Rule::MemberField { .. } => "Each:Reflection._member_field",
            Rule::MetaclassProtocol { .. } => "Each:Outside._metaclass_protocol",
            Rule::CallEach { .. } => "Each:Analysis.call",
            Rule::ImplicitMethod { .. } => "Each:BuiltinRules._implicit_method",
            Rule::PropertyReceiver { .. } => "Each:BuiltinRules._property_receiver",
            Rule::DerivedProperty { .. } => "Each:BuiltinRules._derived_property",
            Rule::BindClass { .. } => "Each:BuiltinRules._bind_class",
            Rule::BindType { .. } => "Each:BuiltinRules._bind_type",
            Rule::BindTo { .. } => "Each:Hierarchy._bind_to",
            Rule::LoadByPattern(_) => "Each:Patterns.load_by_pattern",
            Rule::SuperClass { .. } => "Each:BuiltinRules._super_class",
            Rule::SuperAfterOutside { .. } => "Each:BuiltinRules._super_after_outside",
            Rule::SuperObject { .. } => "Each:BuiltinRules._super_object",
            Rule::SuperGiven { .. } => "Each:BuiltinRules._super_given",
            Rule::SuperAcceptedBy { .. } => "Each:BuiltinRules._super_accepted_by",
            Rule::TypeBases { .. } => "Each:BuiltinRules._type_bases",
            Rule::TypeBase { .. } => "Each:BuiltinRules._type_base",
            Rule::CallTypeMetaclass { .. } => "Each:BuiltinRules._call_type_metaclass",
            Rule::SuperMetaclass { .. } => "Each:Attributes._super_metaclass",
        }
    }

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
            Rule::Shared(shared) => self.shared_captured(shared),
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
                ref unless,
            } => self.type_method(graph, object, owner, name, implicit, unless.clone()),
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
                ref unless,
            } => self.metaclass_protocol(graph, object, class, name, implicit, unless.clone()),
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

impl<T: Trace> Rules<RuleId> for State<T> {
    fn apply(&mut self, graph: &mut Graph, rule: RuleId, objects: &[ObjId]) {
        let found = self.rules[rule.index()].clone();
        if let Rule::Deliveries(id) = found {
            self.trace.apply(rule, objects);
            self.deliveries_apply(graph, id, objects);
            self.trace.applied();
            return;
        }
        if let Rule::Container(container) = &found
            && container.batches()
            && objects.len() > 1
        {
            self.trace.apply(rule, objects);
            self.container_apply_each(graph, container, objects);
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
        self.trace.between_rounds();
        let (answer, unknown) = self.unknown_classes(graph);
        self.trace.between_rounds_done(answer, &unknown);
        answer
    }

    fn wake(&mut self, graph: &mut Graph, watch: WatchId) {
        self.trace.wake(watch);
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
        self.trace.woken();
    }

    fn firing(&mut self, graph: &mut Graph) {
        self.trace.fire(graph, &self.named_nodes);
    }
}
