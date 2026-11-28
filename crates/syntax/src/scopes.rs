use std::cell::RefCell;

use indexmap::{IndexMap, IndexSet};
use ruff_python_ast::token::Tokens;
use ruff_python_ast::{
    Alias, ExceptHandlerExceptHandler, Expr, ExprContext, ModModule, Parameters, Pattern, Stmt,
};
use ruff_source_file::LineIndex;
use rustc_hash::{FxHashMap, FxHashSet};

use crate::constants::{Constant, PyStr, literal};
use crate::names::identifier;
use crate::tree::{Node, position};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct ScopeId(usize);

impl ScopeId {
    pub fn index(self) -> usize {
        self.0
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct NodeKey(usize);

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ScopeKind {
    Module,
    Class,
    Function,
    Lambda,
    Comprehension,
}

#[derive(Debug)]
pub struct Scope<'a> {
    pub kind: ScopeKind,
    pub node: Node<'a>,
    pub parent: Option<ScopeId>,
    pub local_name: Option<String>,
    pub name: String,
    pub private_class: Option<String>,
    pub bound: IndexSet<String>,
    pub defined: IndexSet<String>,
    pub globals: FxHashSet<String>,
    pub nonlocals: FxHashSet<String>,
    pub generator: bool,
    pub asynchronous: bool,
    pub rebound: FxHashSet<String>,
    pub bound_again: FxHashSet<String>,
    pub shared: FxHashSet<String>,
    pub star_import: bool,
    pub dynamic: bool,
    pub imports: IndexMap<String, Option<String>>,
    pub definitions: IndexMap<String, Option<NodeKey>>,
    pub reads: FxHashSet<String>,
}

impl Scope<'_> {
    pub fn mangle(&self, name: &str) -> String {
        mangle(self.private_class.as_deref(), name)
    }
}

pub fn mangle(private_class: Option<&str>, name: &str) -> String {
    let Some(private_class) = private_class else {
        return name.to_owned();
    };
    if !name.starts_with("__") || name.ends_with("__") || name.contains('.') {
        return name.to_owned();
    }
    let stripped = private_class.trim_start_matches('_');
    if stripped.is_empty() {
        return name.to_owned();
    }
    format!("_{stripped}{name}")
}

pub fn node_key(node: &Node<'_>) -> NodeKey {
    let address = match node {
        Node::Module(module) => std::ptr::from_ref(*module).addr(),
        Node::Stmt(statement) => std::ptr::from_ref(*statement).addr(),
        Node::Elif(clauses) => clauses.as_ptr().addr(),
        Node::Expr(expression) => std::ptr::from_ref(*expression).addr(),
        Node::GeneratorArgument(generator, _) => std::ptr::from_ref(*generator).addr(),
        Node::Arguments(parameters) => parameters.map_or(0, |p| std::ptr::from_ref(p).addr()),
        Node::Arg(parameter) => std::ptr::from_ref(*parameter).addr(),
        Node::Keyword(keyword) => std::ptr::from_ref(*keyword).addr(),
        Node::Alias(alias) => std::ptr::from_ref(*alias).addr(),
        Node::Comprehension(comprehension) => std::ptr::from_ref(*comprehension).addr(),
        Node::ExceptHandler(handler) => std::ptr::from_ref(*handler).addr(),
        Node::WithItem(item) => std::ptr::from_ref(*item).addr(),
        Node::MatchCase(case) => std::ptr::from_ref(*case).addr(),
        Node::Pattern(pattern) => std::ptr::from_ref(*pattern).addr(),
        Node::TypeParam(parameter) => std::ptr::from_ref(*parameter).addr(),
        Node::StringPiece(piece) => piece.range.start().to_usize(),
        Node::Interpolation(element, ..) => std::ptr::from_ref(*element).addr(),
        Node::FormatSpec(spec, _) => std::ptr::from_ref(*spec).addr(),
    };
    NodeKey(address)
}

const SURROGATES: std::ops::RangeInclusive<u32> = 0xd800..=0xdfff;
const UNREADABLE_NAME_SURROGATE: char = char::REPLACEMENT_CHARACTER;

const NAMESPACE_CALLS: [(&str, &[NamespaceTarget]); 5] = [
    ("globals", &[NamespaceTarget::Module]),
    ("locals", &[NamespaceTarget::Caller]),
    ("vars", &[NamespaceTarget::Caller]),
    ("exec", &[NamespaceTarget::Caller, NamespaceTarget::Module]),
    ("eval", &[NamespaceTarget::Caller, NamespaceTarget::Module]),
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum NamespaceTarget {
    Module,
    Caller,
}

fn namespace_targets(name: &str) -> Option<&'static [NamespaceTarget]> {
    NAMESPACE_CALLS
        .iter()
        .find(|(call, _)| *call == name)
        .map(|(_, targets)| *targets)
}

