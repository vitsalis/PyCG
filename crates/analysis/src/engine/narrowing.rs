use pycg_solver::{NodeId, ObjId};
use pycg_stubs::DefinitionKind;
use rustc_hash::{FxHashMap, FxHashSet};

use crate::builder::calls::Shape;
use crate::engine::annotations::Owner;
use crate::engine::hierarchy::{BUILTIN_TYPE, LookupAttr, LookupKey, Unless};
use crate::engine::objects::{Kind, Literal, Object, kinds_mask};
use crate::engine::outside::outside_name;
use crate::engine::rules::{Rule, RuleId};
use crate::engine::{Graph, OrderedMap, State};

const TYPE_PATH: &str = "builtins.type";
const STR_PATH: &str = "builtins.str";
const COROUTINE_PATH: &str = "types.CoroutineType";
const CALLABLE_OBJECTS: &[Kind] = &[
    Kind::Function,
    Kind::BoundMethod,
    Kind::ReturnsArgument,
    Kind::Closure,
    Kind::BuiltinMethod,
    Kind::Class,
];
const EXACT_OBJECTS: &[Kind] = &[
    Kind::Const,
    Kind::Pattern,
    Kind::Container,
    Kind::Generator,
    Kind::Coroutine,
];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct FilterId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct AlternativeId(u32);

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub(crate) enum ClassKey {
    Unknown,
    Analysed(ObjId),
    Exactly(Box<[String]>),
    Below(Box<[String]>),
}

struct Filter {
    source: NodeId,
    dst: NodeId,
    holds: bool,
    as_class: bool,
    groups: OrderedMap<ClassKey, Vec<ObjId>>,
    passed: FxHashSet<ClassKey>,
    alternatives: Vec<AlternativeId>,
    all: bool,
}

struct Alternative {
    length: usize,
    classes: Vec<OrderedMap<ObjId, ()>>,
    open: FxHashSet<usize>,
    passed: FxHashMap<ClassKey, FxHashSet<usize>>,
    covered: FxHashMap<ClassKey, usize>,
}

type Subscription = (NodeId, FilterId, Option<(AlternativeId, usize)>);

#[derive(Default)]
pub(crate) struct ClassTests {
    filters: Vec<Filter>,
    alternatives: Vec<Alternative>,
    subscriptions: OrderedMap<Subscription, ()>,
    completed: usize,
    tested: FxHashSet<(NodeId, NodeId, bool)>,
    ancestors: FxHashMap<String, FxHashSet<String>>,
}

#[derive(Clone, Debug)]
pub(crate) enum ClassTestRule {
    CallableValue {
        dst: NodeId,
        holds: bool,
    },
    PassCallable {
        object: ObjId,
        dst: NodeId,
    },
    TestedTuple {
        dst: NodeId,
        as_class: bool,
        owner: Owner,
    },
    Value(FilterId),
    Alternative(FilterId),
    PositionClass {
        filter: FilterId,
        alternative: AlternativeId,
        index: usize,
    },
    Metaclass {
        filter: FilterId,
        alternative: AlternativeId,
        index: usize,
    },
    NotNominal {
        filter: FilterId,
        alternative: AlternativeId,
        index: usize,
    },
    Related {
        filter: FilterId,
        key: ClassKey,
        alternative: AlternativeId,
        index: usize,
    },
}

impl ClassTestRule {
    pub(crate) fn captured(&self) -> Vec<ObjId> {
        match *self {
            ClassTestRule::PassCallable { object, .. } => vec![object],
            _ => Vec::new(),
        }
    }
}

fn is_a(kind: Kind, kinds: &[Kind]) -> bool {
    kind.mask() & kinds_mask(kinds) != 0
}

fn index_of(id: u32) -> usize {
    id as usize
}

fn next_id(length: usize) -> u32 {
    u32::try_from(length).expect("fewer than 2^32 class tests")
}

