mod annotations;
pub mod bindings;
pub mod calls;
mod comprehensions;
pub mod expressions;
pub mod flow;
mod format;
mod literals;
mod matching;
mod narrowing;
mod patterns;
pub mod statements;

use indexmap::IndexMap;
use pycg_solver::{NodeId, ObjId};
use pycg_syntax::scopes::{ModuleScopes, NodeKey, ScopeId, ScopeKind};
use pycg_syntax::tree::{Node, Position, position};
use ruff_python_ast::token::Tokens;
use ruff_python_ast::{ModModule, Stmt};
use ruff_source_file::LineIndex;
use rustc_hash::FxHashMap;

use std::sync::OnceLock;

use pycg_stubs::{Entry, Stubs};
use rustc_hash::FxHashSet;

use crate::builder::annotations::{AnnotationTables, OwnStub};
use crate::builder::calls::{Analysis, MadeFunction};
use crate::builder::expressions::ExpressionTables;
use crate::builder::flow::{
    Definition, FALSE, Flow, Literal, Literals, TRUE, Truth, UNBOUND, UNKNOWN,
};
use crate::builder::narrowing::ClassTests;

pub const IMPLICIT_MODULE_NAMES: [&str; 6] = [
    "__debug__",
    "__doc__",
    "__loader__",
    "__name__",
    "__package__",
    "__spec__",
];
pub const TYPING_MODULES: [&str; 2] = ["typing", "typing_extensions"];
pub const TYPE_CHECKING_IMPORTS: [&str; 2] =
    ["typing.TYPE_CHECKING", "typing_extensions.TYPE_CHECKING"];

pub fn builtin_names() -> &'static FxHashSet<String> {
    static NAMES: OnceLock<FxHashSet<String>> = OnceLock::new();
    NAMES.get_or_init(|| {
        let mut stubs = Stubs::new();
        let module = stubs
            .module("builtins")
            .expect("the stub data has builtins");
        let mut names: FxHashSet<String> = IMPLICIT_MODULE_NAMES
            .iter()
            .map(|name| (*name).to_owned())
            .collect();
        for (name, &entry) in &stubs.module_data(module).names {
            let private = name.starts_with('_') && !name.starts_with("__");
            let stub_only =
                matches!(stubs.entry(entry), Entry::Class(class) if class.type_check_only);
            if !private && !stub_only {
                names.insert(name.to_string());
            }
        }
        names
    })
}

pub type Facts = (Truth, Option<Literals>);

pub const UNKNOWN_FACTS: Facts = (UNKNOWN, None);

#[derive(Clone, Copy)]
pub struct Source<'a> {
    pub text: &'a str,
    pub tokens: &'a Tokens,
    pub lines: &'a LineIndex,
}

pub struct ModuleBuilder<'a, 's, A: Analysis> {
    pub(crate) analysis: &'a mut A,
    pub(crate) module_name: String,
    pub(crate) module: ObjId,
    pub(crate) source: Source<'s>,
    pub(crate) scopes: &'a ModuleScopes<'s>,
    pub(crate) is_package: bool,
    pub(crate) is_entry: bool,
    pub(crate) scope: ScopeId,
    pub(crate) function: Option<MadeFunction>,
    pub(crate) flows: Vec<(ScopeId, Flow)>,
    pub(crate) classes: FxHashMap<ScopeId, ObjId>,
    pub(crate) variables: IndexMap<(ScopeId, String), NodeId>,
    pub(crate) untracked_nodes_by_scope: FxHashMap<ScopeId, IndexMap<String, NodeId>>,
    pub(crate) builtin_globals: IndexMap<String, NodeId>,
    pub(crate) maybe_builtins: IndexMap<String, NodeId>,
    pub(crate) builtin_values: IndexMap<String, NodeId>,
    pub(crate) definitions: FxHashMap<NodeKey, &'s Stmt>,
    pub(crate) assigned_by_declared_binding: FxHashMap<NodeId, Option<NodeId>>,
    pub(crate) names_bound_to_importlib: FxHashSet<String>,
    pub(crate) import_module_names: FxHashSet<String>,
    pub star_imported_modules: Vec<String>,
    pub outside_star_imported_modules: Vec<String>,
    pub(crate) expressions: ExpressionTables,
    pub(crate) class_tests: ClassTests,
    pub(crate) annotations: AnnotationTables<'s>,
}

