use std::collections::{BTreeMap, BTreeSet};
use std::fs::File;
use std::io::{BufRead, BufReader, BufWriter, Lines, Write};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use indexmap::IndexMap;
use pycg_analysis::builder::calls::{
    Analysis, BuilderTables, Call, CallId, ClassFields, ClassStatement, Constant, FunctionFields,
    Key, MadeFunction, MethodKind, NewClass, Operation, Passthrough, Shape, Slice, Subscript,
};
use pycg_analysis::model::Signature;
use pycg_analysis::program::Program;
use pycg_analysis::program::imports::ImportManager;
use pycg_analysis::program::paths::relpath;
use pycg_document::{ProgramPart, dumps, module_definitions, modules_section};
use pycg_solver::{NodeId, ObjId};
use serde_json::{Map, Value, json};

const SAFE_INTEGER_BITS: u64 = 53;

pub fn run(arguments: &[String]) -> Option<ExitCode> {
    let [command, oracle, out, flag, package, entry_points @ ..] = arguments else {
        return None;
    };
    if command != "d4" || flag != "--package" || entry_points.is_empty() {
        return None;
    }
    let entry_points: Vec<PathBuf> = entry_points.iter().map(PathBuf::from).collect();
    let out = Path::new(out);
    let mut program = discover(Path::new(oracle), out, Path::new(package), &entry_points);
    let part = ProgramPart::from_program(&mut program);
    let mut modules = dumps(&modules_section(&part));
    modules.push('\n');
    std::fs::write(out.join("modules.json"), modules).expect("the modules are written");
    let mut definitions = dumps(&module_definitions(&part));
    definitions.push('\n');
    std::fs::write(out.join("definitions.json"), definitions)
        .expect("the module definitions are written");
    Some(ExitCode::SUCCESS)
}

pub fn discover(
    oracle: &Path,
    out: &Path,
    package: &Path,
    entry_points: &[PathBuf],
) -> Program<Replay> {
    let cwd = std::env::current_dir().expect("a working directory");
    std::fs::create_dir_all(out).expect("the output directory can be made");
    let file = File::create(out.join("D4.jsonl")).expect("the D4 dump can be created");
    let replay = Replay::new(Oracle::open(oracle), BufWriter::new(file));
    let mut program = Program::new(entry_points, Some(package), &cwd, replay)
        .expect("the paths of an oracle input are on one drive");
    program
        .build_modules()
        .expect("the paths of an oracle input are on one drive");
    program.analysis.write_linked_defines();
    program
        .analysis
        .out
        .flush()
        .expect("the D4 dump is written");
    let mut listed = String::new();
    for (name, module) in &program.modules {
        let real = std::fs::canonicalize(&module.file).unwrap_or_else(|_| module.file.clone());
        let relative = relpath(&real, &cwd, &cwd)
            .expect("a module file is on the drive of the working directory");
        listed.push_str(&format!("{name}\t{}\n", relative.display()));
    }
    std::fs::write(out.join("modules.tsv"), listed).expect("the module list is written");
    program
}

fn surrogate_escape(text: &str, at: usize) -> Option<u32> {
    let digits = text.get(at + 2..at + 6)?;
    let unit = u32::from_str_radix(digits, 16).ok()?;
    (text[at..].starts_with("\\u") && (0xd800..0xe000).contains(&unit)).then_some(unit)
}

fn without_lone_surrogates(line: &str) -> String {
    let mut out = String::with_capacity(line.len());
    let mut index = 0;
    while let Some(offset) = line[index..].find('\\') {
        let at = index + offset;
        out.push_str(&line[index..at]);
        match surrogate_escape(line, at) {
            Some(0xd800..0xdc00)
                if surrogate_escape(line, at + 6).is_some_and(|low| low >= 0xdc00) =>
            {
                out.push_str(&line[at..at + 12]);
                index = at + 12;
            }
            Some(_) => {
                out.push_str("\\ufffd");
                index = at + 6;
            }
            None => {
                let end = at + 1 + line[at + 1..].chars().next().map_or(0, char::len_utf8);
                out.push_str(&line[at..end]);
                index = end;
            }
        }
    }
    out.push_str(&line[index..]);
    out
}

struct Oracle {
    lines: Option<Lines<BufReader<File>>>,
    next: Option<Value>,
}

impl Oracle {
    fn open(path: &Path) -> Oracle {
        let lines = File::open(path)
            .ok()
            .map(|file| BufReader::new(file).lines());
        let mut oracle = Oracle { lines, next: None };
        oracle.advance();
        oracle
    }

    fn advance(&mut self) {
        self.next = None;
        let Some(lines) = &mut self.lines else {
            return;
        };
        for line in lines.by_ref() {
            let line = line.expect("the oracle's D4 is readable");
            let record: Value =
                serde_json::from_str(&without_lone_surrogates(&line)).expect("an oracle D4 record");
            if record.get("call").is_some() {
                self.next = Some(record);
                return;
            }
        }
    }

    fn skip_finished(&mut self, finished: &BTreeSet<String>) {
        while let Some(record) = &self.next {
            let module = record["module"].as_str().expect("a module");
            if !finished.contains(module) {
                return;
            }
            self.advance();
        }
    }

    fn take(&mut self, module: &str, call: &str) -> Option<Value> {
        let record = self.next.as_mut()?;
        if record["module"] != module || record["call"] != call {
            return None;
        }
        let answer = record["answer"].take();
        self.advance();
        Some(answer)
    }
}

fn label_count(name: &str, label: &str) -> Option<usize> {
    let rest = name.strip_prefix(label)?;
    if rest.is_empty() {
        return Some(1);
    }
    rest.strip_prefix('~')?.parse().ok()
}

