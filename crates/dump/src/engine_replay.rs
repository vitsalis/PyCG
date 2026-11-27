use std::collections::BTreeMap;
use std::fs::{self, File};
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::panic::{self, AssertUnwindSafe};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use indexmap::IndexMap;
use num_bigint::BigInt;
use pycg_analysis::CAP_DEFAULT_OBJECTS;
use pycg_analysis::builder::calls::CallId as BuilderCallId;
use pycg_analysis::builder::calls::{
    Allocator, Analysis, Call, CallSite, ClassStatement, Constant, Key, MethodKind, NewClass,
    Operation, Passthrough, Shape, Slice, Subscript,
};
use pycg_analysis::engine::objects::{Kind, Object};
use pycg_analysis::engine::trace::{Opacity, RuleInfo, Trace};
use pycg_analysis::engine::{Engine, RuleId, not_ported};
use pycg_analysis::model::Signature;
use pycg_analysis::program::Program;
use pycg_solver::{NodeId, ObjId, Solver, WatchId};
use rustc_hash::{FxHashMap, FxHashSet};
use serde_json::{Value, json};

use crate::canonical;

const CONTEXT_PROGRAM: &str = "<program>";
const CONTEXT_SOLVE: &str = "<solve>";
const PROGRAM: &str = "<program>";
const PARTIAL_TRACE: &str = "D3.partial.jsonl";
const IMPORT_MANAGER_CALLS: &[&str] = &["imports.handle_import", "imports.locate"];

struct DeclaredObject {
    kind: Kind,
    opacity: Opacity,
}

struct DeclaredRule {
    name: String,
    call: bool,
    kinds: Option<Vec<&'static str>>,
    each: bool,
    captured: Vec<ObjId>,
}

pub struct Recorder {
    trace: BufWriter<File>,
    context: String,
    label_counts: FxHashMap<String, u32>,
    context_counts: FxHashMap<String, u32>,
    node_names: FxHashMap<NodeId, String>,
    node_by_name: FxHashMap<String, NodeId>,
    reported: Vec<NodeId>,
    object_names: FxHashMap<ObjId, String>,
    object_by_name: FxHashMap<String, ObjId>,
    object_counts: FxHashMap<String, u32>,
    objects: FxHashMap<ObjId, DeclaredObject>,
    fresh: Vec<ObjId>,
    rules: FxHashMap<RuleId, DeclaredRule>,
    other_counts: FxHashMap<String, u32>,
    declared_objects: FxHashSet<ObjId>,
    declared_rules: FxHashSet<RuleId>,
    first_rounds: FxHashMap<(NodeId, ObjId), u32>,
    round: u32,
    witness_of_watch: FxHashMap<WatchId, NodeId>,
}

impl Recorder {
    fn new(out: &Path) -> Recorder {
        let path = out.join(PARTIAL_TRACE);
        let file = File::create(&path)
            .unwrap_or_else(|error| panic!("{} cannot be written: {error}", path.display()));
        Recorder {
            trace: BufWriter::new(file),
            context: CONTEXT_PROGRAM.to_string(),
            label_counts: FxHashMap::default(),
            context_counts: FxHashMap::default(),
            node_names: FxHashMap::default(),
            node_by_name: FxHashMap::default(),
            reported: Vec::new(),
            object_names: FxHashMap::default(),
            object_by_name: FxHashMap::default(),
            object_counts: FxHashMap::default(),
            objects: FxHashMap::default(),
            fresh: Vec::new(),
            rules: FxHashMap::default(),
            other_counts: FxHashMap::default(),
            declared_objects: FxHashSet::default(),
            declared_rules: FxHashSet::default(),
            first_rounds: FxHashMap::default(),
            round: 0,
            witness_of_watch: FxHashMap::default(),
        }
    }

    fn write(&mut self, value: &Value) {
        self.trace
            .write_all(canonical::line(value).as_bytes())
            .expect("the trace is written");
    }

    fn name_node(&mut self, node: NodeId, label: Option<&str>) -> String {
        assert!(
            !self.node_names.contains_key(&node),
            "node {node:?} is named twice"
        );
        let name = match label {
            Some(label) => numbered(&mut self.label_counts, label, '~'),
            None => {
                let count = self.context_counts.entry(self.context.clone()).or_insert(0);
                *count += 1;
                format!("{}#{count}", self.context)
            }
        };
        self.node_names.insert(node, name.clone());
        self.node_by_name.insert(name.clone(), node);
        name
    }

    fn node_name(&self, node: NodeId) -> &str {
        self.node_names
            .get(&node)
            .unwrap_or_else(|| panic!("node {node:?} has no name"))
    }

    fn object_name(&self, object: ObjId) -> &str {
        self.object_names
            .get(&object)
            .unwrap_or_else(|| panic!("object {object:?} has no name"))
    }

    fn node_value(&self, node: NodeId) -> Value {
        json!({"node": self.node_name(node)})
    }

    fn object_value(&self, object: ObjId) -> Value {
        json!({"object": self.object_name(object)})
    }

    pub(crate) fn rule_value(&self, rule: RuleId) -> Value {
        let declared = &self.rules[&rule];
        if declared.call {
            json!({"call": declared.name})
        } else {
            json!({"constraint": declared.name})
        }
    }

    fn declare_object(&mut self, object: ObjId) {
        if !self.declared_objects.insert(object) {
            return;
        }
        let opacity = self.objects[&object].opacity;
        let opacity = match opacity {
            Opacity::Never => Value::Null,
            Opacity::Saturated => json!("saturated"),
            Opacity::Class(class) => {
                self.declare_object(class);
                json!(self.object_name(class))
            }
        };
        let declared = &self.objects[&object];
        let types: Vec<&str> = declared.kind.mro().iter().map(|kind| kind.name()).collect();
        let record = json!({
            "op": "object",
            "object": self.object_name(object),
            "types": types,
            "opacity": opacity,
        });
        self.write(&record);
    }

