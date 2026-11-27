use ruff_python_ast::token::{TokenKind, Tokens};
use ruff_python_ast::{
    Alias, Arguments, Comprehension, ElifElseClause, ExceptHandler, ExceptHandlerExceptHandler,
    Expr, ExprGenerator, FStringPartRef, Identifier, InterpolatedElement,
    InterpolatedStringElement, InterpolatedStringElements, InterpolatedStringFormatSpec, Keyword,
    MatchCase, ModModule, Parameter, Parameters, Pattern, Stmt, StringLiteral, TypeParam,
    TypeParams, WithItem,
};
use ruff_text_size::{Ranged, TextRange, TextSize};

use crate::constants::Text;
use crate::names::identifier;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Strings {
    Joined,
    Template,
}

#[derive(Clone, Debug)]
pub enum Node<'a> {
    Module(&'a ModModule),
    Stmt(&'a Stmt),
    Elif(&'a [ElifElseClause]),
    Expr(&'a Expr),
    GeneratorArgument(&'a ExprGenerator, TextRange),
    Arguments(Option<&'a Parameters>),
    Arg(&'a Parameter),
    Keyword(&'a Keyword),
    Alias(&'a Alias),
    Comprehension(&'a Comprehension),
    ExceptHandler(&'a ExceptHandlerExceptHandler),
    WithItem(&'a WithItem),
    MatchCase(&'a MatchCase),
    Pattern(&'a Pattern),
    TypeParam(&'a TypeParam),
    StringPiece(StringPiece<'a>),
    Interpolation(&'a InterpolatedElement, Strings, bool),
    FormatSpec(&'a InterpolatedStringFormatSpec, bool),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Field {
    One(String),
    Many(Vec<String>),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Position {
    pub lineno: usize,
    pub col_offset: usize,
    pub end_lineno: usize,
    pub end_col_offset: usize,
}

impl<'a> Node<'a> {
    pub fn kind(&self) -> &'static str {
        match self {
            Node::Module(_) => "Module",
            Node::Stmt(statement) => statement_kind(statement),
            Node::Elif(_) => "If",
            Node::Expr(expression) => expression_kind(expression),
            Node::GeneratorArgument(..) => "GeneratorExp",
            Node::Arguments(_) => "arguments",
            Node::Arg(_) => "arg",
            Node::Keyword(_) => "keyword",
            Node::Alias(_) => "alias",
            Node::Comprehension(_) => "comprehension",
            Node::ExceptHandler(_) => "ExceptHandler",
            Node::WithItem(_) => "withitem",
            Node::MatchCase(_) => "match_case",
            Node::Pattern(pattern) => pattern_kind(pattern),
            Node::TypeParam(parameter) => type_param_kind(parameter),
            Node::StringPiece(_) => "Constant",
            Node::Interpolation(_, Strings::Joined, _) => "FormattedValue",
            Node::Interpolation(_, Strings::Template, _) => "Interpolation",
            Node::FormatSpec(..) => "JoinedStr",
        }
    }

    pub fn range(&self, tokens: &Tokens) -> Option<TextRange> {
        match self {
            Node::Module(_)
            | Node::Arguments(_)
            | Node::Comprehension(_)
            | Node::WithItem(_)
            | Node::MatchCase(_) => None,
            Node::Stmt(statement) => Some(statement_range(statement, tokens)),
            Node::Elif(clauses) => Some(with_semicolon(elif_range(clauses), tokens)),
            Node::Expr(expression) => Some(expression.range()),
            Node::GeneratorArgument(_, parentheses) => Some(*parentheses),
            Node::Arg(parameter) => Some(TextRange::new(parameter.name.start(), parameter.end())),
            Node::Keyword(keyword) => Some(keyword.range()),
            Node::Alias(alias) => Some(alias.range()),
            Node::ExceptHandler(handler) => Some(with_semicolon(handler.range(), tokens)),
            Node::Pattern(pattern) => Some(pattern.range()),
            Node::TypeParam(parameter) => Some(parameter.range()),
            Node::StringPiece(piece) => Some(piece.range),
            Node::Interpolation(element, ..) => Some(element.range()),
            Node::FormatSpec(spec, _) => Some(format_spec_range(spec)),
        }
    }

    pub fn children(&self) -> Vec<Node<'a>> {
        let mut children = Vec::new();
        match self.clone() {
            Node::Module(module) => statements(&mut children, &module.body),
            Node::Stmt(statement) => statement_children(&mut children, statement),
            Node::Elif(clauses) => elif_children(&mut children, clauses),
            Node::Expr(expression) => expression_children(&mut children, expression),
            Node::GeneratorArgument(generator, _) => {
                generator_children(&mut children, &generator.elt, &generator.generators);
            }
            Node::Arguments(parameters) => {
                if let Some(parameters) = parameters {
                    parameters_children(&mut children, parameters);
                }
            }
            Node::Arg(parameter) => optional(&mut children, parameter.annotation.as_deref()),
            Node::Keyword(keyword) => children.push(Node::Expr(&keyword.value)),
            Node::Alias(_) | Node::StringPiece(_) => {}
            Node::Comprehension(comprehension) => {
                comprehension_children(&mut children, comprehension)
            }
            Node::ExceptHandler(handler) => {
                optional(&mut children, handler.type_.as_deref());
                statements(&mut children, &handler.body);
            }
            Node::WithItem(item) => {
                children.push(Node::Expr(&item.context_expr));
                optional(&mut children, item.optional_vars.as_deref());
            }
            Node::MatchCase(case) => {
                children.push(Node::Pattern(&case.pattern));
                optional(&mut children, case.guard.as_deref());
                statements(&mut children, &case.body);
            }
            Node::Pattern(pattern) => pattern_children(&mut children, pattern),
            Node::TypeParam(parameter) => type_param_children(&mut children, parameter),
            Node::Interpolation(element, _, raw) => {
                children.push(Node::Expr(&element.expression));
                if let Some(spec) = element.format_spec.as_deref() {
                    children.push(Node::FormatSpec(spec, raw));
                }
            }
            Node::FormatSpec(spec, raw) => {
                let parts = [Part::Elements {
                    elements: &spec.elements,
                    raw,
                }];
                joined_children(&mut children, &parts, Strings::Joined);
            }
        }
        children
    }

    pub fn identifiers(&self, tokens: &Tokens, source: &str) -> Vec<(&'static str, Field)> {
        let mut found = Vec::new();
        match self {
            Node::Stmt(Stmt::FunctionDef(definition)) => one(&mut found, "name", &definition.name),
            Node::Stmt(Stmt::ClassDef(class)) => one(&mut found, "name", &class.name),
            Node::Stmt(Stmt::ImportFrom(import)) => {
                optional_one(&mut found, "module", import.module.as_ref())
            }
            Node::Stmt(Stmt::Global(global)) => many(&mut found, "names", &global.names),
            Node::Stmt(Stmt::Nonlocal(nonlocal)) => many(&mut found, "names", &nonlocal.names),
            Node::Expr(Expr::Name(name)) => {
                found.push(("id", Field::One(identifier(name.id.as_str()).into_owned())));
            }
            Node::Expr(Expr::Attribute(attribute)) => one(&mut found, "attr", &attribute.attr),
            Node::Arg(parameter) => one(&mut found, "arg", &parameter.name),
            Node::Keyword(keyword) => optional_one(&mut found, "arg", keyword.arg.as_ref()),
            Node::Alias(alias) => {
                one(&mut found, "name", &alias.name);
                optional_one(&mut found, "asname", alias.asname.as_ref());
            }
            Node::ExceptHandler(handler) => optional_one(&mut found, "name", handler.name.as_ref()),
            Node::Pattern(Pattern::MatchAs(pattern)) => {
                optional_one(&mut found, "name", pattern.name.as_ref());
            }
            Node::Pattern(Pattern::MatchStar(pattern)) => {
                optional_one(&mut found, "name", pattern.name.as_ref());
            }
            Node::Pattern(Pattern::MatchMapping(pattern)) => {
                optional_one(&mut found, "rest", pattern.rest.as_ref());
            }
            Node::Pattern(Pattern::MatchClass(pattern)) => {
                let attributes: Vec<&Identifier> = pattern
                    .arguments
                    .keywords
                    .iter()
                    .map(|keyword| &keyword.attr)
                    .collect();
                many(&mut found, "kwd_attrs", attributes);
            }
            Node::TypeParam(TypeParam::TypeVar(parameter)) => {
                one(&mut found, "name", &parameter.name)
            }
            Node::TypeParam(TypeParam::TypeVarTuple(parameter)) => {
                one(&mut found, "name", &parameter.name);
            }
            Node::TypeParam(TypeParam::ParamSpec(parameter)) => {
                one(&mut found, "name", &parameter.name)
            }
            Node::Interpolation(element, Strings::Template, _) => {
                found.push((
                    "str",
                    Field::One(interpolation_text(element, tokens, source)),
                ));
            }
            _ => {}
        }
        found
    }
}

fn statement_kind(statement: &Stmt) -> &'static str {
    match statement {
        Stmt::FunctionDef(function) if function.is_async => "AsyncFunctionDef",
        Stmt::FunctionDef(_) => "FunctionDef",
        Stmt::ClassDef(_) => "ClassDef",
        Stmt::Return(_) => "Return",
        Stmt::Delete(_) => "Delete",
        Stmt::TypeAlias(_) => "TypeAlias",
        Stmt::Assign(_) => "Assign",
        Stmt::AugAssign(_) => "AugAssign",
        Stmt::AnnAssign(_) => "AnnAssign",
        Stmt::For(statement) if statement.is_async => "AsyncFor",
        Stmt::For(_) => "For",
        Stmt::While(_) => "While",
        Stmt::If(_) => "If",
        Stmt::With(statement) if statement.is_async => "AsyncWith",
        Stmt::With(_) => "With",
        Stmt::Match(_) => "Match",
        Stmt::Raise(_) => "Raise",
        Stmt::Try(statement) if statement.is_star => "TryStar",
        Stmt::Try(_) => "Try",
        Stmt::Assert(_) => "Assert",
        Stmt::Import(_) => "Import",
        Stmt::ImportFrom(_) => "ImportFrom",
        Stmt::Global(_) => "Global",
        Stmt::Nonlocal(_) => "Nonlocal",
        Stmt::Expr(_) => "Expr",
        Stmt::Pass(_) => "Pass",
        Stmt::Break(_) => "Break",
        Stmt::Continue(_) => "Continue",
        Stmt::IpyEscapeCommand(_) => unreachable!("a module has no IPython escape"),
    }
}

fn expression_kind(expression: &Expr) -> &'static str {
    match expression {
        Expr::BoolOp(_) => "BoolOp",
        Expr::Named(_) => "NamedExpr",
        Expr::BinOp(_) => "BinOp",
        Expr::UnaryOp(_) => "UnaryOp",
        Expr::Lambda(_) => "Lambda",
        Expr::If(_) => "IfExp",
        Expr::Dict(_) => "Dict",
        Expr::Set(_) => "Set",
        Expr::ListComp(_) => "ListComp",
        Expr::SetComp(_) => "SetComp",
        Expr::DictComp(_) => "DictComp",
        Expr::Generator(_) => "GeneratorExp",
        Expr::Await(_) => "Await",
        Expr::Yield(_) => "Yield",
        Expr::YieldFrom(_) => "YieldFrom",
        Expr::Compare(_) => "Compare",
        Expr::Call(_) => "Call",
        Expr::FString(_) => "JoinedStr",
        Expr::TString(_) => "TemplateStr",
        Expr::StringLiteral(_)
        | Expr::BytesLiteral(_)
        | Expr::NumberLiteral(_)
        | Expr::BooleanLiteral(_)
        | Expr::NoneLiteral(_)
        | Expr::EllipsisLiteral(_) => "Constant",
        Expr::Attribute(_) => "Attribute",
        Expr::Subscript(_) => "Subscript",
        Expr::Starred(_) => "Starred",
        Expr::Name(_) => "Name",
        Expr::List(_) => "List",
        Expr::Tuple(_) => "Tuple",
        Expr::Slice(_) => "Slice",
        Expr::IpyEscapeCommand(_) => unreachable!("a module has no IPython escape"),
    }
}

fn pattern_kind(pattern: &Pattern) -> &'static str {
    match pattern {
        Pattern::MatchValue(_) => "MatchValue",
        Pattern::MatchSingleton(_) => "MatchSingleton",
        Pattern::MatchSequence(_) => "MatchSequence",
        Pattern::MatchMapping(_) => "MatchMapping",
        Pattern::MatchClass(_) => "MatchClass",
        Pattern::MatchStar(_) => "MatchStar",
        Pattern::MatchAs(_) => "MatchAs",
        Pattern::MatchOr(_) => "MatchOr",
    }
}

fn type_param_kind(parameter: &TypeParam) -> &'static str {
    match parameter {
        TypeParam::TypeVar(_) => "TypeVar",
        TypeParam::TypeVarTuple(_) => "TypeVarTuple",
        TypeParam::ParamSpec(_) => "ParamSpec",
    }
}

fn with_semicolon(range: TextRange, tokens: &Tokens) -> TextRange {
    match tokens.after(range.end()).first() {
        Some(token) if token.kind() == TokenKind::Semi => range.cover(token.range()),
        _ => range,
    }
}

fn is_compound(statement: &Stmt) -> bool {
    matches!(
        statement,
        Stmt::FunctionDef(_)
            | Stmt::ClassDef(_)
            | Stmt::For(_)
            | Stmt::While(_)
            | Stmt::If(_)
            | Stmt::With(_)
            | Stmt::Match(_)
            | Stmt::Try(_)
    )
}

fn statement_range(statement: &Stmt, tokens: &Tokens) -> TextRange {
    if !is_compound(statement) {
        return statement.range();
    }
    let range = with_semicolon(statement.range(), tokens);
    let decorators = match statement {
        Stmt::FunctionDef(function) => function.decorator_list.last(),
        Stmt::ClassDef(class) => class.decorator_list.last(),
        _ => None,
    };
    let Some(decorator) = decorators else {
        return range;
    };
    let keyword = tokens
        .after(decorator.end())
        .iter()
        .find(|token| {
            matches!(
                token.kind(),
                TokenKind::Async | TokenKind::Def | TokenKind::Class
            )
        })
        .expect("a decorated definition has its keyword after the decorators");
    TextRange::new(keyword.start(), range.end())
}

fn elif_range(clauses: &[ElifElseClause]) -> TextRange {
    let first = clauses.first().expect("an elif chain has a clause");
    let last = clauses.last().expect("an elif chain has a clause");
    TextRange::new(first.start(), last.end())
}

const FORMAT_SPEC_COLON_LENGTH: u32 = 1;

fn format_spec_range(spec: &InterpolatedStringFormatSpec) -> TextRange {
    let colon = TextSize::new(FORMAT_SPEC_COLON_LENGTH);
    TextRange::new(spec.start() - colon, spec.end())
}

fn statements<'a>(children: &mut Vec<Node<'a>>, body: &'a [Stmt]) {
    children.extend(body.iter().map(Node::Stmt));
}

fn expressions<'a>(children: &mut Vec<Node<'a>>, values: &'a [Expr]) {
    children.extend(values.iter().map(Node::Expr));
}

fn optional<'a>(children: &mut Vec<Node<'a>>, value: Option<&'a Expr>) {
    if let Some(value) = value {
        children.push(Node::Expr(value));
    }
}

fn type_params<'a>(children: &mut Vec<Node<'a>>, parameters: Option<&'a TypeParams>) {
    if let Some(parameters) = parameters {
        children.extend(parameters.type_params.iter().map(Node::TypeParam));
    }
}

fn decorators<'a>(children: &mut Vec<Node<'a>>, list: &'a [ruff_python_ast::Decorator]) {
    children.extend(
        list.iter()
            .map(|decorator| Node::Expr(&decorator.expression)),
    );
}

fn statement_children<'a>(children: &mut Vec<Node<'a>>, statement: &'a Stmt) {
    match statement {
        Stmt::FunctionDef(function) => {
            children.push(Node::Arguments(Some(&function.parameters)));
            statements(children, &function.body);
            decorators(children, &function.decorator_list);
            optional(children, function.returns.as_deref());
            type_params(children, function.type_params.as_deref());
        }
        Stmt::ClassDef(class) => {
            if let Some(arguments) = class.arguments.as_deref() {
                expressions(children, &arguments.args);
                children.extend(arguments.keywords.iter().map(Node::Keyword));
            }
            statements(children, &class.body);
            decorators(children, &class.decorator_list);
            type_params(children, class.type_params.as_deref());
        }
        Stmt::Return(statement) => optional(children, statement.value.as_deref()),
        Stmt::Delete(statement) => expressions(children, &statement.targets),
        Stmt::TypeAlias(statement) => {
            children.push(Node::Expr(&statement.name));
            type_params(children, statement.type_params.as_deref());
            children.push(Node::Expr(&statement.value));
        }
        Stmt::Assign(statement) => {
            expressions(children, &statement.targets);
            children.push(Node::Expr(&statement.value));
        }
        Stmt::AugAssign(statement) => {
            children.push(Node::Expr(&statement.target));
            children.push(Node::Expr(&statement.value));
        }
        Stmt::AnnAssign(statement) => {
            children.push(Node::Expr(&statement.target));
            children.push(Node::Expr(&statement.annotation));
            optional(children, statement.value.as_deref());
        }
        Stmt::For(statement) => {
            children.push(Node::Expr(&statement.target));
            children.push(Node::Expr(&statement.iter));
            statements(children, &statement.body);
            statements(children, &statement.orelse);
        }
        Stmt::While(statement) => {
            children.push(Node::Expr(&statement.test));
            statements(children, &statement.body);
            statements(children, &statement.orelse);
        }
        Stmt::If(statement) => {
            children.push(Node::Expr(&statement.test));
            statements(children, &statement.body);
            orelse_children(children, &statement.elif_else_clauses);
        }
        Stmt::With(statement) => {
            children.extend(statement.items.iter().map(Node::WithItem));
            statements(children, &statement.body);
        }
        Stmt::Match(statement) => {
            children.push(Node::Expr(&statement.subject));
            children.extend(statement.cases.iter().map(Node::MatchCase));
        }
        Stmt::Raise(statement) => {
            optional(children, statement.exc.as_deref());
            optional(children, statement.cause.as_deref());
        }
        Stmt::Try(statement) => {
            statements(children, &statement.body);
            children.extend(statement.handlers.iter().map(|handler| match handler {
                ExceptHandler::ExceptHandler(handler) => Node::ExceptHandler(handler),
            }));
            statements(children, &statement.orelse);
            statements(children, &statement.finalbody);
        }
        Stmt::Assert(statement) => {
            children.push(Node::Expr(&statement.test));
            optional(children, statement.msg.as_deref());
        }
        Stmt::Import(statement) => children.extend(statement.names.iter().map(Node::Alias)),
        Stmt::ImportFrom(statement) => children.extend(statement.names.iter().map(Node::Alias)),
        Stmt::Expr(statement) => children.push(Node::Expr(&statement.value)),
        Stmt::Global(_)
        | Stmt::Nonlocal(_)
        | Stmt::Pass(_)
        | Stmt::Break(_)
        | Stmt::Continue(_) => {}
        Stmt::IpyEscapeCommand(_) => unreachable!("a module has no IPython escape"),
    }
}

fn orelse_children<'a>(children: &mut Vec<Node<'a>>, clauses: &'a [ElifElseClause]) {
    let Some(first) = clauses.first() else {
        return;
    };
    if first.test.is_some() {
        children.push(Node::Elif(clauses));
    } else {
        assert_eq!(clauses.len(), 1, "an else clause is the last clause");
        statements(children, &first.body);
    }
}

fn elif_children<'a>(children: &mut Vec<Node<'a>>, clauses: &'a [ElifElseClause]) {
    let (first, rest) = clauses.split_first().expect("an elif chain has a clause");
    children.push(Node::Expr(
        first.test.as_ref().expect("an elif clause has a test"),
    ));
    statements(children, &first.body);
    orelse_children(children, rest);
}

fn parameters_children<'a>(children: &mut Vec<Node<'a>>, parameters: &'a Parameters) {
    let positional = parameters.posonlyargs.iter().chain(parameters.args.iter());
    children.extend(
        parameters
            .posonlyargs
            .iter()
            .map(|p| Node::Arg(&p.parameter)),
    );
    children.extend(parameters.args.iter().map(|p| Node::Arg(&p.parameter)));
    if let Some(vararg) = parameters.vararg.as_deref() {
        children.push(Node::Arg(vararg));
    }
    children.extend(
        parameters
            .kwonlyargs
            .iter()
            .map(|p| Node::Arg(&p.parameter)),
    );
    for parameter in parameters.kwonlyargs.iter() {
        optional(children, parameter.default.as_deref());
    }
    if let Some(kwarg) = parameters.kwarg.as_deref() {
        children.push(Node::Arg(kwarg));
    }
    for parameter in positional {
        optional(children, parameter.default.as_deref());
    }
}

fn comprehension_children<'a>(children: &mut Vec<Node<'a>>, comprehension: &'a Comprehension) {
    children.push(Node::Expr(&comprehension.target));
    children.push(Node::Expr(&comprehension.iter));
    expressions(children, &comprehension.ifs);
}

fn generator_children<'a>(
    children: &mut Vec<Node<'a>>,
    element: &'a Expr,
    generators: &'a [Comprehension],
) {
    children.push(Node::Expr(element));
    children.extend(generators.iter().map(Node::Comprehension));
}

fn call_arguments<'a>(children: &mut Vec<Node<'a>>, arguments: &'a Arguments) {
    if let ([Expr::Generator(generator)], []) = (&arguments.args[..], &arguments.keywords[..])
        && !generator.parenthesized
    {
        children.push(Node::GeneratorArgument(generator, arguments.range()));
        return;
    }
    expressions(children, &arguments.args);
    children.extend(arguments.keywords.iter().map(Node::Keyword));
}

