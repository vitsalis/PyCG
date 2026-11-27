use indexmap::IndexMap;
use pycg_syntax::names::identifier;
use pycg_syntax::tree::Node;
use ruff_python_ast::{Expr, ExprContext, Pattern, Stmt};

pub(crate) fn bound_names<'a>(start: &Node<'a>) -> Vec<String> {
    let mut names = Vec::new();
    let mut pending = vec![start.clone()];
    let mut first = true;
    while let Some(current) = pending.pop() {
        let is_start = std::mem::take(&mut first);
        match &current {
            Node::Stmt(Stmt::FunctionDef(function)) => {
                names.push(identifier(function.name.as_str()).into_owned());
                if !is_start {
                    continue;
                }
                pending.extend(
                    function
                        .decorator_list
                        .iter()
                        .map(|decorator| Node::Expr(&decorator.expression)),
                );
                continue;
            }
            Node::Stmt(Stmt::ClassDef(class)) => {
                names.push(identifier(class.name.as_str()).into_owned());
                if !is_start {
                    continue;
                }
                pending.extend(
                    class
                        .decorator_list
                        .iter()
                        .map(|decorator| Node::Expr(&decorator.expression)),
                );
                if let Some(arguments) = &class.arguments {
                    pending.extend(arguments.args.iter().map(Node::Expr));
                }
                continue;
            }
            Node::Expr(
                Expr::Lambda(_)
                | Expr::ListComp(_)
                | Expr::SetComp(_)
                | Expr::DictComp(_)
                | Expr::Generator(_),
            )
            | Node::GeneratorArgument(..) => continue,
            Node::Stmt(Stmt::AnnAssign(annotated)) if annotated.value.is_none() => continue,
            Node::Expr(Expr::Name(name))
                if matches!(name.ctx, ExprContext::Store | ExprContext::Del) =>
            {
                names.push(identifier(name.id.as_str()).into_owned());
            }
            Node::Stmt(Stmt::Import(import)) => {
                for alias in &import.names {
                    names.push(import_binding(alias));
                }
            }
            Node::Stmt(Stmt::ImportFrom(import)) => {
                for alias in &import.names {
                    names.push(import_binding(alias));
                }
            }
            Node::Pattern(Pattern::MatchAs(pattern)) => {
                if let Some(name) = &pattern.name {
                    names.push(identifier(name.as_str()).into_owned());
                }
            }
            Node::Pattern(Pattern::MatchStar(pattern)) => {
                if let Some(name) = &pattern.name {
                    names.push(identifier(name.as_str()).into_owned());
                }
            }
            Node::Pattern(Pattern::MatchMapping(pattern)) => {
                if let Some(name) = &pattern.rest {
                    names.push(identifier(name.as_str()).into_owned());
                }
            }
            Node::ExceptHandler(handler) => {
                if let Some(name) = &handler.name {
                    names.push(identifier(name.as_str()).into_owned());
                }
            }
            _ => {}
        }
        pending.extend(current.children());
    }
    names
}

fn import_binding(alias: &ruff_python_ast::Alias) -> String {
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

pub(crate) fn walrus_names(statement: &Node<'_>) -> Vec<String> {
    let mut names: Vec<String> = Vec::new();
    let mut pending = vec![statement.clone()];
    while let Some(node) = pending.pop() {
        match &node {
            Node::Expr(Expr::Named(named)) => {
                if let Expr::Name(name) = &*named.target {
                    let name = identifier(name.id.as_str()).into_owned();
                    if !names.contains(&name) {
                        names.push(name);
                    }
                }
            }
            Node::Stmt(Stmt::FunctionDef(function)) => {
                pending.extend(
                    function
                        .decorator_list
                        .iter()
                        .map(|decorator| Node::Expr(&decorator.expression)),
                );
                pending.push(Node::Arguments(Some(&function.parameters)));
                continue;
            }
            Node::Stmt(Stmt::ClassDef(class)) => {
                pending.extend(
                    class
                        .decorator_list
                        .iter()
                        .map(|decorator| Node::Expr(&decorator.expression)),
                );
                if let Some(arguments) = &class.arguments {
                    pending.extend(arguments.args.iter().map(Node::Expr));
                    pending.extend(arguments.keywords.iter().map(Node::Keyword));
                }
                continue;
            }
            Node::Expr(Expr::Lambda(lambda)) => {
                pending.push(Node::Arguments(lambda.parameters.as_deref()));
                continue;
            }
            _ => {}
        }
        pending.extend(node.children());
    }
    names
}

fn is_compound(statement: &Stmt) -> bool {
    matches!(
        statement,
        Stmt::If(_)
            | Stmt::For(_)
            | Stmt::While(_)
            | Stmt::With(_)
            | Stmt::Try(_)
            | Stmt::Match(_)
            | Stmt::Delete(_)
    )
}

pub(crate) fn final_bindings<'a>(body: &'a [Stmt]) -> IndexMap<String, &'a Stmt> {
    let mut finals: IndexMap<String, Option<&'a Stmt>> = IndexMap::new();
    for statement in body {
        let node = Node::Stmt(statement);
        if is_compound(statement) {
            for name in bound_names(&node).into_iter().chain(walrus_names(&node)) {
                finals.insert(name, None);
            }
            continue;
        }
        for name in bound_names(&node) {
            finals.insert(name, Some(statement));
        }
        for name in walrus_names(&node) {
            finals.insert(name, None);
        }
    }
    finals
        .into_iter()
        .filter_map(|(name, statement)| statement.map(|statement| (name, statement)))
        .collect()
}