    fn declare_rule(&mut self, rule: RuleId) {
        if !self.declared_rules.insert(rule) {
            return;
        }
        let captured = self.rules[&rule].captured.clone();
        for &object in &captured {
            self.declare_object(object);
        }
        let declared = &self.rules[&rule];
        let names: Vec<&str> = captured
            .iter()
            .map(|&object| self.object_name(object))
            .collect();
        let record = json!({
            "op": "constraint",
            "constraint": declared.name,
            "kinds": declared.kinds,
            "mode": if declared.each { "each" } else { "list" },
            "captured": names,
        });
        self.write(&record);
    }

    fn note_first_rounds(&mut self, solver: &mut Solver<RuleId>, named_nodes: &[NodeId]) {
        for &node in named_nodes {
            for object in solver.objects(node) {
                self.first_rounds
                    .entry((node, object))
                    .or_insert(self.round);
            }
        }
    }

    fn node_named(&self, value: &Value) -> NodeId {
        let name = value["node"]
            .as_str()
            .unwrap_or_else(|| panic!("not a node: {value}"));
        *self
            .node_by_name
            .get(name)
            .unwrap_or_else(|| panic!("the engine made no node named {name}"))
    }

    fn object_named(&self, value: &Value) -> ObjId {
        let name = value["object"]
            .as_str()
            .unwrap_or_else(|| panic!("not an object: {value}"));
        *self
            .object_by_name
            .get(name)
            .unwrap_or_else(|| panic!("the engine made no object named {name}"))
    }
}

fn numbered(counts: &mut FxHashMap<String, u32>, key: &str, separator: char) -> String {
    let count = counts.entry(key.to_string()).or_insert(0);
    *count += 1;
    if *count == 1 {
        key.to_string()
    } else {
        format!("{key}{separator}{count}")
    }
}

impl Trace for Recorder {
    fn module(&mut self, module: Option<&str>) {
        self.context = module.unwrap_or(CONTEXT_PROGRAM).to_string();
    }

    fn solver(&mut self, cap: Option<u32>, saturated: ObjId, node: NodeId) {
        self.write(&json!({"op": "solver", "cap": cap}));
        self.declare_object(saturated);
        self.name_node(node, None);
        let record = json!({
            "op": "constant",
            "args": [self.object_value(saturated)],
            "answer": self.node_value(node),
        });
        self.write(&record);
    }

    fn node(&mut self, node: NodeId, label: Option<&str>) {
        let name = self.name_node(node, label);
        self.reported.push(node);
        let mut record = json!({"op": "node", "node": name});
        if label.is_some() {
            record["named"] = json!(true);
        }
        self.write(&record);
    }

    fn witness(&mut self, node: NodeId, watch: WatchId) {
        let name = self.name_node(node, None);
        self.reported.push(node);
        self.witness_of_watch.insert(watch, node);
        self.write(&json!({"op": "node", "node": name, "witness": true}));
    }

    fn wake(&mut self, watch: WatchId) {
        let node = self.witness_of_watch[&watch];
        let record = json!({"op": "wake", "node": self.node_name(node)});
        self.write(&record);
    }

    fn woken(&mut self) {
        self.write(&json!({"op": "woken"}));
    }

    fn object(&mut self, object: ObjId, kind: Kind, name: &str, opacity: Opacity) {
        let key = format!("{}:{name}", kind.name());
        let name = numbered(&mut self.object_counts, &key, '~');
        self.object_by_name.insert(name.clone(), object);
        self.object_names.insert(object, name);
        self.objects
            .insert(object, DeclaredObject { kind, opacity });
        self.fresh.push(object);
    }

    fn rule(&mut self, rule: RuleId, info: &RuleInfo<'_>) {
        let name = numbered(&mut self.other_counts, info.key, '~');
        let declared = DeclaredRule {
            name,
            call: info.key.starts_with("Call:"),
            kinds: info
                .kinds
                .map(|kinds| kinds.iter().map(|kind| kind.name()).collect()),
            each: info.each,
            captured: info.captured.to_vec(),
        };
        self.rules.insert(rule, declared);
    }

    fn constant(&mut self, object: ObjId, node: NodeId) {
        self.declare_object(object);
        self.name_node(node, None);
        let record = json!({
            "op": "constant",
            "args": [self.object_value(object)],
            "answer": self.node_value(node),
        });
        self.write(&record);
    }

    fn add_object(&mut self, node: NodeId, object: ObjId) {
        self.declare_object(object);
        let record = json!({
            "op": "add_object",
            "args": [self.node_value(node), self.object_value(object)],
        });
        self.write(&record);
    }

    fn add_edge(&mut self, source: NodeId, target: NodeId) {
        let record = json!({
            "op": "add_edge",
            "args": [self.node_value(source), self.node_value(target)],
        });
        self.write(&record);
    }

    fn attach(&mut self, node: NodeId, rule: RuleId) {
        self.declare_rule(rule);
        let record = json!({
            "op": "attach",
            "args": [self.node_value(node), self.rule_value(rule)],
        });
        self.write(&record);
    }

    fn objects(&mut self, node: NodeId, objects: &[ObjId]) {
        let answer: Vec<Value> = objects
            .iter()
            .map(|&object| self.object_value(object))
            .collect();
        let record = json!({"op": "objects", "args": [self.node_value(node)], "answer": answer});
        self.write(&record);
    }

    fn holds(&mut self, node: NodeId, object: ObjId, answer: bool) {
        let record = json!({
            "op": "holds",
            "args": [self.node_value(node), self.object_value(object)],
            "answer": answer,
        });
        self.write(&record);
    }

    fn is_saturated(&mut self, node: NodeId, answer: bool) {
        let record = json!({
            "op": "is_saturated",
            "args": [self.node_value(node)],
            "answer": answer,
        });
        self.write(&record);
    }

    fn follower(&mut self, source: NodeId, since: u32, node: NodeId) {
        self.name_node(node, None);
        self.reported.push(node);
        let record = json!({
            "op": "follower",
            "args": [self.node_value(source), since],
            "answer": self.node_value(node),
        });
        self.write(&record);
    }

    fn apply_now(&mut self, node: NodeId, rule: RuleId) {
        self.declare_rule(rule);
        let record = json!({
            "op": "apply_now",
            "args": [self.node_value(node), self.rule_value(rule)],
        });
        self.write(&record);
    }

