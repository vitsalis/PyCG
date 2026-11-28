use pycg_solver::{NodeId, ObjId};
use pycg_stubs::DefinitionKind;
use rustc_hash::{FxHashMap, FxHashSet};

use crate::builder::patterns::{PercentField, percent_spans};
use crate::engine::containers::{ContainerOrigin, IterationId};
use crate::engine::hierarchy::Unless;
use crate::engine::objects::{Kind, Literal, Object, kinds_mask};
use crate::engine::outside_calls::PlanId;
use crate::engine::outside_types::TypeOrigin;
use crate::engine::rules::{Rule, RuleId};
use crate::engine::semantics::{CallId, Role, SiteKey};
use crate::engine::symbols::Sym;
use crate::engine::{Graph, OrderedMap, State};
use crate::models::{CONTAINER_CLASSES, LENGTH_HINT, builtin_kind};

const COMPARISON_METHODS: [&str; 6] = ["__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__"];
const EQUALITIES: [&str; 2] = ["__eq__", "__ne__"];
const CONTAINS: &str = "__contains__";

const OPERAND_KINDS: &[Kind] = &[Kind::Instance, Kind::Class, Kind::Container, Kind::Typed];
const OPERAND_CONSTANT_KINDS: &[Kind] = &[
    Kind::Instance,
    Kind::Class,
    Kind::Container,
    Kind::Typed,
    Kind::Const,
];
const MEMBERSHIP_KINDS: &[Kind] = &[
    Kind::Instance,
    Kind::Class,
    Kind::Container,
    Kind::Generator,
    Kind::External,
    Kind::Typed,
];
const MEMBERSHIP_CONSTANT_KINDS: &[Kind] = &[
    Kind::Instance,
    Kind::Class,
    Kind::Container,
    Kind::Generator,
    Kind::External,
    Kind::Typed,
    Kind::Const,
];
const RECEIVER_KINDS: &[Kind] = &[Kind::Instance, Kind::Class];
const CONTAINER_KINDS: &[Kind] = &[Kind::Container];
const CONST_KINDS: &[Kind] = &[Kind::Const];
const CLASS_KINDS: &[Kind] = &[Kind::Class];
const REPR_CONTAINERS: [&str; 5] = ["list", "tuple", "set", "frozenset", "dict"];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct FieldsId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Conversion {
    Str,
    Repr,
    Format,
}

impl Conversion {
    pub(crate) fn of(kind: &str) -> Conversion {
        match kind {
            "str" => Conversion::Str,
            "repr" => Conversion::Repr,
            "format" => Conversion::Format,
            _ => panic!("no conversion {kind}"),
        }
    }

    fn name(self) -> &'static str {
        match self {
            Conversion::Str => "str",
            Conversion::Repr => "repr",
            Conversion::Format => "format",
        }
    }

    fn plan(self) -> &'static [(&'static str, &'static [&'static str])] {
        match self {
            Conversion::Str => &[("__str__", &[]), ("__repr__", &["__str__"])],
            Conversion::Repr => &[("__repr__", &[])],
            Conversion::Format => &[
                ("__format__", &[]),
                ("__str__", &["__format__"]),
                ("__repr__", &["__format__", "__str__"]),
            ],
        }
    }
}