#[derive(Clone, Debug, PartialEq, Eq)]
enum NamespaceUse {
    Call(&'static str),
    SysModules,
}

pub struct ModuleScopes<'a> {
    scopes: Vec<Scope<'a>>,
    order: Vec<ScopeId>,
    scope_of_node: FxHashMap<NodeKey, ScopeId>,
    loops: FxHashMap<NodeKey, IndexMap<String, bool>>,
    loop_nodes: Vec<Node<'a>>,
    resolved: RefCell<FxHashMap<(ScopeId, String), ScopeId>>,
    inline: RefCell<FxHashMap<(ScopeId, ScopeId), bool>>,
    unread_lazy: FxHashSet<NodeKey>,
}

const MODULE_SCOPE: ScopeId = ScopeId(0);

impl<'a> ModuleScopes<'a> {
    pub fn module(&self) -> ScopeId {
        MODULE_SCOPE
    }

    pub fn scope(&self, id: ScopeId) -> &Scope<'a> {
        &self.scopes[id.0]
    }

    pub fn scopes(&self) -> &[ScopeId] {
        &self.order
    }

    pub fn scope_of(&self, node: &Node<'_>) -> ScopeId {
        self.scope_of_node[&node_key(node)]
    }

    pub fn scope_of_key(&self, key: NodeKey) -> Option<ScopeId> {
        self.scope_of_node.get(&key).copied()
    }

    pub fn loop_nodes(&self) -> &[Node<'a>] {
        &self.loop_nodes
    }

    pub fn loop_bindings(&self, node: &Node<'_>) -> &IndexMap<String, bool> {
        &self.loops[&node_key(node)]
    }

    pub fn is_unread_lazy(&self, alias: &Alias) -> bool {
        self.unread_lazy.contains(&node_key(&Node::Alias(alias)))
    }

    pub fn owner(&self, id: ScopeId) -> ScopeId {
        owner(&self.scopes, id)
    }

    pub fn caller(&self, id: ScopeId) -> ScopeId {
        let mut current = id;
        loop {
            let scope = &self.scopes[current.0];
            match (scope.kind, scope.parent) {
                (ScopeKind::Class | ScopeKind::Comprehension, Some(parent)) => current = parent,
                _ => return current,
            }
        }
    }

    pub fn tracked(&self, id: ScopeId, name: &str) -> bool {
        let scope = self.scope(id);
        scope.bound.contains(name)
            && !scope.shared.contains(name)
            && scope.kind != ScopeKind::Comprehension
            && !scope.star_import
            && !scope.dynamic
    }

    pub fn imported(&self, id: ScopeId, name: &str) -> Option<&str> {
        let scope = self.scope(id);
        if scope.shared.contains(name) || scope.star_import || scope.dynamic {
            return None;
        }
        scope
            .imports
            .get(name)
            .and_then(|imported| imported.as_deref())
    }

    pub fn definition(&self, id: ScopeId, name: &str) -> Option<NodeKey> {
        let scope = self.scope(id);
        if scope.shared.contains(name) || scope.star_import || scope.dynamic {
            return None;
        }
        scope.definitions.get(name).copied().flatten()
    }

    pub fn inline(&self, reader: ScopeId, binder: ScopeId) -> bool {
        if let Some(&answer) = self.inline.borrow().get(&(reader, binder)) {
            return answer;
        }
        let mut current = reader;
        while current != binder {
            let scope = self.scope(current);
            let passes = match scope.kind {
                ScopeKind::Class => true,
                ScopeKind::Comprehension => !matches!(
                    scope.node,
                    Node::Expr(Expr::Generator(_)) | Node::GeneratorArgument(..)
                ),
                _ => false,
            };
            match (passes, scope.parent) {
                (true, Some(parent)) => current = parent,
                _ => break,
            }
        }
        let answer = current == binder;
        self.inline.borrow_mut().insert((reader, binder), answer);
        answer
    }

    pub fn resolve(&self, id: ScopeId, name: &str) -> ScopeId {
        let key = (id, name.to_owned());
        if let Some(&found) = self.resolved.borrow().get(&key) {
            return found;
        }
        let found = self.resolve_uncached(id, name);
        self.resolved.borrow_mut().insert(key, found);
        found
    }

    fn resolve_uncached(&self, id: ScopeId, name: &str) -> ScopeId {
        let scope = self.scope(id);
        if scope.globals.contains(name) {
            return MODULE_SCOPE;
        }
        if scope.bound.contains(name) {
            return id;
        }
        self.enclosing(id, name)
    }

    fn enclosing(&self, id: ScopeId, name: &str) -> ScopeId {
        let scope = self.scope(id);
        let mut in_function = matches!(scope.kind, ScopeKind::Function | ScopeKind::Lambda);
        let mut current = scope.parent;
        while let Some(enclosing_id) = current {
            let enclosing = self.scope(enclosing_id);
            if enclosing.kind == ScopeKind::Module {
                break;
            }
            if enclosing.kind == ScopeKind::Class {
                if name == "__class__" && in_function {
                    return enclosing_id;
                }
            } else {
                if enclosing.globals.contains(name) {
                    return MODULE_SCOPE;
                }
                if enclosing.bound.contains(name) {
                    return enclosing_id;
                }
                if matches!(enclosing.kind, ScopeKind::Function | ScopeKind::Lambda) {
                    in_function = true;
                }
            }
            current = enclosing.parent;
        }
        MODULE_SCOPE
    }
}

