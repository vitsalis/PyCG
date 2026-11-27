use pycg_solver::{NodeId, ObjId};
use rustc_hash::{FxHashMap, FxHashSet};

use crate::engine::attributes::{AccessId, AccessKind};
use crate::engine::builtin_rules::DynamicId;
use crate::engine::objects::{Kind, Object};
use crate::engine::rules::{Rule, RuleId};
use crate::engine::semantics::CallId;
use crate::engine::symbols::Sym;
use crate::engine::trace::Trace;
use crate::engine::{Graph, OrderedMap, State};

const TYPED_CLASSES_KEEPING_PATTERNS: [&str; 2] = ["builtins.str", "builtins.bytes"];
const TARGET_KINDS: &[Kind] = &[Kind::Instance, Kind::Module];

type PatternKey = (Box<[u32]>, Box<[u32]>, Option<Sym>, bool);

#[derive(Default)]
struct PatternState {
    targets: OrderedMap<ObjId, Vec<DynamicId>>,
    candidates: FxHashMap<ObjId, OrderedMap<(Sym, bool), ()>>,
    watching: bool,
    class_names: FxHashMap<ObjId, Vec<Sym>>,
    class_seen: FxHashMap<ObjId, Vec<ObjId>>,
}

#[derive(Default)]
struct PatternLoads {
    loaded: FxHashSet<(ObjId, Sym, bool)>,
    loaders: FxHashMap<Sym, AccessId>,
}

#[derive(Default)]
pub(crate) struct Patterns {
    patterns: FxHashMap<PatternKey, ObjId>,
    states: OrderedMap<ObjId, PatternState>,
    operands: Vec<(NodeId, NodeId)>,
    completed_operands: usize,
    module_names: FxHashMap<ObjId, Vec<Sym>>,
    loads: FxHashMap<DynamicId, PatternLoads>,
}

#[derive(Clone, Debug)]
pub(crate) enum PatternRule {
    Operand(NodeId),
    Target { pattern: ObjId, access: DynamicId },
    ClassInstance { pattern: ObjId, class: ObjId },
}

impl PatternRule {
    pub(crate) fn key(&self) -> &'static str {
        match self {
            PatternRule::Operand(_) => "Each:Patterns._pattern_operand",
            PatternRule::Target { .. } => "Each:Patterns._pattern_target",
            PatternRule::ClassInstance { .. } => "Each:Patterns._pattern_class_instance",
        }
    }

    pub(crate) fn kinds(&self) -> Option<&'static [Kind]> {
        match self {
            PatternRule::Target { .. } => Some(TARGET_KINDS),
            PatternRule::Operand(_) | PatternRule::ClassInstance { .. } => None,
        }
    }

    pub(crate) fn captured(&self) -> Vec<ObjId> {
        match *self {
            PatternRule::Operand(_) => Vec::new(),
            PatternRule::Target { pattern, .. } => vec![pattern],
            PatternRule::ClassInstance { pattern, class } => vec![pattern, class],
        }
    }
}

fn cased(name: &str, case: &str) -> String {
    match case {
        "lower" | "casefold" => name.to_ascii_lowercase(),
        "upper" => name.to_ascii_uppercase(),
        _ => panic!("no case {case}"),
    }
}

fn is_ascii(points: &[u32]) -> bool {
    points.iter().all(|&point| point < 0x80)
}

fn cased_points(points: &[u32], case: &str) -> Vec<u32> {
    let text: String = points
        .iter()
        .map(|&point| char::from_u32(point).expect("a code point"))
        .collect();
    cased(&text, case).chars().map(u32::from).collect()
}

impl<T: Trace> State<T> {
    fn pattern_rule(&mut self, rule: PatternRule) -> RuleId {
        self.rule(Rule::Pattern(rule))
    }

    pub(super) fn pattern_results(&self, rule: &PatternRule) -> Vec<NodeId> {
        match *rule {
            PatternRule::Operand(result) => vec![result],
            PatternRule::Target { access, .. } => {
                self.dynamic_access(access).dst.into_iter().collect()
            }
            PatternRule::ClassInstance { .. } => Vec::new(),
        }
    }

