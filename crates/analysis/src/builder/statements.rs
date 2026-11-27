use indexmap::IndexMap;
use pycg_solver::{NodeId, ObjId};
use pycg_syntax::names::identifier;
use pycg_syntax::scopes::{ScopeId, ScopeKind};
use pycg_syntax::tree::Node;
use ruff_python_ast::{
    Alias, ElifElseClause, ExceptHandler, Expr, ExprContext, Parameters, Stmt, StmtClassDef,
    StmtFunctionDef,
};
use rustc_hash::FxHashSet;

use crate::builder::calls::{Allocator, Passthrough};
use crate::builder::calls::{
    Analysis, Call, ClassStatement, Constant, MadeFunction, MethodKind, NewClass,
};
use crate::builder::flow::{FALSE, Literals, StateId, TRUE, Truth, UNKNOWN};
use crate::builder::{ModuleBuilder, TYPING_MODULES, bindings};
use crate::model::Signature;

const IMPLICIT_METHODS: [(&str, MethodKind); 3] = [
    ("__new__", MethodKind::StaticMethod),
    ("__init_subclass__", MethodKind::ClassMethod),
    ("__class_getitem__", MethodKind::ClassMethod),
];

fn implicit_method(name: &str) -> Option<MethodKind> {
    IMPLICIT_METHODS
        .iter()
        .find(|(method, _)| *method == name)
        .map(|(_, kind)| *kind)
}

pub(crate) fn names(expression: &Expr, name: &str) -> bool {
    let expression = match expression {
        Expr::Call(call) => &*call.func,
        Expr::Subscript(subscript) => &*subscript.value,
        other => other,
    };
    match expression {
        Expr::Name(found) => identifier(found.id.as_str()) == name,
        Expr::Attribute(attribute) => identifier(attribute.attr.as_str()) == name,
        _ => false,
    }
}

pub(crate) fn signature_of(parameters: &Parameters, mangle: impl Fn(&str) -> String) -> Signature {
    let positional: Vec<Box<str>> = parameters
        .posonlyargs
        .iter()
        .chain(parameters.args.iter())
        .map(|parameter| Box::from(mangle(&identifier(parameter.parameter.name.as_str()))))
        .collect();
    let keyword_only = parameters
        .kwonlyargs
        .iter()
        .map(|parameter| Box::from(mangle(&identifier(parameter.parameter.name.as_str()))))
        .collect();
    let vararg = parameters
        .vararg
        .as_ref()
        .map(|parameter| Box::from(mangle(&identifier(parameter.name.as_str()))));
    let kwarg = parameters
        .kwarg
        .as_ref()
        .map(|parameter| Box::from(mangle(&identifier(parameter.name.as_str()))));
    Signature::new(
        positional,
        parameters.posonlyargs.len(),
        keyword_only,
        vararg,
        kwarg,
    )
}

