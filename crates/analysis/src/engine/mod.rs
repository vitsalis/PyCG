mod analysis;
mod arguments;
mod attributes;
mod builtin_containers;
mod builtin_rules;
mod containers;
mod fixpoint;
pub mod hierarchy;
pub mod objects;
mod outside;
mod outside_calls;
mod protocols;
mod reflection;
mod rules;
mod semantics;
pub mod symbols;
pub mod trace;

use std::sync::Arc;

use indexmap::{IndexMap, IndexSet};
use pycg_solver::{NodeId, ObjId, Solver, WatchId, Work};
use pycg_stubs::{Definition, Stubs};
use rustc_hash::{FxBuildHasher, FxHashMap, FxHashSet};

use crate::builder::calls::{BuilderTables, ClassFields, FunctionFields, MethodKind};
use crate::model::{BUILTIN_MODULE, Signature};
use crate::program::imports::ImportManager;
use attributes::{
    Access, AccessorEntry, AccessorHooks, Accessors, AccessorsId, Deliveries, DeliveriesId,
    FieldWrites, HookCalls, HookCallsId, HooksId, WritesId,
};
use builtin_containers::Iterated;
use builtin_rules::{DynamicAccess, WrapperKey};
use hierarchy::{LookupAttr, Namespace, Unless};
use objects::{Container, External, Function, Kind, Literal, Module, Object, Objects};
use outside_calls::{Bound, BoundId, Known};
pub use rules::RuleId;
use rules::{Rule, WaitingRule};
pub use semantics::CallId;
use semantics::{
    BoundGroup, Call, Construct, GroupId, Origin, Prefix, Receivers, Returned, ReturnedId, SiteKey,
};
use symbols::{Sym, Symbols};
use trace::{Opacity, Trace};

pub(crate) type OrderedMap<K, V> = IndexMap<K, V, FxBuildHasher>;
pub(crate) type OrderedSet<K> = IndexSet<K, FxBuildHasher>;

pub const EXTERNAL_STEPS_PAST_ROOT_MAX: u32 = 2;

pub type Graph = Solver<RuleId>;

type Receiver = (NodeId, NodeId, ObjId, ObjId, Sym);

#[derive(Clone)]
enum BuilderFields {
    Function(FunctionFields),
    Class(ClassFields),
    Module(Vec<Box<str>>),
}

pub fn not_ported(feature: &str) -> ! {
    panic!("not ported: {feature}")
}

pub struct Engine<T: Trace> {
    graph: Graph,
    state: State<T>,
}