    fn apply(&mut self, rule: RuleId, objects: &[ObjId]) {
        self.declare_rule(rule);
        let listed: Vec<Value> = objects
            .iter()
            .map(|&object| self.object_value(object))
            .collect();
        let record = json!({
            "op": "apply",
            "constraint": self.rules[&rule].name,
            "objects": listed,
        });
        self.write(&record);
    }

    fn applied(&mut self) {
        self.write(&json!({"op": "applied"}));
    }

    fn saturate(&mut self, rule: RuleId) {
        self.declare_rule(rule);
        let record = json!({"op": "saturate", "constraint": self.rules[&rule].name});
        self.write(&record);
    }

    fn saturated(&mut self) {
        self.write(&json!({"op": "saturated"}));
    }

    fn solve(&mut self) {
        self.write(&json!({"op": "solve"}));
    }

    fn solved(&mut self, phase: u32) {
        self.write(&json!({"op": "solved", "phase": phase}));
    }

    fn between_rounds(&mut self) {
        self.write(&json!({"op": "between_rounds"}));
    }

    fn between_rounds_done(&mut self, answer: bool, unknown: &[ObjId]) {
        let unknown: Vec<&str> = unknown
            .iter()
            .map(|&class| self.object_name(class))
            .collect();
        let record = json!({"op": "between_rounds_done", "answer": answer, "unknown": unknown});
        self.write(&record);
    }

    fn fire(&mut self, solver: &mut Solver<RuleId>, named_nodes: &[NodeId]) {
        self.note_first_rounds(solver, named_nodes);
        self.round += 1;
        self.write(&json!({"op": "fire", "phase": solver.phase}));
    }
}

struct Replay {
    engine: Engine<Recorder>,
    fields: FxHashMap<String, Vec<Value>>,
    calls: FxHashMap<String, BuilderCallId>,
    built: Vec<String>,
    annotations: FxHashMap<ObjId, Value>,
}

pub fn build(arguments: &[String]) -> Option<ExitCode> {
    let [command, out, flag, package, entry_points @ ..] = arguments else {
        return None;
    };
    if command != "engine-build" || flag != "--package" || entry_points.is_empty() {
        return None;
    }
    let cwd = std::env::current_dir().expect("a working directory");
    let entry_points: Vec<PathBuf> = entry_points.iter().map(PathBuf::from).collect();
    let engine = Engine::new(Some(CAP_DEFAULT_OBJECTS), Recorder::new(Path::new(out)));
    let mut program = Program::new(&entry_points, Some(Path::new(package)), &cwd, engine);
    let built = panic::catch_unwind(AssertUnwindSafe(|| {
        program.build_modules();
        program.analysis.trace_mut().context = CONTEXT_SOLVE.to_string();
        program.analysis.solve();
    }));
    let modules: Vec<String> = program.modules.keys().cloned().collect();
    let replay = Replay {
        engine: program.analysis,
        fields: FxHashMap::default(),
        calls: FxHashMap::default(),
        built: modules,
        annotations: FxHashMap::default(),
    };
    Some(replay.write(Path::new(out), built.is_ok()))
}

pub fn run(input: &str, out: &str) -> ExitCode {
    let lines = || -> std::io::Result<std::io::Lines<BufReader<File>>> {
        Ok(BufReader::new(File::open(input)?).lines())
    };
    if let Err(error) = lines() {
        eprintln!("pycg-dump engine: cannot read {input}: {error}");
        return ExitCode::FAILURE;
    }
    let out = Path::new(out);
    let mut replay = Replay {
        engine: Engine::new(Some(CAP_DEFAULT_OBJECTS), Recorder::new(out)),
        fields: FxHashMap::default(),
        calls: FxHashMap::default(),
        built: Vec::new(),
        annotations: FxHashMap::default(),
    };
    let replayed = panic::catch_unwind(AssertUnwindSafe(|| {
        let record = |number: usize, line: &str| -> Value {
            serde_json::from_str(line).unwrap_or_else(|error| {
                not_ported(&format!("the record {} of D4 as JSON: {error}", number + 1))
            })
        };
        let read = |line: std::io::Result<String>| line.expect("the D4 dump is readable");
        for (number, line) in lines().expect("the D4 dump opens").enumerate() {
            replay.prescan(&record(number, &read(line)));
        }
        for (number, line) in lines().expect("the D4 dump opens").enumerate() {
            let record = record(number, &read(line));
            if record.get("call").is_some() {
                replay.call(number + 1, &record);
            } else if record.get("fields").is_some() && record["module"] == PROGRAM {
                let object = replay.object(&record["object"]);
                let name = replay.engine.trace().object_name(object).to_string();
                replay.set_recorded_fields(object, &name, &record["fields"]);
            } else if record.get("fields").is_some() {
                let object = replay.object(&record["object"]);
                replay.apply_annotations(object);
            }
        }
        replay.engine.trace_mut().context = CONTEXT_SOLVE.to_string();
        replay.engine.solve();
    }));
    replay.write(out, replayed.is_ok())
}

impl Replay {
    fn write(self, out: &Path, finished: bool) -> ExitCode {
        let mut replay = self;
        if !finished {
            replay
                .engine
                .trace_mut()
                .trace
                .flush()
                .expect("the partial trace is written");
            return ExitCode::FAILURE;
        }
        let points_to = replay.finish();
        replay
            .engine
            .trace_mut()
            .trace
            .flush()
            .expect("the trace is written");
        if let Err(error) = fs::rename(out.join(PARTIAL_TRACE), out.join("D3.jsonl")) {
            eprintln!("pycg-dump engine: cannot name the trace D3.jsonl: {error}");
            return ExitCode::FAILURE;
        }
        if let Err(error) = fs::write(out.join("D5.jsonl"), points_to.concat()) {
            eprintln!("pycg-dump engine: cannot write D5.jsonl: {error}");
            return ExitCode::FAILURE;
        }
        let mut analysis = pycg_document::dumps(&crate::document_build::analysis_value(
            &replay.engine.results(&replay.built),
        ));
        analysis.push('\n');
        if let Err(error) = fs::write(out.join("D6in.json"), analysis) {
            eprintln!("pycg-dump engine: cannot write D6in.json: {error}");
            return ExitCode::FAILURE;
        }
        ExitCode::SUCCESS
    }