impl<'a, 's, A: Analysis> ModuleBuilder<'a, 's, A> {
    pub fn new(
        analysis: &'a mut A,
        module_name: &str,
        module: ObjId,
        source: Source<'s>,
        scopes: &'a ModuleScopes<'s>,
        is_package: bool,
        is_entry: bool,
    ) -> Self {
        ModuleBuilder {
            analysis,
            module_name: module_name.to_owned(),
            module,
            source,
            scopes,
            is_package,
            is_entry,
            scope: scopes.module(),
            function: None,
            flows: vec![(scopes.module(), Flow::new())],
            classes: FxHashMap::default(),
            variables: IndexMap::new(),
            untracked_nodes_by_scope: FxHashMap::default(),
            builtin_globals: IndexMap::new(),
            maybe_builtins: IndexMap::new(),
            builtin_values: IndexMap::new(),
            definitions: FxHashMap::default(),
            assigned_by_declared_binding: FxHashMap::default(),
            names_bound_to_importlib: FxHashSet::default(),
            import_module_names: FxHashSet::default(),
            star_imported_modules: Vec::new(),
            outside_star_imported_modules: Vec::new(),
            expressions: ExpressionTables::default(),
            class_tests: ClassTests::default(),
            annotations: AnnotationTables::default(),
        }
    }

    pub fn with_own_stub(mut self, tree: &'s ModModule, source: Source<'s>) -> Self {
        let absolute = |module: Option<&str>, level: u32| self.absolute_module_name(module, level);
        let stub = OwnStub::new(tree, source, &absolute);
        self.annotations.own_stub = Some(stub);
        self
    }

    pub(crate) fn position(&self, node: &Node<'_>) -> Position {
        let range = node
            .range(self.source.tokens)
            .expect("a node that the builder places has a position");
        position(range, self.source.lines)
    }

    pub(crate) fn site(&self, node: &Node<'_>) -> String {
        self.span(node, node)
    }

    pub(crate) fn span(&self, first: &Node<'_>, last: &Node<'_>) -> String {
        let first = self.position(first);
        let last = self.position(last);
        format!(
            "{}:{}:{}#{}:{}",
            self.module_name, first.lineno, first.col_offset, last.end_lineno, last.end_col_offset
        )
    }

    pub(crate) fn caller(&self) -> &str {
        &self.scopes.scope(self.scopes.caller(self.scope)).name
    }

    pub(crate) fn variable(&mut self, scope: ScopeId, name: &str) -> NodeId {
        match self.scopes.scope(scope).kind {
            ScopeKind::Module => self.analysis.field(self.module, name),
            ScopeKind::Class => {
                let class = self.classes[&scope];
                self.analysis.field(class, name)
            }
            ScopeKind::Function | ScopeKind::Lambda | ScopeKind::Comprehension => {
                let key = (scope, name.to_owned());
                if let Some(&node) = self.variables.get(&key) {
                    return node;
                }
                let label = format!("{}.{name}", self.scopes.scope(scope).name);
                let node = self.analysis.node(Some(&label));
                self.variables.insert(key, node);
                node
            }
        }
    }

    pub(crate) fn flow(&mut self) -> &mut Flow {
        &mut self.flows.last_mut().expect("a flow").1
    }

    pub(crate) fn current_flow(&self) -> &Flow {
        &self.flows.last().expect("a flow").1
    }

    fn flow_of(&self, scope: ScopeId) -> Option<&Flow> {
        self.flows
            .iter()
            .rev()
            .find(|(owner, _)| *owner == scope)
            .map(|(_, flow)| flow)
    }

    pub(crate) fn mangle(&self, name: &str) -> String {
        self.scopes.scope(self.scope).mangle(name)
    }

