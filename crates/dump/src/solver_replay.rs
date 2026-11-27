use std::collections::BTreeMap;
use std::fs::File;
use std::io::{self, BufRead, BufReader, BufWriter, Lines, Stdout, Write};
use std::process::ExitCode;

use pycg_solver::{KindMask, NodeId, ObjId, Order, Rules, Solver, WatchId};
use rustc_hash::{FxHashMap, FxHashSet};
use serde_json::{Value, json};

use crate::canonical;

const KIND_BITS_MAX: usize = 64;

#[derive(Clone, Copy, PartialEq, Eq)]
enum Mode {
    Each,
    List,
}

struct Constraint {
    name: String,
    kinds: Option<KindMask>,
    mode: Mode,
    captured: Vec<ObjId>,
}

enum Opacity {
    Never,
    Saturated,
    Class(ObjId),
}

struct Record {
    number: usize,
    text: String,
    value: Value,
}

pub struct Replay {
    input: Lines<BufReader<File>>,
    pending: Option<Record>,
    records_read: usize,
    output: BufWriter<Stdout>,
    node_by_name: FxHashMap<String, NodeId>,
    node_names: FxHashMap<NodeId, String>,
    reported_nodes: Vec<NodeId>,
    named_nodes: Vec<NodeId>,
    watch_by_witness: FxHashMap<NodeId, WatchId>,
    witness_by_watch: FxHashMap<WatchId, NodeId>,
    object_by_name: FxHashMap<String, ObjId>,
    object_names: Vec<String>,
    opacity: Vec<Opacity>,
    unknown_classes: FxHashSet<ObjId>,
    kind_bits: FxHashMap<String, KindMask>,
    constraint_by_name: FxHashMap<String, usize>,
    constraints: Vec<Constraint>,
    first_rounds: BTreeMap<(String, String), u64>,
    round: u64,
}

pub fn run(input: &str) -> ExitCode {
    let reader = match File::open(input) {
        Ok(file) => BufReader::new(file).lines(),
        Err(error) => {
            eprintln!("pycg-dump solver: cannot read {input}: {error}");
            return ExitCode::FAILURE;
        }
    };
    let writer = BufWriter::new(io::stdout());
    let mut replay = Replay::new(reader, writer);
    let mut solver = replay.start();
    replay.run_block(&mut solver, None);
    replay.finish(&mut solver);
    match replay.output.flush() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("pycg-dump solver: cannot write the trace: {error}");
            ExitCode::FAILURE
        }
    }
}

impl Replay {
    fn new(input: Lines<BufReader<File>>, output: BufWriter<Stdout>) -> Replay {
        Replay {
            input,
            pending: None,
            records_read: 0,
            output,
            node_by_name: FxHashMap::default(),
            node_names: FxHashMap::default(),
            reported_nodes: Vec::new(),
            named_nodes: Vec::new(),
            watch_by_witness: FxHashMap::default(),
            witness_by_watch: FxHashMap::default(),
            object_by_name: FxHashMap::default(),
            object_names: Vec::new(),
            opacity: Vec::new(),
            unknown_classes: FxHashSet::default(),
            kind_bits: FxHashMap::default(),
            constraint_by_name: FxHashMap::default(),
            constraints: Vec::new(),
            first_rounds: BTreeMap::new(),
            round: 0,
        }
    }

    fn start(&mut self) -> Solver<usize> {
        let created = self.next_record();
        self.expect_op(&created, "solver");
        let cap = created.value["cap"]
            .as_u64()
            .map(|cap| u32::try_from(cap).expect("a cap fits u32"));
        self.write_text(&created.text);
        let declaration = self.next_record();
        self.expect_op(&declaration, "object");
        let saturated = self.declare_object(&declaration.value);
        self.write_text(&declaration.text);
        let kinds = self.kinds_of_object(&declaration.value);
        let constant = self.next_record();
        self.expect_op(&constant, "constant");
        assert_eq!(
            self.object_arg(&constant.value, 0),
            saturated,
            "the trace starts with the constant node of the saturated value"
        );
        let solver = Solver::new(saturated, kinds, cap, Order::Canonical);
        let node = solver.saturated_node();
        self.name_node(node, answer_node(&constant.value), false);
        self.write_text(&constant.text);
        solver
    }