pub(crate) fn own_statements<'a>(body: &'a [Stmt]) -> Vec<Node<'a>> {
    let mut found = Vec::new();
    let mut pending: Vec<Node<'a>> = body.iter().map(Node::Stmt).collect();
    while let Some(node) = pending.pop() {
        if matches!(
            node,
            Node::Stmt(Stmt::FunctionDef(_) | Stmt::ClassDef(_)) | Node::Expr(Expr::Lambda(_))
        ) {
            continue;
        }
        pending.extend(node.children());
        found.push(node);
    }
    found
}

pub(crate) fn walk_all<'a>(start: &Node<'a>) -> Vec<Node<'a>> {
    let mut found = Vec::new();
    let mut pending = std::collections::VecDeque::from([start.clone()]);
    while let Some(node) = pending.pop_front() {
        pending.extend(node.children());
        found.push(node);
    }
    found
}

pub(crate) fn slots(finals: &IndexMap<String, &Stmt>, source: &str) -> Vec<String> {
    let value = match finals.get("__slots__") {
        Some(Stmt::Assign(assign))
            if assign.targets.len() == 1 && matches!(assign.targets[0], Expr::Name(_)) =>
        {
            &*assign.value
        }
        Some(Stmt::AnnAssign(annotated)) => match &annotated.value {
            Some(value) => &**value,
            None => return Vec::new(),
        },
        _ => return Vec::new(),
    };
    let constants: Vec<&Expr> = match value {
        Expr::StringLiteral(_) => vec![value],
        Expr::Tuple(tuple) => tuple.elts.iter().collect(),
        Expr::List(list) => list.elts.iter().collect(),
        Expr::Dict(dict) => dict
            .items
            .iter()
            .filter_map(|item| item.key.as_ref())
            .collect(),
        _ => return Vec::new(),
    };
    constants
        .into_iter()
        .filter_map(
            |constant| match pycg_syntax::constants::literal(constant, source) {
                Some(pycg_syntax::constants::Constant::Str(text)) => {
                    let points = text.code_points();
                    let text: Option<String> =
                        points.iter().map(|&point| char::from_u32(point)).collect();
                    text
                }
                _ => None,
            },
        )
        .filter(|name| name != "__dict__")
        .collect()
}

pub(crate) fn names_expression(expression: &Expr, name: &str) -> bool {
    crate::builder::statements::names(expression, name)
}

pub(crate) fn abstract_methods(finals: &IndexMap<String, &Stmt>) -> Vec<Box<str>> {
    finals
        .iter()
        .filter(|(_, statement)| match statement {
            Stmt::FunctionDef(function) => function
                .decorator_list
                .iter()
                .any(|decorator| names_expression(&decorator.expression, "abstractmethod")),
            _ => false,
        })
        .map(|(name, _)| Box::from(name.as_str()))
        .collect()
}

pub(crate) fn structure_fields<'a>(
    finals: &IndexMap<String, &'a Stmt>,
    source: &str,
) -> Vec<(String, &'a Expr)> {
    let Some(Stmt::Assign(assign)) = finals.get("_fields_") else {
        return Vec::new();
    };
    if assign.targets.len() != 1 {
        return Vec::new();
    }
    let elements: &[Expr] = match &*assign.value {
        Expr::Tuple(tuple) => &tuple.elts,
        Expr::List(list) => &list.elts,
        _ => return Vec::new(),
    };
    let mut fields = Vec::new();
    for element in elements {
        let parts: &[Expr] = match element {
            Expr::Tuple(tuple) => &tuple.elts,
            Expr::List(list) => &list.elts,
            _ => return Vec::new(),
        };
        if parts.len() < 2 {
            return Vec::new();
        }
        let Some(pycg_syntax::constants::Constant::Str(name)) =
            pycg_syntax::constants::literal(&parts[0], source)
        else {
            return Vec::new();
        };
        let Some(name) = name
            .code_points()
            .iter()
            .map(|&point| char::from_u32(point))
            .collect::<Option<String>>()
        else {
            return Vec::new();
        };
        fields.push((name, &parts[1]));
    }
    fields
}

pub const NESTING_MAX: usize = 247;

fn continuing_child<'a>(node: &Node<'a>) -> Option<pycg_syntax::scopes::NodeKey> {
    let clauses: &'a [ruff_python_ast::ElifElseClause] = match node {
        Node::Expr(Expr::BinOp(operation)) => {
            return Some(pycg_syntax::scopes::node_key(&Node::Expr(&operation.left)));
        }
        Node::Stmt(Stmt::If(conditional)) => &conditional.elif_else_clauses,
        Node::Elif(clauses) => &clauses[1..],
        _ => return None,
    };
    let first = clauses.first()?;
    if first.test.is_some() {
        return Some(pycg_syntax::scopes::node_key(&Node::Elif(clauses)));
    }
    match first.body.as_slice() {
        [nested @ Stmt::If(_)] => Some(pycg_syntax::scopes::node_key(&Node::Stmt(nested))),
        _ => None,
    }
}

pub fn nesting(statement: &Stmt) -> usize {
    let mut deepest = 0;
    let mut pending = vec![(Node::Stmt(statement), 1usize)];
    while let Some((node, depth)) = pending.pop() {
        deepest = deepest.max(depth);
        let continuing = continuing_child(&node);
        for child in node.children() {
            let same_level = continuing == Some(pycg_syntax::scopes::node_key(&child));
            pending.push((child, if same_level { depth } else { depth + 1 }));
        }
    }
    deepest
}