fn is_a(kind: Kind, kinds: &[Kind]) -> bool {
    kind.mask() & kinds_mask(kinds) != 0
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct OperatorId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct ComparisonId(u32);

fn next_id(length: usize) -> u32 {
    u32::try_from(length).expect("fewer than 2^32 protocol records")
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
enum Family {
    List,
    Tuple,
    Deque,
    Set,
    Dict,
}

impl Family {
    fn of(kind: &str) -> Option<Family> {
        match kind {
            "list" => Some(Family::List),
            "tuple" => Some(Family::Tuple),
            "collections.deque" => Some(Family::Deque),
            "set" | "frozenset" => Some(Family::Set),
            _ if builtin_kind(kind) == "dict" => Some(Family::Dict),
            _ => None,
        }
    }

    fn is_sequence(self) -> bool {
        matches!(self, Family::List | Family::Tuple | Family::Deque)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum CompareSide {
    Element,
    Value,
}

impl CompareSide {
    fn name(self) -> &'static str {
        match self {
            CompareSide::Element => "element",
            CompareSide::Value => "value",
        }
    }
}

struct Operator {
    left: Option<NodeId>,
    right: Option<NodeId>,
    method: Sym,
    reflected: Option<Sym>,
    inplace: bool,
    dst: NodeId,
    unary: bool,
    caller: Sym,
    site: Sym,
    extra: Vec<NodeId>,
    calls: [Option<CallId>; 2],
    membership: Option<IterationId>,
    elements: Option<NodeId>,
    compare_calls: [Option<(Option<NodeId>, CallId)>; 2],
    classes: FxHashSet<ObjId>,
    comparison: Option<ComparisonId>,
    compared_value: bool,
    hashed_value: bool,
}

#[derive(Clone, Copy)]
enum ComparisonSite {
    Operator(OperatorId),
    Call { caller: Sym, site: Sym },
}

struct Comparison {
    method: Sym,
    site: ComparisonSite,
    families: OrderedMap<Family, ([NodeId; 2], [bool; 2])>,
}

#[derive(Default)]
pub(crate) struct Protocols {
    operators: Vec<Operator>,
    comparisons: Vec<Comparison>,
    iterated: FxHashMap<OperatorId, (NodeId, NodeId)>,
    converted: FxHashSet<NodeId>,
    repr_reaches: FxHashMap<ObjId, NodeId>,
    fields: Vec<Vec<(Literal, Option<Conversion>)>>,
    handlers: FxHashSet<(ObjId, NodeId)>,
}

#[derive(Clone, Debug)]
pub(crate) enum ProtocolRule {
    Operand {
        operator: OperatorId,
        is_left: bool,
        kinds: &'static [Kind],
    },
    SearchedType(OperatorId),
    PythonContains(OperatorId),
    CompareMember(OperatorId),
    CallEq(CallId),
    CompareProtocol {
        plan: PlanId,
        comparison: ComparisonId,
    },
    Arrive {
        comparison: ComparisonId,
        is_left: bool,
    },
    ConvertContainer {
        reached: NodeId,
        caller: Sym,
        site: Sym,
    },
    ReachNested(NodeId),
    PercentFormat {
        value: NodeId,
        caller: Sym,
        site: Sym,
    },
    Percent {
        fields: FieldsId,
        caller: Sym,
        site: Sym,
    },
    Finished(NodeId),
    Await {
        call: CallId,
        iterator: NodeId,
        dst: NodeId,
    },
    AwaitType {
        object: ObjId,
        dst: NodeId,
    },
    AwaitedItself {
        object: ObjId,
        dst: NodeId,
    },
    With {
        dst: Option<NodeId>,
        exited: Option<NodeId>,
        enter: CallId,
        leave: CallId,
        is_async: bool,
    },
    Raise(CallId),
    Handler(NodeId),
}

pub(crate) struct OperatorCall<'a> {
    pub left: Option<NodeId>,
    pub right: Option<NodeId>,
    pub method: &'a str,
    pub reflected: Option<&'a str>,
    pub inplace: bool,
    pub dst: NodeId,
    pub caller: Sym,
    pub site: Sym,
    pub unary: bool,
    pub constants: bool,
    pub extra: Vec<NodeId>,
}

impl ProtocolRule {
    pub(crate) fn each(&self) -> bool {
        !matches!(self, ProtocolRule::Operand { .. })
    }

    pub(crate) fn kinds(&self) -> Option<&'static [Kind]> {
        match *self {
            ProtocolRule::Operand { kinds, .. } => Some(kinds),
            ProtocolRule::CompareProtocol { .. } => Some(RECEIVER_KINDS),
            ProtocolRule::ConvertContainer { .. }
            | ProtocolRule::ReachNested(_)
            | ProtocolRule::Arrive { .. } => Some(CONTAINER_KINDS),
            ProtocolRule::PercentFormat { .. } => Some(CONST_KINDS),
            ProtocolRule::Raise(_) => Some(CLASS_KINDS),
            ProtocolRule::SearchedType(_)
            | ProtocolRule::PythonContains(_)
            | ProtocolRule::CompareMember(_)
            | ProtocolRule::CallEq(_)
            | ProtocolRule::Percent { .. }
            | ProtocolRule::Finished(_)
            | ProtocolRule::Await { .. }
            | ProtocolRule::AwaitType { .. }
            | ProtocolRule::AwaitedItself { .. }
            | ProtocolRule::With { .. }
            | ProtocolRule::Handler(_) => None,
        }
    }

    pub(crate) fn captured(&self) -> Vec<ObjId> {
        match *self {
            ProtocolRule::AwaitType { object, .. } | ProtocolRule::AwaitedItself { object, .. } => {
                vec![object]
            }
            _ => Vec::new(),
        }
    }
}

fn operand_kinds(membership: bool, constants: bool) -> &'static [Kind] {
    match (membership, constants) {
        (false, false) => OPERAND_KINDS,
        (false, true) => OPERAND_CONSTANT_KINDS,
        (true, false) => MEMBERSHIP_KINDS,
        (true, true) => MEMBERSHIP_CONSTANT_KINDS,
    }
}

pub(super) fn reflected_comparison(method: &str) -> &'static str {
    match method {
        "__lt__" => "__gt__",
        "__gt__" => "__lt__",
        "__le__" => "__ge__",
        "__ge__" => "__le__",
        _ => unreachable!("an ordering comparison has a reflection"),
    }
}

fn is_container_class(kind: &str) -> bool {
    CONTAINER_CLASSES.iter().any(|(name, _)| *name == kind)
}

fn index_of(id: u32) -> usize {
    id as usize
}

impl State {
    fn protocol_rule(&mut self, rule: ProtocolRule) -> RuleId {
        self.rule(Rule::Protocol(Box::new(rule)))
    }

    fn operator(&self, id: OperatorId) -> &Operator {
        &self.protocols.operators[index_of(id.0)]
    }

    fn operator_mut(&mut self, id: OperatorId) -> &mut Operator {
        &mut self.protocols.operators[index_of(id.0)]
    }