impl<'s, A: Analysis> ModuleBuilder<'_, 's, A> {
    pub fn build(&mut self, body: &'s [Stmt]) -> Option<usize> {
        for statement in body {
            for node in bindings::walk_all(&Node::Stmt(statement)) {
                if let Node::Stmt(found @ (Stmt::FunctionDef(_) | Stmt::ClassDef(_))) = node {
                    self.definitions
                        .insert(pycg_syntax::scopes::node_key(&node), found);
                }
            }
        }
        let name = self.analysis.field(self.module, "__name__");
        let module_name = Constant::Str(self.module_name.chars().map(u32::from).collect());
        let value = self.analysis.const_object(&module_name);
        self.analysis.add_object(name, value);
        if self.is_entry {
            let main = Constant::Str("__main__".chars().map(u32::from).collect());
            let value = self.analysis.const_object(&main);
            self.analysis.add_object(name, value);
        }
        let too_deep = body
            .iter()
            .position(|statement| bindings::nesting(statement) > bindings::NESTING_MAX);
        self.statements(&body[..too_deep.unwrap_or(body.len())]);
        let module_scope = self.scopes.module();
        let bound: Vec<String> = self.bound_at_end(module_scope).into_keys().collect();
        self.names_bound_at_run_time = bound.clone();
        let top_level = top_level_bindings(body);
        let maybe: Vec<(String, NodeId)> = self
            .maybe_builtins
            .iter()
            .map(|(name, &node)| (name.clone(), node))
            .collect();
        for (name, node) in maybe {
            let unbound = if self.scopes.tracked(module_scope, &name) {
                let flow = self.current_flow();
                flow.definition_of(flow.get(&name)).unbound
            } else {
                !top_level.contains(&name)
            };
            if unbound {
                let value = self.builtin_value(&name);
                self.analysis.add_edge(value, node);
            }
        }
        let module = self.module;
        let defines = self.analysis.module_defines(module);
        for name in bound {
            if !defines.iter().any(|defined| **defined == *name) {
                defines.push(name.into_boxed_str());
            }
        }
        too_deep.map(|index| self.position(&Node::Stmt(&body[index])).lineno)
    }

    pub(crate) fn statements(&mut self, statements: &[Stmt]) {
        for statement in statements {
            if !self.current_flow().is_reachable() {
                return;
            }
            self.statement(statement);
        }
    }

    fn statement(&mut self, statement: &Stmt) {
        match statement {
            Stmt::FunctionDef(function) => self.function_definition(statement, function),
            Stmt::ClassDef(class) => self.class_definition(statement, class),
            Stmt::Return(returned) => {
                if let Some(value) = &returned.value {
                    let value = self.returned(value);
                    if let (Some(value), Some(function)) = (value, &self.function) {
                        let target = function.return_node;
                        self.analysis.add_edge(value, target);
                    }
                }
                self.flow().end_path();
            }
            Stmt::Delete(delete) => {
                for target in &delete.targets {
                    self.delete(target);
                }
            }
            Stmt::Assign(assign) => {
                let mut value = self.expression(&assign.value);
                if self.cannot_bind(&assign.value) {
                    self.flow().end_path();
                    return;
                }
                let facts = self.facts(&assign.value);
                if self.may_alias(&assign.targets) {
                    let alias = self.alias_form(&assign.value);
                    value = self.join(&[value, alias]);
                }
                for target in &assign.targets {
                    let stub = self.stub_variable(target);
                    let declared = self.declared(stub, target);
                    let bound = self.declared_binding(value, declared);
                    self.assign(target, bound, facts.0, facts.1.clone());
                }
            }
            Stmt::AnnAssign(annotated) => self.annotated_assign(annotated),
            Stmt::AugAssign(augmented) => self.augmented_assign(augmented),
            Stmt::TypeAlias(alias) => {
                let value = self.annotation(&alias.value);
                if let Expr::Name(name) = &*alias.name {
                    self.bind(&identifier(name.id.as_str()), value, UNKNOWN, None);
                }
            }
            Stmt::Assert(assertion) => {
                self.condition(&assertion.test);
                let truth = self.truth(&assertion.test);
                if let Some(message) = &assertion.msg
                    && truth & FALSE != 0
                {
                    let base = self.current_flow().state;
                    self.flow().branch(base);
                    self.expression(message);
                    self.flow().state = base;
                }
                if truth & TRUE == 0 {
                    self.flow().end_path();
                }
                self.narrow(&assertion.test, true, None);
            }
            Stmt::Expr(expression) => {
                if !matches!(
                    &*expression.value,
                    Expr::StringLiteral(_)
                        | Expr::BytesLiteral(_)
                        | Expr::NumberLiteral(_)
                        | Expr::BooleanLiteral(_)
                        | Expr::NoneLiteral(_)
                        | Expr::EllipsisLiteral(_)
                ) {
                    self.expression(&expression.value);
                    if self.cannot_bind(&expression.value) {
                        self.flow().end_path();
                    }
                }
            }
            Stmt::If(conditional) => self.conditional(
                &conditional.test,
                &conditional.body,
                &conditional.elif_else_clauses,
            ),
            Stmt::For(looping) => self.for_loop(
                statement,
                looping.is_async,
                &looping.target,
                &looping.iter,
                &looping.body,
                &looping.orelse,
            ),
            Stmt::While(looping) => {
                self.while_loop(statement, &looping.test, &looping.body, &looping.orelse)
            }
            Stmt::Break(_) => {
                let analysis = &mut *self.analysis;
                self.flows
                    .last_mut()
                    .expect("a flow")
                    .1
                    .jump(analysis, true);
            }
            Stmt::Continue(_) => {
                let analysis = &mut *self.analysis;
                self.flows
                    .last_mut()
                    .expect("a flow")
                    .1
                    .jump(analysis, false);
            }
            Stmt::With(with) => self.with(with.is_async, &with.items, &with.body),
            Stmt::Raise(raise) => {
                for expression in [&raise.exc, &raise.cause].into_iter().flatten() {
                    if let Some(value) = self.expression(expression) {
                        let site = self.site(&Node::Expr(expression));
                        let caller = self.caller().to_owned();
                        self.analysis.add_raise(value, &caller, &site);
                    }
                }
                self.flow().end_path();
            }
            Stmt::Try(attempt) => self.attempt(
                &attempt.body,
                &attempt.handlers,
                &attempt.orelse,
                &attempt.finalbody,
                attempt.is_star,
            ),
            Stmt::Import(import) => self.import(&import.names),
            Stmt::Match(matched) => self.match_statement(matched),
            Stmt::ImportFrom(import) => self.import_from(
                import.module.as_ref().map(|name| name.as_str()),
                &import.names,
                import.level,
            ),
            _ => self.walk(&Node::Stmt(statement)),
        }
    }

    fn may_alias(&self, targets: &[Expr]) -> bool {
        matches!(
            self.scopes.scope(self.scope).kind,
            ScopeKind::Module | ScopeKind::Class
        ) && matches!(targets, [Expr::Name(_)])
    }

    pub(crate) fn declared_binding(
        &mut self,
        value: Option<NodeId>,
        declared: Option<NodeId>,
    ) -> Option<NodeId> {
        let joined = self.join(&[value, declared]);
        if declared.is_some()
            && let Some(joined) = joined
        {
            self.assigned_by_declared_binding.insert(joined, value);
        }
        joined
    }

    fn base(&mut self, node: &Expr) -> Option<NodeId> {
        let value = self.expression(node);
        if matches!(node, Expr::Name(_))
            && let Some(value) = value
            && let Some(&assigned) = self.assigned_by_declared_binding.get(&value)
        {
            return assigned;
        }
        value
    }

    fn cannot_bind(&self, node: &Expr) -> bool {
        let Expr::Call(call) = node else {
            return false;
        };
        let Expr::Name(function) = &*call.func else {
            return false;
        };
        if call
            .arguments
            .args
            .iter()
            .any(|arg| matches!(arg, Expr::Starred(_)))
        {
            return false;
        }
        if call
            .arguments
            .keywords
            .iter()
            .any(|keyword| keyword.arg.is_none())
        {
            return false;
        }
        let name = self.mangle(&identifier(function.id.as_str()));
        let scope = self.scopes.resolve(self.scope, &name);
        let Some(key) = self.scopes.definition(scope, &name) else {
            return false;
        };
        let Some(Stmt::FunctionDef(definition)) = self.definitions.get(&key).copied() else {
            return false;
        };
        let definition_scope = self.scopes.scope_of(&Node::Stmt(self.definitions[&key]));
        let parameters = &definition.parameters;
        let signature = signature_of(parameters, |name| {
            self.scopes.scope(definition_scope).mangle(name)
        });
        let positional = parameters.posonlyargs.iter().chain(parameters.args.iter());
        let mut optional: Vec<&str> = positional
            .zip(signature.positional.iter())
            .filter(|(parameter, _)| parameter.default.is_some())
            .map(|(_, name)| &**name)
            .collect();
        optional.extend(
            parameters
                .kwonlyargs
                .iter()
                .zip(signature.keyword_only.iter())
                .filter(|(parameter, _)| parameter.default.is_some())
                .map(|(_, name)| &**name),
        );
        let keywords: Vec<String> = call
            .arguments
            .keywords
            .iter()
            .filter_map(|keyword| keyword.arg.as_ref())
            .map(|arg| identifier(arg.as_str()).into_owned())
            .collect();
        let keywords: Vec<&str> = keywords.iter().map(String::as_str).collect();
        !signature.binds(call.arguments.args.len(), &keywords, &optional)
    }

    fn annotated_assign(&mut self, annotated: &ruff_python_ast::StmtAnnAssign) {
        let target = &*annotated.target;
        let targets = std::slice::from_ref(target);
        let class_level =
            self.may_alias(targets) && self.scopes.scope(self.scope).kind == ScopeKind::Class;
        let mut annotation = None;
        if class_level || annotated.value.is_some() {
            annotation = self.annotation(&annotated.annotation);
        }
        if class_level
            && let Some(annotation) = annotation
            && let Expr::Name(name) = target
        {
            let class = self.classes[&self.scope];
            let field = self.mangle(&identifier(name.id.as_str()));
            self.analysis
                .class_fields(class)
                .annotations
                .get_or_insert_with(IndexMap::new)
                .insert(Box::from(field.as_str()), annotation);
        }
        if let Some(value) = &annotated.value {
            let mut node = self.expression(value);
            if self.cannot_bind(value) {
                self.flow().end_path();
                return;
            }
            let facts = self.facts(value);
            if self.may_alias(targets) {
                let alias = self.alias_form(value);
                node = self.join(&[node, alias]);
            }
            let declared = self.declared(annotation, target);
            let bound = self.declared_binding(node, declared);
            self.assign(target, bound, facts.0, facts.1);
            return;
        }
        match target {
            Expr::Attribute(attribute) => {
                self.expression(&attribute.value);
            }
            Expr::Subscript(_) => {
                self.subscript_parts(target);
            }
            _ => {}
        }
    }

    fn augmented_assign(&mut self, augmented: &ruff_python_ast::StmtAugAssign) {
        let target = &*augmented.target;
        let site = self.site(&Node::Expr(target));
        match target {
            Expr::Name(name) => {
                let name = identifier(name.id.as_str()).into_owned();
                let current = self.load_name(&name);
                let value = self.expression(&augmented.value);
                let result = self.operator(current, value, augmented);
                self.bind(&name, result, UNKNOWN, None);
            }
            Expr::Attribute(attribute) => {
                let base = self.expression(&attribute.value);
                let attr = self.mangle(&identifier(attribute.attr.as_str()));
                let mut current = None;
                if let Some(base) = base {
                    let node = self.analysis.node(None);
                    let caller = self.caller().to_owned();
                    self.analysis.add_load(base, &attr, node, &caller, &site);
                    current = Some(node);
                }
                let value = self.expression(&augmented.value);
                let result = self.operator(current, value, augmented);
                if let Some(base) = base {
                    let caller = self.caller().to_owned();
                    self.analysis.add_store(base, &attr, result, &caller, &site);
                }
            }
            Expr::Subscript(_) => {
                let (base, index) = self.subscript_parts(target);
                let mut current = None;
                if let Some(base) = base {
                    let node = self.analysis.node(None);
                    self.subscript(base, &index, Some(node), None, target, false);
                    current = Some(node);
                }
                let value = self.expression(&augmented.value);
                if let Some(base) = base {
                    let result = self.operator(current, value, augmented);
                    self.subscript(base, &index, None, result, target, false);
                }
            }
            _ => {
                self.expression(target);
                self.expression(&augmented.value);
            }
        }
    }

    fn returned(&mut self, value: &Expr) -> Option<NodeId> {
        if matches!(value, Expr::If(_) | Expr::BoolOp(_)) {
            return self.choice(value, |builder, arm| builder.returned(arm));
        }
        if self.returns_parameter(value) {
            return None;
        }
        self.expression(value)
    }

    pub(crate) fn returns_parameter(&mut self, value: &Expr) -> bool {
        let Some(function) = &self.function else {
            return false;
        };
        if function.yield_node.is_some() {
            return false;
        }
        let object = function.object;
        if self.analysis.function_fields(object).is_async {
            return false;
        }
        let function = self.function.as_ref().expect("a function");
        let signature = &function.signature;
        let (name, returned) = if let Some((base, index)) = element_index(value) {
            let name = self.mangle(&base);
            if signature.vararg.as_deref() != Some(name.as_str()) {
                return false;
            }
            let returned = Passthrough::Element(Box::from(name.as_str()), index);
            (name, returned)
        } else if let Expr::Name(found) = value {
            let name = self.mangle(&identifier(found.id.as_str()));
            let declared = signature
                .positional
                .iter()
                .chain(signature.keyword_only.iter());
            if !declared.into_iter().any(|parameter| **parameter == *name) {
                return false;
            }
            let returned = Passthrough::Name(Box::from(name.as_str()));
            (name, returned)
        } else {
            return false;
        };
        let parameter = function.parameters.get(name.as_str()).copied();
        if self.scopes.tracked(self.scope, &name) {
            let flow = self.current_flow();
            let definition = flow.definition_of(flow.get(&name));
            if definition.node != parameter || definition.unbound {
                return false;
            }
        } else if self.scopes.scope(self.scope).rebound.contains(&name) {
            return false;
        }
        let passthrough = &mut self.analysis.function_fields(object).passthrough;
        if !passthrough.contains(&returned) {
            passthrough.push(returned);
        }
        true
    }

    fn decorate(
        &mut self,
        decorators: &[(Option<NodeId>, &Expr)],
        object: ObjId,
    ) -> Option<NodeId> {
        let mut value = Some(self.analysis.constant(object));
        for &(decorator, expression) in decorators.iter().rev() {
            let Some(decorator) = decorator else {
                value = None;
                continue;
            };
            let result = self.analysis.node(None);
            let site = self.site(&Node::Expr(expression));
            let caller = self.caller().to_owned();
            self.analysis.add_call(&Call {
                callee: Some(decorator),
                caller: &caller,
                args: &[value],
                keywords: &[],
                dst: Some(result),
                site: &site,
                star: &[],
                double_star: &[],
                decorator: true,
                applies: false,
            });
            value = Some(result);
        }
        value
    }

    fn function_definition(&mut self, statement: &Stmt, function: &StmtFunctionDef) {
        let scope = self.scopes.scope_of(&Node::Stmt(statement));
        let decorators: Vec<(Option<NodeId>, &Expr)> = function
            .decorator_list
            .iter()
            .map(|decorator| {
                (
                    self.expression(&decorator.expression),
                    &decorator.expression,
                )
            })
            .collect();
        let name = identifier(function.name.as_str()).into_owned();
        let made = self.function_object(
            &Node::Stmt(statement),
            &function.parameters,
            scope,
            &name,
            function.is_async,
        );
        let decorated = function.decorator_list.iter().any(|decorator| {
            !(names(&decorator.expression, "staticmethod")
                || names(&decorator.expression, "classmethod"))
        });
        self.analysis.function_fields(made.object).decorated = decorated;
        if self.scopes.scope(self.scope).kind == ScopeKind::Class {
            let mut kind = ["staticmethod", "classmethod"]
                .into_iter()
                .find(|kind| {
                    function
                        .decorator_list
                        .iter()
                        .any(|decorator| names(&decorator.expression, kind))
                })
                .map(|kind| {
                    if kind == "staticmethod" {
                        MethodKind::StaticMethod
                    } else {
                        MethodKind::ClassMethod
                    }
                });
            if implicit_method(&name).is_some() {
                kind = Some(MethodKind::ClassMethod);
            }
            let class = self.classes[&self.scope];
            let method = self.mangle(&name);
            self.analysis.add_method(class, &method, made.object, kind);
        }
        let truth = if function.decorator_list.is_empty() {
            TRUE
        } else {
            UNKNOWN
        };
        let value = self.decorate(&decorators, made.object);
        self.bind(&name, value, truth, None);
        self.inside(scope, Some(made), |builder| {
            builder.statements(&function.body)
        });
    }

    pub(crate) fn function_object(
        &mut self,
        node: &Node<'_>,
        parameters: &Parameters,
        scope: ScopeId,
        name: &str,
        is_async: bool,
    ) -> MadeFunction {
        let scopes = self.scopes;
        let signature = signature_of(parameters, |name| scopes.scope(scope).mangle(name));
        let mut defaults: Vec<(Box<str>, Option<NodeId>)> = Vec::new();
        let positional = parameters.posonlyargs.iter().chain(parameters.args.iter());
        for (parameter, signature_name) in positional.zip(signature.positional.iter()) {
            if let Some(default) = &parameter.default {
                let value = self.expression(default);
                defaults.push((signature_name.clone(), value));
            }
        }
        for (parameter, signature_name) in parameters
            .kwonlyargs
            .iter()
            .zip(signature.keyword_only.iter())
        {
            if let Some(default) = &parameter.default {
                let value = self.expression(default);
                defaults.push((signature_name.clone(), value));
            }
        }
        let scope_name = self.scopes.scope(scope).name.clone();
        let generator = self.scopes.scope(scope).generator;
        let module_name = self.module_name.clone();
        let made =
            self.analysis
                .function(&scope_name, &module_name, &signature, &defaults, generator);
        let at = self.position(node);
        {
            let fields = self.analysis.function_fields(made.object);
            fields.lineno = Some(u32::try_from(at.lineno).expect("a line fits u32"));
            fields.end_lineno = Some(u32::try_from(at.end_lineno).expect("a line fits u32"));
            fields.col_offset = Some(u32::try_from(at.col_offset).expect("a column fits u32"));
            fields.end_col_offset =
                Some(u32::try_from(at.end_col_offset).expect("a column fits u32"));
        }
        let name_field = self.analysis.field(made.object, "__name__");
        let value = self
            .analysis
            .const_object(&Constant::Str(name.chars().map(u32::from).collect()));
        self.analysis.add_object(name_field, value);
        self.analysis.function_fields(made.object).is_async = is_async;
        self.parameter_annotations(made.object, parameters, scope);
        let entries: Vec<(Box<str>, NodeId)> = made
            .parameters
            .iter()
            .map(|(name, &node)| (name.clone(), node))
            .collect();
        for (parameter_name, parameter) in entries {
            let mut variable = parameter;
            let rebound = self.scopes.scope(scope).rebound.contains(&*parameter_name);
            if rebound && self.scopes.tracked(scope, &parameter_name) {
                let label = self.analysis.node_label(parameter).map(str::to_owned);
                variable = self.analysis.node(label.as_deref());
                self.analysis.add_edge(parameter, variable);
            }
            self.variables
                .insert((scope, parameter_name.into_string()), variable);
        }
        made
    }

    fn class_definition(&mut self, statement: &Stmt, class: &StmtClassDef) {
        let scope = self.scopes.scope_of(&Node::Stmt(statement));
        let decorators: Vec<(Option<NodeId>, &Expr)> = class
            .decorator_list
            .iter()
            .map(|decorator| {
                (
                    self.expression(&decorator.expression),
                    &decorator.expression,
                )
            })
            .collect();
        let empty = Vec::new();
        let (bases_expressions, keywords_nodes) = match &class.arguments {
            Some(arguments) => (
                arguments.args.iter().collect::<Vec<_>>(),
                arguments.keywords.iter().collect::<Vec<_>>(),
            ),
            None => (empty.iter().collect(), Vec::new()),
        };
        let bases: Vec<Option<NodeId>> = bases_expressions
            .iter()
            .map(|base| self.base(base))
            .collect();
        let mut keywords: Vec<(Box<str>, Option<NodeId>)> = Vec::new();
        let mut double_star: Vec<Option<NodeId>> = Vec::new();
        let mut metaclass = None;
        for keyword in keywords_nodes {
            let value = self.expression(&keyword.value);
            match &keyword.arg {
                None => double_star.push(value),
                Some(arg) if identifier(arg.as_str()) == "metaclass" => metaclass = value,
                Some(arg) => keywords.push((Box::from(&*identifier(arg.as_str())), value)),
            }
        }
        let scope_name = self.scopes.scope(scope).name.clone();
        let defined: Vec<Box<str>> = self
            .scopes
            .scope(scope)
            .defined
            .iter()
            .map(|name| Box::from(name.as_str()))
            .collect();
        let dynamic = self.scopes.scope(scope).dynamic;
        let finals: IndexMap<String, &Stmt> = if dynamic {
            IndexMap::new()
        } else {
            bindings::final_bindings(&class.body)
                .into_iter()
                .map(|(name, statement)| (self.scopes.scope(scope).mangle(&name), statement))
                .collect()
        };
        let abstract_methods = bindings::abstract_methods(&finals);
        let module_name = self.module_name.clone();
        let protocol = bases_expressions.iter().any(|base| names(base, "Protocol"));
        let object = self.analysis.new_class(&NewClass {
            name: &scope_name,
            module: &module_name,
            defines: &defined,
            base_nodes: &bases,
            protocol,
            abstract_methods: &abstract_methods,
            metaclass,
            uses_namespace: dynamic,
        });
        let at = self.position(&Node::Stmt(statement));
        {
            let fields = self.analysis.class_fields(object);
            fields.lineno = Some(u32::try_from(at.lineno).expect("a line fits u32"));
            fields.end_lineno = Some(u32::try_from(at.end_lineno).expect("a line fits u32"));
        }
        let allocator = self.allocator(finals.get("__new__").copied(), statement);
        self.analysis.class_fields(object).allocator = allocator;
        self.classes.insert(scope, object);
        self.defined_class(scope, object);
        let site = self.site(&Node::Stmt(statement));
        let namespace = self.inside(scope, None, |builder| {
            builder.statements(&class.body);
            let members = builder.bound_at_end(scope);
            let mut namespace: Vec<(Box<str>, NodeId)> = Vec::new();
            for (name, value) in &members {
                let Some(value) = *value else {
                    continue;
                };
                namespace.push((Box::from(name.as_str()), value));
                let field = builder.analysis.field(object, name);
                match implicit_method(name) {
                    Some(kind) => builder
                        .analysis
                        .add_implicit_method(value, field, kind, &site),
                    None => builder.analysis.add_class_member(value, field),
                }
                let caller = builder.caller().to_owned();
                builder
                    .analysis
                    .add_set_name(value, object, name, &caller, &site);
            }
            let slots: Vec<Box<str>> = if members.contains_key("__slots__") {
                bindings::slots(&finals, builder.source.text)
                    .iter()
                    .map(|name| Box::from(builder.mangle(name).as_str()))
                    .collect()
            } else {
                Vec::new()
            };
            let fields = builder.analysis.class_fields(object);
            fields.bound = namespace.iter().map(|(name, _)| name.clone()).collect();
            fields.defines = members
                .keys()
                .map(|name| Box::from(name.as_str()))
                .chain(slots.iter().cloned())
                .collect();
            fields.slots = slots;
            let structure: Vec<(Box<str>, Option<NodeId>)> =
                bindings::structure_fields(&finals, builder.source.text)
                    .into_iter()
                    .map(|(name, kind)| (Box::from(name.as_str()), builder.annotation(kind)))
                    .collect();
            (namespace, structure)
        });
        let (namespace, structure) = namespace;
        let caller = self.caller().to_owned();
        self.analysis
            .add_init_subclass(object, &keywords, &double_star, &caller, &site);
        let name = identifier(class.name.as_str()).into_owned();
        self.analysis.add_metaclass_call(
            object,
            &ClassStatement {
                name: &name,
                bases: &bases,
                namespace: &namespace,
                keywords: &keywords,
                double_star: &double_star,
            },
            &caller,
            &site,
        );
        let bases_seen: Vec<NodeId> = bases.iter().flatten().copied().collect();
        if !structure.is_empty() {
            self.analysis
                .add_structure_class(object, &structure, &bases_seen);
        }
        if self.analysis.class_fields(object).annotations.is_some() {
            let decorators_seen: Vec<NodeId> =
                decorators.iter().filter_map(|(node, _)| *node).collect();
            self.analysis
                .add_annotated_class(object, &decorators_seen, &bases_seen);
        }
        let plain = class.decorator_list.is_empty() && class.arguments.is_none();
        let truth = if plain { TRUE } else { UNKNOWN };
        let value = self.decorate(&decorators, object);
        self.bind(&name, value, truth, None);
    }

    fn is_builtin_in(&self, scope: ScopeId, node: &Expr, name: &str) -> bool {
        let Expr::Name(found) = node else {
            return false;
        };
        if identifier(found.id.as_str()) != name {
            return false;
        }
        self.is_builtin(self.scopes.resolve(scope, name), name)
    }

    pub(crate) fn is_builtin_reference(&self, node: &Expr, name: &str) -> bool {
        self.is_builtin_in(self.scope, node, name)
    }

    fn allocator(&self, statement: Option<&Stmt>, class_node: &Stmt) -> Option<Allocator> {
        let statement = statement?;
        let Stmt::FunctionDef(function) = statement else {
            return None;
        };
        if function.is_async {
            return None;
        }
        let class_scope = self.scopes.scope_of(&Node::Stmt(class_node));
        let static_only = function.decorator_list.iter().all(|decorator| {
            self.is_builtin_in(class_scope, &decorator.expression, "staticmethod")
        });
        if !static_only {
            return None;
        }
        let parameters = &function.parameters;
        let first = parameters
            .posonlyargs
            .iter()
            .chain(parameters.args.iter())
            .next();
        let scope = self.scopes.scope_of(&Node::Stmt(statement));
        let found = self.scopes.scope(scope);
        let first = first?;
        if found.generator {
            return None;
        }
        let class_name = identifier(first.parameter.name.as_str()).into_owned();
        if found.rebound.contains(&class_name) || found.shared.contains(&class_name) {
            return None;
        }
        let writes_class = bindings::walk_all(&Node::Stmt(statement))
            .iter()
            .any(|node| {
                matches!(node, Node::Expr(Expr::Attribute(attribute))
                if attribute.attr.as_str() == "__class__"
                    && matches!(attribute.ctx, ExprContext::Store | ExprContext::Del))
            });
        if writes_class {
            return None;
        }
        let mut stores: IndexMap<String, usize> = IndexMap::new();
        for line in &function.body {
            let node = Node::Stmt(line);
            let names = bindings::bound_names(&node)
                .into_iter()
                .chain(bindings::walrus_names(&node));
            for name in names {
                *stores.entry(name).or_insert(0) += 1;
            }
        }
        let mut returns: Vec<&Expr> = Vec::new();
        let mut assigned: IndexMap<String, Vec<&Expr>> = IndexMap::new();
        for node in bindings::own_statements(&function.body) {
            match node {
                Node::Stmt(Stmt::Return(returned)) => {
                    if let Some(value) = &returned.value {
                        returns.push(value);
                    }
                }
                Node::Stmt(Stmt::Assign(assign)) => {
                    if let [Expr::Name(target)] = assign.targets.as_slice() {
                        let name = identifier(target.id.as_str()).into_owned();
                        assigned.entry(name).or_default().push(&assign.value);
                    }
                }
                _ => {}
            }
        }
        let mut kinds: Vec<Allocator> = Vec::new();
        for value in returns {
            let mut values = vec![value];
            if let Expr::Name(returned) = value {
                let name = identifier(returned.id.as_str()).into_owned();
                values = assigned.get(&name).cloned().unwrap_or_default();
                let local = self.scopes.resolve(scope, &name) == scope;
                if !local || found.shared.contains(&name) {
                    return None;
                }
                let stored = stores.get(&name).copied().unwrap_or(0);
                if values.is_empty() || values.len() != stored {
                    return None;
                }
            }
            for value in values {
                let kind = self.allocation(value, &class_name, scope, class_node)?;
                if !kinds.contains(&kind) {
                    kinds.push(kind);
                }
            }
        }
        match kinds.as_slice() {
            [kind] => Some(*kind),
            _ => None,
        }
    }

    fn allocation(
        &self,
        value: &Expr,
        class_name: &str,
        scope: ScopeId,
        class_node: &Stmt,
    ) -> Option<Allocator> {
        let Expr::Call(call) = value else {
            return None;
        };
        let Expr::Attribute(attribute) = &*call.func else {
            return None;
        };
        if attribute.attr.as_str() != "__new__" {
            return None;
        }
        let Some(Expr::Name(first)) = call.arguments.args.first() else {
            return None;
        };
        if identifier(first.id.as_str()) != class_name {
            return None;
        }
        let owner = &*attribute.value;
        if self.is_builtin_in(scope, owner, "object") {
            return Some(Allocator::Object);
        }
        let Expr::Call(super_call) = owner else {
            return None;
        };
        if !super_call.arguments.keywords.is_empty()
            || !self.is_builtin_in(scope, &super_call.func, "super")
        {
            return None;
        }
        let class_scope = self.scopes.scope_of(&Node::Stmt(class_node));
        match super_call.arguments.args.as_slice() {
            [] => {
                (self.scopes.resolve(scope, "__class__") == class_scope).then_some(Allocator::Super)
            }
            [Expr::Name(start), Expr::Name(second)]
                if identifier(second.id.as_str()) == class_name =>
            {
                let start = self
                    .scopes
                    .scope(scope)
                    .mangle(&identifier(start.id.as_str()));
                let binder = self.scopes.resolve(scope, &start);
                let defined = self.scopes.definition(binder, &start);
                let class_key = pycg_syntax::scopes::node_key(&Node::Stmt(class_node));
                (defined == Some(class_key)).then_some(Allocator::Super)
            }
            _ => None,
        }
    }

    fn delete(&mut self, target: &Expr) {
        match target {
            Expr::Name(name) => self.unbind(&identifier(name.id.as_str())),
            Expr::Attribute(attribute) => {
                if let Some(base) = self.expression(&attribute.value) {
                    let attr = self.mangle(&identifier(attribute.attr.as_str()));
                    let site = self.site(&Node::Expr(target));
                    let caller = self.caller().to_owned();
                    self.analysis.add_delete(base, &attr, &caller, &site);
                }
            }
            Expr::Subscript(_) => {
                let (base, index) = self.subscript_parts(target);
                if let Some(base) = base {
                    self.subscript(base, &index, None, None, target, true);
                }
            }
            Expr::Tuple(tuple) => {
                for element in &tuple.elts {
                    self.delete(element);
                }
            }
            Expr::List(list) => {
                for element in &list.elts {
                    self.delete(element);
                }
            }
            _ => {
                self.expression(target);
            }
        }
    }

    fn conditional(&mut self, test: &Expr, body: &[Stmt], clauses: &[ElifElseClause]) {
        let base = self.current_flow().state;
        let mut ends: Vec<StateId> = Vec::new();
        let mut branch: (Option<&Expr>, &[Stmt], &[ElifElseClause]) = (Some(test), body, clauses);
        while self.current_flow().is_reachable() {
            let (Some(test), body, clauses) = branch else {
                break;
            };
            self.condition(test);
            let truth = self.truth(test);
            match self.type_checking_truth(&Node::Expr(test)) {
                Some(true) => self.record_type_only(body, &[]),
                Some(false) => self.record_type_only(&[], clauses),
                None => {}
            }
            let tested = self.current_flow().state;
            self.branch_reachable(tested, truth & TRUE != 0);
            self.narrow(test, true, None);
            self.statements(body);
            ends.push(self.current_flow().state);
            self.branch_reachable(tested, truth & FALSE != 0);
            self.narrow(test, false, None);
            match clauses.split_first() {
                Some((clause, rest)) if clause.test.is_some() => {
                    branch = (clause.test.as_ref(), &clause.body, rest);
                }
                Some((clause, _)) => match clause.body.as_slice() {
                    [Stmt::If(nested)] => {
                        branch = (Some(&nested.test), &nested.body, &nested.elif_else_clauses);
                    }
                    orelse => {
                        self.statements(orelse);
                        break;
                    }
                },
                None => break,
            }
        }
        ends.push(self.current_flow().state);
        let analysis = &mut *self.analysis;
        self.flows
            .last_mut()
            .expect("a flow")
            .1
            .merge(analysis, base, &ends, None);
    }

    fn branch_reachable(&mut self, tested: StateId, taken: bool) {
        let flow = self.flow();
        let reachable = flow.reachable(tested) && taken;
        let state = flow.branch(tested);
        flow.set_reachable(state, reachable);
    }

    fn loop_names(&self, statement: &Stmt) -> IndexMap<String, bool> {
        self.scopes
            .loop_bindings(&Node::Stmt(statement))
            .iter()
            .filter(|(name, _)| self.scopes.tracked(self.scope, name))
            .map(|(name, &unbinds)| (name.clone(), unbinds))
            .collect()
    }

    fn for_loop(
        &mut self,
        statement: &Stmt,
        is_async: bool,
        target: &Expr,
        iterable: &Expr,
        body: &[Stmt],
        orelse: &[Stmt],
    ) {
        let elements = self.elements_of(iterable, is_async);
        let names = self.loop_names(statement);
        let analysis = &mut *self.analysis;
        let flow = &mut self.flows.last_mut().expect("a flow").1;
        flow.start_loop(analysis, &names);
        let entry = flow.state;
        flow.branch(entry);
        self.assign(target, elements, UNKNOWN, None);
        self.statements(body);
        let analysis = &mut *self.analysis;
        let flow = &mut self.flows.last_mut().expect("a flow").1;
        flow.next_iteration(analysis, None);
        let breaks = flow.stop_loop();
        self.loop_exit(orelse, entry, entry, breaks);
    }

    fn while_loop(&mut self, statement: &Stmt, test: &Expr, body: &[Stmt], orelse: &[Stmt]) {
        let names = self.loop_names(statement);
        let analysis = &mut *self.analysis;
        self.flows
            .last_mut()
            .expect("a flow")
            .1
            .start_loop(analysis, &names);
        self.condition(test);
        let truth = self.truth(test);
        let tested = self.current_flow().state;
        self.branch_reachable(tested, truth & TRUE != 0);
        self.narrow(test, true, None);
        self.statements(body);
        let analysis = &mut *self.analysis;
        let flow = &mut self.flows.last_mut().expect("a flow").1;
        flow.next_iteration(analysis, None);
        let breaks = flow.stop_loop();
        let exit = flow.new_child(tested);
        let reachable = flow.reachable(tested) && truth & FALSE != 0;
        flow.set_reachable(exit, reachable);
        self.narrow(test, false, Some(exit));
        self.loop_exit(orelse, tested, exit, breaks);
    }

    fn loop_exit(&mut self, orelse: &[Stmt], start: StateId, exit: StateId, breaks: Vec<StateId>) {
        self.flow().branch(exit);
        self.statements(orelse);
        let mut ends = vec![self.current_flow().state];
        ends.extend(breaks);
        let analysis = &mut *self.analysis;
        self.flows
            .last_mut()
            .expect("a flow")
            .1
            .merge(analysis, start, &ends, None);
    }

    fn with(&mut self, is_async: bool, items: &[ruff_python_ast::WithItem], body: &[Stmt]) {
        let base = self.current_flow().state;
        let record = self.flow().record();
        self.flow().branch(base);
        for item in items {
            let manager = self.expression(&item.context_expr);
            let mut target = None;
            if let Some(manager) = manager {
                if item.optional_vars.is_some() {
                    target = Some(self.analysis.node(None));
                }
                let site = self.site(&Node::Expr(&item.context_expr));
                let caller = self.caller().to_owned();
                self.analysis
                    .add_with(manager, target, &caller, &site, is_async);
            }
            if let Some(variables) = &item.optional_vars {
                self.assign(variables, target, UNKNOWN, None);
            }
        }
        self.statements(body);
        let recorder = self.flow().stop(record);
        let analysis = &mut *self.analysis;
        let flow = &mut self.flows.last_mut().expect("a flow").1;
        let end = flow.state;
        let anywhere = flow.anywhere(analysis, base, &recorder);
        flow.merge(analysis, base, &[end, anywhere], None);
    }

    fn attempt(
        &mut self,
        body: &[Stmt],
        handlers: &[ExceptHandler],
        orelse: &[Stmt],
        finalbody: &[Stmt],
        grouped: bool,
    ) {
        let base = self.current_flow().state;
        let mut everything = None;
        if !finalbody.is_empty() {
            everything = Some(self.flow().record());
            self.flow().start_finally();
        }
        let in_body = self.flow().record();
        self.flow().branch(base);
        self.statements(body);
        let body_end = self.current_flow().state;
        let in_body = self.flow().stop(in_body);
        let mut ends = Vec::new();
        let mut raising = None;
        if !handlers.is_empty() {
            let analysis = &mut *self.analysis;
            raising = Some(
                self.flows
                    .last_mut()
                    .expect("a flow")
                    .1
                    .anywhere(analysis, base, &in_body),
            );
        }
        for handler in handlers {
            let ExceptHandler::ExceptHandler(handler) = handler;
            let raised = raising.expect("handlers have a raising state");
            self.flow().branch(raised);
            let types = handler
                .type_
                .as_ref()
                .and_then(|types| self.expression(types));
            if let Some(name) = &handler.name {
                let caught = self.analysis.node(None);
                if let Some(types) = types {
                    self.analysis.add_handler(Some(types), caught);
                }
                self.bind(&identifier(name.as_str()), Some(caught), UNKNOWN, None);
            }
            self.statements(&handler.body);
            if let Some(name) = &handler.name {
                self.unbind(&identifier(name.as_str()));
            }
            if grouped {
                let analysis = &mut *self.analysis;
                let flow = &mut self.flows.last_mut().expect("a flow").1;
                let end = flow.state;
                let reachable = flow.reachable(raised);
                flow.set_reachable(end, reachable);
                let after = flow.new_child(raised);
                let empty = flow.new_child(raised);
                flow.merge(analysis, raised, &[empty, end], Some(after));
                raising = Some(after);
            } else {
                ends.push(self.current_flow().state);
            }
        }
        if grouped && !handlers.is_empty() {
            ends.push(raising.expect("a raising state"));
        }
        self.flow().branch(body_end);
        self.statements(orelse);
        ends.push(self.current_flow().state);
        let Some(everything) = everything else {
            let analysis = &mut *self.analysis;
            self.flows
                .last_mut()
                .expect("a flow")
                .1
                .merge(analysis, base, &ends, None);
            return;
        };
        let everything = self.flow().stop(everything);
        let jumps = self.flow().run_finally();
        let analysis = &mut *self.analysis;
        let start = self
            .flows
            .last_mut()
            .expect("a flow")
            .1
            .anywhere(analysis, base, &everything);
        self.flow().branch(start);
        self.statements(finalbody);
        let analysis = &mut *self.analysis;
        let flow = &mut self.flows.last_mut().expect("a flow").1;
        let finished = flow.state;
        let bound = flow.changed_between(finished, start);
        flow.end_finally(analysis, jumps, start);
        flow.merge(analysis, base, &ends, None);
        for name in bound {
            let definition = flow.get_in(finished, &name);
            flow.set_change(base, &name, definition);
        }
        let reachable = flow.reachable(base) && flow.reachable(finished);
        flow.set_reachable(base, reachable);
    }

    fn import(&mut self, aliases: &[Alias]) {
        for alias in aliases {
            let original = identifier(alias.name.as_str()).into_owned();
            if original == "importlib" {
                let bound = alias.asname.as_ref().map_or_else(
                    || original.clone(),
                    |asname| identifier(asname.as_str()).into_owned(),
                );
                self.names_bound_to_importlib.insert(bound);
            }
            let name = self.mangle(&original);
            let record = !self.scopes.is_unread_lazy(alias);
            let imported = self.analysis.handle_import(&name, 0, record);
            if imported.is_none() {
                self.analysis.add_external_module(&name);
            }
            if let Some(asname) = &alias.asname {
                let value = self.imported_module(&name, imported.as_deref());
                self.bind(&identifier(asname.as_str()), Some(value), UNKNOWN, None);
                continue;
            }
            let top = name
                .split('.')
                .next()
                .expect("a split gives a first part")
                .to_owned();
            let top_object = match imported {
                None => self.analysis.external(&top, 0, false),
                Some(_) => self.analysis.module(&top),
            };
            let value = self.analysis.constant(top_object);
            let bound = original
                .split('.')
                .next()
                .expect("a split gives a first part")
                .to_owned();
            self.bind(&bound, Some(value), UNKNOWN, None);
        }
    }

    fn module_import(&self, name: &str, imported_names: &FxHashSet<String>) -> bool {
        let scope = self.scopes.resolve(self.scope, &self.mangle(name));
        self.scopes.scope(scope).kind == ScopeKind::Module && imported_names.contains(name)
    }

    pub(crate) fn literal_import(&mut self, call: &ruff_python_ast::ExprCall) -> Option<NodeId> {
        let mut top = false;
        let named = match &*call.func {
            Expr::Name(function) => {
                self.module_import(&identifier(function.id.as_str()), &self.import_module_names)
            }
            _ => false,
        };
        let through_importlib = match &*call.func {
            Expr::Attribute(attribute) => {
                attribute.attr.as_str() == "import_module"
                    && matches!(&*attribute.value, Expr::Name(owner)
                        if self.module_import(&identifier(owner.id.as_str()), &self.names_bound_to_importlib))
            }
            _ => false,
        };
        if !named && !through_importlib {
            if !self.is_builtin_reference(&call.func, "__import__") {
                return None;
            }
            let mut fromlist = call.arguments.args.get(3);
            for keyword in &call.arguments.keywords {
                if keyword
                    .arg
                    .as_ref()
                    .is_some_and(|arg| arg.as_str() == "fromlist")
                {
                    fromlist = Some(&keyword.value);
                }
            }
            let listed = match fromlist {
                Some(Expr::List(list)) => !list.elts.is_empty(),
                Some(Expr::Tuple(tuple)) => !tuple.elts.is_empty(),
                Some(Expr::Set(set)) => !set.elts.is_empty(),
                _ => false,
            };
            top = !listed;
        }
        let first = call.arguments.args.first()?;
        let Some(pycg_syntax::constants::Constant::Str(text)) =
            pycg_syntax::constants::literal(first, self.source.text)
        else {
            return None;
        };
        let name: String = text
            .code_points()
            .iter()
            .map(|&point| char::from_u32(point))
            .collect::<Option<String>>()?;
        if !is_dotted_identifier(&name) {
            return None;
        }
        let imported = self.analysis.handle_import(&name, 0, true);
        if imported.is_none() {
            self.analysis.add_external_module(&name);
        }
        if !top {
            return Some(self.imported_module(&name, imported.as_deref()));
        }
        let package = name
            .split('.')
            .next()
            .expect("a split gives a first part")
            .to_owned();
        let object = match imported {
            None => self.analysis.external(&package, 0, false),
            Some(_) => self.analysis.module(&package),
        };
        Some(self.analysis.constant(object))
    }

    fn imported_module(&mut self, name: &str, imported: Option<&str>) -> NodeId {
        match imported {
            Some(found) if found == name => {
                let module = self.analysis.module(name);
                self.analysis.constant(module)
            }
            Some(found) => {
                let module = self.analysis.module(found);
                let last = name.rsplit('.').next().expect("a split gives a first part");
                self.analysis.field(module, last)
            }
            None => {
                let external = self.analysis.external(name, 0, false);
                self.analysis.constant(external)
            }
        }
    }

    fn import_from(&mut self, module: Option<&str>, aliases: &[Alias], level: u32) {
        let source = module.map(|module| self.mangle(&identifier(module)));
        let holder = self.absolute_module_name(source.as_deref(), level);
        for alias in aliases {
            let alias_name = identifier(alias.name.as_str()).into_owned();
            if holder.as_deref() == Some("importlib") && alias_name == "import_module" {
                let bound = alias.asname.as_ref().map_or_else(
                    || alias_name.clone(),
                    |asname| identifier(asname.as_str()).into_owned(),
                );
                self.import_module_names.insert(bound);
            }
            if alias_name == "*" {
                let name = source
                    .as_ref()
                    .map_or_else(|| "*".to_owned(), |source| format!("{source}.*"));
                let imported = self.analysis.handle_import(&name, level, true);
                match (imported, &holder) {
                    (Some(imported), _) => self.star_imported_modules.push(imported),
                    (None, Some(holder)) => {
                        self.outside_star_imported_modules.push(holder.clone());
                        self.analysis.add_external_module(holder);
                    }
                    (None, None) => {}
                }
                continue;
            }
            let member = self.mangle(&alias_name);
            let name = source.as_ref().map_or_else(
                || alias_name.clone(),
                |source| format!("{source}.{alias_name}"),
            );
            let record = !self.scopes.is_unread_lazy(alias);
            let imported = self.analysis.handle_import(&name, level, record);
            let value = match (&imported, &holder) {
                (Some(_), Some(holder)) => {
                    let module = self.analysis.module(holder);
                    let module = self.analysis.constant(module);
                    let value = self.analysis.node(None);
                    let site = self.site(&Node::Alias(alias));
                    let caller = self.caller().to_owned();
                    self.analysis
                        .add_load(module, &member, value, &caller, &site);
                    value
                }
                _ => {
                    let prefix = holder.as_ref().or(source.as_ref());
                    let external = prefix
                        .map_or_else(|| member.clone(), |prefix| format!("{prefix}.{member}"));
                    let value = self.analysis.imported_value(&external);
                    if let Some(holder) = &holder {
                        self.analysis.add_external_module(holder);
                    }
                    value
                }
            };
            let mut truth: Truth = UNKNOWN;
            if imported.is_none()
                && holder
                    .as_deref()
                    .is_some_and(|holder| TYPING_MODULES.contains(&holder))
                && member == "TYPE_CHECKING"
            {
                truth = FALSE;
            }
            let bound = alias.asname.as_ref().map_or(alias_name, |asname| {
                identifier(asname.as_str()).into_owned()
            });
            self.bind(&bound, Some(value), truth, None);
        }
    }

    pub(crate) fn absolute_module_name(&self, module: Option<&str>, level: u32) -> Option<String> {
        if level == 0 {
            return module.map(str::to_owned);
        }
        let package = if self.is_package {
            self.module_name.as_str()
        } else {
            self.module_name
                .rsplit_once('.')
                .map_or("", |(package, _)| package)
        };
        if package.is_empty() {
            return None;
        }
        let parts: Vec<&str> = package.rsplitn(level as usize, '.').collect();
        if parts.len() < level as usize {
            return None;
        }
        let base = parts.last().expect("a package part");
        Some(match module {
            Some(module) if !module.is_empty() => format!("{base}.{module}"),
            _ => (*base).to_owned(),
        })
    }

    pub(crate) fn assign(
        &mut self,
        target: &Expr,
        value: Option<NodeId>,
        truth: Truth,
        values: Option<Literals>,
    ) {
        let value = match (value, target) {
            (None, Expr::Attribute(_) | Expr::Subscript(_)) => Some(self.analysis.node(None)),
            _ => value,
        };
        match target {
            Expr::Name(name) => self.bind(&identifier(name.id.as_str()), value, truth, values),
            Expr::Attribute(attribute) => {
                if let Some(base) = self.expression(&attribute.value) {
                    let attr = self.mangle(&identifier(attribute.attr.as_str()));
                    let site = self.site(&Node::Expr(target));
                    let caller = self.caller().to_owned();
                    self.analysis.add_store(base, &attr, value, &caller, &site);
                }
            }
            Expr::Subscript(_) => {
                let (base, index) = self.subscript_parts(target);
                if let Some(base) = base {
                    self.subscript(base, &index, None, value, target, false);
                }
            }
            Expr::Tuple(tuple) => self.unpack(target, &tuple.elts, value),
            Expr::List(list) => self.unpack(target, &list.elts, value),
            _ => {
                self.expression(target);
            }
        }
    }

    fn unpack(&mut self, target: &Expr, elements: &[Expr], value: Option<NodeId>) {
        let star = elements
            .iter()
            .position(|element| matches!(element, Expr::Starred(_)));
        let (before, starred, after): (&[Expr], Option<&Expr>, &[Expr]) = match star {
            None => (elements, None, &[]),
            Some(index) => {
                let Expr::Starred(starred) = &elements[index] else {
                    unreachable!("the starred element");
                };
                (
                    &elements[..index],
                    Some(&*starred.value),
                    &elements[index + 1..],
                )
            }
        };
        let Some(value) = value else {
            for element in before.iter().chain(starred).chain(after.iter()) {
                self.assign(element, None, UNKNOWN, None);
            }
            return;
        };
        let before_nodes: Vec<NodeId> = before.iter().map(|_| self.analysis.node(None)).collect();
        let after_nodes: Vec<NodeId> = after.iter().map(|_| self.analysis.node(None)).collect();
        let starred_node = starred.map(|_| self.analysis.node(None));
        let site = self.site(&Node::Expr(target));
        let caller = self.caller().to_owned();
        self.analysis.add_unpack(
            value,
            &before_nodes,
            starred_node,
            &after_nodes,
            &caller,
            &site,
        );
        for (element, node) in before.iter().zip(before_nodes) {
            self.assign(element, Some(node), UNKNOWN, None);
        }
        if let (Some(starred), Some(node)) = (starred, starred_node) {
            self.assign(starred, Some(node), UNKNOWN, None);
        }
        for (element, node) in after.iter().zip(after_nodes) {
            self.assign(element, Some(node), UNKNOWN, None);
        }
    }
}