    fn next_record(&mut self) -> Record {
        if let Some(record) = self.pending.take() {
            return record;
        }
        let text = match self.input.next() {
            Some(Ok(text)) => text,
            Some(Err(error)) => panic!("the trace cannot be read: {error}"),
            None => panic!("the trace ends after record {}", self.records_read),
        };
        self.records_read += 1;
        let value: Value = serde_json::from_str(&text)
            .unwrap_or_else(|error| panic!("record {} is not JSON: {error}", self.records_read));
        Record {
            number: self.records_read,
            text,
            value,
        }
    }

    fn push_back(&mut self, record: Record) {
        assert!(self.pending.is_none());
        self.pending = Some(record);
    }

    fn write_text(&mut self, text: &str) {
        self.output
            .write_all(text.as_bytes())
            .and_then(|()| self.output.write_all(b"\n"))
            .expect("the replay's trace can be written");
    }

    fn write_value(&mut self, value: &Value) {
        self.output
            .write_all(canonical::line(value).as_bytes())
            .expect("the replay's trace can be written");
    }

    fn expect_op(&self, record: &Record, op: &str) {
        let found = record.value["op"].as_str().unwrap_or("");
        assert_eq!(
            found, op,
            "the replay diverges at record {}: the engine did `{found}` where the port does `{op}`: {}",
            record.number, record.text
        );
    }

    fn run_until(&mut self, solver: &mut Solver<usize>, end: &str) -> Record {
        self.run_block(solver, Some(end))
            .unwrap_or_else(|| panic!("the trace ends before `{end}`"))
    }

    fn run_block(&mut self, solver: &mut Solver<usize>, end: Option<&str>) -> Option<Record> {
        loop {
            let record = self.next_record();
            let op = record.value["op"].as_str().unwrap_or("").to_string();
            if Some(op.as_str()) == end {
                return Some(record);
            }
            match op.as_str() {
                "final" if end.is_none() => return None,
                "node" => self.create_node(solver, &record),
                "object" => {
                    let object = self.declare_object(&record.value);
                    let kinds = self.kinds_of_object(&record.value);
                    solver.declare(object, kinds);
                    self.write_text(&record.text);
                }
                "constraint" => {
                    self.declare_constraint(&record.value);
                    self.write_text(&record.text);
                }
                "wake" => {
                    let witness =
                        self.node_named(record.value["node"].as_str().expect("a witness"));
                    let watch = self.watch_by_witness[&witness];
                    self.push_back(record);
                    solver.wake(self, watch);
                }
                "solve" => {
                    self.write_text(&record.text);
                    solver.solve(self);
                    let solved = self.next_record();
                    self.expect_op(&solved, "solved");
                    self.write_value(&json!({"op": "solved", "phase": solver.phase}));
                }
                _ => self.call(solver, &op, record),
            }
        }
    }