    pub(super) fn protocol_results(&self, rule: &ProtocolRule) -> Vec<NodeId> {
        match *rule {
            ProtocolRule::Operand { operator, .. } => {
                let operator = self.operator(operator);
                if self.symbols.text(operator.method) == CONTAINS {
                    Vec::new()
                } else {
                    vec![operator.dst]
                }
            }
            ProtocolRule::ConvertContainer { reached: node, .. }
            | ProtocolRule::ReachNested(node)
            | ProtocolRule::Finished(node)
            | ProtocolRule::Await { dst: node, .. }
            | ProtocolRule::AwaitType { dst: node, .. }
            | ProtocolRule::AwaitedItself { dst: node, .. }
            | ProtocolRule::Handler(node) => vec![node],
            ProtocolRule::With { dst, .. } => dst.into_iter().collect(),
            ProtocolRule::SearchedType(_)
            | ProtocolRule::PythonContains(_)
            | ProtocolRule::CompareMember(_)
            | ProtocolRule::CallEq(_)
            | ProtocolRule::CompareProtocol { .. }
            | ProtocolRule::Arrive { .. }
            | ProtocolRule::PercentFormat { .. }
            | ProtocolRule::Percent { .. }
            | ProtocolRule::Raise(_) => Vec::new(),
        }
    }

    pub(super) fn protocol_apply(&mut self, graph: &mut Graph, rule: &ProtocolRule, object: ObjId) {
        match *rule {
            ProtocolRule::Operand {
                operator,
                is_left,
                kinds,
            } => {
                if is_a(self.objects.get(object).kind(), kinds) {
                    self.operand(graph, object, operator, is_left);
                }
            }
            ProtocolRule::SearchedType(operator) => self.searched_type(graph, object, operator),
            ProtocolRule::PythonContains(operator) => self.compare_value(graph, operator),
            ProtocolRule::CompareMember(operator) => self.compare_member(graph, object, operator),
            ProtocolRule::CallEq(call) => self.call_eq(graph, object, call),
            ProtocolRule::CompareProtocol { plan, comparison } => {
                let (caller, site, compare) =
                    match self.protocols.comparisons[index_of(comparison.0)].site {
                        ComparisonSite::Operator(operator) => {
                            let operator = self.operator(operator);
                            (operator.caller, operator.site, true)
                        }
                        ComparisonSite::Call { caller, site } => (caller, site, false),
                    };
                self.call_protocol_at(graph, object, plan, caller, site, compare);
            }
            ProtocolRule::Arrive {
                comparison,
                is_left,
            } => self.arrive(graph, comparison, object, is_left),
            ProtocolRule::ConvertContainer {
                reached,
                caller,
                site,
            } => self.convert_container(graph, object, reached, caller, site),
            ProtocolRule::ReachNested(node) => {
                if REPR_CONTAINERS.contains(&self.container_kind(object)) {
                    let reach = self.repr_reach(graph, object);
                    self.add_edge(graph, reach, node);
                }
            }
            ProtocolRule::PercentFormat {
                value,
                caller,
                site,
            } => self.percent_format(graph, object, value, caller, site),
            ProtocolRule::Percent {
                fields,
                caller,
                site,
            } => self.percent(graph, object, fields, caller, site),
            ProtocolRule::Finished(dst) => self.finished(graph, object, dst),
            ProtocolRule::Await {
                call,
                iterator,
                dst,
            } => self.awaited(graph, object, call, iterator, dst),
            ProtocolRule::AwaitType {
                object: awaited,
                dst,
            } => {
                if self.objects.is_class(object) {
                    let python = self.python_method(graph, object, "__await__");
                    let rule = self.protocol_rule(ProtocolRule::AwaitedItself {
                        object: awaited,
                        dst,
                    });
                    self.attach(graph, python, rule);
                } else {
                    self.add_object(graph, dst, awaited);
                }
            }
            ProtocolRule::AwaitedItself {
                object: awaited,
                dst,
            } => self.add_object(graph, dst, awaited),
            ProtocolRule::With {
                dst,
                exited,
                enter,
                leave,
                is_async,
            } => self.with(graph, object, dst, exited, enter, leave, is_async),
            ProtocolRule::Raise(call) => self.instantiate(graph, object, call),
            ProtocolRule::Handler(dst) => self.handler(graph, object, dst),
        }
    }

    pub(super) fn add_operator(&mut self, graph: &mut Graph, call: OperatorCall<'_>) {
        let id = OperatorId(next_id(self.protocols.operators.len()));
        let method = self.symbols.intern(call.method);
        let reflected = call.reflected.map(|name| self.symbols.intern(name));
        self.protocols.operators.push(Operator {
            left: call.left,
            right: call.right,
            method,
            reflected,
            inplace: call.inplace,
            dst: call.dst,
            unary: call.unary,
            caller: call.caller,
            site: call.site,
            extra: call.extra,
            calls: [None, None],
            membership: None,
            elements: None,
            compare_calls: [None, None],
            classes: FxHashSet::default(),
            comparison: None,
            compared_value: false,
            hashed_value: false,
        });
        let kinds = operand_kinds(call.method == CONTAINS, call.constants);
        for (node, is_left) in [(call.left, true), (call.right, false)] {
            if let Some(node) = node {
                let rule = self.protocol_rule(ProtocolRule::Operand {
                    operator: id,
                    is_left,
                    kinds,
                });
                self.attach(graph, node, rule);
            }
        }
    }