impl State {
    fn class_test_rule(&mut self, rule: ClassTestRule) -> RuleId {
        self.rule(Rule::ClassTest(Box::new(rule)))
    }

    fn filter(&self, id: FilterId) -> &Filter {
        &self.class_tests.filters[index_of(id.0)]
    }

    fn filter_mut(&mut self, id: FilterId) -> &mut Filter {
        &mut self.class_tests.filters[index_of(id.0)]
    }

    fn alternative(&self, id: AlternativeId) -> &Alternative {
        &self.class_tests.alternatives[index_of(id.0)]
    }

    fn alternative_mut(&mut self, id: AlternativeId) -> &mut Alternative {
        &mut self.class_tests.alternatives[index_of(id.0)]
    }

    pub(super) fn class_test_results(&self, rule: &ClassTestRule) -> Vec<NodeId> {
        match *rule {
            ClassTestRule::CallableValue { dst, .. }
            | ClassTestRule::PassCallable { dst, .. }
            | ClassTestRule::TestedTuple { dst, .. } => vec![dst],
            ClassTestRule::Value(filter)
            | ClassTestRule::Alternative(filter)
            | ClassTestRule::PositionClass { filter, .. }
            | ClassTestRule::Metaclass { filter, .. }
            | ClassTestRule::NotNominal { filter, .. }
            | ClassTestRule::Related { filter, .. } => vec![self.filter(filter).dst],
        }
    }

    pub(super) fn class_test_apply(
        &mut self,
        graph: &mut Graph,
        rule: &ClassTestRule,
        object: ObjId,
    ) {
        match *rule {
            ClassTestRule::CallableValue { dst, holds } => {
                self.callable_value(graph, object, dst, holds)
            }
            ClassTestRule::PassCallable {
                object: passed,
                dst,
            } => self.add_object(graph, dst, passed),
            ClassTestRule::TestedTuple {
                dst,
                as_class,
                owner,
            } => {
                if is_a(self.objects.get(object).kind(), &[Kind::Container])
                    && self.container_kind(object) == "tuple"
                {
                    let every = self.every(graph, object);
                    self.tested_classes(graph, every, dst, as_class, owner);
                }
            }
            ClassTestRule::Value(filter) => self.filtered_value(graph, object, filter),
            ClassTestRule::Alternative(filter) => self.class_alternative(graph, object, filter),
            ClassTestRule::PositionClass {
                filter,
                alternative,
                index,
            } => self.position_class(graph, object, filter, alternative, index),
            ClassTestRule::Metaclass {
                filter,
                alternative,
                index,
            } => {
                let builtin_type = is_a(self.objects.get(object).kind(), &[Kind::External])
                    && self.external_name(object) == BUILTIN_TYPE;
                if !builtin_type {
                    self.open_alternative(graph, filter, alternative, index);
                }
            }
            ClassTestRule::NotNominal {
                filter,
                alternative,
                index,
            } => {
                self.open_alternative(graph, filter, alternative, index);
            }
            ClassTestRule::Related {
                filter,
                ref key,
                alternative,
                index,
            } => {
                if self.filter(filter).holds {
                    self.pass_group(graph, key, filter);
                } else {
                    self.passes_at(graph, key, filter, alternative, Some(index));
                }
            }
        }
    }

    pub(super) fn callable_filter(
        &mut self,
        graph: &mut Graph,
        source: NodeId,
        dst: NodeId,
        holds: bool,
    ) {
        let rule = self.class_test_rule(ClassTestRule::CallableValue { dst, holds });
        self.attach(graph, source, rule);
    }

