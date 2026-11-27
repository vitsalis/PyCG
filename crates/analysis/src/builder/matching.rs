use num_bigint::BigInt;
use pycg_solver::NodeId;
use pycg_syntax::names::identifier;
use pycg_syntax::tree::Node;
use ruff_python_ast::{
    CmpOp, Expr, Pattern, PatternMatchClass, PatternMatchMapping, PatternMatchOr,
    PatternMatchSequence, Singleton, StmtMatch,
};

use crate::builder::ModuleBuilder;
use crate::builder::calls::{Analysis, Constant, Subscript};
use crate::builder::flow::{FALSE, Literal, Literals, StateId, TRUE, Truth, UNKNOWN, truth_of};
use crate::builder::literals::{compare, equal};

enum ItemKey {
    Index(i64),
    Node(Option<NodeId>),
}

const BUILTIN_CLASSES_SELF_MATCHING: [&str; 11] = [
    "bool",
    "bytearray",
    "bytes",
    "dict",
    "float",
    "frozenset",
    "int",
    "list",
    "set",
    "str",
    "tuple",
];

impl<A: Analysis> ModuleBuilder<'_, '_, A> {
    pub(crate) fn match_statement(&mut self, statement: &StmtMatch) {
        let subject = self.expression(&statement.subject);
        let values = self.facts(&statement.subject).1;
        let base = self.current_flow().state;
        let mut start = base;
        let mut ends = Vec::new();
        for case in &statement.cases {
            if !self.current_flow().reachable(start) {
                break;
            }
            self.flow().branch(start);
            let matches = self.pattern(&case.pattern, subject, values.as_ref());
            let mut holds = TRUE;
            if let Some(guard) = &case.guard
                && matches & TRUE != 0
            {
                self.condition(guard);
                holds = self.truth(guard);
            }
            let matched = self.current_flow().state;
            let flow = self.flow();
            let reachable = flow.reachable(matched) && matches & holds & TRUE != 0;
            let body = flow.branch(matched);
            flow.set_reachable(body, reachable);
            self.statements(&case.body);
            ends.push(self.current_flow().state);
            let flow = self.flow();
            let mut failures = Vec::new();
            if matches & FALSE != 0 {
                failures.push(flow.new_child(start));
            }
            if matches & TRUE != 0 && holds & FALSE != 0 {
                failures.push(matched);
            }
            let failed = flow.branch(start);
            if failures.is_empty() {
                failures.push(self.unreachable_state(start));
            }
            self.merge_into(start, &failures, Some(failed));
            start = failed;
        }
        ends.push(start);
        self.merge_into(base, &ends, None);
    }

    fn unreachable_state(&mut self, start: StateId) -> StateId {
        let flow = self.flow();
        let state = flow.new_child(start);
        flow.set_reachable(state, false);
        state
    }

    fn merge_into(&mut self, base: StateId, ends: &[StateId], target: Option<StateId>) {
        let analysis = &mut *self.analysis;
        self.flows
            .last_mut()
            .expect("a flow")
            .1
            .merge(analysis, base, ends, target);
    }

    fn pattern(
        &mut self,
        pattern: &Pattern,
        subject: Option<NodeId>,
        values: Option<&Literals>,
    ) -> Truth {
        let present = values.filter(|values| !values.values().is_empty());
        match pattern {
            Pattern::MatchValue(matched) => {
                let value = self.expression(&matched.value);
                let site = self.site(&Node::Pattern(pattern));
                if let Some(compared) = self.rich_comparison(subject, value, CmpOp::Eq, &site) {
                    let caller = self.caller().to_owned();
                    self.analysis.add_truth(compared, &caller, &site);
                }
                let literals = self.facts(&matched.value).1;
                match (present, literals) {
                    (Some(values), Some(literals)) if !literals.values().is_empty() => {
                        truth_of_conditions(values.values().iter().flat_map(|value| {
                            literals
                                .values()
                                .iter()
                                .map(move |literal| equal(value, literal))
                        }))
                    }
                    _ => UNKNOWN,
                }
            }
            Pattern::MatchSingleton(matched) => match present {
                Some(values) => {
                    let singleton = singleton_literal(matched.value);
                    truth_of_conditions(values.values().iter().map(|value| {
                        compare(CmpOp::Is, value, &singleton).expect("identity is decided")
                    }))
                }
                None => UNKNOWN,
            },
            Pattern::MatchOr(alternatives) => self.or_pattern(alternatives, subject, values),
            Pattern::MatchSequence(sequence) => match present {
                Some(_) => FALSE,
                None => self.sequence_pattern(pattern, sequence, subject),
            },
            Pattern::MatchMapping(mapping) => match present {
                Some(_) => FALSE,
                None => self.mapping_pattern(pattern, mapping, subject),
            },
            Pattern::MatchClass(class) => self.class_pattern(class, subject),
            Pattern::MatchStar(star) => {
                if let Some(name) = &star.name {
                    self.bind(&identifier(name.as_str()), subject, UNKNOWN, None);
                }
                TRUE
            }
            Pattern::MatchAs(alias) => {
                let truth = match &alias.pattern {
                    Some(inner) => self.pattern(inner, subject, values),
                    None => TRUE,
                };
                if let Some(name) = &alias.name {
                    let (bound_truth, literals) = truth_and_literals_of(values);
                    self.bind(&identifier(name.as_str()), subject, bound_truth, literals);
                }
                truth
            }
        }
    }