    fn operand(&mut self, graph: &mut Graph, object: ObjId, id: OperatorId, is_left: bool) {
        let object = match self.objects.get(object) {
            Object::Const { .. } => match self.string_constant_value(graph, object) {
                Some(typed) => typed,
                None => return,
            },
            _ => object,
        };
        let method = self.symbols.text(self.operator(id).method).to_owned();
        if method == CONTAINS {
            if is_left {
                self.contains(graph, object, id);
            }
            return;
        }
        let kind = self.objects.get(object).kind();
        if kind == Kind::Container && COMPARISON_METHODS.contains(&method.as_str()) {
            let comparison = self.operator_comparison(id);
            self.arrive(graph, comparison, object, is_left);
        }
        let operator = self.operator(id);
        let (dst, inplace) = (operator.dst, operator.inplace);
        let name = if is_left {
            method
        } else {
            let reflected = operator
                .reflected
                .expect("a binary operator has a reflection");
            self.symbols.text(reflected).to_owned()
        };
        match kind {
            Kind::Instance | Kind::Class => {
                let call = self.operator_call(graph, id, is_left);
                let mut unless = Unless::Nothing;
                if is_left && inplace {
                    let inplace = format!("__i{}", &name[2..]);
                    self.call_dunder(graph, object, &inplace, call, Some(dst), Unless::Nothing);
                    unless = Unless::Names(Box::from([self.symbols.intern(&inplace)]));
                }
                self.call_dunder(graph, object, &name, call, Some(dst), unless);
                if name == "__ne__" {
                    let unless = Unless::Names(Box::from([self.symbols.intern(&name)]));
                    self.call_dunder(graph, object, "__eq__", call, Some(dst), unless);
                }
            }
            Kind::Container if !is_container_class(self.container_kind(object)) => {
                self.combine(graph, object, id, is_left)
            }
            _ => {
                let operator = self.operator(id);
                let origin = TypeOrigin::Operator {
                    caller: operator.caller,
                    site: operator.site,
                    is_left,
                };
                self.typed_special(graph, object, &name, Some(dst), origin);
            }
        }
    }

    fn contains(&mut self, graph: &mut Graph, object: ObjId, id: OperatorId) {
        let kind = self.objects.get(object).kind();
        if matches!(kind, Kind::Instance | Kind::Class) {
            let call = self.operator_call(graph, id, true);
            let dst = self.operator(id).dst;
            self.call_dunder(graph, object, CONTAINS, call, Some(dst), Unless::Nothing);
            let membership = self.membership(graph, id);
            self.iterate(graph, object, membership);
            let types = match *self.objects.get(object) {
                Object::Instance { class, .. } => self.constant(graph, class),
                _ => self.objects.class(object).metaclass,
            };
            let rule = self.protocol_rule(ProtocolRule::SearchedType(id));
            self.attach(graph, types, rule);
        } else {
            let membership = self.membership(graph, id);
            self.iterate(graph, object, membership);
            self.compare_value(graph, id);
            if kind == Kind::Container && self.hashes_keys(object) {
                self.hash_value(graph, id);
            }
        }
    }

    fn compare_member(&mut self, graph: &mut Graph, element: ObjId, id: OperatorId) {
        if matches!(
            self.objects.get(element).kind(),
            Kind::Instance | Kind::Class
        ) {
            let right = self.operator(id).right;
            let call = self.compare_call(graph, id, CompareSide::Element, right);
            self.call_dunder(graph, element, "__eq__", call, None, Unless::Nothing);
        }
    }

    fn compare_value(&mut self, graph: &mut Graph, id: OperatorId) {
        let operator = self.operator(id);
        let Some(right) = operator.right else {
            return;
        };
        if operator.compared_value {
            return;
        }
        self.operator_mut(id).compared_value = true;
        self.membership(graph, id);
        let elements = self.operator(id).elements;
        let call = self.compare_call(graph, id, CompareSide::Value, elements);
        let rule = self.protocol_rule(ProtocolRule::CallEq(call));
        self.attach(graph, right, rule);
    }

    fn hash_value(&mut self, graph: &mut Graph, id: OperatorId) {
        let operator = self.operator(id);
        let Some(right) = operator.right else {
            return;
        };
        if operator.hashed_value {
            return;
        }
        let (caller, site) = (operator.caller, operator.site);
        self.operator_mut(id).hashed_value = true;
        self.add_hash(graph, right, caller, site, None);
    }

    fn searched_type(&mut self, graph: &mut Graph, class: ObjId, id: OperatorId) {
        if !self.objects.is_class(class) {
            self.compare_value(graph, id);
            return;
        }
        if !self.operator_mut(id).classes.insert(class) {
            return;
        }
        let python = self.python_method(graph, class, CONTAINS);
        let rule = self.protocol_rule(ProtocolRule::PythonContains(id));
        self.attach(graph, python, rule);
    }