fn unsuffixed(name: &str) -> &str {
    match name.rsplit_once('~') {
        Some((stem, count)) if count.parse::<usize>().is_ok() => stem,
        _ => name,
    }
}

enum Made {
    Function(FunctionFields),
    Class(ClassFields),
}

const PROGRAM: &str = "<program>";

pub struct Replay {
    module: String,
    oracle: Oracle,
    out: BufWriter<File>,
    label_counts: BTreeMap<String, usize>,
    imports: ImportManager,
    module_objects: BTreeMap<String, ObjId>,
    finished: BTreeSet<String>,
    defines_before_linking: IndexMap<ObjId, BTreeSet<Box<str>>>,
    node_names: Vec<String>,
    node_labels: Vec<Option<String>>,
    node_by_name: BTreeMap<String, NodeId>,
    object_names: Vec<String>,
    object_by_name: BTreeMap<String, ObjId>,
    call_names: Vec<String>,
    call_by_name: BTreeMap<String, CallId>,
    made: IndexMap<ObjId, Made>,
    module_defines: IndexMap<ObjId, Vec<Box<str>>>,
    tables: BuilderTables,
    built: Option<ObjId>,
    divergences: usize,
}

impl Replay {
    fn new(oracle: Oracle, out: BufWriter<File>) -> Replay {
        Replay {
            module: PROGRAM.to_owned(),
            oracle,
            out,
            label_counts: BTreeMap::new(),
            imports: ImportManager::default(),
            module_objects: BTreeMap::new(),
            finished: BTreeSet::new(),
            defines_before_linking: IndexMap::new(),
            node_names: Vec::new(),
            node_labels: Vec::new(),
            node_by_name: BTreeMap::new(),
            object_names: Vec::new(),
            object_by_name: BTreeMap::new(),
            call_names: Vec::new(),
            call_by_name: BTreeMap::new(),
            made: IndexMap::new(),
            module_defines: IndexMap::new(),
            tables: BuilderTables::default(),
            built: None,
            divergences: 0,
        }
    }

    fn answer(&mut self, call: &str) -> Value {
        self.oracle.take(&self.module, call).unwrap_or_else(|| {
            self.divergences += 1;
            json!({"diverged": format!("{call}#{}", self.divergences)})
        })
    }

    fn write(&mut self, record: &Value) {
        write!(self.out, "{}", crate::canonical::line(record)).expect("the D4 dump takes a record");
    }

    fn record(&mut self, call: &str, arguments: Map<String, Value>, answer: Value) {
        let record = json!({
            "module": self.module,
            "call": call,
            "arguments": Value::Object(arguments),
            "answer": answer,
        });
        self.write(&record);
    }

    fn labelled_node(&mut self, label: String) -> NodeId {
        let count = self.label_counts.entry(label.clone()).or_insert(0);
        *count += 1;
        let name = if *count == 1 {
            label.clone()
        } else {
            format!("{label}~{count}")
        };
        self.named_node(name, Some(label))
    }

    fn named_node(&mut self, name: String, label: Option<String>) -> NodeId {
        if let Some(&node) = self.node_by_name.get(&name) {
            return node;
        }
        let node = NodeId::new(self.node_names.len());
        self.node_by_name.insert(name.clone(), node);
        self.node_names.push(name);
        self.node_labels.push(label);
        node
    }

    fn node_from(&mut self, answer: &Value, label: Option<&str>) -> NodeId {
        let name = match answer.get("node").and_then(Value::as_str) {
            Some(name) => name.to_owned(),
            None => answer.to_string(),
        };
        if let Some(label) = label
            && let Some(count) = label_count(&name, label)
        {
            let known = self.label_counts.entry(label.to_owned()).or_insert(0);
            *known = (*known).max(count);
        }
        self.named_node(name, label.map(str::to_owned))
    }

    fn object_from(&mut self, answer: &Value) -> ObjId {
        let name = match answer.get("object").and_then(Value::as_str) {
            Some(name) => name.to_owned(),
            None => answer.to_string(),
        };
        if let Some(&object) = self.object_by_name.get(&name) {
            return object;
        }
        let object = ObjId(u32::try_from(self.object_names.len()).expect("objects fit u32"));
        self.object_by_name.insert(name.clone(), object);
        self.object_names.push(name);
        object
    }

    fn call_from(&mut self, answer: &Value) -> CallId {
        let name = match answer.get("call").and_then(Value::as_str) {
            Some(name) => name.to_owned(),
            None => answer.to_string(),
        };
        if let Some(&call) = self.call_by_name.get(&name) {
            return call;
        }
        let call = CallId(u32::try_from(self.call_names.len()).expect("calls fit u32"));
        self.call_by_name.insert(name.clone(), call);
        self.call_names.push(name);
        call
    }

    fn canon_call(&self, call: CallId) -> Value {
        json!({"call": self.call_names[call.0 as usize]})
    }

    fn canon_node(&self, node: NodeId) -> Value {
        json!({"node": self.node_names[node.index()]})
    }

    fn optional_node(&self, node: Option<NodeId>) -> Value {
        node.map_or(Value::Null, |node| self.canon_node(node))
    }

    fn nodes(&self, nodes: &[NodeId]) -> Value {
        Value::Array(nodes.iter().map(|&node| self.canon_node(node)).collect())
    }

    fn optional_nodes(&self, nodes: &[Option<NodeId>]) -> Value {
        Value::Array(nodes.iter().map(|&node| self.optional_node(node)).collect())
    }