    pub(super) fn pattern_apply(&mut self, graph: &mut Graph, rule: &PatternRule, object: ObjId) {
        match *rule {
            PatternRule::Operand(result) => {
                if !self.certain_operand(object) {
                    let unknown = self.unknown_external;
                    self.add_object(graph, result, unknown);
                }
            }
            PatternRule::Target { pattern, access } => {
                self.pattern_target(graph, object, pattern, access)
            }
            PatternRule::ClassInstance { pattern, class } => {
                self.pattern_class_instance(graph, object, pattern, class)
            }
        }
    }

    pub(super) fn pattern(
        &mut self,
        graph: &mut Graph,
        prefix: &[u32],
        suffix: &[u32],
        case: Option<Sym>,
        exact: bool,
    ) -> ObjId {
        let key: PatternKey = (prefix.into(), suffix.into(), case, exact);
        if let Some(&pattern) = self.patterns.patterns.get(&key) {
            return pattern;
        }
        let pattern = self.new_object(
            graph,
            Object::Pattern {
                prefix: prefix.into(),
                suffix: suffix.into(),
                case,
                exact,
            },
        );
        self.patterns.patterns.insert(key, pattern);
        self.patterns
            .states
            .insert(pattern, PatternState::default());
        pattern
    }

    pub(super) fn rule_case(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        receiver: Option<ObjId>,
        case: &str,
    ) {
        let affixes = receiver.and_then(|receiver| match self.objects.get(receiver) {
            Object::Pattern { prefix, suffix, .. } if is_ascii(prefix) && is_ascii(suffix) => {
                Some((cased_points(prefix, case), cased_points(suffix, case)))
            }
            _ => None,
        });
        let result = match affixes {
            Some((prefix, suffix)) => {
                let case = self.symbols.intern(case);
                self.pattern(graph, &prefix, &suffix, Some(case), true)
            }
            None => self.typed(graph, "builtins.str"),
        };
        let Some(dst) = self.calls[call.index()].dst else {
            return;
        };
        self.add_object(graph, dst, result);
        if receiver.is_some_and(|receiver| self.inexact(receiver)) {
            let unknown = self.unknown_external;
            self.add_object(graph, dst, unknown);
        }
    }

    fn inexact(&self, object: ObjId) -> bool {
        match self.objects.get(object) {
            Object::Const { exact, .. } | Object::Pattern { exact, .. } => !*exact,
            Object::Container(container) => !container.exact,
            _ => false,
        }
    }

    fn certain_operand(&self, object: ObjId) -> bool {
        match self.objects.get(object) {
            Object::Const { exact, .. } | Object::Pattern { exact, .. } => *exact,
            Object::Container(container) => container.exact,
            Object::Typed { class, .. } => {
                TYPED_CLASSES_KEEPING_PATTERNS.contains(&self.symbols.text(*class))
            }
            _ => false,
        }
    }

    pub(super) fn add_pattern_operand(
        &mut self,
        graph: &mut Graph,
        operand: Option<NodeId>,
        result: NodeId,
    ) {
        let Some(operand) = operand else {
            let unknown = self.unknown_external;
            self.add_object(graph, result, unknown);
            return;
        };
        let rule = self.pattern_rule(PatternRule::Operand(result));
        self.attach(graph, operand, rule);
        self.patterns.operands.push((operand, result));
    }

    pub(super) fn complete_pattern_operands(&mut self, graph: &mut Graph) -> bool {
        let mut added = false;
        let pending = self.patterns.operands[self.patterns.completed_operands..].to_vec();
        for (operand, result) in pending {
            if self.objects_of(graph, operand).is_empty() {
                let unknown = self.unknown_external;
                self.add_object(graph, result, unknown);
                added = true;
            }
        }
        self.patterns.completed_operands = self.patterns.operands.len();
        added
    }

    pub(super) fn load_by_pattern(&mut self, graph: &mut Graph, pattern: ObjId, access: DynamicId) {
        let object = self.dynamic_access(access).object;
        let rule = self.pattern_rule(PatternRule::Target { pattern, access });
        self.attach(graph, object, rule);
    }