    fn call_eq(&mut self, graph: &mut Graph, value: ObjId, call: CallId) {
        if matches!(self.objects.get(value).kind(), Kind::Instance | Kind::Class) {
            self.call_dunder(graph, value, "__eq__", call, None, Unless::Nothing);
        }
    }

    fn membership(&mut self, graph: &mut Graph, id: OperatorId) -> IterationId {
        if let Some(membership) = self.operator(id).membership {
            return membership;
        }
        let elements = self.node(graph, None);
        self.operator_mut(id).elements = Some(elements);
        let rule = self.protocol_rule(ProtocolRule::CompareMember(id));
        self.attach(graph, elements, rule);
        let operator = self.operator(id);
        let (caller, site) = (operator.caller, operator.site);
        let unless = Unless::Names(Box::from([self.symbols.intern(CONTAINS)]));
        let membership =
            self.new_iteration(graph, elements, caller, site, false, unless, "membership");
        self.operator_mut(id).membership = Some(membership);
        membership
    }

    fn operator_comparison(&mut self, id: OperatorId) -> ComparisonId {
        if let Some(comparison) = self.operator(id).comparison {
            return comparison;
        }
        let method = self.operator(id).method;
        let comparison = ComparisonId(next_id(self.protocols.comparisons.len()));
        self.protocols.comparisons.push(Comparison {
            method,
            site: ComparisonSite::Operator(id),
            families: OrderedMap::default(),
        });
        self.operator_mut(id).comparison = Some(comparison);
        comparison
    }

    pub(super) fn compare_containers(
        &mut self,
        graph: &mut Graph,
        items: NodeId,
        method: &str,
        caller: Sym,
        site: Sym,
    ) {
        let method = self.symbols.intern(method);
        let comparison = ComparisonId(next_id(self.protocols.comparisons.len()));
        self.protocols.comparisons.push(Comparison {
            method,
            site: ComparisonSite::Call { caller, site },
            families: OrderedMap::default(),
        });
        for is_left in [true, false] {
            let rule = self.protocol_rule(ProtocolRule::Arrive {
                comparison,
                is_left,
            });
            self.attach(graph, items, rule);
        }
    }

    fn compare_call(
        &mut self,
        graph: &mut Graph,
        id: OperatorId,
        side: CompareSide,
        other: Option<NodeId>,
    ) -> CallId {
        let index = side as usize;
        if let Some((compared, call)) = self.operator(id).compare_calls[index] {
            assert_eq!(compared, other, "`in` compares another node");
            return call;
        }
        let operator = self.operator(id);
        let (caller, site) = (operator.caller, operator.site);
        let key = SiteKey {
            caller,
            site,
            role: Role::Compare(self.symbols.intern(side.name())),
            implicit: true,
        };
        let call = self.site_call(graph, key, &[other], None, None);
        self.operator_mut(id).compare_calls[index] = Some((other, call));
        call
    }

    fn operator_call(&mut self, graph: &mut Graph, id: OperatorId, is_left: bool) -> CallId {
        let index = usize::from(!is_left);
        if let Some(call) = self.operator(id).calls[index] {
            return call;
        }
        let operator = self.operator(id);
        let args: Vec<Option<NodeId>> = if operator.unary {
            Vec::new()
        } else {
            let other = if is_left {
                operator.right
            } else {
                operator.left
            };
            std::iter::once(other)
                .chain(operator.extra.iter().map(|&node| Some(node)))
                .collect()
        };
        let key = SiteKey {
            caller: operator.caller,
            site: operator.site,
            role: Role::Operator(operator.method, is_left),
            implicit: true,
        };
        let call = self.site_call(graph, key, &args, None, None);
        self.operator_mut(id).calls[index] = Some(call);
        call
    }

    fn arrive(&mut self, graph: &mut Graph, id: ComparisonId, container: ObjId, is_left: bool) {
        let Some(family) = Family::of(self.container_kind(container)) else {
            return;
        };
        let comparison = &self.protocols.comparisons[index_of(id.0)];
        let ordering = !EQUALITIES.contains(&self.symbols.text(comparison.method));
        if ordering && family == Family::Dict {
            return;
        }
        let sides = match comparison.families.get(&family) {
            Some(&(sides, _)) => sides,
            None => {
                let sides = [self.node(graph, None), self.node(graph, None)];
                self.protocols.comparisons[index_of(id.0)]
                    .families
                    .insert(family, (sides, [false, false]));
                sides
            }
        };
        let side = usize::from(!is_left);
        let every = self.every(graph, container);
        self.add_edge(graph, every, sides[side]);
        if self.is_dict(container) {
            let keys = self.keys(graph, container);
            self.add_edge(graph, keys, sides[side]);
        }
        let present = &mut self.protocols.comparisons[index_of(id.0)]
            .families
            .get_mut(&family)
            .expect("a family that arrived")
            .1;
        if !present[side] {
            present[side] = true;
            if *present == [true, true] {
                self.join_comparison(graph, id, sides, family);
            }
        }
    }