    fn object(&self, object: ObjId) -> Value {
        json!({"object": self.object_names[object.index()]})
    }

    fn keywords(&self, keywords: &[(Box<str>, Option<NodeId>)]) -> Value {
        Value::Array(
            keywords
                .iter()
                .map(|(name, node)| json!([&**name, self.optional_node(*node)]))
                .collect(),
        )
    }

    fn pairs(&self, entries: &[(Box<str>, Option<NodeId>)]) -> Value {
        json!({"dict": self.keywords(entries)})
    }

    fn container_node(&mut self, call: &str, container: ObjId) -> NodeId {
        let answer = self.answer(call);
        let recorded = arguments(vec![("container", self.object(container))]);
        self.record(call, recorded, answer.clone());
        self.node_from(&answer, None)
    }

    fn simple(&mut self, call: &str, arguments: Map<String, Value>) {
        let answer = self.answer(call);
        self.record(call, arguments, answer);
    }

    fn write_linked_defines(&mut self) {
        let modules: Vec<ObjId> = self.module_objects.values().copied().collect();
        for module in modules {
            let Some(before) = self.defines_before_linking.get(&module) else {
                continue;
            };
            let defines: BTreeSet<Box<str>> = self
                .module_defines
                .get(&module)
                .into_iter()
                .flatten()
                .cloned()
                .collect();
            if defines == *before {
                continue;
            }
            let record = json!({
                "module": PROGRAM,
                "object": self.object(module),
                "fields": {"defines": set(defines.iter().map(|name| Value::from(&**name)).collect())},
            });
            self.write(&record);
        }
    }

    fn finish(&mut self) {
        let Some(module) = self.built else {
            return;
        };
        let tables = self.tables_record();
        self.write(&tables);
        let defines = set(self
            .module_defines
            .get(&module)
            .into_iter()
            .flatten()
            .map(|name| Value::from(&**name))
            .collect());
        let defined = json!({
            "module": self.module,
            "object": self.object(module),
            "fields": {"defines": defines},
        });
        self.write(&defined);
        let made: Vec<(ObjId, Value)> = self
            .made
            .iter()
            .map(|(&object, made)| (object, self.fields(made)))
            .collect();
        for (object, fields) in made {
            let record =
                json!({"module": self.module, "object": self.object(object), "fields": fields});
            self.write(&record);
        }
    }

    fn annotations(&self, annotations: &Option<IndexMap<Box<str>, NodeId>>) -> Value {
        match annotations {
            None => Value::Null,
            Some(annotations) => json!({"dict": annotations
                .iter()
                .map(|(name, &node)| json!([&**name, self.canon_node(node)]))
                .collect::<Vec<_>>()}),
        }
    }

    fn fields(&self, made: &Made) -> Value {
        match made {
            Made::Function(fields) => json!({
                "decorated": fields.decorated,
                "lineno": fields.lineno,
                "col_offset": fields.col_offset,
                "end_lineno": fields.end_lineno,
                "end_col_offset": fields.end_col_offset,
                "is_async": fields.is_async,
                "annotations": self.annotations(&fields.annotations),
                "passthrough": set(fields.passthrough.iter().map(|item| match item {
                    Passthrough::Name(name) => Value::from(&**name),
                    Passthrough::Element(name, index) => json!([&**name, index]),
                }).collect()),
            }),
            Made::Class(fields) => json!({
                "lineno": fields.lineno,
                "end_lineno": fields.end_lineno,
                "allocator": fields.allocator.map(|allocator| allocator.name()),
                "slots": names_set(&fields.slots),
                "bound": names_set(&fields.bound),
                "defines": names_set(&fields.defines),
                "annotations": self.annotations(&fields.annotations),
            }),
        }
    }

    fn tables_record(&self) -> Value {
        let tables = &self.tables;
        let sites = |sites: &[(Box<str>, Box<str>)]| {
            set(sites
                .iter()
                .map(|(caller, site)| json!([&**caller, &**site]))
                .collect())
        };
        json!({
            "module": self.module,
            "tables": {
                "iterated_expressions": sites(&tables.iterated_expressions),
                "literal_imports": {"dict": tables.literal_imports.iter().map(|(site, module)| json!([&**site, self.canon_node(*module)])).collect::<Vec<_>>()},
                "none_arguments": {"dict": tables.none_arguments.iter().map(|((caller, site), nones)| json!([[&**caller, &**site], set(nones.iter().map(|&index| Value::from(index)).collect())])).collect::<Vec<_>>()},
                "none_keywords": {"dict": tables.none_keywords.iter().map(|((caller, site), names)| json!([[&**caller, &**site], names_set(names)])).collect::<Vec<_>>()},
                "read_namespaces": names_set(&tables.read_namespaces),
                "zero_argument_super": names_set(&tables.zero_argument_super),
            },
        })
    }
}

fn set(mut items: Vec<Value>) -> Value {
    items.sort_by_key(crate::canonical::line);
    json!({"set": items})
}

fn names_set(names: &[Box<str>]) -> Value {
    set(names.iter().map(|name| Value::from(&**name)).collect())
}

fn integer(value: &num_bigint::BigInt) -> Value {
    if value.bits() < SAFE_INTEGER_BITS {
        Value::from(i64::try_from(value).expect("a small integer"))
    } else {
        json!({"int": value.to_string()})
    }
}

fn constant(value: &Constant) -> Value {
    match value {
        Constant::Str(code_points) => crate::canonical::text(code_points),
        Constant::Bytes(bytes) => {
            json!({"bytes": bytes.iter().map(|byte| format!("{byte:02x}")).collect::<String>()})
        }
        Constant::Int(value) => integer(value),
    }
}