    fn callable_value(&mut self, graph: &mut Graph, object: ObjId, dst: NodeId, holds: bool) {
        if let Object::Instance { class, .. } = *self.objects.get(object) {
            let found = if holds {
                self.lookup_name(
                    graph,
                    class,
                    "__call__",
                    Some(object),
                    None,
                    Unless::Nothing,
                )
            } else {
                self.lookup_name(graph, class, "__call__", None, None, Unless::MayLackMethod)
            };
            let rule = self.class_test_rule(ClassTestRule::PassCallable { object, dst });
            self.attach(graph, found, rule);
            return;
        }
        match self.callable(object) {
            Some(callable) if callable != holds => {}
            _ => self.add_object(graph, dst, object),
        }
    }

    fn callable(&mut self, object: ObjId) -> Option<bool> {
        let kind = self.objects.get(object).kind();
        if is_a(kind, CALLABLE_OBJECTS) {
            return Some(true);
        }
        if is_a(kind, EXACT_OBJECTS) {
            return if self.exact(object) {
                Some(false)
            } else {
                None
            };
        }
        match *self.objects.get(object) {
            Object::Module(_) => Some(false),
            Object::Typed { class, .. } => {
                let class = self.symbols.text(class).to_owned();
                (!self.stubs.member(&class, "__call__").is_empty()).then_some(true)
            }
            Object::External(_) => {
                let kinds: FxHashSet<DefinitionKind> = self
                    .stub_definitions(object)
                    .map(|definitions| {
                        definitions
                            .iter()
                            .map(|definition| definition.kind)
                            .collect()
                    })
                    .unwrap_or_default();
                let only_callables = kinds
                    .iter()
                    .all(|kind| matches!(kind, DefinitionKind::Function | DefinitionKind::Class));
                if !kinds.is_empty() && only_callables {
                    Some(true)
                } else if kinds.len() == 1 && kinds.contains(&DefinitionKind::Module) {
                    Some(false)
                } else {
                    None
                }
            }
            _ => None,
        }
    }

    fn exact(&self, object: ObjId) -> bool {
        match self.objects.get(object) {
            Object::Const { exact, .. }
            | Object::Generator { exact, .. }
            | Object::Coroutine { exact, .. }
            | Object::Pattern { exact, .. } => *exact,
            Object::Container(container) => container.exact,
            _ => unreachable!("an exact kind of object"),
        }
    }

    pub(super) fn tested_classes(
        &mut self,
        graph: &mut Graph,
        classes: NodeId,
        dst: NodeId,
        as_class: bool,
        owner: Owner,
    ) {
        if !self.class_tests.tested.insert((classes, dst, as_class)) {
            return;
        }
        let shape = if as_class {
            Shape::Class
        } else {
            Shape::Instance
        };
        self.annotated(graph, Some(classes), dst, shape, owner);
        let rule = self.class_test_rule(ClassTestRule::TestedTuple {
            dst,
            as_class,
            owner,
        });
        self.attach(graph, classes, rule);
    }

    pub(super) fn class_filter(
        &mut self,
        graph: &mut Graph,
        source: NodeId,
        classes: Option<NodeId>,
        dst: NodeId,
        as_class: bool,
        holds: bool,
    ) {
        let filter = FilterId(next_id(self.class_tests.filters.len()));
        self.class_tests.filters.push(Filter {
            source,
            dst,
            holds,
            as_class,
            groups: OrderedMap::default(),
            passed: FxHashSet::default(),
            alternatives: Vec::new(),
            all: false,
        });
        let Some(classes) = classes else {
            self.pass_all(graph, filter);
            return;
        };
        self.subscribe(graph, classes, filter, None);
        let rule = self.class_test_rule(ClassTestRule::Value(filter));
        self.attach(graph, source, rule);
    }

    fn subscribe(
        &mut self,
        graph: &mut Graph,
        node: NodeId,
        filter: FilterId,
        at: Option<(AlternativeId, usize)>,
    ) {
        let key = (node, filter, at);
        if self.class_tests.subscriptions.contains_key(&key) {
            return;
        }
        self.class_tests.subscriptions.insert(key, ());
        let rule = match at {
            None => ClassTestRule::Alternative(filter),
            Some((alternative, index)) => ClassTestRule::PositionClass {
                filter,
                alternative,
                index,
            },
        };
        let rule = self.class_test_rule(rule);
        self.attach(graph, node, rule);
    }