struct State<T: Trace> {
    trace: T,
    symbols: Symbols,
    objects: Objects,
    saturated: ObjId,
    unknown_external: ObjId,
    labels: FxHashMap<NodeId, Box<str>>,
    named_nodes: Vec<NodeId>,
    fields: FxHashMap<ObjId, OrderedMap<Sym, NodeId>>,
    modules: OrderedMap<Sym, ObjId>,
    externals: FxHashMap<(Sym, u32, bool), ObjId>,
    consts: FxHashMap<Literal, ObjId>,
    constants: FxHashMap<ObjId, NodeId>,
    generators: FxHashMap<ObjId, ObjId>,
    coroutines: FxHashMap<ObjId, ObjId>,
    functions: Vec<ObjId>,
    completed_functions: usize,
    called: FxHashSet<ObjId>,
    rules: Vec<Rule>,
    calls: Vec<Call>,
    receiver_calls: FxHashMap<(CallId, Receivers), CallId>,
    prefixes: FxHashMap<CallId, (CallId, Prefix)>,
    bound_groups: FxHashMap<(CallId, ObjId, usize, bool), Vec<GroupId>>,
    groups: FxHashMap<CallId, GroupId>,
    group_records: Vec<BoundGroup>,
    grouped_externals: FxHashMap<ObjId, bool>,
    site_edges: OrderedMap<(Sym, Sym, Construct), OrderedSet<Sym>>,
    call_expressions: Vec<(Sym, Sym, Option<NodeId>)>,
    classes: Vec<ObjId>,
    stubs: Stubs,
    imports: ImportManager,
    stub_definitions: FxHashMap<Sym, Option<Arc<[Definition]>>>,
    external_modules: FxHashSet<String>,
    watches: FxHashMap<(ObjId, LookupAttr, Option<ObjId>, Unless), WatchId>,
    waiting: FxHashMap<WatchId, Vec<(WaitingRule, ObjId)>>,
    watch_of_witness: FxHashMap<NodeId, WatchId>,
    metaclass_members: FxHashSet<(NodeId, Sym, NodeId)>,
    fallback_binds: FxHashSet<(NodeId, ObjId, NodeId)>,
    class_binds: FxHashSet<(NodeId, Option<ObjId>, NodeId)>,
    fallback_nodes: FxHashMap<(ObjId, NodeId), NodeId>,
    families: FxHashMap<ObjId, NodeId>,
    namespace_nodes: FxHashMap<(ObjId, Namespace), NodeId>,
    classes_below: FxHashMap<String, OrderedSet<ObjId>>,
    below_nodes: FxHashMap<(String, bool), NodeId>,
    instances: FxHashMap<(ObjId, Option<Origin>), ObjId>,
    bound_methods: FxHashMap<(ObjId, ObjId), ObjId>,
    fallbacks: FxHashMap<ObjId, ObjId>,
    inexact: FxHashMap<ObjId, ObjId>,
    new_results: FxHashMap<CallId, ReturnedId>,
    returned: Vec<Returned>,
    class_instances: FxHashMap<ObjId, FxHashSet<ObjId>>,
    roots: FxHashMap<CallId, CallId>,
    dunder_calls: FxHashMap<(Option<ObjId>, Sym, CallId, Unless), CallId>,
    dunder_owners: FxHashMap<CallId, FxHashSet<ObjId>>,
    site_calls: FxHashMap<SiteKey, CallId>,
    receivers: Vec<Receiver>,
    entry_receivers: Vec<Receiver>,
    completed_receivers: usize,
    accesses: Vec<Access>,
    accessor_hooks: Vec<AccessorHooks>,
    accessor_hooks_by_key: FxHashMap<(ObjId, Sym, Option<AccessorEntry>), HooksId>,
    accessor_hook_rules: FxHashMap<HooksId, RuleId>,
    accessors: Vec<Accessors>,
    accessor_receivers: FxHashMap<(NodeId, CallId, bool, u32), AccessorsId>,
    writes: Vec<FieldWrites>,
    field_writes: FxHashMap<NodeId, WritesId>,
    hook_calls: Vec<HookCalls>,
    hook_calls_by_lookup: FxHashMap<NodeId, HookCallsId>,
    deliveries: Vec<Deliveries>,
    deliveries_by_lookup: FxHashMap<NodeId, DeliveriesId>,
    descriptors_itself: FxHashSet<(ObjId, NodeId)>,
    store_names: FxHashSet<Sym>,
    class_store_names: FxHashMap<ObjId, FxHashSet<Sym>>,
    pattern_states: FxHashMap<ObjId, ()>,
    field_readers: FxHashMap<(ObjId, Sym), OrderedMap<NodeId, Vec<ObjId>>>,
    builder_fields: FxHashMap<ObjId, BuilderFields>,
    external_callees: FxHashMap<Sym, Known>,
    typed_callbacks: FxHashSet<(CallId, ObjId)>,
    stub_bindings: FxHashMap<(CallId, Box<str>, usize), BoundId>,
    bindings: Vec<Bound>,
    callbacks: FxHashMap<Origin, CallId>,
    callback_values: FxHashSet<(CallId, NodeId)>,
    protocol_plans: Vec<Vec<(Sym, Unless)>>,
    model_bindings: FxHashMap<(CallId, usize), BoundId>,
    wrappers: FxHashMap<WrapperKey, ObjId>,
    builtin_methods: FxHashMap<(ObjId, Sym), ObjId>,
    none_arguments: FxHashMap<(Sym, Sym), Vec<u32>>,
    synced_none_arguments: usize,
    callees: FxHashMap<CallId, NodeId>,
    dynamic_accesses: Vec<DynamicAccess>,
    namespace_names_read: FxHashSet<Sym>,
    zero_argument_super: FxHashSet<Sym>,
    read_namespaces: FxHashSet<Sym>,
    super_pairs: FxHashSet<(CallId, ObjId)>,
    super_accepted: FxHashMap<ObjId, FxHashSet<ObjId>>,
    supers: FxHashMap<(ObjId, ObjId), ObjId>,
    typed_objects: FxHashMap<String, ObjId>,
    iterated_nodes: FxHashMap<Iterated, (NodeId, NodeId)>,
    length_hints: FxHashSet<(Sym, Sym, NodeId, usize)>,
    length_plans: FxHashMap<usize, outside_calls::PlanId>,
    reverse_sequences: FxHashSet<(ObjId, NodeId, CallId)>,
    namespaces: FxHashSet<ObjId>,
    namespace_calls: FxHashSet<CallId>,
    getmembers: Vec<reflection::Getmembers>,
    getmembers_calls: FxHashSet<CallId>,
    members_listed: FxHashSet<(ObjId, reflection::GetmembersId)>,
    handed: Vec<ObjId>,
    tables: BuilderTables,
    containers: containers::Containers,
    protocols: protocols::Protocols,
    builder_calls: Vec<CallId>,
}