    fn join_comparison(
        &mut self,
        graph: &mut Graph,
        id: ComparisonId,
        sides: [NodeId; 2],
        family: Family,
    ) {
        let elements = self.node(graph, None);
        let method = self.protocols.comparisons[index_of(id.0)].method;
        let mut steps = vec![(self.symbols.intern("__eq__"), Unless::Nothing)];
        let method_text = self.symbols.text(method).to_owned();
        if !EQUALITIES.contains(&method_text.as_str()) && family.is_sequence() {
            let reflected = self.symbols.intern(reflected_comparison(&method_text));
            steps.push((method, Unless::Nothing));
            steps.push((reflected, Unless::Names(Box::from([method]))));
        }
        let plan = self.new_plan(steps);
        let rule = self.protocol_rule(ProtocolRule::CompareProtocol {
            plan,
            comparison: id,
        });
        self.attach(graph, elements, rule);
        for node in sides {
            self.add_edge(graph, node, elements);
        }
    }

    fn combine(&mut self, graph: &mut Graph, object: ObjId, id: OperatorId, is_left: bool) {
        let kind = self.container_kind(object).to_owned();
        let operator = self.operator(id);
        let method = self.symbols.text(operator.method).to_owned();
        if !matches!(kind.as_str(), "list" | "tuple")
            || !matches!(method.as_str(), "__add__" | "__mul__")
        {
            return;
        }
        let (inplace, site, caller, right, dst) = (
            operator.inplace,
            operator.site,
            operator.caller,
            operator.right,
            operator.dst,
        );
        let concatenation = method == "__add__";
        if inplace && !is_left {
            return;
        }
        let result = if inplace && kind == "list" {
            object
        } else {
            let origin = ContainerOrigin::Operator(id);
            let result = self.container_at(graph, &kind, origin, site, None, false);
            if is_left && concatenation {
                self.copy_fields(graph, object, result);
            } else {
                let every = self.every(graph, object);
                let unknown = self.unknown(graph, result);
                self.add_edge(graph, every, unknown);
            }
            result
        };
        if inplace
            && concatenation
            && let Some(right) = right
        {
            let elements = self.operator_iterated(graph, id, right, caller, site);
            let unknown = self.unknown(graph, result);
            self.add_edge(graph, elements, unknown);
            if kind == "list" {
                self.add_length_hint(graph, right, caller, site, LENGTH_HINT);
            }
        }
        self.add_object(graph, dst, result);
    }

    fn protocol_site_call(
        &mut self,
        graph: &mut Graph,
        caller: Sym,
        site: Sym,
        role: Role,
        args: &[Option<NodeId>],
        implicit: bool,
    ) -> CallId {
        let key = SiteKey {
            caller,
            site,
            role,
            implicit,
        };
        self.site_call(graph, key, args, None, None)
    }

    fn unless_names(&mut self, names: &[&str]) -> Unless {
        if names.is_empty() {
            return Unless::Nothing;
        }
        Unless::Names(names.iter().map(|name| self.symbols.intern(name)).collect())
    }

    pub(super) fn add_truth(&mut self, graph: &mut Graph, value: NodeId, caller: Sym, site: Sym) {
        let call = self.protocol_site_call(graph, caller, site, Role::Truth, &[], true);
        self.special_call(graph, value, "__bool__", call, Unless::Nothing);
        let unless = self.unless_names(&["__bool__"]);
        self.special_call(graph, value, "__len__", call, unless);
    }

    pub(super) fn add_conversion(
        &mut self,
        graph: &mut Graph,
        value: NodeId,
        kind: Conversion,
        caller: Sym,
        site: Sym,
        spec: Option<NodeId>,
    ) {
        let role = Role::Convert(self.symbols.intern(kind.name()));
        let call = self.protocol_site_call(graph, caller, site, role, &[], true);
        let formatted = if kind == Conversion::Format {
            self.protocol_site_call(graph, caller, site, Role::Format, &[spec], true)
        } else {
            call
        };
        for &(name, unless) in kind.plan() {
            let implicit = if name == "__format__" {
                formatted
            } else {
                call
            };
            let unless = self.unless_names(unless);
            self.special_call(graph, value, name, implicit, unless);
        }
        let reached = self.node(graph, None);
        let rule = self.protocol_rule(ProtocolRule::ConvertContainer {
            reached,
            caller,
            site,
        });
        self.attach(graph, value, rule);
    }

    fn convert_container(
        &mut self,
        graph: &mut Graph,
        container: ObjId,
        reached: NodeId,
        caller: Sym,
        site: Sym,
    ) {
        if !REPR_CONTAINERS.contains(&self.container_kind(container)) {
            return;
        }
        if self.protocols.converted.insert(reached) {
            let role = Role::Convert(self.symbols.intern(Conversion::Repr.name()));
            let call = self.protocol_site_call(graph, caller, site, role, &[], true);
            self.special_call(graph, reached, "__repr__", call, Unless::Nothing);
        }
        let reach = self.repr_reach(graph, container);
        self.add_edge(graph, reach, reached);
    }