fn expression_children<'a>(children: &mut Vec<Node<'a>>, expression: &'a Expr) {
    match expression {
        Expr::BoolOp(e) => expressions(children, &e.values),
        Expr::Named(e) => {
            children.push(Node::Expr(&e.target));
            children.push(Node::Expr(&e.value));
        }
        Expr::BinOp(e) => {
            children.push(Node::Expr(&e.left));
            children.push(Node::Expr(&e.right));
        }
        Expr::UnaryOp(e) => children.push(Node::Expr(&e.operand)),
        Expr::Lambda(e) => {
            children.push(Node::Arguments(e.parameters.as_deref()));
            children.push(Node::Expr(&e.body));
        }
        Expr::If(e) => {
            children.push(Node::Expr(&e.test));
            children.push(Node::Expr(&e.body));
            children.push(Node::Expr(&e.orelse));
        }
        Expr::Dict(e) => {
            children.extend(
                e.items
                    .iter()
                    .filter_map(|item| item.key.as_ref())
                    .map(Node::Expr),
            );
            children.extend(e.items.iter().map(|item| Node::Expr(&item.value)));
        }
        Expr::Set(e) => expressions(children, &e.elts),
        Expr::ListComp(e) => generator_children(children, &e.elt, &e.generators),
        Expr::SetComp(e) => generator_children(children, &e.elt, &e.generators),
        Expr::DictComp(e) => {
            optional(children, e.key.as_deref());
            children.push(Node::Expr(&e.value));
            children.extend(e.generators.iter().map(Node::Comprehension));
        }
        Expr::Generator(e) => generator_children(children, &e.elt, &e.generators),
        Expr::Await(e) => children.push(Node::Expr(&e.value)),
        Expr::Yield(e) => optional(children, e.value.as_deref()),
        Expr::YieldFrom(e) => children.push(Node::Expr(&e.value)),
        Expr::Compare(e) => expressions(children, &e.operands),
        Expr::Call(e) => {
            children.push(Node::Expr(&e.func));
            call_arguments(children, &e.arguments);
        }
        Expr::FString(e) => {
            let parts: Vec<Part<'a>> = e.value.iter().map(Part::of_fstring).collect();
            joined_children(children, &parts, Strings::Joined);
        }
        Expr::TString(e) => {
            let parts: Vec<Part<'a>> = e
                .value
                .as_slice()
                .iter()
                .map(|t| Part::Elements {
                    elements: &t.elements,
                    raw: t.flags.prefix().is_raw(),
                })
                .collect();
            joined_children(children, &parts, Strings::Template);
        }
        Expr::StringLiteral(_)
        | Expr::BytesLiteral(_)
        | Expr::NumberLiteral(_)
        | Expr::BooleanLiteral(_)
        | Expr::NoneLiteral(_)
        | Expr::EllipsisLiteral(_)
        | Expr::Name(_) => {}
        Expr::Attribute(e) => children.push(Node::Expr(&e.value)),
        Expr::Subscript(e) => {
            children.push(Node::Expr(&e.value));
            children.push(Node::Expr(&e.slice));
        }
        Expr::Starred(e) => children.push(Node::Expr(&e.value)),
        Expr::List(e) => expressions(children, &e.elts),
        Expr::Tuple(e) => expressions(children, &e.elts),
        Expr::Slice(e) => {
            optional(children, e.lower.as_deref());
            optional(children, e.upper.as_deref());
            optional(children, e.step.as_deref());
        }
        Expr::IpyEscapeCommand(_) => unreachable!("a module has no IPython escape"),
    }
}