impl<T: Trace> Engine<T> {
    pub fn new(cap: Option<u32>, trace: T) -> Engine<T> {
        let mut objects = Objects::default();
        let saturated = objects.push(Object::Saturated);
        let mut state = State {
            trace,
            symbols: Symbols::default(),
            objects,
            saturated,
            unknown_external: saturated,
            labels: FxHashMap::default(),
            named_nodes: Vec::new(),
            fields: FxHashMap::default(),
            modules: OrderedMap::default(),
            externals: FxHashMap::default(),
            consts: FxHashMap::default(),
            constants: FxHashMap::default(),
            generators: FxHashMap::default(),
            coroutines: FxHashMap::default(),
            functions: Vec::new(),
            completed_functions: 0,
            called: FxHashSet::default(),
            rules: Vec::new(),
            calls: Vec::new(),
            receiver_calls: FxHashMap::default(),
            prefixes: FxHashMap::default(),
            bound_groups: FxHashMap::default(),
            groups: FxHashMap::default(),
            group_records: Vec::new(),
            grouped_externals: FxHashMap::default(),
            site_edges: OrderedMap::default(),
            call_expressions: Vec::new(),
            classes: Vec::new(),
            stubs: Stubs::new(),
            imports: ImportManager::default(),
            stub_definitions: FxHashMap::default(),
            external_modules: FxHashSet::default(),
            watches: FxHashMap::default(),
            waiting: FxHashMap::default(),
            watch_of_witness: FxHashMap::default(),
            metaclass_members: FxHashSet::default(),
            fallback_binds: FxHashSet::default(),
            class_binds: FxHashSet::default(),
            fallback_nodes: FxHashMap::default(),
            families: FxHashMap::default(),
            namespace_nodes: FxHashMap::default(),
            classes_below: FxHashMap::default(),
            below_nodes: FxHashMap::default(),
            instances: FxHashMap::default(),
            bound_methods: FxHashMap::default(),
            fallbacks: FxHashMap::default(),
            inexact: FxHashMap::default(),
            new_results: FxHashMap::default(),
            returned: Vec::new(),
            class_instances: FxHashMap::default(),
            roots: FxHashMap::default(),
            dunder_calls: FxHashMap::default(),
            dunder_owners: FxHashMap::default(),
            site_calls: FxHashMap::default(),
            receivers: Vec::new(),
            entry_receivers: Vec::new(),
            completed_receivers: 0,
            accesses: Vec::new(),
            accessor_hooks: Vec::new(),
            accessor_hooks_by_key: FxHashMap::default(),
            accessor_hook_rules: FxHashMap::default(),
            accessors: Vec::new(),
            accessor_receivers: FxHashMap::default(),
            writes: Vec::new(),
            field_writes: FxHashMap::default(),
            hook_calls: Vec::new(),
            hook_calls_by_lookup: FxHashMap::default(),
            deliveries: Vec::new(),
            deliveries_by_lookup: FxHashMap::default(),
            descriptors_itself: FxHashSet::default(),
            store_names: FxHashSet::default(),
            class_store_names: FxHashMap::default(),
            pattern_states: FxHashMap::default(),
            field_readers: FxHashMap::default(),
            builder_fields: FxHashMap::default(),
            external_callees: FxHashMap::default(),
            typed_callbacks: FxHashSet::default(),
            stub_bindings: FxHashMap::default(),
            bindings: Vec::new(),
            callbacks: FxHashMap::default(),
            callback_values: FxHashSet::default(),
            protocol_plans: Vec::new(),
            model_bindings: FxHashMap::default(),
            wrappers: FxHashMap::default(),
            builtin_methods: FxHashMap::default(),
            none_arguments: FxHashMap::default(),
            synced_none_arguments: 0,
            callees: FxHashMap::default(),
            dynamic_accesses: Vec::new(),
            namespace_names_read: FxHashSet::default(),
            zero_argument_super: FxHashSet::default(),
            read_namespaces: FxHashSet::default(),
            super_pairs: FxHashSet::default(),
            super_accepted: FxHashMap::default(),
            supers: FxHashMap::default(),
            typed_objects: FxHashMap::default(),
            iterated_nodes: FxHashMap::default(),
            length_hints: FxHashSet::default(),
            length_plans: FxHashMap::default(),
            reverse_sequences: FxHashSet::default(),
            namespaces: FxHashSet::default(),
            namespace_calls: FxHashSet::default(),
            getmembers: Vec::new(),
            getmembers_calls: FxHashSet::default(),
            members_listed: FxHashSet::default(),
            handed: Vec::new(),
            containers: containers::Containers::default(),
            protocols: protocols::Protocols::default(),
            builder_calls: Vec::new(),
            tables: BuilderTables::default(),
        };
        state.trace.object(
            saturated,
            Kind::Saturated,
            "<saturated>",
            Opacity::Saturated,
        );
        let mut graph = Solver::new(saturated, Kind::Saturated.mask(), cap);
        state.trace.solver(cap, saturated, graph.saturated_node());
        let name = state.symbols.intern("<unknown>");
        state.unknown_external = state.new_object(
            &mut graph,
            Object::UnknownExternal(External {
                name,
                steps: EXTERNAL_STEPS_PAST_ROOT_MAX,
                inexact: false,
            }),
        );
        Engine { graph, state }
    }