    pub(crate) fn inside<R>(
        &mut self,
        scope: ScopeId,
        function: Option<MadeFunction>,
        body: impl FnOnce(&mut Self) -> R,
    ) -> R {
        let saved_scope = self.scope;
        let saved_function = self.function.take();
        let opens_flow = self.scopes.scope(scope).kind != ScopeKind::Comprehension;
        if opens_flow {
            let mut flow = Flow::new();
            if let Some(made) = &function {
                for (name, &parameter) in &made.parameters {
                    if self.scopes.tracked(scope, name) {
                        let definition = flow.new_definition(Definition {
                            node: Some(parameter),
                            unbound: false,
                            truth: UNKNOWN,
                            values: None,
                        });
                        let state = flow.state;
                        flow.set_change(state, name, definition);
                    }
                }
            }
            self.flows.push((scope, flow));
        }
        self.scope = scope;
        self.function = function;
        let result = body(self);
        if opens_flow {
            self.flows.pop();
        }
        self.scope = saved_scope;
        self.function = saved_function;
        result
    }

    pub(crate) fn join(&mut self, values: &[Option<NodeId>]) -> Option<NodeId> {
        let values: Vec<NodeId> = values.iter().flatten().copied().collect();
        if values.len() <= 1 {
            return values.first().copied();
        }
        let joined = self.analysis.node(None);
        for value in values {
            self.analysis.add_edge(value, joined);
        }
        Some(joined)
    }

    pub(crate) fn load_name(&mut self, name: &str) -> Option<NodeId> {
        self.read_name(name).0
    }

    pub(crate) fn read_name(&mut self, name: &str) -> (Option<NodeId>, Facts) {
        let name = self.mangle(name);
        let scope = self.scopes.resolve(self.scope, &name);
        let kind = self.scopes.scope(scope).kind;
        if kind == ScopeKind::Class && scope != self.scope {
            let class = self.classes[&scope];
            return (Some(self.analysis.constant(class)), UNKNOWN_FACTS);
        }
        if self.is_builtin(scope, &name) {
            let mut facts = UNKNOWN_FACTS;
            if name == "__name__" && !self.is_entry && !self.scopes.scope(scope).dynamic {
                facts = (
                    TRUE,
                    Some(Literals::of([Literal::Str(
                        self.module_name.chars().map(u32::from).collect(),
                    )])),
                );
            }
            return (Some(self.builtin_global(&name)), facts);
        }
        let mut definition = self.reaching(scope, &name);
        if definition.is_none() && kind == ScopeKind::Class {
            definition = Some(Definition {
                node: Some(self.variable(scope, &name)),
                unbound: true,
                truth: UNKNOWN,
                values: None,
            });
        }
        let Some(definition) = definition else {
            let mut facts = UNKNOWN_FACTS;
            if self
                .scopes
                .imported(scope, &name)
                .is_some_and(|imported| TYPE_CHECKING_IMPORTS.contains(&imported))
            {
                facts = (FALSE, Some(Literals::of([Literal::Bool(false)])));
            }
            let variable = self.variable(scope, &name);
            if kind == ScopeKind::Module && builtin_names().contains(&name) {
                let maybe = self.maybe_builtin(&name);
                return (self.join(&[Some(variable), Some(maybe)]), facts);
            }
            return (Some(variable), facts);
        };
        let truth_or_unknown = if definition.truth == 0 {
            UNKNOWN
        } else {
            definition.truth
        };
        if !definition.unbound {
            return (definition.node, (truth_or_unknown, definition.values));
        }
        if kind == ScopeKind::Class {
            let module_value = self.value_of(self.scopes.module(), &name);
            return (self.join(&[definition.node, module_value]), UNKNOWN_FACTS);
        }
        if kind == ScopeKind::Module && builtin_names().contains(&name) {
            let builtin = self.builtin_value(&name);
            return (self.join(&[definition.node, Some(builtin)]), UNKNOWN_FACTS);
        }
        (definition.node, (truth_or_unknown, definition.values))
    }

    pub(crate) fn maybe_builtin(&mut self, name: &str) -> NodeId {
        if let Some(&node) = self.maybe_builtins.get(name) {
            return node;
        }
        let node = self.analysis.node(None);
        self.maybe_builtins.insert(name.to_owned(), node);
        node
    }