    fn prescan(&mut self, record: &Value) {
        {
            if let Some(fields) = record.get("fields")
                && record["module"] != PROGRAM
            {
                let name = record["object"]["object"]
                    .as_str()
                    .expect("the fields of an object");
                self.fields
                    .entry(name.to_string())
                    .or_default()
                    .push(fields.clone());
            }
            if let Some(tables) = record.get("tables") {
                let module = text(&record["module"]).to_owned();
                if !self.built.contains(&module) {
                    self.built.push(module);
                }
                if !empty_collection(&tables["literal_imports"]) {
                    not_ported("the builder table literal_imports");
                }
                for site in set(&tables["zero_argument_super"]) {
                    self.engine
                        .tables()
                        .zero_argument_super
                        .push(text(site).into());
                }
                for name in set(&tables["read_namespaces"]) {
                    self.engine.tables().read_namespaces.push(text(name).into());
                }
                for pair in set(&tables["iterated_expressions"]) {
                    let site: CallSite = (text(&pair[0]).into(), text(&pair[1]).into());
                    self.engine.tables().iterated_expressions.push(site);
                }
                for pair in pairs(&tables["none_arguments"]) {
                    let site: CallSite = (text(&pair[0][0]).into(), text(&pair[0][1]).into());
                    let indices = set(&pair[1])
                        .iter()
                        .map(|index| {
                            u32::try_from(index.as_u64().expect("an argument index"))
                                .expect("an index fits u32")
                        })
                        .collect();
                    self.engine.tables().none_arguments.push((site, indices));
                }
            }
        }
    }