    pub(super) fn complete_class_tests(&mut self, graph: &mut Graph) -> bool {
        let mut added = false;
        let keys: Vec<Subscription> = self.class_tests.subscriptions.keys().copied().collect();
        let pending = keys[self.class_tests.completed..].to_vec();
        self.class_tests.completed = keys.len();
        for (node, filter, at) in pending {
            if self.objects_of(graph, node).is_empty() {
                added = match at {
                    None => self.pass_all(graph, filter),
                    Some((alternative, index)) => {
                        self.open_alternative(graph, filter, alternative, index)
                    }
                } || added;
            }
        }
        added
    }

    fn class_alternative(&mut self, graph: &mut Graph, value: ObjId, filter: FilterId) {
        if let Some(length) = self.tuple_length(value) {
            match length {
                Some(0) => {
                    if !self.filter(filter).holds {
                        self.pass_all(graph, filter);
                    }
                }
                None => {
                    let alternative = self.new_alternative(filter, 1);
                    self.tuple_at(graph, value, filter, alternative, 0);
                }
                Some(length) => {
                    let alternative = self.new_alternative(filter, length);
                    for index in 0..length {
                        let node = self.element(graph, value, &Literal::Int(index.into()));
                        self.subscribe(graph, node, filter, Some((alternative, index)));
                    }
                }
            }
        } else {
            let alternative = self.new_alternative(filter, 1);
            self.tested_class(graph, value, filter, alternative, 0);
        }
    }

    fn tuple_length(&self, value: ObjId) -> Option<Option<usize>> {
        match self.objects.get(value) {
            Object::Container(container) if self.symbols.text(container.kind) == "tuple" => {
                Some(container.length.map(|length| length as usize))
            }
            _ => None,
        }
    }

    fn tuple_at(
        &mut self,
        graph: &mut Graph,
        value: ObjId,
        filter: FilterId,
        alternative: AlternativeId,
        index: usize,
    ) {
        if !self.filter(filter).holds {
            self.open_alternative(graph, filter, alternative, index);
            return;
        }
        match self.tuple_length(value).expect("a tuple") {
            None => {
                let every = self.every(graph, value);
                self.subscribe(graph, every, filter, Some((alternative, index)));
            }
            Some(length) => {
                for position in 0..length {
                    let node = self.element(graph, value, &Literal::Int(position.into()));
                    self.subscribe(graph, node, filter, Some((alternative, index)));
                }
            }
        }
    }

    fn new_alternative(&mut self, filter: FilterId, length: usize) -> AlternativeId {
        let id = AlternativeId(next_id(self.class_tests.alternatives.len()));
        self.class_tests.alternatives.push(Alternative {
            length,
            classes: (0..length).map(|_| OrderedMap::default()).collect(),
            open: FxHashSet::default(),
            passed: FxHashMap::default(),
            covered: FxHashMap::default(),
        });
        self.filter_mut(filter).alternatives.push(id);
        id
    }

    fn position_class(
        &mut self,
        graph: &mut Graph,
        value: ObjId,
        filter: FilterId,
        alternative: AlternativeId,
        index: usize,
    ) {
        let kind = self.objects.get(value).kind();
        let record = self.filter(filter);
        if record.all && record.holds && !matches!(kind, Kind::Class | Kind::Container) {
            return;
        }
        if self.tuple_length(value).is_some() {
            self.tuple_at(graph, value, filter, alternative, index);
        } else {
            self.tested_class(graph, value, filter, alternative, index);
        }
    }