pub fn is_dotted_identifier(name: &str) -> bool {
    name.split('.').all(pycg_syntax::names::is_identifier)
}

fn element_index(expression: &Expr) -> Option<(String, i64)> {
    let Expr::Subscript(subscript) = expression else {
        return None;
    };
    let Expr::Name(base) = &*subscript.value else {
        return None;
    };
    let Expr::NumberLiteral(number) = &*subscript.slice else {
        return None;
    };
    let ruff_python_ast::Number::Int(index) = &number.value else {
        return None;
    };
    let index = i64::try_from(index.as_u64()?).ok()?;
    Some((identifier(base.id.as_str()).into_owned(), index))
}

fn top_level_bindings(statements: &[Stmt]) -> Vec<String> {
    let mut names = Vec::new();
    for statement in statements {
        match statement {
            Stmt::FunctionDef(function) => {
                names.push(identifier(function.name.as_str()).into_owned())
            }
            Stmt::ClassDef(class) => names.push(identifier(class.name.as_str()).into_owned()),
            Stmt::Assign(assign) => {
                for target in &assign.targets {
                    if let Expr::Name(name) = target {
                        names.push(identifier(name.id.as_str()).into_owned());
                    }
                }
            }
            Stmt::AnnAssign(annotated) if annotated.value.is_some() => {
                if let Expr::Name(name) = &*annotated.target {
                    names.push(identifier(name.id.as_str()).into_owned());
                }
            }
            Stmt::Import(import) => {
                for alias in &import.names {
                    names.push(bound_import_name(alias));
                }
            }
            Stmt::ImportFrom(import) => {
                for alias in &import.names {
                    names.push(bound_import_name(alias));
                }
            }
            _ => {}
        }
    }
    names
}

fn bound_import_name(alias: &Alias) -> String {
    match &alias.asname {
        Some(asname) => identifier(asname.as_str()).into_owned(),
        None => {
            let name = identifier(alias.name.as_str());
            name.split('.')
                .next()
                .expect("a split gives a first part")
                .to_owned()
        }
    }
}