fn pattern_children<'a>(children: &mut Vec<Node<'a>>, pattern: &'a Pattern) {
    match pattern {
        Pattern::MatchValue(p) => children.push(Node::Expr(&p.value)),
        Pattern::MatchSingleton(_) | Pattern::MatchStar(_) => {}
        Pattern::MatchSequence(p) => children.extend(p.patterns.iter().map(Node::Pattern)),
        Pattern::MatchMapping(p) => {
            expressions(children, &p.keys);
            children.extend(p.patterns.iter().map(Node::Pattern));
        }
        Pattern::MatchClass(p) => {
            children.push(Node::Expr(&p.cls));
            children.extend(p.arguments.patterns.iter().map(Node::Pattern));
            children.extend(
                p.arguments
                    .keywords
                    .iter()
                    .map(|k| Node::Pattern(&k.pattern)),
            );
        }
        Pattern::MatchAs(p) => {
            if let Some(inner) = p.pattern.as_deref() {
                children.push(Node::Pattern(inner));
            }
        }
        Pattern::MatchOr(p) => children.extend(p.patterns.iter().map(Node::Pattern)),
    }
}

fn type_param_children<'a>(children: &mut Vec<Node<'a>>, parameter: &'a TypeParam) {
    match parameter {
        TypeParam::TypeVar(p) => {
            optional(children, p.bound.as_deref());
            optional(children, p.default.as_deref());
        }
        TypeParam::TypeVarTuple(p) => optional(children, p.default.as_deref()),
        TypeParam::ParamSpec(p) => optional(children, p.default.as_deref()),
    }
}