    fn tested_class(
        &mut self,
        graph: &mut Graph,
        class: ObjId,
        filter: FilterId,
        alternative: AlternativeId,
        index: usize,
    ) {
        if self.alternative(alternative).classes[index].contains_key(&class) {
            return;
        }
        let kind = self.objects.get(class).kind();
        if kind == Kind::Class {
            let metaclass = self.objects.class(class).metaclass;
            let rule = self.class_test_rule(ClassTestRule::Metaclass {
                filter,
                alternative,
                index,
            });
            self.attach(graph, metaclass, rule);
            let key = LookupKey {
                attr: LookupAttr::Object(class),
                receiver: None,
                after: None,
                unless: Unless::NotNominal,
            };
            let bases = self.lookup(graph, class, key);
            let rule = self.class_test_rule(ClassTestRule::NotNominal {
                filter,
                alternative,
                index,
            });
            self.attach(graph, bases, rule);
        } else {
            let nominal = match self.objects.get(class) {
                Object::External(external) | Object::UnknownExternal(external) => {
                    !external.inexact && self.nominal_outside(class)
                }
                _ => false,
            };
            if !nominal {
                self.open_alternative(graph, filter, alternative, index);
                return;
            }
        }
        self.alternative_mut(alternative).classes[index].insert(class, ());
        let keys: Vec<ClassKey> = self.filter(filter).groups.keys().cloned().collect();
        for key in keys {
            self.decide_remembered(graph, key, class, filter, alternative, index);
        }
    }

    fn filtered_value(&mut self, graph: &mut Graph, object: ObjId, filter: FilterId) {
        if self.filter(filter).all {
            return;
        }
        let as_class = self.filter(filter).as_class;
        let key = self.class_key(graph, object, as_class);
        if self.filter(filter).passed.contains(&key) {
            let dst = self.filter(filter).dst;
            self.add_object(graph, dst, object);
            return;
        }
        if let Some(group) = self.filter_mut(filter).groups.get_mut(&key) {
            group.push(object);
            return;
        }
        self.filter_mut(filter)
            .groups
            .insert(key.clone(), vec![object]);
        let alternatives = self.filter(filter).alternatives.clone();
        for alternative in alternatives {
            if !self.filter(filter).holds {
                self.passes_at(graph, &key, filter, alternative, None);
            }
            let classes: Vec<Vec<ObjId>> = self
                .alternative(alternative)
                .classes
                .iter()
                .map(|classes| classes.keys().copied().collect())
                .collect();
            for (index, classes) in classes.into_iter().enumerate() {
                for class in classes {
                    if !self.opaque(class) {
                        self.decide(graph, &key, class, filter, alternative, index);
                    }
                }
            }
        }
    }

    fn decide_remembered(
        &mut self,
        graph: &mut Graph,
        key: ClassKey,
        class: ObjId,
        filter: FilterId,
        alternative: AlternativeId,
        index: usize,
    ) {
        if let ClassKey::Analysed(known) = key {
            if !self.opaque(known) {
                self.decide(graph, &key, class, filter, alternative, index);
            }
        } else {
            self.decide(graph, &key, class, filter, alternative, index);
        }
    }

    fn decide(
        &mut self,
        graph: &mut Graph,
        key: &ClassKey,
        class: ObjId,
        filter: FilterId,
        alternative: AlternativeId,
        index: usize,
    ) {
        let record = self.filter(filter);
        if record.all || record.passed.contains(key) {
            return;
        }
        let holds = record.holds;
        match key {
            ClassKey::Unknown => {
                if holds {
                    self.pass_group(graph, key, filter);
                } else {
                    self.passes_at(graph, key, filter, alternative, Some(index));
                }
            }
            &ClassKey::Analysed(known) => {
                if holds && self.objects.is_class(class) {
                    return;
                }
                let relation = if holds {
                    Unless::MayDerive
                } else {
                    Unless::MayLack
                };
                let lookup = LookupKey {
                    attr: LookupAttr::Object(class),
                    receiver: None,
                    after: None,
                    unless: relation,
                };
                let related = self.lookup(graph, known, lookup);
                let rule = self.class_test_rule(ClassTestRule::Related {
                    filter,
                    key: key.clone(),
                    alternative,
                    index,
                });
                self.attach(graph, related, rule);
            }
            ClassKey::Exactly(paths) | ClassKey::Below(paths) => {
                let below = matches!(key, ClassKey::Below(_));
                let paths = paths.clone();
                if holds {
                    if self.may_be(below, &paths, class) {
                        self.pass_group(graph, key, filter);
                    }
                } else if !self.certainly(&paths, class) {
                    self.passes_at(graph, key, filter, alternative, Some(index));
                }
            }
        }
    }