fn owner(scopes: &[Scope<'_>], id: ScopeId) -> ScopeId {
    let mut current = id;
    while let (ScopeKind::Comprehension, Some(parent)) =
        (scopes[current.0].kind, scopes[current.0].parent)
    {
        current = parent;
    }
    current
}

pub fn analyse_scopes<'a>(
    module: &'a ModModule,
    module_name: &str,
    tokens: &Tokens,
    lines: &LineIndex,
    source: &str,
) -> ModuleScopes<'a> {
    let mut collector = Collector::new(module);
    collector.run();
    apply_declarations(&mut collector.scopes);
    let place = |node: &Node<'_>| {
        let range = node.range(tokens).expect("a scope's node has a position");
        let at = position(range, lines);
        (at.lineno, at.col_offset)
    };
    assign_names(&mut collector, module_name, &place);
    let mut ordered: Vec<ScopeId> = (1..collector.scopes.len()).map(ScopeId).collect();
    ordered.sort_by_key(|id| place(&collector.scopes[id.0].node));
    let mut order = vec![MODULE_SCOPE];
    order.extend(ordered);
    let mut scopes = ModuleScopes {
        scopes: collector.scopes,
        order,
        scope_of_node: collector.scope_of_node,
        loops: collector.loops,
        loop_nodes: collector.loop_nodes,
        resolved: RefCell::default(),
        inline: RefCell::default(),
        unread_lazy: FxHashSet::default(),
    };
    find_namespace_uses(&mut scopes, &collector.namespace_uses);
    find_unread_lazy_imports(&mut scopes, &collector.explicit_lazy, module, source);
    scopes
}

fn find_namespace_uses(scopes: &mut ModuleScopes<'_>, uses: &[(NamespaceUse, ScopeId)]) {
    for (used, id) in uses {
        match used {
            NamespaceUse::SysModules => {
                let binder = scopes.resolve(*id, "sys");
                if scopes.imported(binder, "sys") == Some("sys") {
                    scopes.scopes[MODULE_SCOPE.0].dynamic = true;
                }
            }
            NamespaceUse::Call(name) => {
                let resolved = scopes.resolve(*id, name);
                if scopes.scope(resolved).bound.contains(*name) {
                    continue;
                }
                let targets = namespace_targets(name).expect("a namespace call is listed");
                for target in targets {
                    let scope = match target {
                        NamespaceTarget::Module => MODULE_SCOPE,
                        NamespaceTarget::Caller => scopes.owner(*id),
                    };
                    scopes.scopes[scope.0].dynamic = true;
                }
            }
        }
    }
}

const LAZY_MODULES: &str = "__lazy_modules__";

fn find_unread_lazy_imports<'a>(
    scopes: &mut ModuleScopes<'a>,
    explicit: &[&'a Alias],
    module: &'a ModModule,
    source: &str,
) {
    let mut lazy: Vec<&'a Alias> = explicit.to_vec();
    lazy.extend(listed_lazy_imports(module, source));
    if lazy.is_empty() || scopes.scope(MODULE_SCOPE).dynamic {
        return;
    }
    let mut read: FxHashSet<String> = FxHashSet::default();
    for &id in &scopes.order {
        for name in &scopes.scope(id).reads {
            if scopes.resolve(id, name) == MODULE_SCOPE {
                read.insert(name.clone());
            }
        }
    }
    for alias in lazy {
        let bound = match &alias.asname {
            Some(asname) => &*identifier(asname.id.as_str()),
            None => alias
                .name
                .id
                .split('.')
                .next()
                .expect("a split has a first part"),
        };
        if !read.contains(bound) {
            scopes.unread_lazy.insert(node_key(&Node::Alias(alias)));
        }
    }
}

fn listed_lazy_imports<'a>(module: &'a ModModule, source: &str) -> Vec<&'a Alias> {
    let mut listed: Option<FxHashSet<String>> = None;
    let mut lazy = Vec::new();
    for statement in &module.body {
        if matches!(statement, Stmt::FunctionDef(_) | Stmt::ClassDef(_)) {
            continue;
        }
        if mentions(statement, LAZY_MODULES) {
            listed = literal_assignment(statement, LAZY_MODULES, source)
                .map(|strings| strings.into_iter().collect());
        }
        let Some(names) = listed.as_ref().filter(|names| !names.is_empty()) else {
            continue;
        };
        match statement {
            Stmt::Import(import) => {
                lazy.extend(
                    import
                        .names
                        .iter()
                        .filter(|a| names.contains(&*identifier(a.name.id.as_str()))),
                );
            }
            Stmt::ImportFrom(import) if import.level == 0 => {
                let listed_module = import
                    .module
                    .as_ref()
                    .is_some_and(|m| names.contains(&*identifier(m.id.as_str())));
                if listed_module {
                    lazy.extend(
                        import
                            .names
                            .iter()
                            .filter(|a| &*identifier(a.name.id.as_str()) != "*"),
                    );
                }
            }
            _ => {}
        }
    }
    lazy
}