#[derive(Clone, Copy)]
enum Part<'a> {
    Literal(&'a StringLiteral),
    Elements {
        elements: &'a InterpolatedStringElements,
        raw: bool,
    },
}

impl<'a> Part<'a> {
    fn of_fstring(part: FStringPartRef<'a>) -> Part<'a> {
        match part {
            FStringPartRef::Literal(literal) => Part::Literal(literal),
            FStringPartRef::FString(fstring) => Part::Elements {
                elements: &fstring.elements,
                raw: fstring.flags.prefix().is_raw(),
            },
        }
    }
}

#[derive(Clone, Debug)]
pub struct StringPiece<'a> {
    pub range: TextRange,
    pub texts: Vec<Text<'a>>,
}

enum Piece<'a> {
    Text {
        range: TextRange,
        empty: bool,
        text: Text<'a>,
    },
    Field(&'a InterpolatedElement, bool),
}

const FIELD_BRACE_LENGTH: u32 = 1;

fn pieces<'a>(parts: &[Part<'a>]) -> Vec<Piece<'a>> {
    let mut found = Vec::new();
    for part in parts {
        match *part {
            Part::Literal(literal) => found.push(Piece::Text {
                range: literal.range(),
                empty: literal.value.is_empty(),
                text: Text::Literal(literal),
            }),
            Part::Elements { elements, raw } => {
                for element in elements.iter() {
                    element_pieces(&mut found, element, raw);
                }
            }
        }
    }
    found
}