    pub fn builder_call_rule(&self, call: crate::builder::calls::CallId) -> RuleId {
        let call = self.state.builder_calls[call.0 as usize];
        self.state.calls[call.index()].rule
    }

    pub fn trace(&self) -> &T {
        &self.state.trace
    }

    pub fn trace_mut(&mut self) -> &mut T {
        &mut self.state.trace
    }

    pub fn intern(&mut self, text: &str) -> Sym {
        self.state.symbols.intern(text)
    }

    pub fn text(&self, sym: Sym) -> &str {
        self.state.symbols.text(sym)
    }

    pub fn object_name(&self, object: ObjId) -> String {
        self.state.objects.name(object, &self.state.symbols)
    }

    pub fn object(&self, object: ObjId) -> &Object {
        self.state.objects.get(object)
    }

    pub fn saturated(&self) -> ObjId {
        self.state.saturated
    }

    pub fn named_nodes(&self) -> &[NodeId] {
        &self.state.named_nodes
    }

    pub fn label(&self, node: NodeId) -> Option<&str> {
        self.state.labels.get(&node).map(|label| &**label)
    }

    pub fn held(&mut self, node: NodeId) -> Vec<ObjId> {
        self.graph.objects(node)
    }

    pub fn held_saturated(&mut self, node: NodeId) -> bool {
        self.graph.is_saturated(node)
    }

    pub fn absorbed(&self) -> Vec<ObjId> {
        self.graph.absorbed()
    }

    pub fn work(&self) -> Work {
        self.graph.work()
    }

    pub fn phase(&self) -> u32 {
        self.graph.phase
    }

    pub fn solve(&mut self) {
        self.state.solve(&mut self.graph);
    }
}