    fn class_key(&mut self, graph: &mut Graph, object: ObjId, as_class: bool) -> ClassKey {
        let _ = graph;
        if as_class {
            return match self.objects.get(object) {
                Object::Class(_) => ClassKey::Analysed(object),
                Object::External(external) | Object::UnknownExternal(external)
                    if external.inexact =>
                {
                    ClassKey::Unknown
                }
                _ => {
                    let paths = self.stub_classes(object);
                    if paths.is_empty() {
                        ClassKey::Unknown
                    } else {
                        ClassKey::Exactly(paths.into())
                    }
                }
            };
        }
        match *self.objects.get(object) {
            Object::Instance { class, .. } => return ClassKey::Analysed(class),
            Object::Const {
                ref value,
                exact: true,
            } => {
                let name = match value {
                    Literal::Str(_) => "str",
                    Literal::Bytes(_) => "bytes",
                    Literal::Int(_) => "int",
                };
                return ClassKey::Exactly(Box::from([format!("builtins.{name}")]));
            }
            Object::Pattern { exact: true, .. } => {
                return ClassKey::Exactly(Box::from([STR_PATH.to_owned()]));
            }
            Object::Container(ref container) if container.exact => {
                let kind = self.symbols.text(container.kind).to_owned();
                return ClassKey::Exactly(Box::from([self.kind_class(&kind).0]));
            }
            Object::Generator {
                function,
                exact: true,
            } => {
                let kind = if self.objects.function(function).is_async {
                    "async_generator"
                } else {
                    "generator"
                };
                return ClassKey::Exactly(Box::from([self.kind_class(kind).0]));
            }
            Object::Coroutine { exact: true, .. } => {
                return ClassKey::Exactly(Box::from([COROUTINE_PATH.to_owned()]));
            }
            Object::Typed { class, .. } => {
                return ClassKey::Below(Box::from([self.symbols.text(class).to_owned()]));
            }
            _ => {}
        }
        if self.objects.is_class(object) || !self.stub_classes(object).is_empty() {
            return ClassKey::Below(Box::from([TYPE_PATH.to_owned()]));
        }
        ClassKey::Unknown
    }

    fn may_be(&mut self, below: bool, paths: &[String], class: ObjId) -> bool {
        if self.objects.is_class(class) {
            return below;
        }
        let tested = self.stub_names(class);
        for path in paths {
            if !tested.is_disjoint(&self.ancestor_names(path)) {
                return true;
            }
        }
        if below {
            let names: FxHashSet<String> = paths.iter().map(|path| self.public(path)).collect();
            for path in self.stub_classes(class) {
                if !names.is_disjoint(&self.ancestor_names(&path)) {
                    return true;
                }
            }
        }
        false
    }

    fn certainly(&mut self, paths: &[String], class: ObjId) -> bool {
        if self.objects.is_class(class) {
            return false;
        }
        let tested = self.stub_names(class);
        paths
            .iter()
            .any(|path| !tested.is_disjoint(&self.ancestor_names(path)))
    }

    fn stub_names(&mut self, class: ObjId) -> FxHashSet<String> {
        self.stub_classes(class)
            .iter()
            .map(|path| self.public(path))
            .collect()
    }