    fn call(&mut self, solver: &mut Solver<usize>, op: &str, record: Record) {
        let args = record.value["args"]
            .as_array()
            .unwrap_or_else(|| panic!("record {} has no arguments: {}", record.number, record.text))
            .clone();
        match op {
            "add_object" => {
                self.write_text(&record.text);
                let (node, object) = (self.node(&args[0]), self.object(&args[1]));
                solver.add_object(self, node, object);
            }
            "add_edge" => {
                self.write_text(&record.text);
                let (source, target) = (self.node(&args[0]), self.node(&args[1]));
                solver.add_edge(self, source, target);
            }
            "attach" => {
                self.write_text(&record.text);
                let (node, constraint) = (self.node(&args[0]), self.constraint(&args[1]));
                solver.attach(self, node, constraint);
            }
            "apply_now" => {
                self.write_text(&record.text);
                let (node, constraint) = (self.node(&args[0]), self.constraint(&args[1]));
                solver.apply_now(self, node, constraint);
            }
            "constant" => {
                let object = self.object(&args[0]);
                let node = solver.constant(object);
                self.name_node(node, answer_node(&record.value), false);
                self.write_text(&record.text);
            }
            "follower" => {
                let source = self.node(&args[0]);
                let since = args[1].as_u64().expect("a phase") as u32;
                let node = solver.follower(self, source, since);
                self.name_node(node, answer_node(&record.value), false);
                self.reported_nodes.push(node);
                self.write_text(&record.text);
            }
            "objects" => {
                let node = self.node(&args[0]);
                let held: Vec<Value> = solver
                    .objects(node)
                    .into_iter()
                    .map(|object| json!({"object": self.object_names[object.index()]}))
                    .collect();
                self.write_answer(&record.value, Value::Array(held));
            }
            "holds" => {
                let (node, object) = (self.node(&args[0]), self.object(&args[1]));
                let answer = solver.holds(node, object);
                self.write_answer(&record.value, Value::Bool(answer));
            }
            "is_saturated" => {
                let node = self.node(&args[0]);
                let answer = solver.is_saturated(node);
                self.write_answer(&record.value, Value::Bool(answer));
            }
            _ => panic!(
                "the replay diverges at record {}: the engine did `{op}` where the port expects a call: {}",
                record.number, record.text
            ),
        }
    }

    fn write_answer(&mut self, record: &Value, answer: Value) {
        let mut own = record.clone();
        own["answer"] = answer;
        self.write_value(&own);
    }

    fn create_node(&mut self, solver: &mut Solver<usize>, record: &Record) {
        let name = record.value["node"]
            .as_str()
            .expect("a node name")
            .to_string();
        let named = record.value.get("named").and_then(Value::as_bool) == Some(true);
        let node = if record.value.get("witness").and_then(Value::as_bool) == Some(true) {
            let watch = solver.watch();
            let node = solver.witness(watch);
            self.watch_by_witness.insert(node, watch);
            self.witness_by_watch.insert(watch, node);
            node
        } else {
            solver.node()
        };
        self.name_node(node, name, named);
        self.reported_nodes.push(node);
        self.write_text(&record.text);
    }

    fn name_node(&mut self, node: NodeId, name: String, named: bool) {
        assert!(
            self.node_by_name.insert(name.clone(), node).is_none(),
            "a node name is given once: {name}"
        );
        self.node_names.insert(node, name);
        if named {
            self.named_nodes.push(node);
        }
    }

    fn node(&self, value: &Value) -> NodeId {
        self.node_named(value["node"].as_str().expect("a node argument"))
    }

    fn node_named(&self, name: &str) -> NodeId {
        *self
            .node_by_name
            .get(name)
            .unwrap_or_else(|| panic!("node {name} is used before it is made"))
    }

    fn object(&self, value: &Value) -> ObjId {
        let name = value["object"].as_str().expect("an object argument");
        *self
            .object_by_name
            .get(name)
            .unwrap_or_else(|| panic!("object {name} is used before it is declared"))
    }

    fn object_arg(&self, record: &Value, index: usize) -> ObjId {
        self.object(&record["args"][index])
    }

    fn constraint(&self, value: &Value) -> usize {
        let name = value
            .get("constraint")
            .or_else(|| value.get("call"))
            .and_then(Value::as_str)
            .expect("a constraint argument");
        *self
            .constraint_by_name
            .get(name)
            .unwrap_or_else(|| panic!("constraint {name} is used before it is declared"))
    }

    fn declare_object(&mut self, record: &Value) -> ObjId {
        let name = record["object"]
            .as_str()
            .expect("an object name")
            .to_string();
        let object = ObjId(u32::try_from(self.object_names.len()).expect("objects fit u32"));
        assert!(
            self.object_by_name.insert(name.clone(), object).is_none(),
            "an object is declared once: {name}"
        );
        self.object_names.push(name);
        let opacity = match record["opacity"].as_str() {
            None => Opacity::Never,
            Some("saturated") => Opacity::Saturated,
            Some(class) if class == self.object_names[object.index()] => Opacity::Class(object),
            Some(class) => Opacity::Class(
                *self
                    .object_by_name
                    .get(class)
                    .unwrap_or_else(|| panic!("class {class} is declared after its instance")),
            ),
        };
        self.opacity.push(opacity);
        object
    }