    fn call(&mut self, number: usize, record: &Value) {
        let module = record["module"].as_str().expect("the module of a call");
        self.engine.trace_mut().context = module.to_string();
        let call = record["call"].as_str().expect("a call name");
        if IMPORT_MANAGER_CALLS.contains(&call) {
            return;
        }
        let arguments = &record["arguments"];
        let answer = match call {
            "module" => {
                let module = self.engine.module(text(&arguments["name"]));
                Some(self.object_answer(module))
            }
            "field" => {
                let object = self.object(&arguments["obj"]);
                let node = self.engine.field(object, text(&arguments["name"]));
                Some(self.node_answer(node))
            }
            "const" => {
                let object = self.engine.const_object(&literal(&arguments["value"]));
                Some(self.object_answer(object))
            }
            "constant" => {
                let object = self.object(&arguments["obj"]);
                let node = self.engine.constant(object);
                Some(self.node_answer(node))
            }
            "node" => {
                let node = self.engine.node(arguments["label"].as_str());
                Some(self.node_answer(node))
            }
            "add_edge" => {
                let source = self.node(&arguments["src"]);
                let target = self.node(&arguments["dst"]);
                self.engine.add_edge(source, target);
                None
            }
            "add_object" => {
                let node = self.node(&arguments["node"]);
                let object = self.object(&arguments["obj"]);
                self.engine.add_object(node, object);
                None
            }
            "function" => {
                let signature = signature(&arguments["signature"]["signature"]);
                let defaults: Vec<(Box<str>, Option<NodeId>)> = pairs(&arguments["defaults"])
                    .iter()
                    .map(|pair| (text(&pair[0]).into(), self.optional_node(&pair[1])))
                    .collect();
                let function = self
                    .engine
                    .function(
                        text(&arguments["name"]),
                        text(&arguments["module"]),
                        &signature,
                        &defaults,
                        arguments["generator"].as_bool().expect("generator"),
                    )
                    .object;
                Some(self.object_answer(function))
            }
            "new_class" => {
                let names = |value: &Value| -> Vec<Box<str>> {
                    let entries = match value.get("set") {
                        Some(_) => set(value).to_vec(),
                        None => pairs(value).iter().map(|pair| pair[0].clone()).collect(),
                    };
                    entries.iter().map(|name| text(name).into()).collect()
                };
                let defines = names(&arguments["defines"]);
                let abstract_methods = names(&arguments["abstract_methods"]);
                let base_nodes: Vec<Option<NodeId>> = list(&arguments["base_nodes"])
                    .iter()
                    .map(|node| self.optional_node(node))
                    .collect();
                let metaclass = self.optional_node(&arguments["metaclass"]);
                let class = self.engine.new_class(&NewClass {
                    name: text(&arguments["name"]),
                    module: text(&arguments["module"]),
                    defines: &defines,
                    base_nodes: &base_nodes,
                    protocol: arguments["protocol"].as_bool().expect("protocol"),
                    abstract_methods: &abstract_methods,
                    metaclass,
                    uses_namespace: arguments["uses_namespace"]
                        .as_bool()
                        .expect("uses_namespace"),
                });
                Some(self.object_answer(class))
            }
            "add_method" => {
                let class = self.object(&arguments["cls"]);
                let function = self.object(&arguments["function"]);
                let kind = match arguments["kind"].as_str() {
                    None => None,
                    Some("staticmethod") => Some(MethodKind::StaticMethod),
                    Some("classmethod") => Some(MethodKind::ClassMethod),
                    Some(other) => panic!("a method kind: {other}"),
                };
                self.engine
                    .add_method(class, text(&arguments["name"]), function, kind);
                None
            }
            "add_implicit_method" => {
                let value = self.node(&arguments["value"]);
                let field = self.node(&arguments["field"]);
                let kind = match text(&arguments["kind"]) {
                    "staticmethod" => MethodKind::StaticMethod,
                    "classmethod" => MethodKind::ClassMethod,
                    other => panic!("a method kind: {other}"),
                };
                self.engine
                    .add_implicit_method(value, field, kind, text(&arguments["site"]));
                None
            }
            "add_class_member" => {
                let value = self.node(&arguments["value"]);
                let field = self.node(&arguments["field"]);
                self.engine.add_class_member(value, field);
                None
            }
            "add_set_name" => {
                let value = self.node(&arguments["value"]);
                let class = self.object(&arguments["cls"]);
                self.engine.add_set_name(
                    value,
                    class,
                    text(&arguments["name"]),
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                );
                None
            }
            "add_init_subclass" => {
                let class = self.object(&arguments["cls"]);
                let keywords: Vec<(Box<str>, Option<NodeId>)> = list(&arguments["keywords"])
                    .iter()
                    .map(|pair| (text(&pair[0]).into(), self.optional_node(&pair[1])))
                    .collect();
                let double_star: Vec<Option<NodeId>> = list(&arguments["double_star"])
                    .iter()
                    .map(|mapping| self.optional_node(mapping))
                    .collect();
                self.engine.add_init_subclass(
                    class,
                    &keywords,
                    &double_star,
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                );
                None
            }
            "add_metaclass_call" => {
                let class = self.object(&arguments["cls"]);
                let recorded = list(&arguments["statement"]);
                let bases: Vec<Option<NodeId>> = list(&recorded[1])
                    .iter()
                    .map(|base| self.optional_node(base))
                    .collect();
                let namespace: Vec<(Box<str>, NodeId)> = list(&recorded[2])
                    .iter()
                    .map(|pair| (text(&pair[0]).into(), self.node(&pair[1])))
                    .collect();
                let keywords: Vec<(Box<str>, Option<NodeId>)> = list(&recorded[3])
                    .iter()
                    .map(|pair| (text(&pair[0]).into(), self.optional_node(&pair[1])))
                    .collect();
                let double_star: Vec<Option<NodeId>> = list(&recorded[4])
                    .iter()
                    .map(|mapping| self.optional_node(mapping))
                    .collect();
                let statement = ClassStatement {
                    name: text(&recorded[0]),
                    bases: &bases,
                    namespace: &namespace,
                    keywords: &keywords,
                    double_star: &double_star,
                };
                self.engine.add_metaclass_call(
                    class,
                    &statement,
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                );
                None
            }
            "imported_value" => {
                let node = self.engine.imported_value(text(&arguments["name"]));
                Some(self.node_answer(node))
            }
            "external" => {
                let steps = u32::try_from(arguments["steps"].as_u64().expect("steps"))
                    .expect("steps fit u32");
                let external = self.engine.external(
                    text(&arguments["name"]),
                    steps,
                    arguments["inexact"].as_bool().expect("inexact"),
                );
                Some(self.object_answer(external))
            }
            "add_load" => {
                let base = self.node(&arguments["base"]);
                let dst = self.node(&arguments["dst"]);
                self.engine.add_load(
                    base,
                    text(&arguments["attr"]),
                    dst,
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                );
                None
            }
            "add_store" => {
                let base = self.node(&arguments["base"]);
                let src = self.optional_node(&arguments["src"]);
                self.engine.add_store(
                    base,
                    text(&arguments["attr"]),
                    src,
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                );
                None
            }
            "add_delete" => {
                let base = self.node(&arguments["base"]);
                self.engine.add_delete(
                    base,
                    text(&arguments["attr"]),
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                );
                None
            }
            "add_external_module" => {
                self.engine.add_external_module(text(&arguments["name"]));
                None
            }
            "add_call" => {
                self.add_call(arguments);
                None
            }
            "container" => {
                let length = arguments["length"]
                    .as_u64()
                    .map(|length| usize::try_from(length).expect("a length fits usize"));
                let container = self.engine.container(
                    text(&arguments["kind"]),
                    text(&arguments["site"]),
                    length,
                );
                Some(self.object_answer(container))
            }
            "element" => {
                let container = self.object(&arguments["container"]);
                let key = match &arguments["key"] {
                    Value::String(name) => Key::Name(name.as_str().into()),
                    value => Key::Index(value.as_i64().expect("an element index")),
                };
                let node = self.engine.element(container, &key);
                Some(self.node_answer(node))
            }
            "unknown" | "keys" | "elements" => {
                let container = self.object(&arguments["container"]);
                let node = match call {
                    "unknown" => self.engine.unknown(container),
                    "keys" => self.engine.keys(container),
                    _ => self.engine.elements(container),
                };
                Some(self.node_answer(node))
            }
            "write_keyed" => {
                let container = self.object(&arguments["container"]);
                let key = self.optional_node(&arguments["key"]);
                let src = self.optional_node(&arguments["src"]);
                self.engine.write_keyed(container, key, src);
                None
            }
            "add_hash" => {
                let key = self.node(&arguments["key"]);
                let stored = self.optional_node(&arguments["stored"]);
                self.engine.add_hash(
                    key,
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                    stored,
                );
                None
            }
            "site_call" => {
                let role: Vec<&str> = list(&arguments["role"]).iter().map(text).collect();
                let call = self.engine.site_call(
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                    &role,
                );
                let answer = self
                    .engine
                    .trace()
                    .rule_value(self.engine.builder_call_rule(call));
                let name = text(&answer["call"]).to_owned();
                self.calls.insert(name, call);
                Some(answer)
            }
            "add_special_call" => {
                let value = self.node(&arguments["value"]);
                let call = self.calls[text(&arguments["call"]["call"])];
                assert!(
                    list(&arguments["unless"]).is_empty(),
                    "the builder calls a special method unconditionally"
                );
                self.engine
                    .add_special_call(value, text(&arguments["name"]), call);
                None
            }
            "pattern" => {
                assert!(arguments["case"].is_null() && arguments["exact"] == true);
                let prefix: Vec<u32> = text(&arguments["prefix"]).chars().map(u32::from).collect();
                let suffix: Vec<u32> = text(&arguments["suffix"]).chars().map(u32::from).collect();
                let object = self.engine.pattern(&prefix, &suffix);
                Some(self.object_answer(object))
            }
            "add_pattern_operand" => {
                let operand = self.optional_node(&arguments["operand"]);
                let result = self.node(&arguments["result"]);
                self.engine.add_pattern_operand(operand, result);
                None
            }
            "add_truth" => {
                let value = self.node(&arguments["value"]);
                self.engine
                    .add_truth(value, text(&arguments["caller"]), text(&arguments["site"]));
                None
            }
            "add_conversion" => {
                let value = self.node(&arguments["value"]);
                let spec = self.optional_node(&arguments["spec"]);
                self.engine.add_conversion(
                    value,
                    text(&arguments["kind"]),
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                    spec,
                );
                None
            }
            "add_percent" => {
                let format = self.node(&arguments["fmt"]);
                let value = self.node(&arguments["value"]);
                self.engine.add_percent(
                    format,
                    value,
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                );
                None
            }
            "add_await" => {
                let value = self.node(&arguments["value"]);
                let dst = self.node(&arguments["dst"]);
                self.engine.add_await(
                    value,
                    dst,
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                );
                None
            }
            "add_with" => {
                let manager = self.node(&arguments["manager"]);
                let dst = self.optional_node(&arguments["dst"]);
                self.engine.add_with(
                    manager,
                    dst,
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                    arguments["is_async"].as_bool().expect("is_async"),
                );
                None
            }
            "add_raise" => {
                let exception = self.node(&arguments["exception"]);
                self.engine.add_raise(
                    exception,
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                );
                None
            }
            "add_handler" => {
                let types = self.optional_node(&arguments["types"]);
                let dst = self.node(&arguments["dst"]);
                self.engine.add_handler(types, dst);
                None
            }
            "add_operator" => {
                assert!(
                    list(&arguments["extra"]).is_empty(),
                    "the builder passes no extra operand"
                );
                let operation = Operation {
                    left: self.optional_node(&arguments["left"]),
                    right: self.optional_node(&arguments["right"]),
                    method: text(&arguments["method"]),
                    reflected: arguments["reflected"].as_str(),
                    inplace: arguments["inplace"].as_bool().expect("inplace"),
                    dst: self.node(&arguments["dst"]),
                    caller: text(&arguments["caller"]),
                    site: text(&arguments["site"]),
                    unary: arguments["unary"].as_bool().expect("unary"),
                    constants: arguments["constants"].as_bool().expect("constants"),
                };
                self.engine.add_operator(&operation);
                None
            }
            "add_subscript" => {
                let subscript = Subscript {
                    base: self.node(&arguments["base"]),
                    key: self.optional_node(&arguments["key"]),
                    dst: self.optional_node(&arguments["dst"]),
                    src: self.optional_node(&arguments["src"]),
                    caller: text(&arguments["caller"]),
                    site: text(&arguments["site"]),
                    delete: arguments["delete"].as_bool().expect("delete"),
                };
                self.engine.add_subscript(&subscript);
                None
            }
            "add_slice" => {
                let bounds = match &arguments["bounds"] {
                    Value::Null => None,
                    value => Some((bound(&list(value)[0]), bound(&list(value)[1]))),
                };
                let slice = Slice {
                    base: self.node(&arguments["base"]),
                    bounds: bounds.as_ref(),
                    dst: self.optional_node(&arguments["dst"]),
                    src: self.optional_node(&arguments["src"]),
                    caller: text(&arguments["caller"]),
                    site: text(&arguments["site"]),
                    delete: arguments["delete"].as_bool().expect("delete"),
                };
                self.engine.add_slice(&slice);
                None
            }
            "add_unpack" => {
                let value = self.node(&arguments["value"]);
                let before: Vec<NodeId> = list(&arguments["before"])
                    .iter()
                    .map(|node| self.node(node))
                    .collect();
                let after: Vec<NodeId> = list(&arguments["after"])
                    .iter()
                    .map(|node| self.node(node))
                    .collect();
                let starred = self.optional_node(&arguments["starred"]);
                self.engine.add_unpack(
                    value,
                    &before,
                    starred,
                    &after,
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                );
                None
            }
            "add_iteration" => {
                let iterable = self.node(&arguments["iterable"]);
                let dst = self.node(&arguments["dst"]);
                self.engine.add_iteration(
                    iterable,
                    dst,
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                    arguments["is_async"].as_bool().expect("is_async"),
                );
                None
            }
            "entering_keys" => {
                let source = self.node(&arguments["source"]);
                let construct = list(&arguments["construct"]);
                let (hashed, kept) = self.engine.entering_keys(
                    source,
                    (text(&construct[0]), text(&construct[1])),
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                );
                let hashed = self.node_answer(hashed);
                let kept = self.node_answer(kept);
                Some(Value::Array(vec![hashed, kept]))
            }
            "add_dict_items" => {
                let target = self.object(&arguments["target"]);
                let source = self.node(&arguments["source"]);
                self.engine.add_dict_items(
                    target,
                    source,
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                );
                None
            }
            "add_yield_from" => {
                let iterable = self.node(&arguments["iterable"]);
                let function = self.object(&arguments["function"]);
                let dst = self.node(&arguments["dst"]);
                self.engine.add_yield_from(
                    iterable,
                    function,
                    dst,
                    text(&arguments["caller"]),
                    text(&arguments["site"]),
                );
                None
            }
            "type_form" => {
                let parts: Vec<Option<NodeId>> = list(&arguments["parts"])
                    .iter()
                    .map(|part| self.optional_node(part))
                    .collect();
                let form = self.engine.type_form(
                    text(&arguments["operator"]),
                    &parts,
                    text(&arguments["site"]),
                );
                Some(self.object_answer(form))
            }
            "gate_type_form" => {
                let form = self.object(&arguments["form"]);
                let gate = self.node(&arguments["gate"]);
                self.engine.gate_type_form(form, gate);
                None
            }
            "annotated" => {
                let node = self.node(&arguments["node"]);
                let dst = self.node(&arguments["dst"]);
                let shape = match text(&arguments["shape"]) {
                    "instance" => Shape::Instance,
                    "element" => Shape::Element,
                    "class" => Shape::Class,
                    other => panic!("an annotation shape: {other}"),
                };
                let owner = list(&arguments["owner"]);
                let object = self.object(&owner[0]);
                self.engine
                    .annotated(node, dst, shape, object, text(&owner[1]));
                None
            }
            "bind_annotations" => {
                let function = self.object(&arguments["function"]);
                self.apply_annotations(function);
                self.engine.bind_annotations(function);
                None
            }
            "add_name_lookup" => {
                let base = self.node(&arguments["base"]);
                let dst = self.node(&arguments["dst"]);
                self.engine
                    .add_name_lookup(base, text(&arguments["attr"]), dst);
                None
            }
            "add_stub_bases" => {
                let class = self.object(&arguments["cls"]);
                let node = self.node(&arguments["node"]);
                self.engine.add_stub_bases(class, node);
                None
            }
            "add_annotated_class" => {
                let class = self.object(&arguments["cls"]);
                self.apply_annotations(class);
                let decorators: Vec<NodeId> = list(&arguments["decorators"])
                    .iter()
                    .map(|node| self.node(node))
                    .collect();
                let bases: Vec<NodeId> = list(&arguments["bases"])
                    .iter()
                    .map(|node| self.node(node))
                    .collect();
                self.engine.add_annotated_class(class, &decorators, &bases);
                None
            }
            "add_structure_class" => {
                let class = self.object(&arguments["cls"]);
                let fields: Vec<(Box<str>, Option<NodeId>)> = pairs(&arguments["fields"])
                    .iter()
                    .map(|pair| (text(&pair[0]).into(), self.optional_node(&pair[1])))
                    .collect();
                let bases: Vec<NodeId> = list(&arguments["bases"])
                    .iter()
                    .map(|node| self.node(node))
                    .collect();
                self.engine.add_structure_class(class, &fields, &bases);
                None
            }
            _ => not_ported(&format!("the builder call {call}")),
        };
        let expected = &record["answer"];
        let actual = answer.unwrap_or(Value::Null);
        assert!(
            *expected == actual,
            "the engine diverges at D4 record {number}: it answers {actual}: {record}"
        );
        let fresh = std::mem::take(&mut self.engine.trace_mut().fresh);
        for object in fresh {
            self.set_fields(object);
        }
    }