pub fn mentions(statement: &Stmt, name: &str) -> bool {
    let mut stack = vec![Node::Stmt(statement)];
    while let Some(node) = stack.pop() {
        if let Node::Expr(Expr::Name(expression)) = &node
            && &*identifier(expression.id.as_str()) == name
        {
            return true;
        }
        stack.extend(node.children());
    }
    false
}

fn is_name(expression: &Expr, name: &str) -> bool {
    matches!(expression, Expr::Name(e) if &*identifier(e.id.as_str()) == name)
}

pub fn literal_assignment(statement: &Stmt, name: &str, source: &str) -> Option<Vec<String>> {
    let value = match statement {
        Stmt::Assign(assign) if assign.targets.iter().all(|t| is_name(t, name)) => &assign.value,
        Stmt::AnnAssign(assign) if is_name(&assign.target, name) => assign.value.as_ref()?,
        _ => return None,
    };
    let elements = match value.as_ref() {
        Expr::List(list) => &list.elts,
        Expr::Tuple(tuple) => &tuple.elts,
        _ => return None,
    };
    elements
        .iter()
        .map(|element| match literal(element, source) {
            Some(Constant::Str(text)) => Some(declared_name(&text)),
            _ => None,
        })
        .collect()
}

fn declared_name(text: &PyStr) -> String {
    text.code_points()
        .iter()
        .map(|&point| match char::from_u32(point) {
            Some(character) => character,
            None => {
                assert!(
                    SURROGATES.contains(&point),
                    "a code point of a str is a char or a surrogate"
                );
                UNREADABLE_NAME_SURROGATE
            }
        })
        .collect()
}