    fn kind_bit(&mut self, name: &str) -> KindMask {
        let count = self.kind_bits.len();
        *self.kind_bits.entry(name.to_string()).or_insert_with(|| {
            assert!(count < KIND_BITS_MAX, "the kinds fit a mask");
            1 << count
        })
    }

    fn kinds_of_object(&mut self, record: &Value) -> KindMask {
        let types = record["types"]
            .as_array()
            .expect("an object has types")
            .clone();
        types
            .iter()
            .map(|name| self.kind_bit(name.as_str().expect("a type name")))
            .fold(0, |mask, bit| mask | bit)
    }

    fn declare_constraint(&mut self, record: &Value) {
        let name = record["constraint"]
            .as_str()
            .expect("a constraint name")
            .to_string();
        let kinds = record["kinds"].as_array().cloned().map(|kinds| {
            kinds
                .iter()
                .map(|kind| self.kind_bit(kind.as_str().expect("a kind name")))
                .fold(0, |mask, bit| mask | bit)
        });
        let mode = match record["mode"].as_str() {
            Some("each") => Mode::Each,
            Some("list") => Mode::List,
            other => panic!("constraint {name} has no mode: {other:?}"),
        };
        let captured = record["captured"]
            .as_array()
            .expect("captured objects")
            .iter()
            .map(|captured| {
                let object = captured.as_str().expect("an object name");
                self.object_by_name[object]
            })
            .collect();
        let index = self.constraints.len();
        assert!(
            self.constraint_by_name
                .insert(name.clone(), index)
                .is_none(),
            "a constraint is declared once: {name}"
        );
        self.constraints.push(Constraint {
            name,
            kinds,
            mode,
            captured,
        });
    }

    fn expect_application(
        &mut self,
        solver: &mut Solver<usize>,
        constraint: usize,
        objects: &[ObjId],
    ) {
        let record = self.next_record();
        self.expect_op(&record, "apply");
        let name = &self.constraints[constraint].name;
        let listed: Vec<&str> = record.value["objects"]
            .as_array()
            .expect("applied objects")
            .iter()
            .map(|object| object["object"].as_str().expect("an object"))
            .collect();
        let expected: Vec<&str> = objects
            .iter()
            .map(|object| self.object_names[object.index()].as_str())
            .collect();
        assert!(
            record.value["constraint"].as_str() == Some(name.as_str()) && listed == expected,
            "the replay diverges at record {}: the port applies {name} to {expected:?}: {}",
            record.number,
            record.text
        );
        self.write_text(&record.text);
        let end = self.run_until(solver, "applied");
        self.write_text(&end.text);
    }

    fn note_first_rounds(&mut self, solver: &mut Solver<usize>) {
        for index in 0..self.named_nodes.len() {
            let node = self.named_nodes[index];
            for object in solver.objects(node) {
                let key = (
                    self.node_names[&node].clone(),
                    self.object_names[object.index()].clone(),
                );
                self.first_rounds.entry(key).or_insert(self.round);
            }
        }
    }

    fn finish(&mut self, solver: &mut Solver<usize>) {
        self.note_first_rounds(solver);
        for index in 0..self.reported_nodes.len() {
            let node = self.reported_nodes[index];
            let held: Vec<&str> = solver
                .objects(node)
                .into_iter()
                .map(|object| self.object_names[object.index()].as_str())
                .collect();
            let record = json!({
                "op": "final",
                "node": self.node_names[&node],
                "objects": held,
                "saturated": solver.is_saturated(node),
            });
            self.write_value(&record);
        }
        let mut absorbed: Vec<&str> = solver
            .absorbed()
            .into_iter()
            .map(|object| self.object_names[object.index()].as_str())
            .collect();
        absorbed.sort_unstable_by(|a, b| a.chars().cmp(b.chars()));
        self.write_value(&json!({"op": "absorbed", "objects": absorbed}));
        let firsts: Vec<Value> = self
            .first_rounds
            .iter()
            .map(|((node, object), round)| {
                json!({"op": "first", "node": node, "object": object, "round": round})
            })
            .collect();
        for record in firsts {
            self.write_value(&record);
        }
        let work = solver.work();
        self.write_value(&json!({
            "op": "work",
            "rounds": solver.phase,
            "work": {
                "copied": work.copied,
                "applied": work.applied,
                "edges": work.edges,
                "processed": work.processed,
                "merged": work.merged,
                "searched": work.searched,
            },
        }));
    }
}