impl<T: Trace> State<T> {
    fn new_object(&mut self, graph: &mut Graph, object: Object) -> ObjId {
        let kind = object.kind();
        let id = self.objects.push(object);
        graph.declare(id, kind.mask());
        let name = self.objects.name(id, &self.symbols);
        let opacity = match self.objects.get(id) {
            Object::Saturated => Opacity::Saturated,
            Object::Class(_) => Opacity::Class(id),
            &Object::Instance { class, .. } => Opacity::Class(class),
            &Object::Fallback { method } => match self.objects.get(method) {
                &Object::Instance { class, .. } => Opacity::Class(class),
                Object::Class(_) => Opacity::Class(method),
                _ => Opacity::Never,
            },
            _ => Opacity::Never,
        };
        self.trace.object(id, kind, &name, opacity);
        id
    }

    fn node(&mut self, graph: &mut Graph, label: Option<&str>) -> NodeId {
        let node = graph.node();
        if let Some(label) = label {
            self.labels.insert(node, label.into());
            self.named_nodes.push(node);
        }
        self.trace.node(node, label);
        node
    }

    fn witness(&mut self, graph: &mut Graph, watch: WatchId) -> NodeId {
        let node = graph.witness(watch);
        self.watch_of_witness.insert(node, watch);
        self.trace.witness(node, watch);
        node
    }

    fn objects_of(&mut self, graph: &mut Graph, node: NodeId) -> Vec<ObjId> {
        let objects = graph.objects(node);
        self.trace.objects(node, &objects);
        objects
    }

    fn follower(&mut self, graph: &mut Graph, source: NodeId, since: u32) -> NodeId {
        let node = graph.follower(self, source, since);
        self.trace.follower(source, since, node);
        node
    }

    fn is_saturated(&mut self, graph: &mut Graph, node: NodeId) -> bool {
        let answer = graph.is_saturated(node);
        self.trace.is_saturated(node, answer);
        answer
    }

    fn apply_now(&mut self, graph: &mut Graph, node: NodeId, rule: RuleId) {
        self.trace.apply_now(node, rule);
        graph.apply_now(self, node, rule);
    }

    fn read_field(&mut self, graph: &mut Graph, instance: ObjId, name: Sym, dst: NodeId) {
        if let Some(&node) = self
            .fields
            .get(&instance)
            .and_then(|fields| fields.get(&name))
        {
            self.add_edge(graph, node, dst);
            return;
        }
        let &Object::Instance { class, .. } = self.objects.get(instance) else {
            panic!("a field read of an instance")
        };
        self.field_readers
            .entry((class, name))
            .or_default()
            .entry(dst)
            .or_default()
            .push(instance);
    }

    fn holds(&mut self, graph: &mut Graph, node: NodeId, object: ObjId) -> bool {
        let answer = graph.holds(node, object);
        self.trace.holds(node, object, answer);
        answer
    }

    fn object_name(&self, object: ObjId) -> String {
        self.objects.name(object, &self.symbols)
    }

    fn constant(&mut self, graph: &mut Graph, object: ObjId) -> NodeId {
        if let Some(&node) = self.constants.get(&object) {
            return node;
        }
        let node = graph.constant(object);
        self.trace.constant(object, node);
        self.constants.insert(object, node);
        node
    }

    fn add_object(&mut self, graph: &mut Graph, node: NodeId, object: ObjId) {
        self.trace.add_object(node, object);
        graph.add_object(self, node, object);
    }

    fn add_edge(&mut self, graph: &mut Graph, source: NodeId, target: NodeId) {
        self.trace.add_edge(source, target);
        graph.add_edge(self, source, target);
    }

    fn attach(&mut self, graph: &mut Graph, node: NodeId, rule: RuleId) {
        self.trace.attach(node, rule);
        graph.attach(self, node, rule);
    }

    fn field(&mut self, graph: &mut Graph, object: ObjId, name: Sym) -> NodeId {
        assert!(
            !matches!(self.objects.get(object), Object::Const { .. }),
            "a constant has no fields"
        );
        if let Some(&node) = self
            .fields
            .get(&object)
            .and_then(|fields| fields.get(&name))
        {
            return node;
        }
        let label = format!(
            "{}.{}",
            self.objects.name(object, &self.symbols),
            self.symbols.text(name)
        );
        let node = self.node(graph, Some(&label));
        self.fields.entry(object).or_default().insert(name, node);
        if let &Object::Instance { class, .. } = self.objects.get(object) {
            let readers: Vec<NodeId> = self
                .field_readers
                .get(&(class, name))
                .map(|readers| {
                    readers
                        .iter()
                        .filter(|(_, receivers)| receivers.contains(&object))
                        .map(|(&dst, _)| dst)
                        .collect()
                })
                .unwrap_or_default();
            for dst in readers {
                self.add_edge(graph, node, dst);
            }
        }
        node
    }