    fn or_pattern(
        &mut self,
        pattern: &PatternMatchOr,
        subject: Option<NodeId>,
        values: Option<&Literals>,
    ) -> Truth {
        let start = self.current_flow().state;
        let mut matched = Vec::new();
        let mut may_match = 0;
        let mut always_fails = true;
        for alternative in &pattern.patterns {
            self.flow().branch(start);
            let truth = self.pattern(alternative, subject, values);
            if truth & TRUE != 0 {
                matched.push(self.current_flow().state);
                may_match = TRUE;
            }
            always_fails = always_fails && truth & FALSE != 0;
        }
        if matched.is_empty() {
            matched.push(self.unreachable_state(start));
        }
        self.merge_into(start, &matched, None);
        may_match | if always_fails { FALSE } else { 0 }
    }

    fn sequence_pattern(
        &mut self,
        pattern: &Pattern,
        sequence: &PatternMatchSequence,
        subject: Option<NodeId>,
    ) -> Truth {
        let patterns = &sequence.patterns;
        let star = patterns
            .iter()
            .position(|inner| matches!(inner, Pattern::MatchStar(_)));
        let site = self.site(&Node::Pattern(pattern));
        self.length(subject, &site);
        let mut truths = Vec::new();
        for (index, inner) in patterns.iter().enumerate() {
            let part = if Some(index) == star {
                self.rest(subject, index, patterns.len(), &site)
            } else {
                let index = i64::try_from(index).expect("a pattern index fits i64");
                let count = i64::try_from(patterns.len()).expect("a pattern count fits i64");
                let key = match star {
                    Some(star) if index > i64::try_from(star).expect("fits i64") => index - count,
                    _ => index,
                };
                self.item(subject, ItemKey::Index(key), &site)
            };
            truths.push(self.pattern(inner, part, None));
        }
        truth_of_all_parts(&truths)
    }

    fn mapping_pattern(
        &mut self,
        pattern: &Pattern,
        mapping: &PatternMatchMapping,
        subject: Option<NodeId>,
    ) -> Truth {
        let site = self.site(&Node::Pattern(pattern));
        let keys: Vec<Option<NodeId>> = mapping
            .keys
            .iter()
            .map(|key| self.expression(key))
            .collect();
        if !keys.is_empty() {
            self.length(subject, &site);
        }
        let mut truths = Vec::new();
        for (inner, &key) in mapping.patterns.iter().zip(&keys) {
            let item = self.item(subject, ItemKey::Node(key), &site);
            truths.push(self.pattern(inner, item, None));
        }
        if let Some(rest) = &mapping.rest {
            let container = self.analysis.container("dict", &site, None);
            if let Some(subject) = subject {
                let caller = self.caller().to_owned();
                self.analysis
                    .add_dict_items(container, subject, &caller, &site);
            }
            let value = self.analysis.constant(container);
            self.bind(&identifier(rest.as_str()), Some(value), UNKNOWN, None);
        }
        truth_of_all_parts(&truths)
    }

    fn class_pattern(&mut self, pattern: &PatternMatchClass, subject: Option<NodeId>) -> Truth {
        let class = self.expression(&pattern.cls);
        let mut truths = Vec::new();
        let positional = &pattern.arguments.patterns;
        if self.matches_itself(&pattern.cls) && positional.len() == 1 {
            truths.push(self.pattern(&positional[0], subject, None));
        } else {
            for (index, inner) in positional.iter().enumerate() {
                let part = self.matched_argument(subject, class, index, inner);
                truths.push(self.pattern(inner, part, None));
            }
        }
        for keyword in &pattern.arguments.keywords {
            let inner = &keyword.pattern;
            let mut part = None;
            if let Some(subject) = subject {
                let node = self.analysis.node(None);
                let attr = self.mangle(&identifier(keyword.attr.as_str()));
                let site = self.site(&Node::Pattern(inner));
                let caller = self.caller().to_owned();
                self.analysis.add_load(subject, &attr, node, &caller, &site);
                part = Some(node);
            }
            truths.push(self.pattern(inner, part, None));
        }
        truth_of_all_parts(&truths)
    }