fn element_pieces<'a>(
    found: &mut Vec<Piece<'a>>,
    element: &'a InterpolatedStringElement,
    raw: bool,
) {
    match element {
        InterpolatedStringElement::Literal(literal) => found.push(Piece::Text {
            range: literal.range(),
            empty: literal.value.is_empty(),
            text: Text::Element {
                element: literal,
                raw,
            },
        }),
        InterpolatedStringElement::Interpolation(field) => {
            if let Some(debug) = &field.debug_text {
                let start = field.start() + TextSize::new(FIELD_BRACE_LENGTH);
                let length =
                    TextSize::try_from(debug.as_str().len()).expect("a debug text fits the source");
                found.push(Piece::Text {
                    range: TextRange::at(start, length),
                    empty: debug.as_str().is_empty(),
                    text: Text::Debug(debug),
                });
            }
            found.push(Piece::Field(field, raw));
        }
    }
}

fn joined_children<'a>(children: &mut Vec<Node<'a>>, parts: &[Part<'a>], strings: Strings) {
    let mut text: Option<StringPiece<'a>> = None;
    for piece in pieces(parts) {
        match piece {
            Piece::Text { empty: true, .. } => {}
            Piece::Text {
                range,
                empty: false,
                text: source,
            } => match text.as_mut() {
                Some(merged) => {
                    merged.range = merged.range.cover(range);
                    merged.texts.push(source);
                }
                None => {
                    text = Some(StringPiece {
                        range,
                        texts: vec![source],
                    })
                }
            },
            Piece::Field(field, raw) => {
                if let Some(merged) = text.take() {
                    children.push(Node::StringPiece(merged));
                }
                children.push(Node::Interpolation(field, strings, raw));
            }
        }
    }
    if let Some(merged) = text {
        children.push(Node::StringPiece(merged));
    }
}

