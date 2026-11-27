use indexmap::IndexMap;
use pycg_solver::{NodeId, ObjId};
use pycg_syntax::constants::{Constant, literal};
use pycg_syntax::names::{identifier, is_python_space};
use pycg_syntax::parse::parse_nested_expression;
use pycg_syntax::scopes::{NodeKey, ScopeId, ScopeKind, mangle, node_key};
use pycg_syntax::tree::{Node, position};
use ruff_python_ast::{
    ElifElseClause, ExceptHandler, Expr, ModModule, Operator, Parameter, Parameters, Stmt,
};
use ruff_source_file::LineIndex;
use ruff_text_size::Ranged;
use rustc_hash::{FxHashMap, FxHashSet};

use crate::builder::calls::{Analysis, Shape};
use crate::builder::{ModuleBuilder, Source, builtin_names};
use crate::model::BUILTIN_MODULE;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
enum ParameterKind {
    Named,
    Vararg,
    Kwarg,
}

#[derive(Clone, Debug)]
enum StubBinding<'s> {
    Class(Vec<String>),
    Import(String),
    Alias(&'s Expr),
    Other,
}

impl PartialEq for StubBinding<'_> {
    fn eq(&self, other: &Self) -> bool {
        match (self, other) {
            (StubBinding::Class(a), StubBinding::Class(b)) => a == b,
            (StubBinding::Import(a), StubBinding::Import(b)) => a == b,
            (StubBinding::Alias(a), StubBinding::Alias(b)) => std::ptr::eq(*a, *b),
            (StubBinding::Other, StubBinding::Other) => true,
            _ => false,
        }
    }
}

#[derive(Clone, Copy)]
enum Item<'s> {
    Statement(&'s Stmt),
    Elif(&'s [ElifElseClause]),
}

fn items(statements: &[Stmt]) -> impl Iterator<Item = Item<'_>> {
    statements.iter().map(Item::Statement)
}

fn orelse(clauses: &[ElifElseClause]) -> Vec<Item<'_>> {
    match clauses.first() {
        Some(clause) if clause.test.is_some() => vec![Item::Elif(clauses)],
        Some(clause) => items(&clause.body).collect(),
        None => Vec::new(),
    }
}

fn conditional_blocks<'s>(item: Item<'s>) -> Option<[Vec<Item<'s>>; 2]> {
    match item {
        Item::Statement(Stmt::If(conditional)) => Some([
            items(&conditional.body).collect(),
            orelse(&conditional.elif_else_clauses),
        ]),
        Item::Elif(clauses) => {
            let (clause, rest) = clauses.split_first().expect("an elif clause");
            Some([items(&clause.body).collect(), orelse(rest)])
        }
        Item::Statement(_) => None,
    }
}

fn attempt_blocks(statement: &Stmt) -> Option<Vec<Vec<Item<'_>>>> {
    let Stmt::Try(attempt) = statement else {
        return None;
    };
    let mut blocks = vec![
        items(&attempt.body).collect(),
        items(&attempt.orelse).collect(),
        items(&attempt.finalbody).collect(),
    ];
    for handler in &attempt.handlers {
        let ExceptHandler::ExceptHandler(handler) = handler;
        blocks.push(items(&handler.body).collect());
    }
    Some(blocks)
}

type StubPath = Vec<String>;
type ParameterKey = (StubPath, String, ParameterKind);

pub struct OwnStub<'s> {
    source: Source<'s>,
    parameters: IndexMap<ParameterKey, Vec<&'s Expr>>,
    variables: IndexMap<StubPath, Vec<&'s Expr>>,
    names: IndexMap<(StubPath, String), Vec<StubBinding<'s>>>,
    bases: IndexMap<StubPath, Vec<&'s Expr>>,
}