    fn matches_itself(&self, class: &Expr) -> bool {
        let Expr::Name(name) = class else {
            return false;
        };
        let id = identifier(&name.id);
        BUILTIN_CLASSES_SELF_MATCHING.contains(&&*id) && self.is_builtin_reference(class, &id)
    }

    fn length(&mut self, subject: Option<NodeId>, site: &str) {
        if let Some(subject) = subject {
            let caller = self.caller().to_owned();
            let call = self
                .analysis
                .site_call(&caller, site, &["special", "__len__"]);
            self.analysis.add_special_call(subject, "__len__", call);
        }
    }

    fn index_constant(&mut self, index: i64) -> NodeId {
        let object = self
            .analysis
            .const_object(&Constant::Int(BigInt::from(index)));
        self.analysis.constant(object)
    }

    fn item(&mut self, subject: Option<NodeId>, key: ItemKey, site: &str) -> Option<NodeId> {
        let subject = subject?;
        let key = match key {
            ItemKey::Index(index) => self.index_constant(index),
            ItemKey::Node(Some(key)) => key,
            ItemKey::Node(None) => self.analysis.node(None),
        };
        let item = self.analysis.node(None);
        let caller = self.caller().to_owned();
        self.analysis.add_subscript(&Subscript {
            base: subject,
            key: Some(key),
            dst: Some(item),
            src: None,
            caller: &caller,
            site,
            delete: false,
        });
        Some(item)
    }

    fn rest(
        &mut self,
        subject: Option<NodeId>,
        star: usize,
        count: usize,
        site: &str,
    ) -> Option<NodeId> {
        let subject = subject?;
        let before: Vec<NodeId> = (0..star).map(|_| self.analysis.node(None)).collect();
        let after: Vec<NodeId> = (star + 1..count)
            .map(|_| self.analysis.node(None))
            .collect();
        let rest = self.analysis.node(None);
        let caller = self.caller().to_owned();
        self.analysis
            .add_unpack(subject, &before, Some(rest), &after, &caller, site);
        Some(rest)
    }

    fn matched_argument(
        &mut self,
        subject: Option<NodeId>,
        class: Option<NodeId>,
        index: usize,
        inner: &Pattern,
    ) -> Option<NodeId> {
        let (subject, class) = (subject?, class?);
        let site = self.site(&Node::Pattern(inner));
        let caller = self.caller().to_owned();
        let names = self.analysis.node(None);
        let name = self.analysis.node(None);
        self.analysis
            .add_load(class, "__match_args__", names, &caller, &site);
        let index = i64::try_from(index).expect("a pattern index fits i64");
        let key = self.index_constant(index);
        self.analysis.add_subscript(&Subscript {
            base: names,
            key: Some(key),
            dst: Some(name),
            src: None,
            caller: &caller,
            site: &site,
            delete: false,
        });
        let attribute = self.analysis.node(None);
        self.analysis
            .add_named_load(subject, name, attribute, &caller, &site);
        Some(attribute)
    }
}

fn singleton_literal(singleton: Singleton) -> Literal {
    match singleton {
        Singleton::None => Literal::None,
        Singleton::True => Literal::Bool(true),
        Singleton::False => Literal::Bool(false),
    }
}

fn truth_of_conditions(conditions: impl Iterator<Item = bool>) -> Truth {
    conditions.fold(0, |truth, holds| truth | if holds { TRUE } else { FALSE })
}

fn truth_of_all_parts(truths: &[Truth]) -> Truth {
    let all = truths.iter().all(|&truth| truth & TRUE != 0);
    (if all { TRUE } else { 0 }) | FALSE
}

fn truth_and_literals_of(values: Option<&Literals>) -> (Truth, Option<Literals>) {
    match values {
        None => (UNKNOWN, None),
        Some(values) => {
            let truth = truth_of(values.values());
            (
                if truth == 0 { UNKNOWN } else { truth },
                Some(values.clone()),
            )
        }
    }
}