    fn ancestor_names(&mut self, path: &str) -> FxHashSet<String> {
        if let Some(found) = self.class_tests.ancestors.get(path) {
            return found.clone();
        }
        let mro: Vec<String> = self
            .stubs
            .mro(path)
            .iter()
            .map(|ancestor| ancestor.to_string())
            .collect();
        let names: FxHashSet<String> = mro.iter().map(|ancestor| self.public(ancestor)).collect();
        self.class_tests
            .ancestors
            .insert(path.to_owned(), names.clone());
        names
    }

    fn public(&mut self, path: &str) -> String {
        outside_name(&self.stubs.public_name(path))
    }

    fn stub_classes(&mut self, object: ObjId) -> Vec<String> {
        if !matches!(
            self.objects.get(object).kind(),
            Kind::External | Kind::UnknownExternal
        ) {
            return Vec::new();
        }
        self.stub_definitions(object)
            .map(|definitions| {
                definitions
                    .iter()
                    .filter(|definition| definition.kind == DefinitionKind::Class)
                    .map(|definition| definition.path.to_string())
                    .collect()
            })
            .unwrap_or_default()
    }

    fn passes_at(
        &mut self,
        graph: &mut Graph,
        key: &ClassKey,
        filter: FilterId,
        alternative: AlternativeId,
        index: Option<usize>,
    ) {
        let found = self.alternative_mut(alternative);
        if !found.covered.contains_key(key) {
            found.passed.insert(key.clone(), FxHashSet::default());
            let open = found.open.len();
            found.covered.insert(key.clone(), open);
        }
        if let Some(index) = index
            && !found.open.contains(&index)
            && found
                .passed
                .get_mut(key)
                .expect("a passed set")
                .insert(index)
        {
            *found.covered.get_mut(key).expect("a covered count") += 1;
        }
        let covered = found.covered[key] == found.length;
        if covered {
            self.pass_group(graph, key, filter);
        }
    }

    fn pass_group(&mut self, graph: &mut Graph, key: &ClassKey, filter: FilterId) {
        if !self.filter_mut(filter).passed.insert(key.clone()) {
            return;
        }
        let record = self.filter(filter);
        let dst = record.dst;
        let objects = record.groups.get(key).cloned().unwrap_or_default();
        for object in objects {
            if !self.opaque(object) {
                self.add_object(graph, dst, object);
            }
        }
    }

    fn open_alternative(
        &mut self,
        graph: &mut Graph,
        filter: FilterId,
        alternative: AlternativeId,
        index: usize,
    ) -> bool {
        if self.filter(filter).holds {
            return self.pass_all(graph, filter);
        }
        let found = self.alternative_mut(alternative);
        if !found.open.insert(index) {
            return false;
        }
        let keys: Vec<ClassKey> = found
            .passed
            .iter()
            .filter(|(_, passed)| !passed.contains(&index))
            .map(|(key, _)| key.clone())
            .collect();
        for key in keys {
            *found.covered.get_mut(&key).expect("a covered count") += 1;
        }
        let groups: Vec<ClassKey> = self.filter(filter).groups.keys().cloned().collect();
        for key in groups {
            self.passes_at(graph, &key, filter, alternative, None);
        }
        true
    }

    fn pass_all(&mut self, graph: &mut Graph, filter: FilterId) -> bool {
        let record = self.filter_mut(filter);
        if record.all {
            return false;
        }
        record.all = true;
        let (source, dst) = (record.source, record.dst);
        self.add_edge(graph, source, dst);
        true
    }
}

impl ClassTests {
    pub(crate) fn table_sizes(&self, sizes: &mut Vec<(&'static str, usize)>) {
        let ClassTests {
            filters,
            alternatives: _,
            subscriptions: _,
            completed: _,
            tested: _,
            ancestors: _,
        } = self;
        sizes.extend([("class tests filters", filters.len())]);
    }
}
