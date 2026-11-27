use std::collections::BTreeMap;
use std::io::Write;
use std::path::Path;
use std::process::ExitCode;

use indexmap::IndexMap;
use pycg_analysis::builder::calls::{
    Analysis, BuilderTables, Call, ClassFields, ClassStatement, Constant, FunctionFields,
    MadeFunction, MethodKind, NewClass, Passthrough,
};
use pycg_analysis::builder::{ModuleBuilder, Source};
use pycg_analysis::model::Signature;
use pycg_solver::{NodeId, ObjId};
use pycg_syntax::parse::with_parsed;
use pycg_syntax::read::read_file;
use pycg_syntax::scopes::analyse_scopes;
use ruff_source_file::LineIndex;
use serde_json::{Map, Value, json};

const SAFE_INTEGER_BITS: u64 = 53;

pub fn run(arguments: &[String]) -> Option<ExitCode> {
    let [command, modules, entries, oracle, out] = arguments else {
        return None;
    };
    if command != "d4" {
        return None;
    }
    let listed = std::fs::read_to_string(modules).expect("the module list is readable");
    let entries: Vec<String> = std::fs::read_to_string(entries)
        .expect("the entry list is readable")
        .lines()
        .map(str::to_owned)
        .collect();
    let oracle = read_oracle(Path::new(oracle));
    let file = std::fs::File::create(out).expect("the D4 dump can be created");
    let mut out = std::io::BufWriter::new(file);
    for line in listed.lines() {
        let (module, path) = line.split_once('\t').expect("a module and its file");
        let records = oracle.get(module).cloned().unwrap_or_default();
        let mut replay = Replay::new(module, records);
        build(
            &mut replay,
            module,
            Path::new(path),
            entries.iter().any(|entry| entry == module),
        );
        for record in replay.finish() {
            write!(out, "{}", crate::canonical::line(&record)).expect("the D4 dump takes a record");
        }
    }
    out.flush().expect("the D4 dump is written");
    Some(ExitCode::SUCCESS)
}

fn read_oracle(path: &Path) -> IndexMap<String, Vec<Value>> {
    let mut grouped: IndexMap<String, Vec<Value>> = IndexMap::new();
    let text = std::fs::read_to_string(path).unwrap_or_default();
    for line in text.lines() {
        let record: Value = serde_json::from_str(line).expect("an oracle D4 record");
        if record.get("call").is_none() {
            continue;
        }
        let module = record["module"].as_str().expect("a module").to_owned();
        grouped.entry(module).or_default().push(record);
    }
    grouped
}

fn build(replay: &mut Replay, module: &str, path: &Path, is_entry: bool) {
    let Ok(source) = read_file(path) else {
        return;
    };
    with_parsed(&source, |parsed| {
        let Ok(parsed) = parsed else {
            return;
        };
        let lines = LineIndex::from_source_text(&source);
        let tokens = parsed.tokens();
        let scopes = analyse_scopes(parsed.syntax(), module, tokens, &lines, &source);
        let object = replay.module(module);
        replay.built = Some(object);
        let is_package = path.file_name().is_some_and(|name| name == "__init__.py");
        let mut builder = ModuleBuilder::new(
            replay,
            module,
            object,
            Source {
                text: &source,
                tokens,
                lines: &lines,
            },
            &scopes,
            is_package,
            is_entry,
        );
        builder.build(&parsed.syntax().body);
    });
}

enum Made {
    Function(FunctionFields),
    Class(ClassFields),
}

struct Replay {
    module: String,
    oracle: Vec<Value>,
    cursor: usize,
    records: Vec<Value>,
    node_names: Vec<String>,
    node_labels: Vec<Option<String>>,
    node_by_name: BTreeMap<String, NodeId>,
    object_names: Vec<String>,
    object_by_name: BTreeMap<String, ObjId>,
    made: IndexMap<ObjId, Made>,
    module_defines: Vec<Box<str>>,
    tables: BuilderTables,
    built: Option<ObjId>,
    divergences: usize,
}

impl Replay {
    fn new(module: &str, oracle: Vec<Value>) -> Replay {
        Replay {
            module: module.to_owned(),
            oracle,
            cursor: 0,
            records: Vec::new(),
            node_names: Vec::new(),
            node_labels: Vec::new(),
            node_by_name: BTreeMap::new(),
            object_names: Vec::new(),
            object_by_name: BTreeMap::new(),
            made: IndexMap::new(),
            module_defines: Vec::new(),
            tables: BuilderTables::default(),
            built: None,
            divergences: 0,
        }
    }

    fn answer(&mut self, call: &str) -> Value {
        let recorded = self.oracle.get(self.cursor);
        match recorded {
            Some(record) if record["call"] == call => {
                self.cursor += 1;
                record["answer"].clone()
            }
            _ => {
                self.divergences += 1;
                json!({"diverged": format!("{call}#{}", self.divergences)})
            }
        }
    }

    fn record(&mut self, call: &str, arguments: Map<String, Value>, answer: Value) {
        self.records.push(json!({
            "module": self.module,
            "call": call,
            "arguments": Value::Object(arguments),
            "answer": answer,
        }));
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

    fn simple(&mut self, call: &str, arguments: Map<String, Value>) {
        let answer = self.answer(call);
        self.record(call, arguments, answer);
    }

    fn finish(mut self) -> Vec<Value> {
        if self.built.is_none() {
            return self.records;
        }
        let tables = self.tables_record();
        self.records.push(tables);
        let module = self.built.expect("a built module");
        let defines = set(self
            .module_defines
            .iter()
            .map(|name| Value::from(&**name))
            .collect());
        self.records.push(json!({
            "module": self.module,
            "object": self.object(module),
            "fields": {"defines": defines},
        }));
        let made: Vec<(ObjId, Value)> = self
            .made
            .iter()
            .map(|(&object, made)| (object, self.fields(made)))
            .collect();
        for (object, fields) in made {
            self.records.push(
                json!({"module": self.module, "object": self.object(object), "fields": fields}),
            );
        }
        self.records
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
                "none_arguments": {"dict": tables.none_arguments.iter().map(|((caller, site), nones)| json!([[&**caller, &**site], nones])).collect::<Vec<_>>()},
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
        Constant::Str(code_points) => {
            let text: String = code_points
                .iter()
                .map(|&point| char::from_u32(point).unwrap_or('\u{fffd}'))
                .collect();
            Value::from(text)
        }
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
            self.object_names[object.index()]
                .split_once(':')
                .map_or("", |(_, name)| name)
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
        self.object_from(&answer)
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
            parameters.insert(
                Box::from(parameter),
                self.named_node(label.clone(), Some(label)),
            );
        }
        let mut labelled = |suffix: &str| {
            let label = format!("{name}.{suffix}");
            self.named_node(label.clone(), Some(label))
        };
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
        let answer = self.answer("imports.handle_import");
        let recorded = arguments(vec![
            ("name", json!(name)),
            ("level", json!(level)),
            ("record", json!(record)),
        ]);
        self.record("imports.handle_import", recorded, answer.clone());
        answer.as_str().map(str::to_owned)
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
        assert_eq!(
            Some(module),
            self.built,
            "the defines of the module being built"
        );
        &mut self.module_defines
    }

    fn tables(&mut self) -> &mut BuilderTables {
        &mut self.tables
    }
}