    fn pattern_state(&mut self, pattern: ObjId) -> &mut PatternState {
        self.patterns
            .states
            .get_mut(&pattern)
            .expect("the state of a pattern")
    }

    fn pattern_matches(&self, pattern: ObjId, name: Sym) -> bool {
        let points: Vec<u32> = self.symbols.text(name).chars().map(u32::from).collect();
        self.pattern_matches_points(pattern, &points)
    }

    pub(super) fn pattern_matches_points(&self, pattern: ObjId, points: &[u32]) -> bool {
        let Object::Pattern {
            prefix,
            suffix,
            case,
            ..
        } = self.objects.get(pattern)
        else {
            unreachable!("a pattern");
        };
        if points.len() < prefix.len() + suffix.len()
            || !points.starts_with(prefix)
            || !points.ends_with(suffix)
        {
            return false;
        }
        let Some(case) = case else {
            return true;
        };
        if !points.iter().all(|&point| point < 128) {
            return true;
        }
        let text: String = points
            .iter()
            .map(|&point| char::from_u32(point).expect("an ASCII code point"))
            .collect();
        cased(&text, self.symbols.text(*case)) == text
    }

    fn pattern_target(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        pattern: ObjId,
        access: DynamicId,
    ) {
        let targets = self
            .pattern_state(pattern)
            .targets
            .entry(object)
            .or_default();
        assert!(
            !targets.contains(&access),
            "a pattern access sees an object twice"
        );
        targets.push(access);
        if matches!(self.objects.get(object), Object::Instance { .. }) {
            self.watch_classes(graph, pattern);
            let mut names: Vec<Sym> = self.store_names.iter().copied().collect();
            names.sort_by(|a, b| self.symbols.text(*a).cmp(self.symbols.text(*b)));
            for name in names {
                self.pattern_candidate(graph, object, pattern, name, false);
            }
        } else {
            let names = self
                .patterns
                .module_names
                .get(&object)
                .cloned()
                .unwrap_or_default();
            for name in names {
                self.pattern_candidate(graph, object, pattern, name, true);
            }
        }
        let candidates: Vec<(Sym, bool)> = self
            .pattern_state(pattern)
            .candidates
            .get(&object)
            .map(|found| found.keys().copied().collect())
            .unwrap_or_default();
        for (name, full) in candidates {
            self.pattern_load(graph, access, object, name, full);
        }
    }

    fn watch_classes(&mut self, graph: &mut Graph, pattern: ObjId) {
        let state = self.pattern_state(pattern);
        if state.watching {
            return;
        }
        state.watching = true;
        for class in self.classes.clone() {
            let mut names: FxHashSet<Sym> =
                self.objects.class(class).defines.iter().copied().collect();
            if let Some(stored) = self.class_store_names.get(&class) {
                names.extend(stored.iter().copied());
            }
            let mut names: Vec<Sym> = names.into_iter().collect();
            names.sort_by(|a, b| self.symbols.text(*a).cmp(self.symbols.text(*b)));
            for name in names {
                self.pattern_class_name(graph, pattern, class, name);
            }
        }
    }

    fn pattern_class_name(&mut self, graph: &mut Graph, pattern: ObjId, class: ObjId, name: Sym) {
        if !self.pattern_matches(pattern, name) {
            return;
        }
        if !self.pattern_state(pattern).class_names.contains_key(&class) {
            let state = self.pattern_state(pattern);
            state.class_names.insert(class, Vec::new());
            state.class_seen.insert(class, Vec::new());
            let instances = self.objects.class(class).instances;
            let rule = self.pattern_rule(PatternRule::ClassInstance { pattern, class });
            self.attach(graph, instances, rule);
        }
        let names = self
            .pattern_state(pattern)
            .class_names
            .get_mut(&class)
            .expect("the names of a class");
        if names.contains(&name) {
            return;
        }
        names.push(name);
        let seen = self.pattern_state(pattern).class_seen[&class].clone();
        for instance in seen {
            if !self.opaque(instance) {
                self.pattern_candidate(graph, instance, pattern, name, true);
            }
        }
    }