fn one(found: &mut Vec<(&'static str, Field)>, field: &'static str, name: &Identifier) {
    found.push((field, Field::One(identifier(name.as_str()).into_owned())));
}

fn optional_one(
    found: &mut Vec<(&'static str, Field)>,
    field: &'static str,
    name: Option<&Identifier>,
) {
    if let Some(name) = name {
        one(found, field, name);
    }
}

fn many<'n>(
    found: &mut Vec<(&'static str, Field)>,
    field: &'static str,
    names: impl IntoIterator<Item = &'n Identifier>,
) {
    let names: Vec<String> = names
        .into_iter()
        .map(|name| identifier(name.as_str()).into_owned())
        .collect();
    if !names.is_empty() {
        found.push((field, Field::Many(names)));
    }
}

fn interpolation_text(element: &InterpolatedElement, tokens: &Tokens, source: &str) -> String {
    let start = element.start() + TextSize::of('{');
    let end = tokens
        .after(element.expression.end())
        .iter()
        .find(|token| {
            matches!(
                token.kind(),
                TokenKind::Exclamation | TokenKind::Colon | TokenKind::Rbrace
            )
        })
        .expect("an interpolation ends at a conversion, a format spec or a brace")
        .start();
    let mut text = String::new();
    let mut from = start;
    for token in tokens.in_range(TextRange::new(start, end)) {
        if token.kind() == TokenKind::Comment {
            text.push_str(&source[TextRange::new(from, token.start())]);
            from = token.end();
        }
    }
    text.push_str(&source[TextRange::new(from, end)]);
    if element.debug_text.is_some() {
        let expression = text
            .trim_end()
            .strip_suffix('=')
            .expect("the text of a debug interpolation ends with =");
        return expression.to_owned();
    }
    text
}

pub fn walk<'a>(module: &'a ModModule) -> Vec<Node<'a>> {
    let mut order = Vec::new();
    let mut queue = std::collections::VecDeque::from([Node::Module(module)]);
    while let Some(node) = queue.pop_front() {
        queue.extend(node.children());
        order.push(node);
    }
    order
}

pub fn position(range: TextRange, lines: &ruff_source_file::LineIndex) -> Position {
    let line_and_column = |offset: TextSize| {
        let line = lines.line_index(offset);
        let start = lines.line_starts()[line.to_zero_indexed()];
        (line.get(), usize::from(offset - start))
    };
    let (lineno, col_offset) = line_and_column(range.start());
    let (end_lineno, end_col_offset) = line_and_column(range.end());
    Position {
        lineno,
        col_offset,
        end_lineno,
        end_col_offset,
    }
}