fn signature(signature: &Signature) -> Value {
    let names = |names: &[Box<str>]| {
        names
            .iter()
            .map(|name| Value::from(&**name))
            .collect::<Vec<_>>()
    };
    json!({"signature": {
        "positional": names(&signature.positional),
        "positional_only_count": signature.positional_only_count,
        "keyword_only": names(&signature.keyword_only),
        "vararg": signature.vararg.as_deref(),
        "kwarg": signature.kwarg.as_deref(),
    }})
}

fn arguments(entries: Vec<(&str, Value)>) -> Map<String, Value> {
    entries
        .into_iter()
        .map(|(key, value)| (key.to_owned(), value))
        .collect()
}

impl Analysis for Replay {
    fn container(&mut self, kind: &str, site: &str, length: Option<usize>) -> ObjId {
        let answer = self.answer("container");
        let recorded = arguments(vec![
            ("kind", json!(kind)),
            ("site", json!(site)),
            ("length", json!(length)),
        ]);
        self.record("container", recorded, answer.clone());
        self.object_from(&answer)
    }

    fn element(&mut self, container: ObjId, key: &Key) -> NodeId {
        let answer = self.answer("element");
        let key = match key {
            Key::Index(index) => json!(index),
            Key::Name(name) => json!(&**name),
        };
        let recorded = arguments(vec![("container", self.object(container)), ("key", key)]);
        self.record("element", recorded, answer.clone());
        self.node_from(&answer, None)
    }

    fn unknown(&mut self, container: ObjId) -> NodeId {
        self.container_node("unknown", container)
    }

    fn keys(&mut self, container: ObjId) -> NodeId {
        self.container_node("keys", container)
    }

    fn elements(&mut self, container: ObjId) -> NodeId {
        self.container_node("elements", container)
    }

    fn write_keyed(&mut self, container: ObjId, key: Option<NodeId>, src: Option<NodeId>) {
        let recorded = arguments(vec![
            ("container", self.object(container)),
            ("key", self.optional_node(key)),
            ("src", self.optional_node(src)),
        ]);
        self.simple("write_keyed", recorded);
    }

    fn typed(&mut self, cls: &str) -> ObjId {
        let answer = self.answer("typed");
        self.record(
            "typed",
            arguments(vec![("cls", json!(cls))]),
            answer.clone(),
        );
        self.object_from(&answer)
    }

    fn add_operator(&mut self, operation: &Operation<'_>) {
        let recorded = arguments(vec![
            ("left", self.optional_node(operation.left)),
            ("right", self.optional_node(operation.right)),
            ("method", json!(operation.method)),
            ("reflected", json!(operation.reflected)),
            ("inplace", json!(operation.inplace)),
            ("dst", self.canon_node(operation.dst)),
            ("caller", json!(operation.caller)),
            ("site", json!(operation.site)),
            ("unary", json!(operation.unary)),
            ("constants", json!(operation.constants)),
            ("extra", json!([])),
        ]);
        self.simple("add_operator", recorded);
    }

    fn add_percent(&mut self, fmt: NodeId, value: NodeId, caller: &str, site: &str) {
        let recorded = arguments(vec![
            ("fmt", self.canon_node(fmt)),
            ("value", self.canon_node(value)),
            ("caller", json!(caller)),
            ("site", json!(site)),
        ]);
        self.simple("add_percent", recorded);
    }

    fn add_conversion(
        &mut self,
        value: NodeId,
        kind: &str,
        caller: &str,
        site: &str,
        spec: Option<NodeId>,
    ) {
        let recorded = arguments(vec![
            ("value", self.canon_node(value)),
            ("kind", json!(kind)),
            ("caller", json!(caller)),
            ("site", json!(site)),
            ("spec", self.optional_node(spec)),
        ]);
        self.simple("add_conversion", recorded);
    }

    fn add_hash(&mut self, key: NodeId, caller: &str, site: &str, stored: Option<NodeId>) {
        let recorded = arguments(vec![
            ("key", self.canon_node(key)),
            ("caller", json!(caller)),
            ("site", json!(site)),
            ("stored", self.optional_node(stored)),
        ]);
        self.simple("add_hash", recorded);
    }

    fn add_subscript(&mut self, subscript: &Subscript<'_>) {
        let recorded = arguments(vec![
            ("base", self.canon_node(subscript.base)),
            ("key", self.optional_node(subscript.key)),
            ("dst", self.optional_node(subscript.dst)),
            ("src", self.optional_node(subscript.src)),
            ("caller", json!(subscript.caller)),
            ("site", json!(subscript.site)),
            ("delete", json!(subscript.delete)),
        ]);
        self.simple("add_subscript", recorded);
    }

    fn add_slice(&mut self, slice: &Slice<'_>) {
        let bound =
            |bound: &Option<num_bigint::BigInt>| bound.as_ref().map_or(Value::Null, integer);
        let bounds = slice.bounds.map_or(Value::Null, |(lower, upper)| {
            json!([bound(lower), bound(upper)])
        });
        let recorded = arguments(vec![
            ("base", self.canon_node(slice.base)),
            ("bounds", bounds),
            ("dst", self.optional_node(slice.dst)),
            ("src", self.optional_node(slice.src)),
            ("caller", json!(slice.caller)),
            ("site", json!(slice.site)),
            ("delete", json!(slice.delete)),
        ]);
        self.simple("add_slice", recorded);
    }