    fn repr_reach(&mut self, graph: &mut Graph, container: ObjId) -> NodeId {
        if let Some(&node) = self.protocols.repr_reaches.get(&container) {
            return node;
        }
        let node = self.node(graph, None);
        self.protocols.repr_reaches.insert(container, node);
        let mut parts = vec![self.every(graph, container)];
        if self.container_kind(container) == "dict" {
            parts.push(self.keys(graph, container));
        }
        for part in parts {
            self.add_edge(graph, part, node);
            let rule = self.protocol_rule(ProtocolRule::ReachNested(node));
            self.attach(graph, part, rule);
        }
        node
    }

    pub(super) fn add_percent(
        &mut self,
        graph: &mut Graph,
        format: NodeId,
        value: NodeId,
        caller: Sym,
        site: Sym,
    ) {
        let rule = self.protocol_rule(ProtocolRule::PercentFormat {
            value,
            caller,
            site,
        });
        self.attach(graph, format, rule);
    }

    fn percent_format(
        &mut self,
        graph: &mut Graph,
        format: ObjId,
        value: NodeId,
        caller: Sym,
        site: Sym,
    ) {
        let Object::Const { value: literal, .. } = self.objects.get(format) else {
            unreachable!("a percent format is a constant");
        };
        let (text, bytes): (Vec<u32>, bool) = match literal {
            Literal::Str(points) => (points.to_vec(), false),
            Literal::Bytes(bytes) => (bytes.iter().map(|&byte| u32::from(byte)).collect(), true),
            Literal::Int(_) => return,
        };
        let (spans, _) = percent_spans(&text, bytes);
        let mut fields = Vec::new();
        for (_, _, field) in spans {
            let (key, conversion) = match field {
                PercentField::Escaped => continue,
                PercentField::Positional {
                    position,
                    conversion,
                } => (Literal::Int(position.into()), conversion),
                PercentField::Keyed { key, conversion } => {
                    let key = if bytes {
                        let bytes = key
                            .iter()
                            .map(|&point| u8::try_from(point).expect("a Latin-1 key"))
                            .collect();
                        Literal::Bytes(bytes)
                    } else {
                        Literal::Str(key.into())
                    };
                    (key, conversion)
                }
            };
            fields.push((key, percent_conversion(conversion, bytes)));
        }
        if fields.iter().any(|(_, conversion)| conversion.is_some()) {
            let id = FieldsId(next_id(self.protocols.fields.len()));
            self.protocols.fields.push(fields);
            let rule = self.protocol_rule(ProtocolRule::Percent {
                fields: id,
                caller,
                site,
            });
            self.attach(graph, value, rule);
        }
    }

    fn percent(&mut self, graph: &mut Graph, object: ObjId, id: FieldsId, caller: Sym, site: Sym) {
        let fields = self.protocols.fields[index_of(id.0)].clone();
        let kind = self.objects.get(object).kind();
        if kind == Kind::Container && self.container_kind(object) == "tuple" {
            for (key, conversion) in fields {
                if !matches!(key, Literal::Int(_)) {
                    return;
                }
                if let Some(conversion) = conversion {
                    let element = self.element(graph, object, &key);
                    self.add_conversion(graph, element, conversion, caller, site, None);
                }
            }
            return;
        }
        let whole = matches!(kind, Kind::Instance | Kind::Class | Kind::Container);
        let mapping = kind == Kind::Container && self.is_dict(object);
        let mut named = false;
        for (key, conversion) in fields {
            let item = match key {
                Literal::Int(ref position) => {
                    let first = *position == 0.into();
                    if named || !first || (conversion.is_none() && mapping) {
                        return;
                    }
                    if !whole {
                        continue;
                    }
                    self.constant(graph, object)
                }
                _ => {
                    if !mapping {
                        return;
                    }
                    named = true;
                    self.element(graph, object, &key)
                }
            };
            if let Some(conversion) = conversion {
                self.add_conversion(graph, item, conversion, caller, site, None);
            }
        }
    }

    pub(super) fn add_await(
        &mut self,
        graph: &mut Graph,
        value: NodeId,
        dst: NodeId,
        caller: Sym,
        site: Sym,
    ) {
        let iterator = self.node(graph, None);
        let rule = self.protocol_rule(ProtocolRule::Finished(dst));
        self.attach(graph, iterator, rule);
        let call = self.protocol_site_call(graph, caller, site, Role::Await, &[], true);
        let rule = self.protocol_rule(ProtocolRule::Await {
            call,
            iterator,
            dst,
        });
        self.attach(graph, value, rule);
    }

    fn awaited(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        call: CallId,
        iterator: NodeId,
        dst: NodeId,
    ) {
        let kind = self.objects.get(object).kind();
        if matches!(kind, Kind::Instance | Kind::Class) {
            self.call_dunder(
                graph,
                object,
                "__await__",
                call,
                Some(iterator),
                Unless::Nothing,
            );
            let types = match *self.objects.get(object) {
                Object::Instance { class, .. } => self.constant(graph, class),
                _ => self.objects.class(object).metaclass,
            };
            let rule = self.protocol_rule(ProtocolRule::AwaitType { object, dst });
            self.attach(graph, types, rule);
        } else if is_a(kind, &[Kind::External, Kind::Typed, Kind::Container]) {
            self.add_object(graph, dst, object);
        } else {
            self.finished(graph, object, dst);
        }
    }

