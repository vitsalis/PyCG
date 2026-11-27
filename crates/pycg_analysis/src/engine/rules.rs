use pycg_solver::{KindMask, NodeId, ObjId, Rules, WatchId};

use crate::engine::hierarchy::Unless;
use crate::engine::objects::{Kind, kinds_mask};
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
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub(crate) enum WaitingRule {
    CallDunder {
        name: Sym,
        call: CallId,
        dst: Option<NodeId>,
        unless: Unless,
    },
}

const SET_NAME_KINDS: &[Kind] = &[Kind::Instance, Kind::Class];
const CLASS_KINDS: &[Kind] = &[Kind::Class];

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
        }
    }

    fn each(&self) -> bool {
        !matches!(self, Rule::Call(_) | Rule::Bases { .. } | Rule::Bind { .. })
    }

    fn kinds(&self) -> Option<&'static [Kind]> {
        match self {
            Rule::SetName { .. } => Some(SET_NAME_KINDS),
            Rule::CallMetaclass { .. } => Some(CLASS_KINDS),
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
            Rule::TypeMethod { object, .. } => vec![object],
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
            _ => rule.key().to_string(),
        };
        let captured = rule.captured();
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
        }
    }
}

impl<T: Trace> Rules<RuleId> for State<T> {
    fn apply(&mut self, graph: &mut Graph, rule: RuleId, objects: &[ObjId]) {
        let found = self.rules[rule.index()].clone();
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