    fn add_iteration(
        &mut self,
        iterable: NodeId,
        dst: NodeId,
        caller: &str,
        site: &str,
        is_async: bool,
    ) {
        let recorded = arguments(vec![
            ("iterable", self.canon_node(iterable)),
            ("dst", self.canon_node(dst)),
            ("caller", json!(caller)),
            ("site", json!(site)),
            ("is_async", json!(is_async)),
        ]);
        self.simple("add_iteration", recorded);
    }

    fn add_length_hint(&mut self, iterable: NodeId, caller: &str, site: &str) {
        let recorded = arguments(vec![
            ("iterable", self.canon_node(iterable)),
            ("caller", json!(caller)),
            ("site", json!(site)),
            (
                "plan",
                json!([["__len__", []], ["__length_hint__", ["__len__"]]]),
            ),
        ]);
        self.simple("add_length_hint", recorded);
    }

    fn entering_keys(
        &mut self,
        source: NodeId,
        construct: (&str, &str),
        caller: &str,
        site: &str,
    ) -> (NodeId, NodeId) {
        let answer = self.answer("entering_keys");
        let recorded = arguments(vec![
            ("source", self.canon_node(source)),
            ("construct", json!([construct.0, construct.1])),
            ("caller", json!(caller)),
            ("site", json!(site)),
            ("keeps", json!({"function": "keeps_hashes"})),
        ]);
        self.record("entering_keys", recorded, answer.clone());
        let hashed = self.node_from(&answer[0], None);
        let kept = self.node_from(&answer[1], None);
        (hashed, kept)
    }

    fn add_dict_items(&mut self, target: ObjId, source: NodeId, caller: &str, site: &str) {
        let recorded = arguments(vec![
            ("target", self.object(target)),
            ("source", self.canon_node(source)),
            ("caller", json!(caller)),
            ("site", json!(site)),
        ]);
        self.simple("add_dict_items", recorded);
    }

    fn add_await(&mut self, value: NodeId, dst: NodeId, caller: &str, site: &str) {
        let recorded = arguments(vec![
            ("value", self.canon_node(value)),
            ("dst", self.canon_node(dst)),
            ("caller", json!(caller)),
            ("site", json!(site)),
        ]);
        self.simple("add_await", recorded);
    }

    fn add_yield_from(
        &mut self,
        iterable: NodeId,
        function: ObjId,
        dst: NodeId,
        caller: &str,
        site: &str,
    ) {
        let recorded = arguments(vec![
            ("iterable", self.canon_node(iterable)),
            ("function", self.object(function)),
            ("dst", self.canon_node(dst)),
            ("caller", json!(caller)),
            ("site", json!(site)),
        ]);
        self.simple("add_yield_from", recorded);
    }

    fn pattern(&mut self, prefix: &[u32], suffix: &[u32]) -> ObjId {
        let answer = self.answer("pattern");
        let recorded = arguments(vec![
            ("prefix", constant(&Constant::Str(prefix.into()))),
            ("suffix", constant(&Constant::Str(suffix.into()))),
            ("case", Value::Null),
            ("exact", json!(true)),
        ]);
        self.record("pattern", recorded, answer.clone());
        self.object_from(&answer)
    }

    fn site_call(&mut self, caller: &str, site: &str, role: &[&str]) -> CallId {
        let answer = self.answer("site_call");
        let recorded = arguments(vec![
            ("caller", json!(caller)),
            ("site", json!(site)),
            ("role", json!(role)),
            ("args", json!([])),
            ("implicit", json!(true)),
            ("dst", Value::Null),
            ("rest", Value::Null),
        ]);
        self.record("site_call", recorded, answer.clone());
        self.call_from(&answer)
    }

    fn add_special_call(&mut self, value: NodeId, name: &str, call: CallId) {
        let recorded = arguments(vec![
            ("value", self.canon_node(value)),
            ("name", json!(name)),
            ("call", self.canon_call(call)),
            ("unless", json!([])),
        ]);
        self.simple("add_special_call", recorded);
    }

    fn add_named_load(&mut self, obj: NodeId, name: NodeId, dst: NodeId, caller: &str, site: &str) {
        let recorded = arguments(vec![
            ("obj", self.canon_node(obj)),
            ("name", self.canon_node(name)),
            ("dst", self.canon_node(dst)),
            ("caller", json!(caller)),
            ("site", json!(site)),
        ]);
        self.simple("add_named_load", recorded);
    }

    fn callable_filter(&mut self, source: NodeId, dst: NodeId, holds: bool) {
        let recorded = arguments(vec![
            ("source", self.canon_node(source)),
            ("dst", self.canon_node(dst)),
            ("holds", json!(holds)),
        ]);
        self.simple("callable_filter", recorded);
    }

    fn class_filter(
        &mut self,
        source: NodeId,
        classes: Option<NodeId>,
        dst: NodeId,
        as_class: bool,
        holds: bool,
    ) {
        let recorded = arguments(vec![
            ("source", self.canon_node(source)),
            ("classes", self.optional_node(classes)),
            ("dst", self.canon_node(dst)),
            ("as_class", json!(as_class)),
            ("holds", json!(holds)),
        ]);
        self.simple("class_filter", recorded);
    }

    fn tested_classes(
        &mut self,
        classes: NodeId,
        dst: NodeId,
        as_class: bool,
        module: ObjId,
        site: &str,
    ) {
        let recorded = arguments(vec![
            ("classes", self.canon_node(classes)),
            ("dst", self.canon_node(dst)),
            ("as_class", json!(as_class)),
            ("owner", json!([self.object(module), site])),
        ]);
        self.simple("tested_classes", recorded);
    }

