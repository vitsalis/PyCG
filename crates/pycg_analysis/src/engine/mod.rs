mod arguments;
mod fixpoint;
pub mod objects;
mod semantics;
pub mod symbols;
pub mod trace;

use indexmap::{IndexMap, IndexSet};
use pycg_solver::{KindMask, NodeId, ObjId, Rules, Solver, WatchId, Work};
use rustc_hash::{FxBuildHasher, FxHashMap, FxHashSet};

use crate::model::{BUILTIN_MODULE, Signature};
use objects::{Container, External, Function, Kind, Literal, Module, Object, Objects};
use semantics::{Call, Construct, Receivers};
pub use semantics::{CallId, NewCall};
use symbols::{Sym, Symbols};
use trace::{Opacity, RuleInfo, Trace};

type OrderedMap<K, V> = IndexMap<K, V, FxBuildHasher>;
type OrderedSet<K> = IndexSet<K, FxBuildHasher>;

pub const EXTERNAL_STEPS_PAST_ROOT_MAX: u32 = 2;

pub type Graph = Solver<RuleId>;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct RuleId(u32);

#[derive(Clone, Copy, Debug)]
enum Rule {
    Call(CallId),
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
    prefixes: FxHashMap<CallId, (CallId, Receivers)>,
    site_edges: OrderedMap<(Sym, Sym, Construct), OrderedSet<Sym>>,
    call_expressions: Vec<(Sym, Sym, Option<NodeId>)>,
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
        let opacity = match kind {
            Kind::Saturated => Opacity::Saturated,
            _ => Opacity::Never,
        };
        self.trace.object(id, kind, &name, opacity);
        id
    }

    fn new_rule(&mut self, rule: Rule, info: &RuleInfo<'_>) -> RuleId {
        let id = RuleId(u32::try_from(self.rules.len()).expect("fewer than 2^32 rules"));
        self.rules.push(rule);
        self.trace.rule(id, info);
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

impl<T: Trace> Rules<RuleId> for State<T> {
    fn apply(&mut self, graph: &mut Graph, rule: RuleId, objects: &[ObjId]) {
        match self.rules[rule.0 as usize] {
            Rule::Call(call) => {
                self.trace.apply(rule, objects);
                for &object in objects {
                    self.call(graph, object, call);
                }
                self.trace.applied();
            }
        }
    }

    fn saturate(&mut self, graph: &mut Graph, rule: RuleId) {
        self.trace.saturate(rule);
        match self.rules[rule.0 as usize] {
            Rule::Call(call) => {
                if let Some(dst) = self.calls[call.index()].dst {
                    let saturated = self.saturated;
                    self.add_object(graph, dst, saturated);
                }
            }
        }
        self.trace.saturated();
    }

    fn kinds(&self, rule: RuleId) -> Option<KindMask> {
        match self.rules[rule.0 as usize] {
            Rule::Call(_) => None,
        }
    }

    fn captures_opaque(&self, _graph: &Graph, rule: RuleId) -> bool {
        match self.rules[rule.0 as usize] {
            Rule::Call(_) => false,
        }
    }

    fn opaque(&self, object: ObjId) -> bool {
        matches!(self.objects.get(object), Object::Saturated)
    }

    fn between_rounds(&mut self, _graph: &mut Graph) -> bool {
        self.trace.between_rounds();
        self.trace.between_rounds_done(false, &[]);
        false
    }

    fn wake(&mut self, _graph: &mut Graph, _watch: WatchId) {
        not_ported("watches")
    }

    fn firing(&mut self, graph: &mut Graph) {
        self.trace.fire(graph, &self.named_nodes);
    }
}