    fn pattern_class_instance(
        &mut self,
        graph: &mut Graph,
        instance: ObjId,
        pattern: ObjId,
        class: ObjId,
    ) {
        let state = self.pattern_state(pattern);
        state
            .class_seen
            .get_mut(&class)
            .expect("the instances of a class")
            .push(instance);
        let names = state.class_names[&class].clone();
        for name in names {
            self.pattern_candidate(graph, instance, pattern, name, true);
        }
    }

    pub(super) fn pattern_class_store(&mut self, graph: &mut Graph, class: ObjId, name: Sym) {
        if !self
            .class_store_names
            .entry(class)
            .or_default()
            .insert(name)
        {
            return;
        }
        let patterns: Vec<ObjId> = self.patterns.states.keys().copied().collect();
        for pattern in patterns {
            if self.pattern_state(pattern).watching {
                self.pattern_class_name(graph, pattern, class, name);
            }
        }
    }

    pub(super) fn pattern_store_name(&mut self, graph: &mut Graph, name: Sym) {
        if !self.store_names.insert(name) {
            return;
        }
        let patterns: Vec<ObjId> = self.patterns.states.keys().copied().collect();
        for pattern in patterns {
            let targets: Vec<ObjId> = self
                .pattern_state(pattern)
                .targets
                .keys()
                .copied()
                .collect();
            for object in targets {
                if matches!(self.objects.get(object), Object::Instance { .. })
                    && !self.opaque(object)
                {
                    self.pattern_candidate(graph, object, pattern, name, false);
                }
            }
        }
    }

    fn pattern_candidate(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        pattern: ObjId,
        name: Sym,
        full: bool,
    ) {
        if !self.pattern_matches(pattern, name) {
            return;
        }
        let state = self.pattern_state(pattern);
        let candidates = state.candidates.entry(object).or_default();
        if candidates.contains_key(&(name, full)) {
            return;
        }
        candidates.insert((name, full), ());
        let accesses = state.targets.get(&object).cloned().unwrap_or_default();
        for access in accesses {
            self.pattern_load(graph, access, object, name, full);
        }
    }

    fn pattern_load(
        &mut self,
        graph: &mut Graph,
        access: DynamicId,
        object: ObjId,
        name: Sym,
        full: bool,
    ) {
        let loads = self.patterns.loads.entry(access).or_default();
        if !loads.loaded.insert((object, name, full)) {
            return;
        }
        let found = self.dynamic_access(access);
        let (dst, call) = (found.dst, found.call);
        if full {
            let loader = match self.patterns.loads[&access].loaders.get(&name) {
                Some(&loader) => loader,
                None => {
                    let details = &self.calls[call.index()];
                    let (caller, site) = (details.caller, details.site);
                    let (attr, caller, site) = (
                        self.symbols.text(name).to_owned(),
                        self.symbols.text(caller).to_owned(),
                        self.symbols.text(site).to_owned(),
                    );
                    let loader =
                        self.new_access(AccessKind::Load, &attr, dst, None, &caller, &site);
                    self.patterns
                        .loads
                        .get_mut(&access)
                        .expect("the loads of an access")
                        .loaders
                        .insert(name, loader);
                    loader
                }
            };
            self.apply_access(graph, object, loader);
        } else {
            let field = self.field(graph, object, name);
            let dst = dst.expect("a load by a pattern has a destination");
            self.add_edge(graph, field, dst);
        }
    }

    pub(super) fn freeze_module_names(&mut self) {
        let modules: Vec<ObjId> = self.modules.values().copied().collect();
        for module in modules {
            let mut names: Vec<Sym> = self
                .fields
                .get(&module)
                .map(|fields| fields.keys().copied().collect())
                .unwrap_or_default();
            names.sort_by(|a, b| self.symbols.text(*a).cmp(self.symbols.text(*b)));
            self.patterns.module_names.insert(module, names);
        }
    }
}

pub(crate) fn pattern_name(prefix: &[u32], suffix: &[u32], case: Option<&str>) -> String {
    use crate::model::{ConstValue, constant_name};
    let name = format!(
        "pattern {}*{}",
        constant_name(&ConstValue::Str(prefix)),
        constant_name(&ConstValue::Str(suffix))
    );
    match case {
        None => name,
        Some(case) => format!("{name} {case}"),
    }
}