impl Rules<usize> for Replay {
    fn apply(&mut self, solver: &mut Solver<usize>, constraint: usize, objects: &[ObjId]) {
        let mode = self.constraints[constraint].mode;
        let kinds = self.constraints[constraint].kinds;
        match mode {
            Mode::List => self.expect_application(solver, constraint, objects),
            Mode::Each => {
                for &object in objects {
                    let selected = match kinds {
                        None => true,
                        Some(kinds) => solver
                            .sets
                            .number_of(object)
                            .is_some_and(|number| solver.sets.kinds(number) & kinds != 0),
                    };
                    if selected {
                        self.expect_application(solver, constraint, &[object]);
                    }
                }
            }
        }
    }

    fn saturate(&mut self, solver: &mut Solver<usize>, constraint: usize) {
        let record = self.next_record();
        self.expect_op(&record, "saturate");
        let name = &self.constraints[constraint].name;
        assert!(
            record.value["constraint"].as_str() == Some(name.as_str()),
            "the replay diverges at record {}: the port saturates {name}: {}",
            record.number,
            record.text
        );
        self.write_text(&record.text);
        let end = self.run_until(solver, "saturated");
        self.write_text(&end.text);
    }

    fn kinds(&self, constraint: usize) -> Option<KindMask> {
        self.constraints[constraint].kinds
    }

    fn captures_opaque(&self, _solver: &Solver<usize>, constraint: usize) -> bool {
        self.constraints[constraint]
            .captured
            .iter()
            .any(|&object| self.opaque(object))
    }

    fn opaque(&self, object: ObjId) -> bool {
        match self.opacity[object.index()] {
            Opacity::Never => false,
            Opacity::Saturated => true,
            Opacity::Class(class) => self.unknown_classes.contains(&class),
        }
    }

    fn between_rounds(&mut self, solver: &mut Solver<usize>) -> bool {
        let record = self.next_record();
        self.expect_op(&record, "between_rounds");
        self.write_text(&record.text);
        let end = self.run_until(solver, "between_rounds_done");
        let unknown = end.value["unknown"]
            .as_array()
            .expect("unknown classes")
            .clone();
        for class in &unknown {
            let class = self.object_by_name[class.as_str().expect("a class name")];
            self.unknown_classes.insert(class);
        }
        if !unknown.is_empty() {
            solver.enable_opacity();
        }
        self.write_text(&end.text);
        end.value["answer"].as_bool().expect("an answer")
    }

    fn wake(&mut self, solver: &mut Solver<usize>, watch: WatchId) {
        let record = self.next_record();
        self.expect_op(&record, "wake");
        let witness = self.node_named(record.value["node"].as_str().expect("a witness"));
        assert!(
            self.witness_by_watch[&watch] == witness,
            "the replay diverges at record {}: the port wakes the watch of {}: {}",
            record.number,
            self.node_names[&self.witness_by_watch[&watch]],
            record.text
        );
        self.write_text(&record.text);
        let end = self.run_until(solver, "woken");
        self.write_text(&end.text);
    }

    fn firing(&mut self, solver: &mut Solver<usize>) {
        self.note_first_rounds(solver);
        self.round += 1;
        let record = self.next_record();
        self.expect_op(&record, "fire");
        self.write_value(&json!({"op": "fire", "phase": solver.phase}));
    }
}

fn answer_node(record: &Value) -> String {
    record["answer"]["node"]
        .as_str()
        .expect("an answer that is a node")
        .to_string()
}