    fn finished(&mut self, graph: &mut Graph, object: ObjId, dst: NodeId) {
        let function = match *self.objects.get(object) {
            Object::Coroutine { function, .. } | Object::Generator { function, .. } => function,
            _ => return,
        };
        let returned = self
            .objects
            .function(function)
            .return_node
            .expect("an analysed function returns");
        self.add_edge(graph, returned, dst);
    }

    pub(super) fn add_with(
        &mut self,
        graph: &mut Graph,
        manager: NodeId,
        dst: Option<NodeId>,
        caller: Sym,
        site: Sym,
        is_async: bool,
    ) {
        let enter = self.protocol_site_call(graph, caller, site, Role::Enter, &[], true);
        let leave = self.protocol_site_call(graph, caller, site, Role::Exit, &[None; 3], true);
        let (dst, exited) = if is_async {
            let entered = dst;
            let dst = self.node(graph, None);
            let entered = match entered {
                Some(entered) => entered,
                None => self.node(graph, None),
            };
            self.add_await(graph, dst, entered, caller, site);
            let exited = self.node(graph, None);
            let result = self.node(graph, None);
            self.add_await(graph, exited, result, caller, site);
            (Some(dst), Some(exited))
        } else {
            (dst, None)
        };
        let rule = self.protocol_rule(ProtocolRule::With {
            dst,
            exited,
            enter,
            leave,
            is_async,
        });
        self.attach(graph, manager, rule);
    }

    #[allow(clippy::too_many_arguments)]
    fn with(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        dst: Option<NodeId>,
        exited: Option<NodeId>,
        enter: CallId,
        leave: CallId,
        is_async: bool,
    ) {
        let (entering, leaving) = if is_async {
            ("__aenter__", "__aexit__")
        } else {
            ("__enter__", "__exit__")
        };
        let kind = self.objects.get(object).kind();
        if matches!(kind, Kind::Instance | Kind::Class) {
            self.call_dunder(graph, object, entering, enter, dst, Unless::Nothing);
            self.call_dunder(graph, object, leaving, leave, exited, Unless::Nothing);
        } else if kind == Kind::Typed {
            let details = &self.calls[enter.index()];
            let origin = TypeOrigin::Enter {
                caller: details.caller,
                site: details.site,
            };
            self.typed_special(graph, object, entering, dst, origin);
        } else if is_a(kind, &[Kind::External])
            && let Some(dst) = dst
        {
            self.add_object(graph, dst, object);
        }
    }

    pub(super) fn add_raise(
        &mut self,
        graph: &mut Graph,
        exception: NodeId,
        caller: Sym,
        site: Sym,
    ) {
        let call = self.protocol_site_call(graph, caller, site, Role::Raise, &[], false);
        let rule = self.protocol_rule(ProtocolRule::Raise(call));
        self.attach(graph, exception, rule);
    }

    pub(super) fn add_handler(&mut self, graph: &mut Graph, types: NodeId, dst: NodeId) {
        let rule = self.protocol_rule(ProtocolRule::Handler(dst));
        self.attach(graph, types, rule);
    }

    fn handler(&mut self, graph: &mut Graph, object: ObjId, dst: NodeId) {
        let kind = self.objects.get(object).kind();
        if kind == Kind::Class {
            let instances = self.objects.class(object).instances;
            self.add_edge(graph, instances, dst);
        } else if is_a(kind, &[Kind::External]) {
            let values = match self.stub_definitions(object) {
                None => vec![object],
                Some(definitions) => {
                    let paths: Vec<String> = definitions
                        .iter()
                        .filter(|definition| definition.kind == DefinitionKind::Class)
                        .map(|definition| definition.path.to_string())
                        .collect();
                    paths.iter().map(|path| self.typed(graph, path)).collect()
                }
            };
            for value in values {
                self.add_object(graph, dst, value);
            }
        } else if kind == Kind::Container && self.protocols.handlers.insert((object, dst)) {
            let every = self.every(graph, object);
            let rule = self.protocol_rule(ProtocolRule::Handler(dst));
            self.attach(graph, every, rule);
        }
    }

    fn operator_iterated(
        &mut self,
        graph: &mut Graph,
        id: OperatorId,
        iterable: NodeId,
        caller: Sym,
        site: Sym,
    ) -> NodeId {
        if let Some(&(iterated, node)) = self.protocols.iterated.get(&id) {
            assert_eq!(iterated, iterable, "an operator iterates another node");
            return node;
        }
        let node = self.node(graph, None);
        self.protocols.iterated.insert(id, (iterable, node));
        self.add_iteration(graph, iterable, node, caller, site, false);
        node
    }
}

fn percent_conversion(conversion: u32, bytes: bool) -> Option<Conversion> {
    let conversion = char::from_u32(conversion).expect("a conversion character");
    match conversion {
        'r' | 'a' => Some(Conversion::Repr),
        's' if !bytes => Some(Conversion::Str),
        _ => None,
    }
}