    fn add_call(&mut self, arguments: &Value) {
        let args: Vec<Option<NodeId>> = list(&arguments["args"])
            .iter()
            .map(|arg| self.optional_node(arg))
            .collect();
        let keywords: Vec<(Box<str>, Option<NodeId>)> = list(&arguments["keywords"])
            .iter()
            .map(|pair| (text(&pair[0]).into(), self.optional_node(&pair[1])))
            .collect();
        let star: Vec<(Option<NodeId>, bool)> = list(&arguments["star"])
            .iter()
            .map(|pair| {
                (
                    self.optional_node(&pair[0]),
                    pair[1].as_bool().expect("starred"),
                )
            })
            .collect();
        let double_star: Vec<Option<NodeId>> = list(&arguments["double_star"])
            .iter()
            .map(|mapping| self.optional_node(mapping))
            .collect();
        let callee = self.optional_node(&arguments["callee"]);
        let dst = self.optional_node(&arguments["dst"]);
        self.engine.add_call(&Call {
            callee,
            caller: text(&arguments["caller"]),
            args: &args,
            keywords: &keywords,
            dst,
            site: text(&arguments["site"]),
            star: &star,
            double_star: &double_star,
            decorator: arguments["decorator"].as_bool().expect("decorator"),
            applies: arguments["applies"].as_bool().expect("applies"),
        });
    }