fn mark_asynchronous(scopes: &mut [Scope<'_>], id: ScopeId) {
    let mut current = id;
    loop {
        let scope = &mut scopes[current.0];
        if scope.kind != ScopeKind::Comprehension || scope.asynchronous {
            return;
        }
        scope.asynchronous = true;
        if matches!(
            scope.node,
            Node::Expr(Expr::Generator(_)) | Node::GeneratorArgument(..)
        ) {
            return;
        }
        match scope.parent {
            Some(parent) => current = parent,
            None => return,
        }
    }
}

fn bind(scope: &mut Scope<'_>, name: &str, how: Binding) {
    let name = scope.mangle(name);
    let imported = match scope.imports.get(&name) {
        Some(previous) if *previous != how.imported => None,
        _ => how.imported,
    };
    scope.imports.insert(name.clone(), imported);
    let definition = match scope.definitions.get(&name) {
        Some(previous) if *previous != how.definition => None,
        _ => how.definition,
    };
    scope.definitions.insert(name.clone(), definition);
    scope.bound.insert(name.clone());
    if !scope.defined.insert(name.clone()) {
        scope.bound_again.insert(name.clone());
    }
    if !how.parameter {
        scope.rebound.insert(name);
    }
}

#[derive(Default)]
struct Binding {
    parameter: bool,
    imported: Option<String>,
    definition: Option<NodeKey>,
}

fn declare(scope: &mut Scope<'_>, name: &str) {
    let name = scope.mangle(name);
    scope.bound.insert(name);
}

fn apply_declarations(scopes: &mut [Scope<'_>]) {
    for index in 0..scopes.len() {
        let names: Vec<String> = scopes[index].bound.iter().cloned().collect();
        for name in names {
            if scopes[index].globals.contains(&name) {
                apply_global(scopes, index, &name);
            } else if scopes[index].nonlocals.contains(&name) {
                apply_nonlocal(scopes, index, &name);
            }
        }
    }
}

fn apply_global(scopes: &mut [Scope<'_>], index: usize, name: &str) {
    scopes[index].bound.shift_remove(name);
    let module = &mut scopes[MODULE_SCOPE.0];
    module.bound.insert(name.to_owned());
    if index != MODULE_SCOPE.0 {
        module.shared.insert(name.to_owned());
    }
    if scopes[index].defined.shift_remove(name) {
        scopes[MODULE_SCOPE.0].defined.insert(name.to_owned());
    }
}

fn apply_nonlocal(scopes: &mut [Scope<'_>], index: usize, name: &str) {
    scopes[index].bound.shift_remove(name);
    scopes[index].defined.shift_remove(name);
    let mut enclosing = scopes[index].parent;
    while let Some(id) = enclosing {
        let scope = &scopes[id.0];
        if scope.kind != ScopeKind::Class && scope.bound.contains(name) {
            break;
        }
        enclosing = scope.parent;
    }
    if let Some(id) = enclosing
        && scopes[id.0].kind != ScopeKind::Module
    {
        scopes[id.0].rebound.insert(name.to_owned());
        scopes[id.0].shared.insert(name.to_owned());
    }
}

fn assign_names(
    collector: &mut Collector<'_>,
    module_name: &str,
    place: &dyn Fn(&Node<'_>) -> (usize, usize),
) {
    for lambdas in collector.lambdas_by_owner.values_mut() {
        lambdas.sort_by_key(|id| place(&collector.scopes[id.0].node));
        for (number, id) in lambdas.iter().enumerate() {
            collector.scopes[id.0].local_name = Some(format!("<lambda{}>", number + 1));
        }
    }
    for index in 0..collector.scopes.len() {
        let scope = &collector.scopes[index];
        let name = match (scope.kind, scope.parent) {
            (ScopeKind::Module, _) => module_name.to_owned(),
            (ScopeKind::Comprehension, Some(parent)) => {
                let local = scope
                    .local_name
                    .as_deref()
                    .expect("a comprehension has a name");
                format!("{}.{local}", collector.scopes[parent.0].name)
            }
            (_, Some(parent)) => {
                let owner = owner(&collector.scopes, parent);
                let local = scope.local_name.as_deref().expect("a scope has a name");
                format!("{}.{local}", collector.scopes[owner.0].name)
            }
            (_, None) => unreachable!("only the module has no parent"),
        };
        collector.scopes[index].name = name;
    }
}

struct Work<'a> {
    node: Node<'a>,
    scope: ScopeId,
    loops: Vec<NodeKey>,
}

struct Collector<'a> {
    scopes: Vec<Scope<'a>>,
    scope_of_node: FxHashMap<NodeKey, ScopeId>,
    lambdas_by_owner: IndexMap<ScopeId, Vec<ScopeId>>,
    loops: FxHashMap<NodeKey, IndexMap<String, bool>>,
    loop_nodes: Vec<Node<'a>>,
    namespace_uses: Vec<(NamespaceUse, ScopeId)>,
    explicit_lazy: Vec<&'a Alias>,
    work: Vec<Work<'a>>,
    current_loops: Vec<NodeKey>,
}

const COMPREHENSION_NAMES: [(&str, &str); 4] = [
    ("ListComp", "<listcomp>"),
    ("SetComp", "<setcomp>"),
    ("DictComp", "<dictcomp>"),
    ("GeneratorExp", "<genexpr>"),
];

impl<'a> Collector<'a> {
    fn new(module: &'a ModModule) -> Collector<'a> {
        let node = Node::Module(module);
        let mut collector = Collector {
            scopes: Vec::new(),
            scope_of_node: FxHashMap::default(),
            lambdas_by_owner: IndexMap::new(),
            loops: FxHashMap::default(),
            loop_nodes: Vec::new(),
            namespace_uses: Vec::new(),
            explicit_lazy: Vec::new(),
            work: Vec::new(),
            current_loops: Vec::new(),
        };
        let id = collector.new_scope(ScopeKind::Module, node.clone(), None, None);
        let body = module.body.iter().map(Node::Stmt).collect();
        collector.push(body, id, Vec::new());
        collector
    }

    fn new_scope(
        &mut self,
        kind: ScopeKind,
        node: Node<'a>,
        parent: Option<ScopeId>,
        local_name: Option<String>,
    ) -> ScopeId {
        let private_class = match kind {
            ScopeKind::Class => local_name.clone(),
            _ => parent.and_then(|p| self.scopes[p.0].private_class.clone()),
        };
        let id = ScopeId(self.scopes.len());
        self.scope_of_node.insert(node_key(&node), id);
        self.scopes.push(Scope {
            kind,
            node,
            parent,
            local_name,
            name: String::new(),
            private_class,
            bound: IndexSet::new(),
            defined: IndexSet::new(),
            globals: FxHashSet::default(),
            nonlocals: FxHashSet::default(),
            generator: false,
            asynchronous: false,
            rebound: FxHashSet::default(),
            bound_again: FxHashSet::default(),
            shared: FxHashSet::default(),
            star_import: false,
            dynamic: false,
            imports: IndexMap::new(),
            definitions: IndexMap::new(),
            reads: FxHashSet::default(),
        });
        id
    }

    fn push(&mut self, nodes: Vec<Node<'a>>, scope: ScopeId, loops: Vec<NodeKey>) {
        for node in nodes.into_iter().rev() {
            self.work.push(Work {
                node,
                scope,
                loops: loops.clone(),
            });
        }
    }

    fn push_here(&mut self, nodes: Vec<Node<'a>>, scope: ScopeId) {
        let loops = self.current_loops.clone();
        self.push(nodes, scope, loops);
    }

    fn run(&mut self) {
        while let Some(work) = self.work.pop() {
            self.current_loops = work.loops;
            self.visit(work.node, work.scope);
        }
    }

    fn bind_here(&mut self, scope: ScopeId, name: &str, unbinds: bool, how: Binding) {
        bind(&mut self.scopes[scope.0], name, how);
        let name = self.scopes[scope.0].mangle(name);
        for loop_key in &self.current_loops {
            let names = self
                .loops
                .get_mut(loop_key)
                .expect("a loop records its bindings");
            let previous = names.get(&name).copied().unwrap_or(false);
            names.insert(name.clone(), previous || unbinds);
        }
    }

    fn bind_parameters(&mut self, parameters: Option<&'a Parameters>, scope: ScopeId) {
        let Some(parameters) = parameters else {
            return;
        };
        let mut identifiers: Vec<&ruff_python_ast::Identifier> = Vec::new();
        identifiers.extend(parameters.posonlyargs.iter().map(|p| &p.parameter.name));
        identifiers.extend(parameters.args.iter().map(|p| &p.parameter.name));
        identifiers.extend(parameters.kwonlyargs.iter().map(|p| &p.parameter.name));
        identifiers.extend(parameters.vararg.iter().map(|p| &p.name));
        identifiers.extend(parameters.kwarg.iter().map(|p| &p.name));
        let names: Vec<String> = identifiers
            .into_iter()
            .map(|name| identifier(name.id.as_str()).into_owned())
            .collect();
        for name in &names {
            let how = Binding {
                parameter: true,
                ..Binding::default()
            };
            bind(&mut self.scopes[scope.0], name, how);
        }
    }

    fn defaults(parameters: Option<&'a Parameters>) -> Vec<Node<'a>> {
        let Some(parameters) = parameters else {
            return Vec::new();
        };
        let positional = parameters.posonlyargs.iter().chain(parameters.args.iter());
        let defaults = positional.filter_map(|p| p.default.as_deref());
        let keyword_defaults = parameters
            .kwonlyargs
            .iter()
            .filter_map(|p| p.default.as_deref());
        defaults.chain(keyword_defaults).map(Node::Expr).collect()
    }

    fn visit(&mut self, node: Node<'a>, scope: ScopeId) {
        match &node {
            Node::Stmt(statement) => self.visit_statement(statement, &node, scope),
            Node::Expr(expression) => self.visit_expression(expression, &node, scope),
            Node::GeneratorArgument(..) => self.visit_comprehension(&node, scope),
            Node::ExceptHandler(handler) => self.visit_handler(handler, scope),
            Node::Pattern(pattern) => self.visit_pattern(pattern, &node, scope),
            _ => self.push_here(node.children(), scope),
        }
    }

    fn visit_statement(&mut self, statement: &'a Stmt, node: &Node<'a>, scope: ScopeId) {
        match statement {
            Stmt::FunctionDef(function) => {
                let plain = function.decorator_list.is_empty()
                    && self.scopes[scope.0].kind != ScopeKind::Class;
                let definition = plain.then(|| node_key(node));
                let how = Binding {
                    definition,
                    ..Binding::default()
                };
                self.bind_here(scope, &identifier(function.name.id.as_str()), false, how);
                let name = Some(identifier(function.name.id.as_str()).into_owned());
                let inner = self.new_scope(ScopeKind::Function, node.clone(), Some(scope), name);
                self.bind_parameters(Some(&function.parameters), inner);
                let mut outer: Vec<Node<'a>> = function
                    .decorator_list
                    .iter()
                    .map(|d| Node::Expr(&d.expression))
                    .collect();
                outer.extend(Self::defaults(Some(&function.parameters)));
                self.push_here(outer, scope);
                self.push(
                    function.body.iter().map(Node::Stmt).collect(),
                    inner,
                    Vec::new(),
                );
            }
            Stmt::ClassDef(class) => {
                let plain = class.decorator_list.is_empty()
                    && self.scopes[scope.0].kind != ScopeKind::Class;
                let definition = plain.then(|| node_key(node));
                let how = Binding {
                    definition,
                    ..Binding::default()
                };
                self.bind_here(scope, &identifier(class.name.id.as_str()), false, how);
                let name = Some(identifier(class.name.id.as_str()).into_owned());
                let body = self.new_scope(ScopeKind::Class, node.clone(), Some(scope), name);
                let mut outer: Vec<Node<'a>> = class
                    .decorator_list
                    .iter()
                    .map(|d| Node::Expr(&d.expression))
                    .collect();
                if let Some(arguments) = class.arguments.as_deref() {
                    outer.extend(arguments.args.iter().map(Node::Expr));
                    outer.extend(arguments.keywords.iter().map(|k| Node::Expr(&k.value)));
                }
                self.push_here(outer, scope);
                self.push(
                    class.body.iter().map(Node::Stmt).collect(),
                    body,
                    Vec::new(),
                );
            }
            Stmt::For(statement) => {
                self.loops.insert(node_key(node), IndexMap::new());
                self.loop_nodes.push(node.clone());
                let mut inside = self.current_loops.clone();
                inside.push(node_key(node));
                self.push_here(statement.orelse.iter().map(Node::Stmt).collect(), scope);
                self.push(
                    statement.body.iter().map(Node::Stmt).collect(),
                    scope,
                    inside.clone(),
                );
                self.push_here(vec![Node::Expr(&statement.iter)], scope);
                self.push(vec![Node::Expr(&statement.target)], scope, inside);
            }
            Stmt::While(statement) => {
                self.loops.insert(node_key(node), IndexMap::new());
                self.loop_nodes.push(node.clone());
                let mut inside = self.current_loops.clone();
                inside.push(node_key(node));
                self.push_here(statement.orelse.iter().map(Node::Stmt).collect(), scope);
                let mut body = vec![Node::Expr(&statement.test)];
                body.extend(statement.body.iter().map(Node::Stmt));
                self.push(body, scope, inside);
            }
            Stmt::Global(statement) => {
                let names: Vec<String> = statement
                    .names
                    .iter()
                    .map(|n| self.scopes[scope.0].mangle(&identifier(n.id.as_str())))
                    .collect();
                self.scopes[scope.0].globals.extend(names);
            }
            Stmt::Nonlocal(statement) => {
                let names: Vec<String> = statement
                    .names
                    .iter()
                    .map(|n| self.scopes[scope.0].mangle(&identifier(n.id.as_str())))
                    .collect();
                self.scopes[scope.0].nonlocals.extend(names);
            }
            Stmt::Import(import) => {
                if import.is_lazy {
                    self.explicit_lazy.extend(import.names.iter());
                }
                for alias in &import.names {
                    let name = identifier(alias.name.id.as_str()).into_owned();
                    let (bound, imported) = match &alias.asname {
                        Some(asname) => (identifier(asname.id.as_str()).into_owned(), name),
                        None => {
                            let top = name.split('.').next().expect("a first part").to_owned();
                            (top.clone(), top)
                        }
                    };
                    let how = Binding {
                        imported: Some(imported),
                        ..Binding::default()
                    };
                    self.bind_here(scope, &bound, false, how);
                }
            }
            Stmt::ImportFrom(import) => {
                if import.is_lazy {
                    self.explicit_lazy.extend(import.names.iter());
                }
                for alias in &import.names {
                    if &*identifier(alias.name.id.as_str()) == "*" {
                        self.scopes[scope.0].star_import = true;
                        continue;
                    }
                    let imported = match (&import.module, import.level) {
                        (Some(module), 0) => Some(format!(
                            "{}.{}",
                            identifier(module.id.as_str()),
                            identifier(alias.name.id.as_str())
                        )),
                        _ => None,
                    };
                    let bound = alias.asname.as_ref().unwrap_or(&alias.name).id.as_str();
                    self.bind_here(
                        scope,
                        bound,
                        false,
                        Binding {
                            imported,
                            ..Binding::default()
                        },
                    );
                }
            }
            Stmt::AnnAssign(statement) => {
                if statement.value.is_none()
                    && let Expr::Name(target) = statement.target.as_ref()
                {
                    declare(&mut self.scopes[scope.0], &identifier(target.id.as_str()));
                    return;
                }
                let mut nodes = vec![Node::Expr(&statement.target)];
                nodes.extend(statement.value.as_deref().map(Node::Expr));
                self.push_here(nodes, scope);
            }
            Stmt::TypeAlias(statement) => {
                if let Expr::Name(name) = statement.name.as_ref() {
                    self.bind_here(
                        scope,
                        &identifier(name.id.as_str()),
                        false,
                        Binding::default(),
                    );
                }
            }
            _ => self.push_here(node.children(), scope),
        }
    }

    fn visit_expression(&mut self, expression: &'a Expr, node: &Node<'a>, scope: ScopeId) {
        match expression {
            Expr::Lambda(lambda) => {
                let inner = self.new_scope(ScopeKind::Lambda, node.clone(), Some(scope), None);
                let owner = owner(&self.scopes, scope);
                self.lambdas_by_owner.entry(owner).or_default().push(inner);
                self.bind_parameters(lambda.parameters.as_deref(), inner);
                self.push_here(Self::defaults(lambda.parameters.as_deref()), scope);
                self.push(vec![Node::Expr(&lambda.body)], inner, Vec::new());
            }
            Expr::ListComp(_) | Expr::SetComp(_) | Expr::DictComp(_) | Expr::Generator(_) => {
                self.visit_comprehension(node, scope);
            }
            Expr::Subscript(subscript) => {
                if is_sys_modules_of_name(subscript) {
                    self.namespace_uses.push((NamespaceUse::SysModules, scope));
                }
                self.push_here(node.children(), scope);
            }
            Expr::Call(call) => {
                if let Expr::Name(function) = call.func.as_ref()
                    && let Some((name, _)) = NAMESPACE_CALLS
                        .iter()
                        .find(|(name, _)| *name == &*identifier(function.id.as_str()))
                {
                    let arguments = &call.arguments;
                    let empty = arguments.args.is_empty() && arguments.keywords.is_empty();
                    if *name != "vars" || empty {
                        self.namespace_uses.push((NamespaceUse::Call(name), scope));
                    }
                }
                self.push_here(node.children(), scope);
            }
            Expr::Name(name) => match name.ctx {
                ExprContext::Load => {
                    let mangled = self.scopes[scope.0].mangle(&identifier(name.id.as_str()));
                    self.scopes[scope.0].reads.insert(mangled);
                }
                ExprContext::Store | ExprContext::Del => {
                    let unbinds = name.ctx == ExprContext::Del;
                    self.bind_here(
                        scope,
                        &identifier(name.id.as_str()),
                        unbinds,
                        Binding::default(),
                    );
                }
                ExprContext::Invalid => unreachable!("a parsed module has no invalid context"),
            },
            Expr::Named(named) => {
                let Expr::Name(target) = named.target.as_ref() else {
                    unreachable!("an assignment expression targets a name");
                };
                if self.scopes[scope.0].kind == ScopeKind::Comprehension {
                    let owner = owner(&self.scopes, scope);
                    bind(
                        &mut self.scopes[owner.0],
                        &identifier(target.id.as_str()),
                        Binding::default(),
                    );
                    let mangled = self.scopes[owner.0].mangle(&identifier(target.id.as_str()));
                    self.scopes[owner.0].shared.insert(mangled);
                } else {
                    self.bind_here(
                        scope,
                        &identifier(target.id.as_str()),
                        false,
                        Binding::default(),
                    );
                }
                self.push_here(vec![Node::Expr(&named.value)], scope);
            }
            Expr::Yield(_) | Expr::YieldFrom(_) => {
                let owner = owner(&self.scopes, scope);
                self.scopes[owner.0].generator = true;
                self.push_here(node.children(), scope);
            }
            Expr::Await(_) => {
                mark_asynchronous(&mut self.scopes, scope);
                self.push_here(node.children(), scope);
            }
            _ => self.push_here(node.children(), scope),
        }
    }

    fn visit_comprehension(&mut self, node: &Node<'a>, scope: ScopeId) {
        let (generators, elements): (&'a [ruff_python_ast::Comprehension], Vec<Node<'a>>) =
            match node {
                Node::Expr(Expr::ListComp(e)) => (&e.generators, vec![Node::Expr(&e.elt)]),
                Node::Expr(Expr::SetComp(e)) => (&e.generators, vec![Node::Expr(&e.elt)]),
                Node::Expr(Expr::Generator(e)) => (&e.generators, vec![Node::Expr(&e.elt)]),
                Node::GeneratorArgument(e, _) => (&e.generators, vec![Node::Expr(&e.elt)]),
                Node::Expr(Expr::DictComp(e)) => {
                    let mut parts: Vec<Node<'a>> =
                        e.key.as_deref().map(Node::Expr).into_iter().collect();
                    parts.push(Node::Expr(&e.value));
                    (&e.generators, parts)
                }
                _ => unreachable!("a comprehension node"),
            };
        let kind = node.kind();
        let local = COMPREHENSION_NAMES
            .iter()
            .find(|(name, _)| *name == kind)
            .map(|(_, local)| (*local).to_owned());
        let inner = self.new_scope(ScopeKind::Comprehension, node.clone(), Some(scope), local);
        let first = generators.first().expect("a comprehension has a generator");
        self.push_here(vec![Node::Expr(&first.iter)], scope);
        if generators.iter().any(|generator| generator.is_async) {
            mark_asynchronous(&mut self.scopes, inner);
        }
        let mut inside: Vec<Node<'a>> = Vec::new();
        for (index, generator) in generators.iter().enumerate() {
            if index > 0 {
                inside.push(Node::Expr(&generator.iter));
            }
            inside.push(Node::Expr(&generator.target));
            inside.extend(generator.ifs.iter().map(Node::Expr));
        }
        inside.extend(elements);
        self.push(inside, inner, Vec::new());
    }

    fn visit_handler(&mut self, handler: &'a ExceptHandlerExceptHandler, scope: ScopeId) {
        if let Some(name) = &handler.name {
            self.bind_here(
                scope,
                &identifier(name.id.as_str()),
                true,
                Binding::default(),
            );
        }
        let mut nodes: Vec<Node<'a>> = handler
            .type_
            .as_deref()
            .map(Node::Expr)
            .into_iter()
            .collect();
        nodes.extend(handler.body.iter().map(Node::Stmt));
        self.push_here(nodes, scope);
    }

    fn visit_pattern(&mut self, pattern: &'a Pattern, node: &Node<'a>, scope: ScopeId) {
        match pattern {
            Pattern::MatchAs(p) => {
                if let Some(name) = &p.name {
                    self.bind_here(
                        scope,
                        &identifier(name.id.as_str()),
                        false,
                        Binding::default(),
                    );
                }
                if let Some(inner) = p.pattern.as_deref() {
                    self.push_here(vec![Node::Pattern(inner)], scope);
                }
            }
            Pattern::MatchStar(p) => {
                if let Some(name) = &p.name {
                    self.bind_here(
                        scope,
                        &identifier(name.id.as_str()),
                        false,
                        Binding::default(),
                    );
                }
            }
            Pattern::MatchMapping(p) => {
                if let Some(rest) = &p.rest {
                    self.bind_here(
                        scope,
                        &identifier(rest.id.as_str()),
                        false,
                        Binding::default(),
                    );
                }
                let mut nodes: Vec<Node<'a>> = p.keys.iter().map(Node::Expr).collect();
                nodes.extend(p.patterns.iter().map(Node::Pattern));
                self.push_here(nodes, scope);
            }
            _ => self.push_here(node.children(), scope),
        }
    }
}

fn is_sys_modules_of_name(subscript: &ruff_python_ast::ExprSubscript) -> bool {
    let Expr::Attribute(attribute) = subscript.value.as_ref() else {
        return false;
    };
    &*identifier(attribute.attr.id.as_str()) == "modules"
        && is_name(&attribute.value, "sys")
        && is_name(&subscript.slice, "__name__")
}