impl<'s> OwnStub<'s> {
    pub(crate) fn new(
        tree: &'s ModModule,
        source: Source<'s>,
        absolute: &dyn Fn(Option<&str>, u32) -> Option<String>,
    ) -> OwnStub<'s> {
        let mut stub = OwnStub {
            source,
            parameters: IndexMap::new(),
            variables: IndexMap::new(),
            names: IndexMap::new(),
            bases: IndexMap::new(),
        };
        let mut function_aliases: Vec<(StubPath, String, String)> = Vec::new();
        let mut pending: Vec<(Vec<Item<'s>>, StubPath)> =
            vec![(items(&tree.body).collect(), Vec::new())];
        while let Some((block, path)) = pending.pop() {
            for item in block {
                stub.definition(item, &path, &mut pending, &mut function_aliases, absolute);
            }
        }
        let mut copied = true;
        while copied {
            copied = false;
            for (path, name, source) in &function_aliases {
                let mut function = path.clone();
                function.push(source.clone());
                let entries: Vec<(ParameterKey, Vec<&'s Expr>)> = stub
                    .parameters
                    .iter()
                    .map(|(key, annotations)| (key.clone(), annotations.clone()))
                    .collect();
                for ((found, parameter, kind), annotations) in entries {
                    if found != function {
                        continue;
                    }
                    let mut alias = path.clone();
                    alias.push(name.clone());
                    let known = stub.parameters.entry((alias, parameter, kind)).or_default();
                    for annotation in annotations {
                        if !known.iter().any(|seen| std::ptr::eq(*seen, annotation)) {
                            known.push(annotation);
                            copied = true;
                        }
                    }
                }
            }
        }
        stub
    }

    fn bind(&mut self, path: &[String], name: &str, binding: StubBinding<'s>) {
        let bindings = self
            .names
            .entry((path.to_vec(), stored(path, name)))
            .or_default();
        if !bindings.contains(&binding) {
            bindings.push(binding);
        }
    }

    fn definition(
        &mut self,
        item: Item<'s>,
        path: &StubPath,
        pending: &mut Vec<(Vec<Item<'s>>, StubPath)>,
        function_aliases: &mut Vec<(StubPath, String, String)>,
        absolute: &dyn Fn(Option<&str>, u32) -> Option<String>,
    ) {
        if let Some(blocks) = conditional_blocks(item) {
            pending.extend(blocks.into_iter().map(|block| (block, path.clone())));
            return;
        }
        let Item::Statement(statement) = item else {
            unreachable!("an elif is a conditional");
        };
        if let Some(blocks) = attempt_blocks(statement) {
            pending.extend(blocks.into_iter().map(|block| (block, path.clone())));
            return;
        }
        match statement {
            Stmt::FunctionDef(function) => {
                let name = identifier(function.name.as_str());
                self.bind(path, &name, StubBinding::Other);
                let mut qualified = path.clone();
                qualified.push(name.into_owned());
                for (parameter, kind) in parameter_kinds(&function.parameters) {
                    if let Some(annotation) = &parameter.annotation {
                        let key = (
                            qualified.clone(),
                            identifier(parameter.name.as_str()).into_owned(),
                            kind,
                        );
                        self.parameters.entry(key).or_default().push(annotation);
                    }
                }
            }
            Stmt::ClassDef(class) => {
                let name = identifier(class.name.as_str());
                let mut qualified = path.clone();
                qualified.push(name.to_string());
                self.bind(path, &name, StubBinding::Class(qualified.clone()));
                let bases = self.bases.entry(qualified.clone()).or_default();
                for base in class.bases() {
                    let mut base = base;
                    while let Expr::Subscript(subscript) = base {
                        base = &subscript.value;
                    }
                    if matches!(base, Expr::Name(_) | Expr::Attribute(_)) {
                        bases.push(base);
                    }
                }
                pending.push((items(&class.body).collect(), qualified));
            }
            Stmt::Assign(assign)
                if matches!(assign.targets.as_slice(), [Expr::Name(_)])
                    && is_alias_value(&assign.value) =>
            {
                let [Expr::Name(target)] = assign.targets.as_slice() else {
                    unreachable!("a single name target");
                };
                let target = identifier(target.id.as_str());
                self.bind(path, &target, StubBinding::Alias(&assign.value));
                if let Expr::Name(value) = &*assign.value {
                    function_aliases.push((
                        path.clone(),
                        target.into_owned(),
                        identifier(value.id.as_str()).into_owned(),
                    ));
                }
            }
            Stmt::AnnAssign(annotated) if matches!(&*annotated.target, Expr::Name(_)) => {
                let Expr::Name(target) = &*annotated.target else {
                    unreachable!("a name target");
                };
                let target = identifier(target.id.as_str());
                match &annotated.value {
                    Some(value) if is_type_alias(&annotated.annotation) => {
                        self.bind(path, &target, StubBinding::Alias(value));
                    }
                    _ => {
                        self.bind(path, &target, StubBinding::Other);
                        let mut key = path.clone();
                        key.push(stored(path, &target));
                        self.variables
                            .entry(key)
                            .or_default()
                            .push(&annotated.annotation);
                    }
                }
            }
            Stmt::TypeAlias(alias) => {
                if let Expr::Name(target) = &*alias.name {
                    let target = identifier(target.id.as_str());
                    self.bind(path, &target, StubBinding::Alias(&alias.value));
                }
            }
            Stmt::Import(_) | Stmt::ImportFrom(_) => {
                let private = path.last().map(String::as_str);
                for (name, target) in
                    imported_names(vec![Item::Statement(statement)], absolute, private)
                {
                    self.bind(path, &name, StubBinding::Import(target));
                }
            }
            Stmt::Assign(assign) => {
                let targets: Vec<&Expr> = assign.targets.iter().collect();
                for name in target_names(&targets) {
                    self.bind(path, &name, StubBinding::Other);
                }
            }
            Stmt::AugAssign(augmented) => {
                for name in target_names(&[&augmented.target]) {
                    self.bind(path, &name, StubBinding::Other);
                }
            }
            _ => {}
        }
    }
}

fn is_alias_value(value: &Expr) -> bool {
    match value {
        Expr::BinOp(operation) => operation.op == Operator::BitOr,
        _ => matches!(
            value,
            Expr::Name(_) | Expr::Attribute(_) | Expr::Subscript(_)
        ),
    }
}

fn is_type_alias(annotation: &Expr) -> bool {
    match annotation {
        Expr::Name(name) => identifier(name.id.as_str()) == "TypeAlias",
        Expr::Attribute(attribute) => identifier(attribute.attr.as_str()) == "TypeAlias",
        _ => false,
    }
}

fn stored(path: &[String], name: &str) -> String {
    mangle(path.last().map(String::as_str), name)
}

fn target_names(targets: &[&Expr]) -> Vec<String> {
    let mut names = Vec::new();
    let mut pending: Vec<&Expr> = targets.to_vec();
    while let Some(target) = pending.pop() {
        match target {
            Expr::Name(name) => names.push(identifier(name.id.as_str()).into_owned()),
            Expr::Tuple(tuple) => pending.extend(tuple.elts.iter()),
            Expr::List(list) => pending.extend(list.elts.iter()),
            Expr::Starred(starred) => pending.push(&starred.value),
            _ => {}
        }
    }
    names
}

fn parameter_kinds(parameters: &Parameters) -> Vec<(&Parameter, ParameterKind)> {
    let mut kinds: Vec<(&Parameter, ParameterKind)> = parameters
        .posonlyargs
        .iter()
        .chain(parameters.args.iter())
        .chain(parameters.kwonlyargs.iter())
        .map(|parameter| (&parameter.parameter, ParameterKind::Named))
        .collect();
    if let Some(vararg) = &parameters.vararg {
        kinds.push((vararg, ParameterKind::Vararg));
    }
    if let Some(kwarg) = &parameters.kwarg {
        kinds.push((kwarg, ParameterKind::Kwarg));
    }
    kinds
}

fn imported_names(
    statements: Vec<Item<'_>>,
    absolute: &dyn Fn(Option<&str>, u32) -> Option<String>,
    private_class: Option<&str>,
) -> Vec<(String, String)> {
    let mut found = Vec::new();
    let mut stack = statements;
    while let Some(item) = stack.pop() {
        if let Some(blocks) = conditional_blocks(item) {
            stack.extend(blocks.into_iter().flatten());
            continue;
        }
        let Item::Statement(statement) = item else {
            unreachable!("an elif is a conditional");
        };
        if let Some(blocks) = attempt_blocks(statement) {
            stack.extend(blocks.into_iter().flatten());
            continue;
        }
        match statement {
            Stmt::With(with) if !with.is_async => stack.extend(items(&with.body)),
            Stmt::Import(import) => {
                for alias in &import.names {
                    let name = identifier(alias.name.as_str());
                    let module = mangle(private_class, &name);
                    match &alias.asname {
                        Some(asname) => {
                            found.push((identifier(asname.as_str()).into_owned(), module));
                        }
                        None => {
                            let first = name.split('.').next().unwrap_or(&name).to_owned();
                            let module = module.split('.').next().unwrap_or(&module).to_owned();
                            found.push((first, module));
                        }
                    }
                }
            }
            Stmt::ImportFrom(import) => {
                let module = import
                    .module
                    .as_ref()
                    .map(|module| mangle(private_class, &identifier(module.as_str())));
                let holder = absolute(module.as_deref(), import.level);
                for alias in &import.names {
                    let name = identifier(alias.name.as_str());
                    if name == "*" {
                        continue;
                    }
                    let member = mangle(private_class, &name);
                    let target = match holder.as_deref() {
                        Some(holder) if !holder.is_empty() => format!("{holder}.{member}"),
                        _ => member,
                    };
                    let bound = alias
                        .asname
                        .as_ref()
                        .map_or(name.clone(), |asname| identifier(asname.as_str()));
                    found.push((bound.into_owned(), target));
                }
            }
            _ => {}
        }
    }
    found
}

#[derive(Clone, Copy)]
struct Origin<'t> {
    name: &'t str,
    text: &'t str,
    lines: &'t LineIndex,
}

#[derive(Default)]
pub(crate) struct AnnotationTables<'s> {
    pub(crate) own_stub: Option<OwnStub<'s>>,
    type_only_names: FxHashMap<String, String>,
    stub_scope_path_being_read: Option<StubPath>,
    source_annotated_names_by_scope: FxHashMap<ScopeId, FxHashSet<String>>,
    source_classes_by_stub_path: FxHashMap<StubPath, NodeId>,
    stub_aliases: FxHashMap<NodeKey, NodeId>,
}