    pub(crate) fn value_of(&mut self, scope: ScopeId, name: &str) -> Option<NodeId> {
        if self.is_builtin(scope, name) {
            return Some(self.builtin_global(name));
        }
        let Some(definition) = self.reaching(scope, name) else {
            return Some(self.variable(scope, name));
        };
        if definition.unbound && builtin_names().contains(name) {
            let builtin = self.builtin_value(name);
            return self.join(&[definition.node, Some(builtin)]);
        }
        definition.node
    }

    pub(crate) fn reaching(&self, scope: ScopeId, name: &str) -> Option<Definition> {
        let flow = self.flow_of(scope)?;
        if !self.scopes.tracked(scope, name) || !self.scopes.inline(self.scope, scope) {
            return None;
        }
        Some(flow.definition_of(flow.read(name)).clone())
    }

    pub(crate) fn bind(
        &mut self,
        name: &str,
        value: Option<NodeId>,
        truth: Truth,
        values: Option<Literals>,
    ) {
        let name = self.mangle(name);
        let scope = self.scopes.resolve(self.scope, &name);
        let variable = if scope == self.scope && self.scopes.tracked(scope, &name) {
            self.flow().define(&name, value, truth, values);
            if self.scopes.scope(scope).kind == ScopeKind::Class {
                return;
            }
            self.variable(scope, &name)
        } else {
            self.untracked(scope, &name)
        };
        if let Some(value) = value {
            self.analysis.add_edge(value, variable);
        }
    }

    pub(crate) fn untracked(&mut self, scope: ScopeId, name: &str) -> NodeId {
        if let Some(&node) = self
            .untracked_nodes_by_scope
            .get(&scope)
            .and_then(|bound| bound.get(name))
        {
            return node;
        }
        let node = if self.scopes.scope(scope).kind == ScopeKind::Class {
            self.analysis.node(None)
        } else {
            self.variable(scope, name)
        };
        self.untracked_nodes_by_scope
            .entry(scope)
            .or_default()
            .insert(name.to_owned(), node);
        node
    }

    pub(crate) fn bound_at_end(&self, scope: ScopeId) -> IndexMap<String, Option<NodeId>> {
        let flow = self.flow_of(scope).expect("the scope's flow is open");
        let mut members = IndexMap::new();
        for name in flow.changed_from_root(flow.state) {
            let definition = flow.get(&name);
            if flow.definition_of(definition) != flow.definition_of(UNBOUND) {
                members.insert(name, flow.definition_of(definition).node);
            }
        }
        if let Some(untracked) = self.untracked_nodes_by_scope.get(&scope) {
            for (name, &node) in untracked {
                members.insert(name.clone(), Some(node));
            }
        }
        members
    }

    pub(crate) fn unbind(&mut self, name: &str) {
        let name = self.mangle(name);
        let scope = self.scopes.resolve(self.scope, &name);
        if scope == self.scope && self.scopes.tracked(scope, &name) {
            self.flow().unbind(&name);
        }
    }

    pub(crate) fn is_builtin(&self, scope: ScopeId, name: &str) -> bool {
        let found = self.scopes.scope(scope);
        found.kind == ScopeKind::Module
            && !found.bound.contains(name)
            && builtin_names().contains(name)
    }

    pub(crate) fn builtin_global(&mut self, name: &str) -> NodeId {
        if let Some(&node) = self.builtin_globals.get(name) {
            return node;
        }
        let node = self.analysis.node(None);
        let field = self.analysis.field(self.module, name);
        self.analysis.add_edge(field, node);
        let value = self.builtin_value(name);
        self.analysis.add_edge(value, node);
        self.builtin_globals.insert(name.to_owned(), node);
        node
    }

    pub(crate) fn builtin_value(&mut self, name: &str) -> NodeId {
        if let Some(&value) = self.builtin_values.get(name) {
            return value;
        }
        let value = self.analysis.imported_value(&format!("builtins.{name}"));
        self.builtin_values.insert(name.to_owned(), value);
        value
    }
}