    fn set_fields(&mut self, object: ObjId) {
        let name = self.engine.trace().object_name(object).to_string();
        for fields in self.fields.remove(&name).unwrap_or_default() {
            self.set_recorded_fields(object, &name, &fields);
        }
    }

    fn set_recorded_fields(&mut self, object: ObjId, name: &str, fields: &Value) {
        match self.engine.object(object) {
            Object::Module(_) => {
                let defines = self.engine.module_defines(object);
                for name in set(&fields["defines"]) {
                    let name: Box<str> = text(name).into();
                    if !defines.contains(&name) {
                        defines.push(name);
                    }
                }
            }
            Object::Function(_) => {
                self.pending_annotations(object, &fields["annotations"]);
                let passthrough: Vec<Passthrough> = set(&fields["passthrough"])
                    .iter()
                    .map(|entry| match entry {
                        Value::String(name) => Passthrough::Name(name.as_str().into()),
                        Value::Array(pair) => Passthrough::Element(
                            text(&pair[0]).into(),
                            pair[1].as_i64().expect("an element index"),
                        ),
                        _ => panic!("a passthrough entry: {entry}"),
                    })
                    .collect();
                let function = self.engine.function_fields(object);
                function.passthrough = passthrough;
                function.decorated = fields["decorated"].as_bool().expect("decorated");
                function.is_async = fields["is_async"].as_bool().expect("is_async");
                function.lineno = position(&fields["lineno"]);
                function.col_offset = position(&fields["col_offset"]);
                function.end_lineno = position(&fields["end_lineno"]);
                function.end_col_offset = position(&fields["end_col_offset"]);
            }
            Object::Class(_) => {
                self.pending_annotations(object, &fields["annotations"]);
                let names = |value: &Value| -> Vec<Box<str>> {
                    set(value).iter().map(|name| text(name).into()).collect()
                };
                let defines = names(&fields["defines"]);
                let bound = names(&fields["bound"]);
                let slots = names(&fields["slots"]);
                let allocator = match fields["allocator"].as_str() {
                    None => None,
                    Some("object") => Some(Allocator::Object),
                    Some("super") => Some(Allocator::Super),
                    Some(other) => panic!("an allocator: {other}"),
                };
                let class = self.engine.class_fields(object);
                class.defines = defines;
                class.bound = bound;
                class.slots = slots;
                class.allocator = allocator;
                class.lineno = position(&fields["lineno"]);
                class.end_lineno = position(&fields["end_lineno"]);
            }
            _ => panic!("the fields of {name}, which the builder does not write"),
        }
    }

    fn object_answer(&self, object: ObjId) -> Value {
        self.engine.trace().object_value(object)
    }

    fn node_answer(&self, node: NodeId) -> Value {
        self.engine.trace().node_value(node)
    }

    fn node(&self, value: &Value) -> NodeId {
        self.engine.trace().node_named(value)
    }

    fn pending_annotations(&mut self, object: ObjId, value: &Value) {
        if !value.is_null() {
            self.annotations.insert(object, value.clone());
        }
    }