fn stub_owned_path(scope: &[String]) -> &[String] {
    &scope[..scope
        .len()
        .checked_sub(1)
        .expect("a stub path names its definition")]
}

impl<'s, A: Analysis> ModuleBuilder<'_, 's, A> {
    pub(crate) fn annotation(&mut self, expression: &Expr) -> Option<NodeId> {
        self.annotation_from(expression, None)
    }

    fn annotation_from(&mut self, expression: &Expr, origin: Option<Origin<'_>>) -> Option<NodeId> {
        let site = self.annotation_site(expression, origin);
        match expression {
            Expr::StringLiteral(_) => {
                let text = origin.map_or(self.source.text, |origin| origin.text);
                let Some(Constant::Str(value)) = literal(expression, text) else {
                    unreachable!("a string literal is a str constant");
                };
                let value: String = value
                    .code_points()
                    .iter()
                    .map(|&point| char::from_u32(point))
                    .collect::<Option<String>>()?;
                let stripped = value.trim_matches(is_python_space);
                let parsed = parse_nested_expression(stripped).ok()?;
                let lines = LineIndex::from_source_text(stripped);
                let name = site.split_once('#').map_or(site.as_str(), |(name, _)| name);
                let nested = Origin {
                    name,
                    text: stripped,
                    lines: &lines,
                };
                self.annotation_from(parsed.expression(), Some(nested))
            }
            Expr::Name(_) | Expr::Attribute(_) => self.annotation_name(expression, origin),
            Expr::BinOp(operation) if operation.op == Operator::BitOr => {
                let mut arms = Vec::new();
                let mut left = expression;
                while let Expr::BinOp(operation) = left
                    && operation.op == Operator::BitOr
                {
                    arms.push(&*operation.right);
                    left = &operation.left;
                }
                arms.push(left);
                let parts: Vec<Option<NodeId>> = arms
                    .into_iter()
                    .rev()
                    .map(|arm| self.annotation_from(arm, origin))
                    .collect();
                Some(self.type_form("|", &parts, &site))
            }
            Expr::Subscript(subscript) => {
                let value = self.annotation_from(&subscript.value, origin);
                let arguments: Vec<&Expr> = match &*subscript.slice {
                    Expr::Tuple(tuple) => tuple.elts.iter().collect(),
                    other => vec![other],
                };
                let mut parts = vec![value];
                for argument in arguments {
                    parts.push(self.annotation_from(argument, origin));
                }
                Some(self.type_form("[]", &parts, &site))
            }
            _ => None,
        }
    }

    fn annotation_site(&self, expression: &Expr, origin: Option<Origin<'_>>) -> String {
        let Some(origin) = origin else {
            return self.site(&Node::Expr(expression));
        };
        let at = position(expression.range(), origin.lines);
        format!(
            "{}/{}:{}#{}:{}",
            origin.name, at.lineno, at.col_offset, at.end_lineno, at.end_col_offset
        )
    }

    fn annotation_name(&mut self, expression: &Expr, origin: Option<Origin<'_>>) -> Option<NodeId> {
        if let Some(path) = self.annotations.stub_scope_path_being_read.clone() {
            return self.stub_name(expression, &path);
        }
        match expression {
            Expr::Name(name) => {
                let name = identifier(name.id.as_str());
                let variable = self.annotation_variable(&name);
                let type_only = self.type_only(&name);
                self.join(&[variable, type_only])
            }
            Expr::Attribute(attribute) => {
                let base = self.annotation_name(&attribute.value, origin)?;
                let value = self.analysis.node(None);
                let attr = self.mangle(&identifier(attribute.attr.as_str()));
                if origin.is_some() {
                    self.analysis.add_name_lookup(base, &attr, value);
                    return Some(value);
                }
                let site = self.annotation_site(expression, origin);
                let caller = self.caller().to_owned();
                self.analysis.add_load(base, &attr, value, &caller, &site);
                Some(value)
            }
            _ => None,
        }
    }

    fn annotation_variable(&mut self, name: &str) -> Option<NodeId> {
        let name = self.mangle(name);
        let scope = self.scopes.resolve(self.scope, &name);
        let kind = self.scopes.scope(scope).kind;
        if kind == ScopeKind::Class && scope != self.scope {
            let class = *self
                .classes
                .get(&scope)
                .expect("an enclosing class is made before its body");
            return Some(self.analysis.constant(class));
        }
        if self.is_builtin(scope, &name) {
            return Some(self.builtin_global(&name));
        }
        let value = self.variable(scope, &name);
        if kind != ScopeKind::Class {
            return Some(value);
        }
        let module = self.scopes.module();
        let global = if self.is_builtin(module, &name) {
            self.builtin_global(&name)
        } else {
            self.variable(module, &name)
        };
        self.join(&[Some(value), Some(global)])
    }

    fn type_only(&mut self, name: &str) -> Option<NodeId> {
        let mut scope = Some(self.scope);
        let mut target = None;
        while let Some(found) = scope
            && target.is_none()
        {
            let found = self.scopes.scope(found);
            let qualified = format!("{}.{}", found.name, found.mangle(name));
            target = self.annotations.type_only_names.get(&qualified).cloned();
            scope = found.parent;
        }
        let target = target?;
        Some(self.imported(&target))
    }

    fn imported(&mut self, target: &str) -> NodeId {
        let Some((module, attribute)) = self.analysis.locate(target) else {
            let external = self.analysis.external(target, 0, false);
            return self.analysis.constant(external);
        };
        let (module, attribute) = match attribute {
            Some(attribute) => (module, attribute),
            None => {
                let (module, attribute) = module.rsplit_once('.').unwrap_or(("", &module));
                if module.is_empty() {
                    let object = self.analysis.module(attribute);
                    return self.analysis.constant(object);
                }
                (module.to_owned(), attribute.to_owned())
            }
        };
        let object = self.analysis.module(&module);
        self.analysis.field(object, &attribute)
    }

    fn type_form(&mut self, operator: &str, parts: &[Option<NodeId>], site: &str) -> NodeId {
        let form = self.analysis.type_form(operator, parts, site);
        self.analysis.constant(form)
    }

    pub(crate) fn alias_form(&mut self, value: &Expr) -> Option<NodeId> {
        let operator = match value {
            Expr::Subscript(_) => "[]",
            Expr::BinOp(operation) if operation.op == Operator::BitOr => "|",
            _ => return None,
        };
        self.annotation(value);
        let site = self.site(&Node::Expr(value));
        let form = self.analysis.type_form(operator, &[], &site);
        let gate = self.analysis.node(None);
        self.analysis.gate_type_form(form, gate);
        Some(gate)
    }

    pub(crate) fn declared(&mut self, annotation: Option<NodeId>, target: &Expr) -> Option<NodeId> {
        let annotation = annotation?;
        let node = self.analysis.node(None);
        let at = self.position(&Node::Expr(target));
        let owner = format!("{}:{}", at.lineno, at.col_offset);
        let module = self.module;
        self.analysis
            .annotated(annotation, node, Shape::Instance, module, &owner);
        Some(node)
    }

    pub(crate) fn parameter_annotations(
        &mut self,
        function: ObjId,
        parameters: &Parameters,
        scope: ScopeId,
    ) {
        let path = match &self.annotations.own_stub {
            Some(_) if self.scopes.scope(scope).kind == ScopeKind::Function => {
                self.stub_path(scope)
            }
            _ => None,
        };
        let mut annotations: Option<IndexMap<Box<str>, NodeId>> = None;
        for (parameter, kind) in parameter_kinds(parameters) {
            let name = identifier(parameter.name.as_str());
            let node = if let Some(annotation) = &parameter.annotation {
                self.annotation(annotation)
            } else if let Some(path) = &path {
                let key = (path.clone(), name.to_string(), kind);
                let found = self
                    .annotations
                    .own_stub
                    .as_ref()
                    .and_then(|stub| stub.parameters.get(&key).cloned());
                self.stub_annotation(found, stub_owned_path(path))
            } else {
                None
            };
            if let Some(node) = node {
                let mangled = self.scopes.scope(scope).mangle(&name);
                annotations
                    .get_or_insert_with(IndexMap::new)
                    .insert(Box::from(mangled.as_str()), node);
            }
        }
        let bound = annotations.as_ref().is_some_and(|found| !found.is_empty());
        self.analysis.function_fields(function).annotations = annotations;
        if bound {
            self.analysis.bind_annotations(function);
        }
    }

    pub(crate) fn stub_variable(&mut self, target: &Expr) -> Option<NodeId> {
        self.annotations.own_stub.as_ref()?;
        let Expr::Name(target) = target else {
            return None;
        };
        let name = self.mangle(&identifier(target.id.as_str()));
        let scope = self.scopes.resolve(self.scope, &name);
        if !matches!(
            self.scopes.scope(scope).kind,
            ScopeKind::Module | ScopeKind::Class
        ) {
            return None;
        }
        let path = self.stub_path(scope)?;
        if self.annotated_in(scope).contains(&name) {
            return None;
        }
        let mut key = path.clone();
        key.push(name);
        let found = self
            .annotations
            .own_stub
            .as_ref()
            .and_then(|stub| stub.variables.get(&key).cloned());
        self.stub_annotation(found, &path)
    }

    fn annotated_in(&mut self, scope: ScopeId) -> &FxHashSet<String> {
        if !self
            .annotations
            .source_annotated_names_by_scope
            .contains_key(&scope)
        {
            let found = self.scopes.scope(scope);
            let body: &[Stmt] = match &found.node {
                Node::Module(module) => &module.body,
                Node::Stmt(Stmt::ClassDef(class)) => &class.body,
                _ => unreachable!("a module or class scope"),
            };
            let mut names = FxHashSet::default();
            let mut pending: Vec<Node<'_>> = body.iter().map(Node::Stmt).collect();
            while let Some(node) = pending.pop() {
                if let Node::Stmt(Stmt::AnnAssign(annotated)) = &node
                    && let Expr::Name(target) = &*annotated.target
                {
                    names.insert(found.mangle(&identifier(target.id.as_str())));
                }
                let nested = matches!(
                    node,
                    Node::Stmt(Stmt::FunctionDef(_) | Stmt::ClassDef(_))
                        | Node::Expr(Expr::Lambda(_))
                );
                if !nested {
                    pending.extend(node.children());
                }
            }
            self.annotations
                .source_annotated_names_by_scope
                .insert(scope, names);
        }
        &self.annotations.source_annotated_names_by_scope[&scope]
    }

    fn stub_origin(&self) -> (String, Source<'s>) {
        let stub = self
            .annotations
            .own_stub
            .as_ref()
            .expect("a stub is read only when the module has one");
        (format!("{}:stub", self.module_name), stub.source)
    }

    fn stub_annotation(
        &mut self,
        annotations: Option<Vec<&'s Expr>>,
        scope: &[String],
    ) -> Option<NodeId> {
        let annotations = annotations.filter(|found| !found.is_empty())?;
        let (name, source) = self.stub_origin();
        let origin = Origin {
            name: &name,
            text: source.text,
            lines: source.lines,
        };
        self.annotations.stub_scope_path_being_read = Some(scope.to_vec());
        let nodes: Vec<Option<NodeId>> = annotations
            .into_iter()
            .map(|annotation| self.annotation_from(annotation, Some(origin)))
            .collect();
        self.annotations.stub_scope_path_being_read = None;
        self.join(&nodes)
    }

    fn stub_name(&mut self, expression: &Expr, scope: &[String]) -> Option<NodeId> {
        let mut attributes = Vec::new();
        let mut base = expression;
        while let Expr::Attribute(attribute) = base {
            attributes.push(identifier(attribute.attr.as_str()).into_owned());
            base = &attribute.value;
        }
        let Expr::Name(base) = base else {
            return None;
        };
        let name = stored(scope, &identifier(base.id.as_str()));
        let rest: String = attributes
            .iter()
            .rev()
            .map(|attribute| format!(".{}", stored(scope, attribute)))
            .collect();
        let mut paths = vec![scope.to_vec()];
        if !scope.is_empty() {
            paths.push(Vec::new());
        }
        for path in paths {
            let Some(bindings) = self
                .annotations
                .own_stub
                .as_ref()
                .and_then(|stub| stub.names.get(&(path.clone(), name.clone())).cloned())
            else {
                continue;
            };
            let mut contributions = Vec::new();
            for binding in bindings {
                match binding {
                    StubBinding::Import(target) => {
                        contributions.push(Some(self.imported(&format!("{target}{rest}"))));
                    }
                    StubBinding::Class(target) if attributes.is_empty() => {
                        contributions.push(Some(self.source_classes(&target)));
                    }
                    StubBinding::Alias(value) if attributes.is_empty() => {
                        contributions.push(Some(self.stub_alias(&path, value)));
                    }
                    _ => {}
                }
            }
            return self.join(&contributions);
        }
        if !attributes.is_empty() {
            return None;
        }
        self.builtin_name(&name)
    }

    fn stub_alias(&mut self, path: &[String], value: &'s Expr) -> NodeId {
        let key = node_key(&Node::Expr(value));
        if let Some(&node) = self.annotations.stub_aliases.get(&key) {
            return node;
        }
        let node = self.analysis.node(None);
        self.annotations.stub_aliases.insert(key, node);
        let reading = self
            .annotations
            .stub_scope_path_being_read
            .replace(path.to_vec());
        let (name, source) = self.stub_origin();
        let origin = Origin {
            name: &name,
            text: source.text,
            lines: source.lines,
        };
        let read = self.annotation_from(value, Some(origin));
        self.annotations.stub_scope_path_being_read = reading;
        if let Some(read) = read {
            self.analysis.add_edge(read, node);
        }
        node
    }

    fn source_classes(&mut self, path: &[String]) -> NodeId {
        if let Some(&node) = self.annotations.source_classes_by_stub_path.get(path) {
            return node;
        }
        let node = self.analysis.node(None);
        self.annotations
            .source_classes_by_stub_path
            .insert(path.to_vec(), node);
        node
    }

    pub(crate) fn defined_class(&mut self, scope: ScopeId, class: ObjId) {
        if self.annotations.own_stub.is_none() {
            return;
        }
        let Some(path) = self.stub_path(scope) else {
            return;
        };
        let classes = self.source_classes(&path);
        self.analysis.add_object(classes, class);
        let bases = self
            .annotations
            .own_stub
            .as_ref()
            .and_then(|stub| stub.bases.get(&path).cloned());
        if let Some(node) = self.stub_annotation(bases, stub_owned_path(&path)) {
            self.analysis.add_stub_bases(class, node);
        }
    }

    fn builtin_name(&mut self, name: &str) -> Option<NodeId> {
        if !builtin_names().contains(name) {
            return None;
        }
        let external = self
            .analysis
            .external(&format!("{BUILTIN_MODULE}.{name}"), 0, false);
        Some(self.analysis.constant(external))
    }

    fn stub_path(&self, scope: ScopeId) -> Option<StubPath> {
        let mut path = Vec::new();
        let mut current = scope;
        while self.scopes.scope(current).kind != ScopeKind::Module {
            let found = self.scopes.scope(current);
            path.push(
                found
                    .local_name
                    .clone()
                    .expect("a scope below the module has a local name"),
            );
            current = found.parent.expect("a scope below the module has a parent");
            if !matches!(
                self.scopes.scope(current).kind,
                ScopeKind::Module | ScopeKind::Class
            ) {
                return None;
            }
        }
        path.reverse();
        Some(path)
    }

    pub(crate) fn record_type_only(&mut self, statements: &[Stmt], clauses: &[ElifElseClause]) {
        let private = self.scopes.scope(self.scope).private_class.clone();
        let mut block: Vec<Item<'_>> = items(statements).collect();
        block.extend(orelse(clauses));
        let imports = {
            let absolute =
                |module: Option<&str>, level: u32| self.absolute_module_name(module, level);
            imported_names(block, &absolute, private.as_deref())
        };
        for (name, target) in imports {
            let found = self.scopes.scope(self.scope);
            let qualified = format!("{}.{}", found.name, found.mangle(&name));
            self.annotations.type_only_names.insert(qualified, target);
        }
    }
}
