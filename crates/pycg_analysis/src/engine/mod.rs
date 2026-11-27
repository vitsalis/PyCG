mod arguments;
mod containers;
mod fixpoint;
pub mod hierarchy;
pub mod objects;
mod outside;
mod rules;
mod semantics;
pub mod symbols;
pub mod trace;

use std::rc::Rc;

use indexmap::{IndexMap, IndexSet};
use pycg_solver::{NodeId, ObjId, Solver, WatchId, Work};
use pycg_stubs::{Definition, Stubs};
use rustc_hash::{FxBuildHasher, FxHashMap, FxHashSet};

use crate::model::{BUILTIN_MODULE, Signature};
use hierarchy::{LookupAttr, Namespace, NewClass, Unless};
use objects::{Class, Container, External, Function, Kind, Literal, Module, Object, Objects};
pub use rules::RuleId;
use rules::{Rule, WaitingRule};
use semantics::{Call, Construct, Origin, Receivers, Returned, ReturnedId, SiteKey};
pub use semantics::{CallId, NewCall};
use symbols::{Sym, Symbols};
use trace::{Opacity, Trace};

pub(crate) type OrderedMap<K, V> = IndexMap<K, V, FxBuildHasher>;
pub(crate) type OrderedSet<K> = IndexSet<K, FxBuildHasher>;

pub const EXTERNAL_STEPS_PAST_ROOT_MAX: u32 = 2;

pub type Graph = Solver<RuleId>;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MethodKind {
    StaticMethod,
    ClassMethod,
}

type Receiver = (NodeId, NodeId, ObjId, ObjId, Sym);

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
    prefixes: FxHashMap<CallId, (CallId, Receivers)>,
    site_edges: OrderedMap<(Sym, Sym, Construct), OrderedSet<Sym>>,
    call_expressions: Vec<(Sym, Sym, Option<NodeId>)>,
    classes: Vec<ObjId>,
    stubs: Stubs,
    stub_definitions: FxHashMap<Sym, Option<Rc<[Definition]>>>,
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
            site_edges: OrderedMap::default(),
            call_expressions: Vec::new(),
            classes: Vec::new(),
            stubs: Stubs::new(),
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

    pub fn function_mut(&mut self, function: ObjId) -> &mut Function {
        self.state.objects.function_mut(function)
    }

    pub fn class_mut(&mut self, class: ObjId) -> &mut Class {
        self.state.objects.class_mut(class)
    }

    pub fn module_defines_mut(&mut self, module: ObjId) -> &mut FxHashSet<Sym> {
        match self.state.objects.get_mut(module) {
            Object::Module(module) => &mut module.defines,
            _ => panic!("object {module:?} is not a module"),
        }
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

    pub fn node(&mut self, label: Option<&str>) -> NodeId {
        self.state.node(&mut self.graph, label)
    }

    pub fn constant(&mut self, object: ObjId) -> NodeId {
        self.state.constant(&mut self.graph, object)
    }

    pub fn const_object(&mut self, value: &Literal) -> ObjId {
        self.state.const_object(&mut self.graph, value)
    }

    pub fn field(&mut self, object: ObjId, name: &str) -> NodeId {
        let name = self.state.symbols.intern(name);
        self.state.field(&mut self.graph, object, name)
    }

    pub fn add_edge(&mut self, source: NodeId, target: NodeId) {
        self.state.add_edge(&mut self.graph, source, target);
    }

    pub fn add_object(&mut self, node: NodeId, object: ObjId) {
        self.state.add_object(&mut self.graph, node, object);
    }

    pub fn module(&mut self, name: &str) -> ObjId {
        self.state.module(&mut self.graph, name)
    }

    pub fn external(&mut self, name: &str, steps: u32, inexact: bool) -> ObjId {
        self.state.external(&mut self.graph, name, steps, inexact)
    }

    pub fn function(
        &mut self,
        name: &str,
        module: &str,
        signature: &Signature,
        defaults: &[(Box<str>, Option<NodeId>)],
        generator: bool,
    ) -> ObjId {
        self.state.function(
            &mut self.graph,
            name,
            module,
            signature,
            defaults,
            generator,
        )
    }

    pub fn add_call(&mut self, call: &NewCall<'_>) {
        self.state.add_call(&mut self.graph, call);
    }

    pub fn new_class(&mut self, class: &NewClass<'_>) -> ObjId {
        self.state.new_class(&mut self.graph, class)
    }

    pub fn add_method(
        &mut self,
        class: ObjId,
        name: &str,
        function: ObjId,
        kind: Option<MethodKind>,
    ) {
        self.state
            .add_method(&mut self.graph, class, name, function, kind);
    }

    pub fn add_class_member(&mut self, value: NodeId, field: NodeId) {
        self.state.add_inexact(&mut self.graph, value, field);
    }

    pub fn add_set_name(
        &mut self,
        value: NodeId,
        class: ObjId,
        name: &str,
        caller: &str,
        site: &str,
    ) {
        self.state
            .add_set_name(&mut self.graph, value, class, name, caller, site);
    }

    pub fn add_init_subclass(
        &mut self,
        class: ObjId,
        keywords: &[(Box<str>, Option<NodeId>)],
        double_star: &[Option<NodeId>],
        caller: &str,
        site: &str,
    ) {
        self.state
            .add_init_subclass(&mut self.graph, class, keywords, double_star, caller, site);
    }

    pub fn add_metaclass_call(&mut self, class: ObjId) {
        self.state.add_metaclass_call(&mut self.graph, class);
    }

    pub fn imported_value(&mut self, name: &str) -> NodeId {
        self.state.imported_value(&mut self.graph, name)
    }

    pub fn add_external_module(&mut self, name: &str) {
        self.state.add_external_module(name);
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
                return_node,
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