    fn add_pattern_operand(&mut self, operand: Option<NodeId>, result: NodeId) {
        let recorded = arguments(vec![
            ("operand", self.optional_node(operand)),
            ("result", self.canon_node(result)),
        ]);
        self.simple("add_pattern_operand", recorded);
    }

    fn node(&mut self, label: Option<&str>) -> NodeId {
        let answer = self.answer("node");
        self.record(
            "node",
            arguments(vec![("label", json!(label))]),
            answer.clone(),
        );
        self.node_from(&answer, label)
    }

    fn node_label(&self, node: NodeId) -> Option<&str> {
        self.node_labels[node.index()].as_deref()
    }

    fn constant(&mut self, object: ObjId) -> NodeId {
        let answer = self.answer("constant");
        let recorded = arguments(vec![("obj", self.object(object))]);
        self.record("constant", recorded, answer.clone());
        self.node_from(&answer, None)
    }

    fn const_object(&mut self, value: &Constant) -> ObjId {
        let answer = self.answer("const");
        self.record(
            "const",
            arguments(vec![("value", constant(value))]),
            answer.clone(),
        );
        self.object_from(&answer)
    }

    fn field(&mut self, object: ObjId, name: &str) -> NodeId {
        let answer = self.answer("field");
        let recorded = arguments(vec![("obj", self.object(object)), ("name", json!(name))]);
        self.record("field", recorded, answer.clone());
        let label = format!(
            "{}.{name}",
            unsuffixed(
                self.object_names[object.index()]
                    .split_once(':')
                    .map_or("", |(_, name)| name)
            )
        );
        self.node_from(&answer, Some(&label))
    }

    fn add_edge(&mut self, source: NodeId, target: NodeId) {
        let recorded = arguments(vec![
            ("src", self.canon_node(source)),
            ("dst", self.canon_node(target)),
        ]);
        self.simple("add_edge", recorded);
    }

    fn add_object(&mut self, node: NodeId, object: ObjId) {
        let recorded = arguments(vec![
            ("node", self.canon_node(node)),
            ("obj", self.object(object)),
        ]);
        self.simple("add_object", recorded);
    }

    fn module(&mut self, name: &str) -> ObjId {
        let answer = self.answer("module");
        self.record(
            "module",
            arguments(vec![("name", json!(name))]),
            answer.clone(),
        );
        let object = self.object_from(&answer);
        self.module_objects.insert(name.to_owned(), object);
        object
    }

    fn begin_module(&mut self, name: &str) {
        self.module = name.to_owned();
        self.made.clear();
        self.tables = BuilderTables::default();
        self.built = None;
    }

    fn end_module(&mut self, name: &str, analysed: bool) {
        if analysed {
            self.built = self.module_objects.get(name).copied();
            self.finish();
        }
        self.finished.insert(name.to_owned());
        self.oracle.skip_finished(&self.finished);
        self.module = PROGRAM.to_owned();
        self.built = None;
    }

    fn imports(&mut self) -> &mut ImportManager {
        &mut self.imports
    }

    fn external(&mut self, name: &str, steps: u32, inexact: bool) -> ObjId {
        let answer = self.answer("external");
        let recorded = arguments(vec![
            ("name", json!(name)),
            ("steps", json!(steps)),
            ("inexact", json!(inexact)),
        ]);
        self.record("external", recorded, answer.clone());
        self.object_from(&answer)
    }

    fn imported_value(&mut self, name: &str) -> NodeId {
        let answer = self.answer("imported_value");
        self.record(
            "imported_value",
            arguments(vec![("name", json!(name))]),
            answer.clone(),
        );
        self.node_from(&answer, None)
    }

    fn add_external_module(&mut self, name: &str) {
        self.simple(
            "add_external_module",
            arguments(vec![("name", json!(name))]),
        );
    }

    fn function(
        &mut self,
        name: &str,
        module: &str,
        function_signature: &Signature,
        defaults: &[(Box<str>, Option<NodeId>)],
        generator: bool,
    ) -> MadeFunction {
        let answer = self.answer("function");
        let recorded = arguments(vec![
            ("name", json!(name)),
            ("module", json!(module)),
            ("signature", signature(function_signature)),
            ("defaults", self.pairs(defaults)),
            ("generator", json!(generator)),
        ]);
        self.record("function", recorded, answer.clone());
        let object = self.object_from(&answer);
        let mut parameters = IndexMap::new();
        for parameter in function_signature.names() {
            let label = format!("{name}.{parameter}");
            parameters.insert(Box::from(parameter), self.labelled_node(label));
        }
        let mut labelled = |suffix: &str| self.labelled_node(format!("{name}.{suffix}"));
        let return_node = labelled("<return>");
        let (yield_node, sent_node) = if generator {
            (Some(labelled("<yield>")), Some(labelled("<sent>")))
        } else {
            (None, None)
        };
        self.made
            .insert(object, Made::Function(FunctionFields::default()));
        MadeFunction {
            object,
            signature: function_signature.clone(),
            parameters,
            return_node,
            yield_node,
            sent_node,
        }
    }

    fn new_class(&mut self, class: &NewClass<'_>) -> ObjId {
        let answer = self.answer("new_class");
        let defines = json!({"dict": class.defines.iter().map(|name| json!([&**name, null])).collect::<Vec<_>>()});
        let recorded = arguments(vec![
            ("name", json!(class.name)),
            ("module", json!(class.module)),
            ("defines", defines),
            ("base_nodes", self.optional_nodes(class.base_nodes)),
            ("protocol", json!(class.protocol)),
            ("abstract_methods", names_set(class.abstract_methods)),
            ("metaclass", self.optional_node(class.metaclass)),
            ("uses_namespace", json!(class.uses_namespace)),
        ]);
        self.record("new_class", recorded, answer.clone());
        let object = self.object_from(&answer);
        self.made
            .insert(object, Made::Class(ClassFields::default()));
        object
    }