    fn apply_annotations(&mut self, object: ObjId) {
        let Some(value) = self.annotations.remove(&object) else {
            return;
        };
        let annotations: IndexMap<Box<str>, NodeId> = pairs(&value)
            .iter()
            .map(|pair| (text(&pair[0]).into(), self.node(&pair[1])))
            .collect();
        match self.engine.object(object) {
            Object::Function(_) => {
                self.engine.function_fields(object).annotations = Some(annotations);
            }
            Object::Class(_) => self.engine.class_fields(object).annotations = Some(annotations),
            _ => panic!("annotations of a function or a class"),
        }
    }

    fn optional_node(&self, value: &Value) -> Option<NodeId> {
        if value.is_null() {
            None
        } else {
            Some(self.node(value))
        }
    }

    fn object(&self, value: &Value) -> ObjId {
        self.engine.trace().object_named(value)
    }

    fn finish(&mut self) -> Vec<String> {
        let named: Vec<NodeId> = self.engine.named_nodes().to_vec();
        let mut points_to: BTreeMap<String, Vec<String>> = BTreeMap::new();
        for &node in &named {
            let label = self.engine.label(node).expect("a named node").to_string();
            let saturated = self.engine.saturated();
            let held: Vec<String> = self
                .engine
                .held(node)
                .into_iter()
                .filter(|&object| object != saturated)
                .map(|object| self.engine.object_name(object))
                .collect();
            points_to.entry(label).or_default().extend(held);
        }
        let points_to = points_to
            .into_iter()
            .map(|(label, mut held)| {
                held.sort_unstable_by(|a, b| a.chars().cmp(b.chars()));
                held.dedup();
                canonical::line(&json!({"node": label, "objects": held}))
            })
            .collect();
        let round = self.engine.trace().round;
        for &node in &named {
            for object in self.engine.held(node) {
                self.engine
                    .trace_mut()
                    .first_rounds
                    .entry((node, object))
                    .or_insert(round);
            }
        }
        let reported = self.engine.trace().reported.clone();
        for node in reported {
            let held: Vec<String> = self
                .engine
                .held(node)
                .into_iter()
                .map(|object| self.engine.trace().object_name(object).to_string())
                .collect();
            let saturated = self.engine.held_saturated(node);
            let record = json!({
                "op": "final",
                "node": self.engine.trace().node_name(node),
                "objects": held,
                "saturated": saturated,
            });
            self.engine.trace_mut().write(&record);
        }
        let mut absorbed: Vec<String> = self
            .engine
            .absorbed()
            .into_iter()
            .map(|object| self.engine.trace().object_name(object).to_string())
            .collect();
        absorbed.sort_unstable_by(|a, b| a.chars().cmp(b.chars()));
        let work = self.engine.work();
        let phase = self.engine.phase();
        let recorder = self.engine.trace_mut();
        recorder.write(&json!({"op": "absorbed", "objects": absorbed}));
        let first = std::mem::take(&mut recorder.first_rounds);
        let mut first: Vec<(String, String, u32)> = first
            .into_iter()
            .map(|((node, object), round)| {
                (
                    recorder.node_name(node).to_string(),
                    recorder.object_name(object).to_string(),
                    round,
                )
            })
            .collect();
        first.sort_unstable();
        for (node, object, round) in first {
            recorder.write(&json!({"op": "first", "node": node, "object": object, "round": round}));
        }
        recorder.write(&json!({
            "op": "work",
            "rounds": phase,
            "work": {
                "copied": work.copied,
                "applied": work.applied,
                "edges": work.edges,
                "processed": work.processed,
                "merged": work.merged,
                "searched": work.searched,
            },
        }));
        points_to
    }
}

fn text(value: &Value) -> &str {
    value
        .as_str()
        .unwrap_or_else(|| panic!("not a string: {value}"))
}

fn bound(value: &Value) -> Option<BigInt> {
    match value {
        Value::Null => None,
        Value::Number(number) => Some(BigInt::from(number.as_i64().expect("an integer bound"))),
        Value::Object(form) => Some(
            form["int"]
                .as_str()
                .expect("a large integer bound")
                .parse()
                .expect("a decimal bound"),
        ),
        _ => panic!("not a bound: {value}"),
    }
}

fn list(value: &Value) -> &[Value] {
    value
        .as_array()
        .unwrap_or_else(|| panic!("not a list: {value}"))
}

fn pairs(value: &Value) -> &[Value] {
    list(&value["dict"])
}

fn set(value: &Value) -> &[Value] {
    list(&value["set"])
}

fn empty_collection(value: &Value) -> bool {
    ["set", "dict"].iter().any(|form| {
        value
            .get(form)
            .and_then(Value::as_array)
            .is_some_and(Vec::is_empty)
    })
}

fn position(value: &Value) -> Option<u32> {
    value
        .as_u64()
        .map(|position| u32::try_from(position).expect("a position fits u32"))
}

fn literal(value: &Value) -> Constant {
    match value {
        Value::String(text) => Constant::Str(text.chars().map(u32::from).collect()),
        Value::Number(number) => {
            Constant::Int(BigInt::from(number.as_i64().expect("an integer constant")))
        }
        Value::Object(form) if form.contains_key("int") => Constant::Int(
            text(&form["int"])
                .parse()
                .expect("the digits of an integer constant"),
        ),
        Value::Object(form) if form.contains_key("bytes") => {
            let digits = text(&form["bytes"]).as_bytes();
            let bytes = digits
                .chunks(2)
                .map(|pair| {
                    u8::from_str_radix(std::str::from_utf8(pair).expect("hex digits"), 16)
                        .expect("a byte in hex")
                })
                .collect();
            Constant::Bytes(bytes)
        }
        _ => panic!("not a constant: {value}"),
    }
}

fn signature(value: &Value) -> Signature {
    let names = |value: &Value| -> Vec<Box<str>> {
        list(value).iter().map(|name| text(name).into()).collect()
    };
    Signature::new(
        names(&value["positional"]),
        usize::try_from(
            value["positional_only_count"]
                .as_u64()
                .expect("a positional-only count"),
        )
        .expect("a count fits usize"),
        names(&value["keyword_only"]),
        value["vararg"].as_str().map(Into::into),
        value["kwarg"].as_str().map(Into::into),
    )
}