    fn module(&mut self, graph: &mut Graph, name: &str) -> ObjId {
        let name = self.symbols.intern(name);
        if let Some(&module) = self.modules.get(&name) {
            return module;
        }
        let module = self.new_object(
            graph,
            Object::Module(Module {
                name,
                defines: FxHashSet::default(),
            }),
        );
        self.modules.insert(name, module);
        module
    }

    fn external(&mut self, graph: &mut Graph, name: &str, steps: u32, inexact: bool) -> ObjId {
        let renamed;
        let name = match name.split_once('.') {
            Some(("builtins", rest)) => {
                renamed = format!("{BUILTIN_MODULE}.{rest}");
                &renamed
            }
            None if name == "builtins" => BUILTIN_MODULE,
            _ => name,
        };
        let name = self.symbols.intern(name);
        let key = (name, steps, inexact);
        if let Some(&external) = self.externals.get(&key) {
            return external;
        }
        let external = self.new_object(
            graph,
            Object::External(External {
                name,
                steps,
                inexact,
            }),
        );
        self.externals.insert(key, external);
        external
    }

    fn const_object(&mut self, graph: &mut Graph, value: &Literal) -> ObjId {
        if let Some(&object) = self.consts.get(value) {
            return object;
        }
        let object = self.new_object(
            graph,
            Object::Const {
                value: value.clone(),
                exact: true,
            },
        );
        self.consts.insert(value.clone(), object);
        object
    }

    fn function(
        &mut self,
        graph: &mut Graph,
        name: &str,
        module: &str,
        signature: &Signature,
        defaults: &[(Box<str>, Option<NodeId>)],
        generator: bool,
    ) -> ObjId {
        let mut parameters = Vec::new();
        for parameter in signature.names() {
            let node = self.node(graph, Some(&format!("{name}.{parameter}")));
            parameters.push((self.symbols.intern(parameter), node));
        }
        let return_node = self.node(graph, Some(&format!("{name}.<return>")));
        let optional = defaults
            .iter()
            .map(|(parameter, _)| self.symbols.intern(parameter))
            .collect();
        let given = defaults
            .iter()
            .filter_map(|(parameter, default)| {
                default.map(|default| (self.symbols.intern(parameter), default))
            })
            .collect();
        let function_name = self.symbols.intern(name);
        let module = self.symbols.intern(module);
        let function = self.new_object(
            graph,
            Object::Function(Box::new(Function {
                name: function_name,
                module,
                signature: signature.clone(),
                parameters,
                defaults: given,
                optional,
                return_node: Some(return_node),
                yield_node: None,
                sent_node: None,
                is_async: false,
                varargs: None,
                varkeywords: None,
                passthrough: Vec::new(),
                decorated: false,
                lineno: None,
                col_offset: None,
                end_lineno: None,
                end_col_offset: None,
            })),
        );
        if generator {
            let yield_node = self.node(graph, Some(&format!("{name}.<yield>")));
            let sent_node = self.node(graph, Some(&format!("{name}.<sent>")));
            let made = self.objects.function_mut(function);
            made.yield_node = Some(yield_node);
            made.sent_node = Some(sent_node);
        }
        for (parameter, kind) in [(&signature.vararg, "tuple"), (&signature.kwarg, "dict")] {
            let Some(parameter) = parameter.as_deref().filter(|name| !name.is_empty()) else {
                continue;
            };
            let container = Container {
                kind: self.symbols.intern(kind),
                site: function_name,
                length: None,
                exact: true,
            };
            let container = self.new_object(graph, Object::Container(container));
            let made = self.objects.function_mut(function);
            if kind == "tuple" {
                made.varargs = Some(container);
            } else {
                made.varkeywords = Some(container);
            }
            let parameter = self.symbols.intern(parameter);
            let node = self.objects.function(function).parameter(parameter);
            self.add_object(graph, node, container);
        }
        self.functions.push(function);
        function
    }
}