    fn add_method(&mut self, class: ObjId, name: &str, function: ObjId, kind: Option<MethodKind>) {
        let recorded = arguments(vec![
            ("cls", self.object(class)),
            ("name", json!(name)),
            ("function", self.object(function)),
            ("kind", json!(kind.map(MethodKind::name))),
        ]);
        self.simple("add_method", recorded);
    }

    fn add_implicit_method(&mut self, value: NodeId, field: NodeId, kind: MethodKind, site: &str) {
        let recorded = arguments(vec![
            ("value", self.canon_node(value)),
            ("field", self.canon_node(field)),
            ("kind", json!(kind.name())),
            ("site", json!(site)),
        ]);
        self.simple("add_implicit_method", recorded);
    }

    fn add_class_member(&mut self, value: NodeId, field: NodeId) {
        let recorded = arguments(vec![
            ("value", self.canon_node(value)),
            ("field", self.canon_node(field)),
        ]);
        self.simple("add_class_member", recorded);
    }

    fn add_set_name(&mut self, value: NodeId, class: ObjId, name: &str, caller: &str, site: &str) {
        let recorded = arguments(vec![
            ("value", self.canon_node(value)),
            ("cls", self.object(class)),
            ("name", json!(name)),
            ("caller", json!(caller)),
            ("site", json!(site)),
        ]);
        self.simple("add_set_name", recorded);
    }

    fn add_init_subclass(
        &mut self,
        class: ObjId,
        keywords: &[(Box<str>, Option<NodeId>)],
        double_star: &[Option<NodeId>],
        caller: &str,
        site: &str,
    ) {
        let recorded = arguments(vec![
            ("cls", self.object(class)),
            ("keywords", self.keywords(keywords)),
            ("double_star", self.optional_nodes(double_star)),
            ("caller", json!(caller)),
            ("site", json!(site)),
        ]);
        self.simple("add_init_subclass", recorded);
    }

    fn add_metaclass_call(
        &mut self,
        class: ObjId,
        statement: &ClassStatement<'_>,
        caller: &str,
        site: &str,
    ) {
        let namespace: Vec<Value> = statement
            .namespace
            .iter()
            .map(|(name, node)| json!([&**name, self.canon_node(*node)]))
            .collect();
        let recorded = arguments(vec![
            ("cls", self.object(class)),
            (
                "statement",
                json!([
                    statement.name,
                    self.optional_nodes(statement.bases),
                    namespace,
                    self.keywords(statement.keywords),
                    self.optional_nodes(statement.double_star),
                ]),
            ),
            ("caller", json!(caller)),
            ("site", json!(site)),
        ]);
        self.simple("add_metaclass_call", recorded);
    }

    fn add_structure_class(
        &mut self,
        class: ObjId,
        fields: &[(Box<str>, Option<NodeId>)],
        bases: &[NodeId],
    ) {
        let recorded = arguments(vec![
            ("cls", self.object(class)),
            ("fields", self.pairs(fields)),
            ("bases", self.nodes(bases)),
        ]);
        self.simple("add_structure_class", recorded);
    }

    fn add_annotated_class(&mut self, class: ObjId, decorators: &[NodeId], bases: &[NodeId]) {
        let recorded = arguments(vec![
            ("cls", self.object(class)),
            ("decorators", self.nodes(decorators)),
            ("bases", self.nodes(bases)),
        ]);
        self.simple("add_annotated_class", recorded);
    }

    fn add_call(&mut self, call: &Call<'_>) {
        let star: Vec<Value> = call
            .star
            .iter()
            .map(|(node, length)| json!([self.optional_node(*node), length]))
            .collect();
        let recorded = arguments(vec![
            ("callee", self.optional_node(call.callee)),
            ("caller", json!(call.caller)),
            ("args", self.optional_nodes(call.args)),
            ("keywords", self.keywords(call.keywords)),
            ("dst", self.optional_node(call.dst)),
            ("site", json!(call.site)),
            ("star", Value::Array(star)),
            ("double_star", self.optional_nodes(call.double_star)),
            ("decorator", json!(call.decorator)),
            ("applies", json!(call.applies)),
        ]);
        self.simple("add_call", recorded);
    }

    fn add_load(&mut self, base: NodeId, attr: &str, dst: NodeId, caller: &str, site: &str) {
        let recorded = arguments(vec![
            ("base", self.canon_node(base)),
            ("attr", json!(attr)),
            ("dst", self.canon_node(dst)),
            ("caller", json!(caller)),
            ("site", json!(site)),
        ]);
        self.simple("add_load", recorded);
    }

    fn add_load_text(&mut self, base: NodeId, attr: &[u32], dst: NodeId, caller: &str, site: &str) {
        let recorded = arguments(vec![
            ("base", self.canon_node(base)),
            ("attr", crate::canonical::text(attr)),
            ("dst", self.canon_node(dst)),
            ("caller", json!(caller)),
            ("site", json!(site)),
        ]);
        self.simple("add_load", recorded);
    }

    fn add_store(
        &mut self,
        base: NodeId,
        attr: &str,
        src: Option<NodeId>,
        caller: &str,
        site: &str,
    ) {
        let recorded = arguments(vec![
            ("base", self.canon_node(base)),
            ("attr", json!(attr)),
            ("src", self.optional_node(src)),
            ("caller", json!(caller)),
            ("site", json!(site)),
        ]);
        self.simple("add_store", recorded);
    }

    fn add_delete(&mut self, base: NodeId, attr: &str, caller: &str, site: &str) {
        let recorded = arguments(vec![
            ("base", self.canon_node(base)),
            ("attr", json!(attr)),
            ("caller", json!(caller)),
            ("site", json!(site)),
        ]);
        self.simple("add_delete", recorded);
    }

    fn add_unpack(
        &mut self,
        value: NodeId,
        before: &[NodeId],
        starred: Option<NodeId>,
        after: &[NodeId],
        caller: &str,
        site: &str,
    ) {
        let recorded = arguments(vec![
            ("value", self.canon_node(value)),
            ("before", self.nodes(before)),
            ("starred", self.optional_node(starred)),
            ("after", self.nodes(after)),
            ("caller", json!(caller)),
            ("site", json!(site)),
        ]);
        self.simple("add_unpack", recorded);
    }

    fn add_with(
        &mut self,
        manager: NodeId,
        dst: Option<NodeId>,
        caller: &str,
        site: &str,
        is_async: bool,
    ) {
        let recorded = arguments(vec![
            ("manager", self.canon_node(manager)),
            ("dst", self.optional_node(dst)),
            ("caller", json!(caller)),
            ("site", json!(site)),
            ("is_async", json!(is_async)),
        ]);
        self.simple("add_with", recorded);
    }

    fn add_raise(&mut self, exception: NodeId, caller: &str, site: &str) {
        let recorded = arguments(vec![
            ("exception", self.canon_node(exception)),
            ("caller", json!(caller)),
            ("site", json!(site)),
        ]);
        self.simple("add_raise", recorded);
    }

    fn add_truth(&mut self, value: NodeId, caller: &str, site: &str) {
        let recorded = arguments(vec![
            ("value", self.canon_node(value)),
            ("caller", json!(caller)),
            ("site", json!(site)),
        ]);
        self.simple("add_truth", recorded);
    }

    fn add_handler(&mut self, types: Option<NodeId>, dst: NodeId) {
        let recorded = arguments(vec![
            ("types", self.optional_node(types)),
            ("dst", self.canon_node(dst)),
        ]);
        self.simple("add_handler", recorded);
    }

    fn handle_import(&mut self, name: &str, level: u32, record: bool) -> Option<String> {
        self.answer("imports.handle_import");
        let imported = self.imports.handle_import(name, level, record);
        let recorded = arguments(vec![
            ("name", json!(name)),
            ("level", json!(level)),
            ("record", json!(record)),
        ]);
        self.record("imports.handle_import", recorded, json!(imported));
        imported
    }

    fn locate(&mut self, name: &str) -> Option<(String, Option<String>)> {
        self.answer("imports.locate");
        let found = self.imports.locate(name);
        self.record(
            "imports.locate",
            arguments(vec![("name", json!(name))]),
            json!(found),
        );
        found
    }

    fn type_form(&mut self, operator: &str, parts: &[Option<NodeId>], site: &str) -> ObjId {
        let answer = self.answer("type_form");
        let recorded = arguments(vec![
            ("operator", json!(operator)),
            ("parts", self.optional_nodes(parts)),
            ("site", json!(site)),
        ]);
        self.record("type_form", recorded, answer.clone());
        self.object_from(&answer)
    }

    fn gate_type_form(&mut self, form: ObjId, gate: NodeId) {
        let recorded = arguments(vec![
            ("form", self.object(form)),
            ("gate", self.canon_node(gate)),
        ]);
        self.simple("gate_type_form", recorded);
    }

    fn annotated(&mut self, node: NodeId, dst: NodeId, shape: Shape, owner: ObjId, name: &str) {
        let recorded = arguments(vec![
            ("node", self.canon_node(node)),
            ("dst", self.canon_node(dst)),
            ("shape", json!(shape.name())),
            ("owner", json!([self.object(owner), name])),
        ]);
        self.simple("annotated", recorded);
    }

    fn bind_annotations(&mut self, function: ObjId) {
        let recorded = arguments(vec![("function", self.object(function))]);
        self.simple("bind_annotations", recorded);
    }

    fn add_name_lookup(&mut self, base: NodeId, attr: &str, dst: NodeId) {
        let recorded = arguments(vec![
            ("base", self.canon_node(base)),
            ("attr", json!(attr)),
            ("dst", self.canon_node(dst)),
        ]);
        self.simple("add_name_lookup", recorded);
    }

    fn add_stub_bases(&mut self, cls: ObjId, node: NodeId) {
        let recorded = arguments(vec![
            ("cls", self.object(cls)),
            ("node", self.canon_node(node)),
        ]);
        self.simple("add_stub_bases", recorded);
    }

    fn function_fields(&mut self, function: ObjId) -> &mut FunctionFields {
        match self.made.get_mut(&function) {
            Some(Made::Function(fields)) => fields,
            _ => panic!("the fields of a function that the build made"),
        }
    }

    fn class_fields(&mut self, class: ObjId) -> &mut ClassFields {
        match self.made.get_mut(&class) {
            Some(Made::Class(fields)) => fields,
            _ => panic!("the fields of a class that the build made"),
        }
    }

    fn module_defines(&mut self, module: ObjId) -> &mut Vec<Box<str>> {
        let defines = self.module_defines.entry(module).or_default();
        if self.module == PROGRAM {
            self.defines_before_linking
                .entry(module)
                .or_insert_with(|| defines.iter().cloned().collect());
        }
        defines
    }

    fn tables(&mut self) -> &mut BuilderTables {
        &mut self.tables
    }
}
