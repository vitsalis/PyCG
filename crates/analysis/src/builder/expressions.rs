use num_bigint::BigInt;
use pycg_solver::NodeId;
use pycg_syntax::constants::{self, Constant as SyntaxConstant};
use pycg_syntax::names::identifier;
use pycg_syntax::scopes::{NodeKey, ScopeKind, node_key};
use pycg_syntax::tree::{Node, Strings, position};
use ruff_python_ast::{
    BoolOp, CmpOp, ConversionFlag, Expr, ExprAttribute, ExprBinOp, ExprBoolOp, ExprCall,
    ExprCompare, ExprDict, ExprIf, ExprLambda, ExprName, ExprSlice, ExprSubscript, ExprUnaryOp,
    Operator, Parameters, StmtAugAssign, UnaryOp,
};
use rustc_hash::FxHashMap;

use crate::builder::calls::{Analysis, Call, Constant, Key, Operation, Slice, Subscript};
use crate::builder::flow::StateId;
use crate::builder::flow::{FALSE, Literal, Literals, TRUE, Truth, UNKNOWN, truth_of};
use crate::builder::format::{FieldName, format_fields};
use crate::builder::literals::{compare, equal};
use crate::builder::{Facts, ModuleBuilder, TYPE_CHECKING_IMPORTS, TYPING_MODULES, UNKNOWN_FACTS};

#[derive(Clone, Debug)]
pub(crate) enum SubscriptIndex {
    Key(Option<NodeId>),
    Bounds(Option<(Option<BigInt>, Option<BigInt>)>),
}

#[derive(Debug, Default)]
pub(crate) struct ExpressionTables {
    facts_by_expression: FxHashMap<NodeKey, Facts>,
    operand_nodes_by_binop: FxHashMap<NodeKey, (Option<NodeId>, Option<NodeId>)>,
    type_checking_truth_by_test: FxHashMap<NodeKey, bool>,
}

fn special_method(operator: Operator) -> &'static str {
    match operator {
        Operator::Add => "add",
        Operator::Sub => "sub",
        Operator::Mult => "mul",
        Operator::MatMult => "matmul",
        Operator::Div => "truediv",
        Operator::FloorDiv => "floordiv",
        Operator::Mod => "mod",
        Operator::Pow => "pow",
        Operator::LShift => "lshift",
        Operator::RShift => "rshift",
        Operator::BitOr => "or",
        Operator::BitXor => "xor",
        Operator::BitAnd => "and",
    }
}

fn comparison_methods(operator: CmpOp) -> Option<(&'static str, &'static str)> {
    match operator {
        CmpOp::Eq => Some(("__eq__", "__eq__")),
        CmpOp::NotEq => Some(("__ne__", "__ne__")),
        CmpOp::Lt => Some(("__lt__", "__gt__")),
        CmpOp::LtE => Some(("__le__", "__ge__")),
        CmpOp::Gt => Some(("__gt__", "__lt__")),
        CmpOp::GtE => Some(("__ge__", "__le__")),
        CmpOp::Is | CmpOp::IsNot | CmpOp::In | CmpOp::NotIn => None,
    }
}

fn format_conversion(conversion: Option<u32>) -> &'static str {
    match conversion.and_then(char::from_u32) {
        Some('r' | 'a') => "repr",
        Some('s') => "str",
        _ => "format",
    }
}

fn fstring_conversion(flag: ConversionFlag) -> &'static str {
    match flag {
        ConversionFlag::Str => "str",
        ConversionFlag::Repr | ConversionFlag::Ascii => "repr",
        ConversionFlag::None => "format",
    }
}

pub(crate) fn literal_of(constant: &SyntaxConstant) -> Option<Literal> {
    match constant {
        SyntaxConstant::Str(text) => Some(Literal::Str(text.code_points().into())),
        SyntaxConstant::Bytes(bytes) => Some(Literal::Bytes(bytes.as_slice().into())),
        SyntaxConstant::Int(value) => Some(Literal::Int(value.clone())),
        SyntaxConstant::Float(value) => Some(Literal::Float(*value)),
        SyntaxConstant::Bool(value) => Some(Literal::Bool(*value)),
        SyntaxConstant::None => Some(Literal::None),
        SyntaxConstant::Ellipsis | SyntaxConstant::Complex { .. } => None,
    }
}

fn constant_truth(constant: &SyntaxConstant) -> Truth {
    let true_ = match constant {
        SyntaxConstant::Ellipsis => true,
        SyntaxConstant::Complex { real, imag } => *real != 0.0 || *imag != 0.0,
        other => literal_of(other)
            .expect("every other constant is a literal")
            .is_true(),
    };
    if true_ { TRUE } else { FALSE }
}

pub(crate) fn int_literal(expression: &Expr, source: &str) -> Option<BigInt> {
    let (negative, operand) = match expression {
        Expr::UnaryOp(ExprUnaryOp {
            op: UnaryOp::USub,
            operand,
            ..
        }) => (true, operand.as_ref()),
        other => (false, other),
    };
    match constants::literal(operand, source) {
        Some(SyntaxConstant::Int(value)) => Some(if negative { -value } else { value }),
        _ => None,
    }
}

fn join_facts(facts: &[Facts]) -> Facts {
    let mut truth = 0;
    let mut values = Some(Literals::default());
    for (bits, literals) in facts {
        truth |= bits;
        values = match (&values, literals) {
            (Some(joined), Some(literals)) => Some(joined.union(literals)),
            _ => None,
        };
    }
    (if truth == 0 { UNKNOWN } else { truth }, values)
}

fn has_fixed_identity(value: &Literal) -> bool {
    matches!(value, Literal::None | Literal::Bool(_))
}

fn is_str_constant(expression: &Expr) -> bool {
    matches!(expression, Expr::StringLiteral(_))
}

pub(crate) fn argument_nodes(call: &ExprCall) -> Vec<Node<'_>> {
    let arguments = &call.arguments;
    if let ([Expr::Generator(generator)], []) = (&arguments.args[..], &arguments.keywords[..])
        && !generator.parenthesized
    {
        return vec![Node::GeneratorArgument(generator, arguments.range)];
    }
    arguments.args.iter().map(Node::Expr).collect()
}

impl<'a, 's, A: Analysis> ModuleBuilder<'a, 's, A> {
    pub(crate) fn namespace_read(&mut self, name: &str) {
        let name = self.mangle(name);
        let binder = self.scopes.resolve(self.scope, &name);
        let mut read = Vec::new();
        for &scope in self.scopes.scopes() {
            let found = self.scopes.scope(scope);
            if found.kind == ScopeKind::Class
                && found.parent == Some(binder)
                && found.local_name.as_deref() == Some(name.as_str())
            {
                read.push(found.name.clone().into_boxed_str());
            }
        }
        for name in read {
            add_once(&mut self.analysis.tables().read_namespaces, name);
        }
    }

    pub(crate) fn expression(&mut self, expression: &Expr) -> Option<NodeId> {
        self.expression_at(&Node::Expr(expression))
    }

    pub(crate) fn expression_at(&mut self, node: &Node<'_>) -> Option<NodeId> {
        let value = match node {
            Node::Expr(expression) => self.expression_kind(node, expression),
            Node::GeneratorArgument(..) => Some(self.comprehension(node)),
            Node::StringPiece(piece) => {
                let text = constants::text_value(&piece.texts, self.source.text);
                Some(self.constant_of(Constant::Str(text.code_points().into())))
            }
            Node::FormatSpec(..) => self.joined_str(node),
            _ => {
                self.walk(node);
                None
            }
        };
        if matches!(
            node,
            Node::Expr(Expr::BinOp(_) | Expr::FString(_) | Expr::Call(_)) | Node::FormatSpec(..)
        ) && let Some(pattern) = self.string_pattern(node)
        {
            let joined = self
                .join(&[value, Some(pattern)])
                .expect("a join with a pattern has a node");
            for operand in self.pattern_operands(node) {
                self.analysis.add_pattern_operand(operand, joined);
            }
            return Some(joined);
        }
        value
    }

    fn pattern_operands(&self, node: &Node<'_>) -> Vec<Option<NodeId>> {
        let Node::Expr(Expr::BinOp(operation)) = node else {
            return Vec::new();
        };
        if operation.op == Operator::Mod {
            let right = self.binop_operands(node).1;
            return dynamic_operands(&[(operation.right.as_ref(), right)]);
        }
        let mut operands: Vec<(&Expr, Option<NodeId>)> = Vec::new();
        let Node::Expr(mut expression) = *node else {
            unreachable!("a binary operation is an expression")
        };
        let mut left = None;
        while let Expr::BinOp(operation) = expression
            && operation.op == Operator::Add
        {
            let (operand_left, operand_right) = self.binop_operands(&Node::Expr(expression));
            left = operand_left;
            operands.push((operation.right.as_ref(), operand_right));
            expression = operation.left.as_ref();
        }
        operands.push((expression, left));
        dynamic_operands(&operands)
    }

    fn expression_kind(&mut self, node: &Node<'_>, expression: &Expr) -> Option<NodeId> {
        match expression {
            Expr::Name(name) => self.name(node, name),
            Expr::Attribute(attribute) => self.attribute(node, attribute),
            Expr::Call(call) => self.call(node, call),
            Expr::Lambda(lambda) => Some(self.lambda(node, lambda)),
            Expr::If(_) | Expr::BoolOp(_) => self.choice(expression, Self::expression),
            Expr::Named(named) => {
                let value = self.expression(&named.value);
                let facts = self.facts_at(&Node::Expr(&named.value));
                let Expr::Name(target) = named.target.as_ref() else {
                    unreachable!("the target of an assignment expression is a name")
                };
                self.bind(&identifier(&target.id), value, facts.0, facts.1.clone());
                self.known(node, facts.0, facts.1);
                value
            }
            Expr::Await(awaited) => {
                let value = self.expression(&awaited.value)?;
                let result = self.analysis.node(None);
                let (caller, site) = (self.caller().to_owned(), self.site(node));
                self.analysis.add_await(value, result, &caller, &site);
                Some(result)
            }
            Expr::Yield(yielded) => {
                let value = yielded
                    .value
                    .as_deref()
                    .and_then(|value| self.expression(value));
                let function = self.function.as_ref()?;
                let yield_node = function.yield_node?;
                let sent_node = function.sent_node;
                if let Some(value) = value {
                    self.analysis.add_edge(value, yield_node);
                }
                sent_node
            }
            Expr::YieldFrom(yielded) => {
                let value = self.expression(&yielded.value);
                let function = self.function.as_ref()?;
                function.yield_node?;
                let object = function.object;
                let value = value?;
                let result = self.analysis.node(None);
                let (caller, site) = (self.caller().to_owned(), self.site(node));
                self.analysis
                    .add_yield_from(value, object, result, &caller, &site);
                Some(result)
            }
            Expr::BinOp(_) => self.binary(expression),
            Expr::UnaryOp(operation) => self.unary(node, expression, operation),
            Expr::Compare(comparison) => self.compare(node, comparison),
            Expr::FString(_) => self.joined_str(node),
            Expr::Subscript(subscript) => self.subscript_expression(node, subscript),
            Expr::Tuple(tuple) => Some(self.display(node, "tuple", &tuple.elts)),
            Expr::List(list) => Some(self.display(node, "list", &list.elts)),
            Expr::Set(set) => Some(self.display(node, "set", &set.elts)),
            Expr::Dict(dict) => Some(self.dict(node, dict)),
            Expr::ListComp(_) | Expr::SetComp(_) | Expr::DictComp(_) | Expr::Generator(_) => {
                Some(self.comprehension(node))
            }
            Expr::StringLiteral(_)
            | Expr::BytesLiteral(_)
            | Expr::NumberLiteral(_)
            | Expr::BooleanLiteral(_)
            | Expr::NoneLiteral(_)
            | Expr::EllipsisLiteral(_) => self.constant_expression(expression),
            Expr::Starred(_) | Expr::Slice(_) | Expr::TString(_) => {
                self.walk(node);
                None
            }
            Expr::IpyEscapeCommand(_) => unreachable!("a module has no IPython escape"),
        }
    }

    fn constant_of(&mut self, value: Constant) -> NodeId {
        let object = self.analysis.const_object(&value);
        self.analysis.constant(object)
    }

    fn constant_expression(&mut self, expression: &Expr) -> Option<NodeId> {
        let constant = constants::literal(expression, self.source.text)
            .expect("a literal expression has a constant value");
        let value = match constant {
            SyntaxConstant::Str(text) => Constant::Str(text.code_points().into()),
            SyntaxConstant::Bytes(bytes) => Constant::Bytes(bytes.into()),
            SyntaxConstant::Int(value) => Constant::Int(value),
            _ => return None,
        };
        Some(self.constant_of(value))
    }

    pub(crate) fn walk(&mut self, node: &Node<'_>) {
        let mut pending = node.children();
        pending.reverse();
        while let Some(child) = pending.pop() {
            if is_expression(&child) {
                self.expression_at(&child);
            } else {
                let mut children = child.children();
                children.reverse();
                pending.extend(children);
            }
        }
    }

    pub(crate) fn condition(&mut self, test: &Expr) -> Option<NodeId> {
        self.condition_at(&Node::Expr(test))
    }

    pub(crate) fn facts(&self, expression: &Expr) -> Facts {
        self.facts_at(&Node::Expr(expression))
    }

    pub(crate) fn truth(&self, expression: &Expr) -> Truth {
        self.truth_at(&Node::Expr(expression))
    }

    fn merge_flow(&mut self, base: StateId, ends: &[StateId]) {
        let (_, flow) = self.flows.last_mut().expect("a builder has a flow");
        flow.merge(&mut *self.analysis, base, ends, None);
    }

    pub(crate) fn truth_at(&self, node: &Node<'_>) -> Truth {
        self.facts_at(node).0
    }

    pub(crate) fn literals_at(&self, node: &Node<'_>) -> Option<Literals> {
        self.facts_at(node).1
    }

    pub(crate) fn facts_at(&self, node: &Node<'_>) -> Facts {
        if let Some(facts) = self.expressions.facts_by_expression.get(&node_key(node)) {
            return facts.clone();
        }
        let constant = match node {
            Node::Expr(expression) => constants::literal(expression, self.source.text),
            Node::StringPiece(piece) => Some(SyntaxConstant::Str(constants::text_value(
                &piece.texts,
                self.source.text,
            ))),
            _ => None,
        };
        match constant {
            Some(constant) => (
                constant_truth(&constant),
                literal_of(&constant).map(|literal| Literals::of([literal])),
            ),
            None => UNKNOWN_FACTS,
        }
    }

    pub(crate) fn known(&mut self, node: &Node<'_>, truth: Truth, values: Option<Literals>) {
        let truth = match &values {
            Some(values) => truth_of(values.values()),
            None => truth,
        };
        if truth != UNKNOWN || values.is_some() {
            self.expressions
                .facts_by_expression
                .insert(node_key(node), (truth, values));
        }
    }

    pub(crate) fn type_checking_truth(&self, node: &Node<'_>) -> Option<bool> {
        self.expressions
            .type_checking_truth_by_test
            .get(&node_key(node))
            .copied()
    }

    fn names_type_checking(&mut self, name: &str, value: Option<NodeId>) -> bool {
        for target in TYPE_CHECKING_IMPORTS {
            let external = self.analysis.external(target, 0, false);
            if Some(self.analysis.constant(external)) == value {
                return true;
            }
        }
        let name = self.scopes.scope(self.scope).mangle(name);
        let scope = self.scopes.resolve(self.scope, &name);
        self.scopes
            .imported(scope, &name)
            .is_some_and(|imported| TYPE_CHECKING_IMPORTS.contains(&imported))
    }

    fn is_typing_module(&mut self, expression: &Expr, value: NodeId) -> bool {
        for module in TYPING_MODULES {
            let external = self.analysis.external(module, 0, false);
            if self.analysis.constant(external) == value {
                return true;
            }
        }
        let Expr::Name(name) = expression else {
            return false;
        };
        let name = self.scopes.scope(self.scope).mangle(&identifier(&name.id));
        let scope = self.scopes.resolve(self.scope, &name);
        self.scopes
            .imported(scope, &name)
            .is_some_and(|imported| TYPING_MODULES.contains(&imported))
    }

    fn name(&mut self, node: &Node<'_>, name: &ExprName) -> Option<NodeId> {
        let id = identifier(&name.id);
        let (value, facts) = self.read_name(&id);
        let falsy = facts.0 == FALSE;
        self.known(node, facts.0, facts.1);
        if falsy && self.names_type_checking(&id, value) {
            self.expressions
                .type_checking_truth_by_test
                .insert(node_key(node), true);
        }
        value
    }

    fn attribute(&mut self, node: &Node<'_>, attribute: &ExprAttribute) -> Option<NodeId> {
        let attr = identifier(attribute.attr.as_str());
        if attr == "__dict__"
            && let Expr::Name(name) = attribute.value.as_ref()
        {
            self.namespace_read(&identifier(&name.id));
        }
        let base = self.expression(&attribute.value)?;
        if attr == "TYPE_CHECKING" && self.is_typing_module(&attribute.value, base) {
            self.known(node, UNKNOWN, Some(Literals::of([Literal::Bool(false)])));
            self.expressions
                .type_checking_truth_by_test
                .insert(node_key(node), true);
        }
        let value = self.analysis.node(None);
        let attr = self.scopes.scope(self.scope).mangle(&attr);
        let (caller, site) = (self.caller().to_owned(), self.site(node));
        self.analysis.add_load(base, &attr, value, &caller, &site);
        Some(value)
    }

    fn call(&mut self, node: &Node<'_>, call: &ExprCall) -> Option<NodeId> {
        let arguments = &call.arguments;
        if let [Expr::Name(argument)] = &arguments.args[..]
            && self.is_builtin_reference(&call.func, "vars")
        {
            self.namespace_read(&identifier(&argument.id));
        }
        let callee = self.expression(&call.func);
        let mut args = self.implicit_super_arguments(node, call);
        let mut star: Vec<(Option<NodeId>, bool)> = Vec::new();
        let mut nones: Vec<u32> = Vec::new();
        for (index, argument) in arguments.args.iter().enumerate() {
            if matches!(argument, Expr::NoneLiteral(_))
                && !arguments.args[..index]
                    .iter()
                    .any(|earlier| matches!(earlier, Expr::Starred(_)))
            {
                nones.push(u32::try_from(index).expect("an argument index fits u32"));
            }
        }
        for argument in argument_nodes(call) {
            if let Node::Expr(Expr::Starred(starred)) = argument {
                let value = self.expression(&starred.value);
                star.push((value, true));
                if let Some(value) = value {
                    let (caller, site) = (self.caller().to_owned(), self.site(node));
                    self.analysis.add_length_hint(value, &caller, &site);
                }
            } else if !star.is_empty() {
                let value = self.expression_at(&argument);
                star.push((value, false));
            } else {
                args.push(self.expression_at(&argument));
            }
        }
        let mut keywords: Vec<(Box<str>, Option<NodeId>)> = Vec::new();
        let mut double_star: Vec<Option<NodeId>> = Vec::new();
        for keyword in arguments.keywords.iter() {
            let value = self.expression(&keyword.value);
            match &keyword.arg {
                None => double_star.push(value),
                Some(name) => keywords.push((identifier(name.as_str()).into(), value)),
            }
        }
        self.class_test(call, &args);
        if let Expr::Attribute(method) = call.func.as_ref()
            && method.attr.as_str() == "format"
            && is_str_constant(&method.value)
        {
            self.format_fields(node, &method.value, &args, &keywords);
        }
        let caller = self.caller().to_owned();
        let site = self.site(node);
        let Some(callee) = callee else {
            self.analysis.add_call(&Call {
                callee: None,
                caller: &caller,
                args: &[],
                keywords: &[],
                dst: None,
                site: &site,
                star: &[],
                double_star: &[],
                decorator: false,
                applies: false,
            });
            return None;
        };
        if let Some(module) = self.literal_import(call) {
            put(
                &mut self.analysis.tables().literal_imports,
                site.clone().into(),
                module,
            );
        }
        if !nones.is_empty() {
            put(
                &mut self.analysis.tables().none_arguments,
                (caller.clone().into(), site.clone().into()),
                nones,
            );
        }
        let mut none_keywords: Vec<Box<str>> = Vec::new();
        for keyword in arguments.keywords.iter() {
            if let Some(name) = &keyword.arg
                && matches!(keyword.value, Expr::NoneLiteral(_))
            {
                let name: Box<str> = identifier(name.as_str()).into();
                if !none_keywords.contains(&name) {
                    none_keywords.push(name);
                }
            }
        }
        if !none_keywords.is_empty() {
            put(
                &mut self.analysis.tables().none_keywords,
                (caller.clone().into(), site.clone().into()),
                none_keywords,
            );
        }
        let result = self.analysis.node(None);
        let applies = matches!(call.func.as_ref(), Expr::Call(_)) && args.len() == 1;
        let applies = applies && keywords.is_empty() && star.is_empty() && double_star.is_empty();
        self.analysis.add_call(&Call {
            callee: Some(callee),
            caller: &caller,
            args: &args,
            keywords: &keywords,
            dst: Some(result),
            site: &site,
            star: &star,
            double_star: &double_star,
            decorator: false,
            applies,
        });
        Some(result)
    }

    fn format_fields(
        &mut self,
        node: &Node<'_>,
        text: &Expr,
        args: &[Option<NodeId>],
        keywords: &[(Box<str>, Option<NodeId>)],
    ) {
        let Some(SyntaxConstant::Str(text)) = constants::literal(text, self.source.text) else {
            unreachable!("the receiver of the format method is a str literal")
        };
        let mut auto = 0;
        for (index, field) in format_fields(text.code_points()).into_iter().enumerate() {
            let first = match field.first {
                FieldName::Name(name) if name.is_empty() => {
                    auto += 1;
                    FieldName::Index(Some(auto - 1))
                }
                other => other,
            };
            let value = match first {
                FieldName::Index(Some(position)) => args.get(position).copied().flatten(),
                FieldName::Index(None) => None,
                FieldName::Name(name) => keywords
                    .iter()
                    .rev()
                    .find(|(keyword, _)| keyword.chars().map(u32::from).eq(name.iter().copied()))
                    .and_then(|(_, value)| *value),
            };
            let (Some(mut value), Some(attributes)) = (value, field.attributes) else {
                continue;
            };
            let caller = self.caller().to_owned();
            let site = format!("{}#{index}", self.site(node));
            for attr in attributes {
                let loaded = self.analysis.node(None);
                self.analysis
                    .add_load_text(value, &attr, loaded, &caller, &site);
                value = loaded;
            }
            let kind = format_conversion(field.conversion);
            let spec = self.constant_of(Constant::Str(field.spec.into()));
            self.analysis
                .add_conversion(value, kind, &caller, &site, Some(spec));
        }
    }

    fn implicit_super_arguments(
        &mut self,
        node: &Node<'_>,
        call: &ExprCall,
    ) -> Vec<Option<NodeId>> {
        if !call.arguments.args.is_empty() || !call.arguments.keywords.is_empty() {
            return Vec::new();
        }
        if !self.is_builtin_reference(&call.func, "super") {
            return Vec::new();
        }
        let Some(function) = self.function.as_ref() else {
            return Vec::new();
        };
        let Some(first) = function.signature.positional.first() else {
            return Vec::new();
        };
        let first = function.parameters[first];
        let cell = self.load_name("__class__");
        let site = self.site(node);
        add_once(&mut self.analysis.tables().zero_argument_super, site.into());
        vec![cell, Some(first)]
    }

    fn lambda(&mut self, node: &Node<'_>, lambda: &ExprLambda) -> NodeId {
        self.known(node, TRUE, None);
        let scope = self.scopes.scope_of(node);
        let empty = Parameters::default();
        let parameters = lambda.parameters.as_deref().unwrap_or(&empty);
        let function = self.function_object(node, parameters, scope, "<lambda>", false);
        let return_node = function.return_node;
        let object = function.object;
        let value = self.inside(scope, Some(function), |builder| {
            if builder.returns_parameter(&lambda.body) {
                None
            } else {
                builder.expression(&lambda.body)
            }
        });
        if let Some(value) = value {
            self.analysis.add_edge(value, return_node);
        }
        self.analysis.constant(object)
    }

    pub(crate) fn condition_at(&mut self, node: &Node<'_>) -> Option<NodeId> {
        let value = self.expression_at(node);
        if let Some(value) = value {
            let (caller, site) = (self.caller().to_owned(), self.site(node));
            self.analysis.add_truth(value, &caller, &site);
        }
        value
    }

    pub(crate) fn choice(
        &mut self,
        expression: &Expr,
        evaluate: impl FnMut(&mut Self, &Expr) -> Option<NodeId>,
    ) -> Option<NodeId> {
        let node = Node::Expr(expression);
        match expression {
            Expr::If(choice) => self.choose_arm(&node, choice, evaluate),
            Expr::BoolOp(choice) => self.choose_operand(&node, choice, evaluate),
            _ => unreachable!("a choice is a conditional expression or a boolean operation"),
        }
    }

    fn choose_arm(
        &mut self,
        node: &Node<'_>,
        choice: &ExprIf,
        mut evaluate: impl FnMut(&mut Self, &Expr) -> Option<NodeId>,
    ) -> Option<NodeId> {
        let test = Node::Expr(&choice.test);
        self.condition_at(&test);
        let truth = self.truth_at(&test);
        let base = self.current_flow().state;
        let mut values = Vec::new();
        let mut ends = Vec::new();
        let mut facts = Vec::new();
        for (arm, runs, positive) in [
            (&choice.body, truth & TRUE, true),
            (&choice.orelse, truth & FALSE, false),
        ] {
            if runs == 0 {
                continue;
            }
            self.flow().branch(base);
            self.narrow(&choice.test, positive, None);
            values.push(evaluate(self, arm));
            let arm = Node::Expr(arm);
            ends.push(self.current_flow().state);
            facts.push(self.facts_at(&arm));
        }
        self.merge_flow(base, &ends);
        let (truth, values_known) = join_facts(&facts);
        self.known(node, truth, values_known);
        self.join(&values)
    }

    fn choose_operand(
        &mut self,
        node: &Node<'_>,
        choice: &ExprBoolOp,
        mut evaluate: impl FnMut(&mut Self, &Expr) -> Option<NodeId>,
    ) -> Option<NodeId> {
        let decides = if choice.op == BoolOp::Or { TRUE } else { FALSE };
        let goes_on = UNKNOWN ^ decides;
        let base = self.current_flow().state;
        let mut values = Vec::new();
        let mut ends = Vec::new();
        let mut facts: Vec<Facts> = Vec::new();
        let last = choice.values.len() - 1;
        for (index, operand) in choice.values.iter().enumerate() {
            let operand_node = Node::Expr(operand);
            if index > 0 {
                ends.push(self.current_flow().state);
                let state = self.current_flow().state;
                self.flow().branch(state);
                self.narrow(&choice.values[index - 1], goes_on == TRUE, None);
            }
            let value = evaluate(self, operand);
            if index < last {
                let mut tested = value;
                if tested.is_none() && matches!(operand, Expr::Name(_)) {
                    tested = self.expression_at(&operand_node);
                }
                if let Some(tested) = tested {
                    let (caller, site) = (self.caller().to_owned(), self.site(&operand_node));
                    self.analysis.add_truth(tested, &caller, &site);
                }
            }
            let (operand_truth, literals) = self.facts_at(&operand_node);
            if index == last {
                values.push(value);
                facts.push((operand_truth, literals));
                break;
            }
            if operand_truth & decides != 0 {
                values.push(value);
                let literals = literals.map(|literals| {
                    Literals::of(
                        literals
                            .values()
                            .iter()
                            .filter(|literal| truth_of(std::slice::from_ref(literal)) == decides)
                            .cloned(),
                    )
                });
                facts.push((decides, literals));
            }
            if operand_truth & goes_on == 0 {
                break;
            }
        }
        ends.push(self.current_flow().state);
        self.merge_flow(base, &ends);
        let (truth, values_known) = join_facts(&facts);
        self.known(node, truth, values_known);
        self.join(&values)
    }

    fn binary(&mut self, expression: &Expr) -> Option<NodeId> {
        let mut chain: Vec<(&Expr, &ExprBinOp)> = Vec::new();
        let mut left = expression;
        while let Expr::BinOp(operation) = left {
            chain.push((left, operation));
            left = operation.left.as_ref();
        }
        let mut value = self.expression(left);
        let constants = self.pattern_affixes(&Node::Expr(expression)).is_none();
        for (expression, operation) in chain.into_iter().rev() {
            let right = self.expression(&operation.right);
            let node = Node::Expr(expression);
            self.expressions
                .operand_nodes_by_binop
                .insert(node_key(&node), (value, right));
            let site = self.site(&node);
            value = self.operate(value, right, operation.op, &site, false, constants);
        }
        value
    }

    pub(crate) fn binop_operands(&self, node: &Node<'_>) -> (Option<NodeId>, Option<NodeId>) {
        self.expressions.operand_nodes_by_binop[&node_key(node)]
    }

    fn unary(
        &mut self,
        node: &Node<'_>,
        expression: &Expr,
        operation: &ExprUnaryOp,
    ) -> Option<NodeId> {
        if let Some(value) = int_literal(expression, self.source.text) {
            self.known(
                node,
                UNKNOWN,
                Some(Literals::of([Literal::Int(value.clone())])),
            );
            return Some(self.constant_of(Constant::Int(value)));
        }
        let operand_node = Node::Expr(&operation.operand);
        let operand = self.expression_at(&operand_node);
        if operation.op == UnaryOp::Not {
            if let Some(operand) = operand {
                let (caller, site) = (self.caller().to_owned(), self.site(node));
                self.analysis.add_truth(operand, &caller, &site);
            }
            if let Some(truth) = self.type_checking_truth(&operand_node) {
                self.expressions
                    .type_checking_truth_by_test
                    .insert(node_key(node), !truth);
            }
            let truth = self.truth_at(&operand_node);
            let mut results = Vec::new();
            if truth & TRUE != 0 {
                results.push(Literal::Bool(false));
            }
            if truth & FALSE != 0 {
                results.push(Literal::Bool(true));
            }
            self.known(node, UNKNOWN, Some(Literals::of(results)));
        }
        let method = match operation.op {
            UnaryOp::USub => "__neg__",
            UnaryOp::UAdd => "__pos__",
            UnaryOp::Invert => "__invert__",
            UnaryOp::Not => return None,
        };
        let operand = operand?;
        let result = self.analysis.node(None);
        let (caller, site) = (self.caller().to_owned(), self.site(node));
        self.analysis.add_operator(&Operation {
            left: Some(operand),
            right: None,
            method,
            reflected: None,
            inplace: false,
            dst: result,
            caller: &caller,
            site: &site,
            unary: true,
            constants: false,
        });
        Some(result)
    }

    fn compare(&mut self, node: &Node<'_>, comparison: &ExprCompare) -> Option<NodeId> {
        let operands = &comparison.operands;
        let mut left = self.expression(&operands[0]);
        let mut results = Vec::new();
        let base = self.current_flow().state;
        let mut ends = Vec::new();
        let mut outcomes: Option<Vec<bool>> = Some(Vec::new());
        let last = comparison.ops.len() - 1;
        for (index, (&operator, comparator)) in
            comparison.ops.iter().zip(operands[1..].iter()).enumerate()
        {
            let previous = &operands[index];
            if index > 0 {
                ends.push(self.current_flow().state);
                let state = self.current_flow().state;
                self.flow().branch(state);
            }
            let right = self.expression(comparator);
            let outcome = self.comparison(operator, previous, comparator);
            let site = self.span(&Node::Expr(previous), &Node::Expr(comparator));
            outcomes = match (outcomes, &outcome) {
                (Some(mut known), Some(outcome)) => {
                    for &result in outcome {
                        if !known.contains(&result) {
                            known.push(result);
                        }
                    }
                    Some(known)
                }
                _ => None,
            };
            if comparison_methods(operator).is_some() {
                if let Some(result) = self.rich_comparison(left, right, operator, &site) {
                    results.push(Some(result));
                    if index < last {
                        let caller = self.caller().to_owned();
                        self.analysis.add_truth(result, &caller, &site);
                    }
                }
            } else if matches!(operator, CmpOp::In | CmpOp::NotIn) {
                let container = match right {
                    Some(right) => right,
                    None => self.analysis.node(None),
                };
                let contained = self.analysis.node(None);
                let caller = self.caller().to_owned();
                self.analysis.add_operator(&Operation {
                    left: Some(container),
                    right: left,
                    method: "__contains__",
                    reflected: None,
                    inplace: false,
                    dst: contained,
                    caller: &caller,
                    site: &site,
                    unary: false,
                    constants: false,
                });
                self.analysis.add_truth(contained, &caller, &site);
            }
            left = right;
            if outcome.as_deref() == Some(&[false]) {
                outcomes = outcomes.map(|_| vec![false]);
                break;
            }
        }
        ends.push(self.current_flow().state);
        self.merge_flow(base, &ends);
        if let Some(outcomes) = outcomes {
            self.known(
                node,
                UNKNOWN,
                Some(Literals::of(outcomes.into_iter().map(Literal::Bool))),
            );
        }
        self.join(&results)
    }

    pub(crate) fn rich_comparison(
        &mut self,
        left: Option<NodeId>,
        right: Option<NodeId>,
        operator: CmpOp,
        site: &str,
    ) -> Option<NodeId> {
        if left.is_none() && right.is_none() {
            return None;
        }
        let (method, reflected) =
            comparison_methods(operator).expect("a rich comparison has special methods");
        let result = self.analysis.node(None);
        let caller = self.caller().to_owned();
        self.analysis.add_operator(&Operation {
            left,
            right,
            method,
            reflected: Some(reflected),
            inplace: false,
            dst: result,
            caller: &caller,
            site,
            unary: false,
            constants: false,
        });
        Some(result)
    }

    fn comparison(&self, operator: CmpOp, left: &Expr, right: &Expr) -> Option<Vec<bool>> {
        let lefts = self.literals_at(&Node::Expr(left))?;
        let lefts = lefts.values();
        if lefts.is_empty() {
            return None;
        }
        let mut outcome: Vec<bool> = Vec::new();
        let mut add = |result: bool| {
            if !outcome.contains(&result) {
                outcome.push(result);
            }
        };
        if matches!(operator, CmpOp::In | CmpOp::NotIn) {
            let members = self.members(right)?;
            for value in lefts {
                let found = members.iter().any(|member| equal(value, member));
                add(if operator == CmpOp::NotIn {
                    !found
                } else {
                    found
                });
            }
            return Some(outcome);
        }
        let rights = self.literals_at(&Node::Expr(right))?;
        let rights = rights.values();
        if rights.is_empty() {
            return None;
        }
        if matches!(operator, CmpOp::Is | CmpOp::IsNot)
            && !lefts.iter().chain(rights).all(has_fixed_identity)
        {
            return None;
        }
        for a in lefts {
            for b in rights {
                add(compare(operator, a, b)?);
            }
        }
        Some(outcome)
    }

    fn members(&self, node: &Expr) -> Option<Vec<Literal>> {
        let elements = match node {
            Expr::Tuple(tuple) => &tuple.elts,
            Expr::List(list) => &list.elts,
            Expr::Set(set) => &set.elts,
            _ => return None,
        };
        let mut members = Vec::new();
        for element in elements {
            let literals = self.literals_at(&Node::Expr(element))?;
            if literals.values().len() != 1 {
                return None;
            }
            members.extend(literals.values().iter().cloned());
        }
        Some(members)
    }

    fn joined_str(&mut self, node: &Node<'_>) -> Option<NodeId> {
        let values = node.children();
        if values
            .iter()
            .all(|value| matches!(value, Node::StringPiece(_)))
        {
            let mut text: Vec<u32> = Vec::new();
            for value in &values {
                let Node::StringPiece(piece) = value else {
                    unreachable!("every value is a piece of text")
                };
                text.extend(constants::text_value(&piece.texts, self.source.text).code_points());
            }
            self.known(
                node,
                UNKNOWN,
                Some(Literals::of([Literal::Str(text.clone().into())])),
            );
            return Some(self.constant_of(Constant::Str(text.into())));
        }
        for value in &values {
            let Node::Interpolation(element, Strings::Joined, raw) = value else {
                continue;
            };
            let operand = self.expression(&element.expression);
            let spec = match &element.format_spec {
                Some(spec) => self.expression_at(&Node::FormatSpec(spec, *raw)),
                None => Some(self.constant_of(Constant::Str(Box::new([])))),
            };
            if let Some(operand) = operand {
                let conversion = match element.conversion {
                    ConversionFlag::None
                        if element.debug_text.is_some() && element.format_spec.is_none() =>
                    {
                        ConversionFlag::Repr
                    }
                    other => other,
                };
                let kind = fstring_conversion(conversion);
                let (caller, site) = (self.caller().to_owned(), self.site(value));
                self.analysis
                    .add_conversion(operand, kind, &caller, &site, spec);
            }
        }
        if self.pattern_affixes(node).is_some() {
            return None;
        }
        let typed = self.analysis.typed("builtins.str");
        Some(self.analysis.constant(typed))
    }

    fn subscript_expression(
        &mut self,
        node: &Node<'_>,
        subscript: &ExprSubscript,
    ) -> Option<NodeId> {
        let Node::Expr(expression) = node else {
            unreachable!("a subscript is an expression")
        };
        let (base, index) = self.subscript_parts(expression);
        let base = base?;
        let result = self.analysis.node(None);
        self.subscript(base, &index, Some(result), None, expression, false);
        if let Some(module) = self.loaded_module(subscript) {
            let external = self.analysis.external(&module, 0, false);
            self.analysis.add_object(result, external);
        }
        Some(result)
    }

    fn loaded_module(&self, subscript: &ExprSubscript) -> Option<String> {
        if self.imported_function(&subscript.value).as_deref() != Some("sys.modules") {
            return None;
        }
        let Some(SyntaxConstant::Str(key)) = constants::literal(&subscript.slice, self.source.text)
        else {
            return None;
        };
        let key: String = key
            .code_points()
            .iter()
            .map(|&point| char::from_u32(point))
            .collect::<Option<String>>()?;
        if !key.split('.').all(pycg_syntax::names::is_identifier) {
            return None;
        }
        let first = key.split('.').next().expect("a split has a first part");
        if first
            == self
                .module_name
                .split('.')
                .next()
                .expect("a module name has a first part")
        {
            return None;
        }
        Some(key)
    }

    pub(crate) fn imported_function(&self, function: &Expr) -> Option<String> {
        match function {
            Expr::Name(name) => self.import_of(&identifier(&name.id)).map(str::to_owned),
            Expr::Attribute(attribute) => {
                let Expr::Name(name) = attribute.value.as_ref() else {
                    return None;
                };
                let module = self.import_of(&identifier(&name.id))?;
                Some(format!("{module}.{}", identifier(attribute.attr.as_str())))
            }
            _ => None,
        }
    }

    fn import_of(&self, name: &str) -> Option<&str> {
        let name = self.scopes.scope(self.scope).mangle(name);
        self.scopes
            .imported(self.scopes.resolve(self.scope, &name), &name)
    }

    fn display(&mut self, node: &Node<'_>, kind: &str, elements: &[Expr]) -> NodeId {
        let mut positional = kind != "set";
        let unpacked = elements
            .iter()
            .any(|element| matches!(element, Expr::Starred(_)));
        if kind == "tuple" && !unpacked {
            self.known(node, if elements.is_empty() { FALSE } else { TRUE }, None);
        }
        let length = (positional && !unpacked).then_some(elements.len());
        let site = self.site(node);
        let container = self.analysis.container(kind, &site, length);
        let mut unordered = Vec::new();
        let mut hashed = Vec::new();
        for (index, element) in elements.iter().enumerate() {
            if let Expr::Starred(starred) = element {
                if kind == "set" {
                    if let Some(entering) = self.entering(&starred.value) {
                        unordered.extend([entering.0, entering.1]);
                        hashed.push(entering.0);
                    }
                    continue;
                }
                positional = false;
                if let Some(elements) = self.elements_at(&Node::Expr(&starred.value), false, true) {
                    unordered.push(elements);
                }
                continue;
            }
            let Some(value) = self.expression(element) else {
                continue;
            };
            if positional {
                let index = i64::try_from(index).expect("an element index fits i64");
                let element = self.analysis.element(container, &Key::Index(index));
                self.analysis.add_edge(value, element);
            } else {
                unordered.push(value);
                hashed.push(value);
            }
        }
        for &value in &unordered {
            let unknown = self.analysis.unknown(container);
            self.analysis.add_edge(value, unknown);
        }
        if kind == "set" && !hashed.is_empty() {
            let keys = self.analysis.node(None);
            let stored = self.analysis.node(None);
            for &value in &hashed {
                self.analysis.add_edge(value, keys);
            }
            for &value in &unordered {
                self.analysis.add_edge(value, stored);
            }
            let caller = self.caller().to_owned();
            self.analysis.add_hash(keys, &caller, &site, Some(stored));
        }
        self.analysis.constant(container)
    }

    pub(crate) fn entering(&mut self, iterable: &Expr) -> Option<(NodeId, NodeId)> {
        let value = self.expression(iterable)?;
        let site = self.site(&Node::Expr(iterable));
        let caller = self.caller().to_owned();
        add_once(
            &mut self.analysis.tables().iterated_expressions,
            (caller.clone().into(), site.clone().into()),
        );
        Some(
            self.analysis
                .entering_keys(value, ("unpacked", &site), &caller, &site),
        )
    }

    fn dict(&mut self, node: &Node<'_>, dict: &ExprDict) -> NodeId {
        let site = self.site(node);
        let container = self.analysis.container("dict", &site, None);
        for item in &dict.items {
            let key_node = item.key.as_ref().and_then(|key| self.expression(key));
            let value_node = self.expression(&item.value);
            let Some(key) = &item.key else {
                if let Some(value_node) = value_node {
                    let site = self.site(&Node::Expr(&item.value));
                    let caller = self.caller().to_owned();
                    self.analysis
                        .add_dict_items(container, value_node, &caller, &site);
                    add_once(
                        &mut self.analysis.tables().iterated_expressions,
                        (caller.into(), site.into()),
                    );
                }
                continue;
            };
            self.analysis.write_keyed(container, key_node, value_node);
            if let Some(key_node) = key_node {
                let stored = self.analysis.keys(container);
                let (caller, site) = (self.caller().to_owned(), self.site(&Node::Expr(key)));
                self.analysis
                    .add_hash(key_node, &caller, &site, Some(stored));
            }
        }
        self.analysis.constant(container)
    }

    pub(crate) fn elements_of(&mut self, iterable: &Expr, is_async: bool) -> Option<NodeId> {
        self.elements_at(&Node::Expr(iterable), is_async, false)
    }

    pub(crate) fn elements_at(
        &mut self,
        iterable: &Node<'_>,
        is_async: bool,
        length_hint: bool,
    ) -> Option<NodeId> {
        let value = self.expression_at(iterable)?;
        let elements = self.analysis.node(None);
        let site = self.site(iterable);
        let caller = self.caller().to_owned();
        if length_hint {
            self.analysis.add_length_hint(value, &caller, &site);
        }
        self.analysis
            .add_iteration(value, elements, &caller, &site, is_async);
        add_once(
            &mut self.analysis.tables().iterated_expressions,
            (caller.into(), site.into()),
        );
        Some(elements)
    }

    pub(crate) fn subscript_parts(&mut self, target: &Expr) -> (Option<NodeId>, SubscriptIndex) {
        let Expr::Subscript(subscript) = target else {
            unreachable!("only a subscript has subscript parts")
        };
        let base = self.expression(&subscript.value);
        if let Expr::Slice(slice) = subscript.slice.as_ref() {
            for part in [&slice.lower, &slice.upper, &slice.step]
                .into_iter()
                .flatten()
            {
                self.expression(part);
            }
            return (base, SubscriptIndex::Bounds(self.slice_bounds(slice)));
        }
        (base, SubscriptIndex::Key(self.expression(&subscript.slice)))
    }

    fn slice_bounds(&self, slice: &ExprSlice) -> Option<(Option<BigInt>, Option<BigInt>)> {
        if slice.step.is_some() {
            return None;
        }
        let mut bounds = [None, None];
        for (bound, part) in bounds.iter_mut().zip([&slice.lower, &slice.upper]) {
            if let Some(part) = part {
                *bound = Some(int_literal(part, self.source.text)?);
            }
        }
        let [lower, upper] = bounds;
        Some((lower, upper))
    }

    pub(crate) fn subscript(
        &mut self,
        base: NodeId,
        index: &SubscriptIndex,
        dst: Option<NodeId>,
        src: Option<NodeId>,
        target: &Expr,
        delete: bool,
    ) {
        assert!(
            dst.is_some() || src.is_some() || delete,
            "a subscript does nothing"
        );
        let (caller, site) = (self.caller().to_owned(), self.site(&Node::Expr(target)));
        match index {
            SubscriptIndex::Bounds(bounds) => self.analysis.add_slice(&Slice {
                base,
                bounds: bounds.as_ref(),
                dst,
                src,
                caller: &caller,
                site: &site,
                delete,
            }),
            SubscriptIndex::Key(key) => self.analysis.add_subscript(&Subscript {
                base,
                key: *key,
                dst,
                src,
                caller: &caller,
                site: &site,
                delete,
            }),
        }
    }

    pub(crate) fn operator(
        &mut self,
        left: Option<NodeId>,
        right: Option<NodeId>,
        augmented: &StmtAugAssign,
    ) -> Option<NodeId> {
        let at = position(augmented.range, self.source.lines);
        let site = format!(
            "{}:{}:{}#{}:{}",
            self.module_name, at.lineno, at.col_offset, at.end_lineno, at.end_col_offset
        );
        self.operate(left, right, augmented.op, &site, true, true)
    }

    fn operate(
        &mut self,
        left: Option<NodeId>,
        right: Option<NodeId>,
        operator: Operator,
        site: &str,
        inplace: bool,
        constants: bool,
    ) -> Option<NodeId> {
        if left.is_none() && right.is_none() {
            return None;
        }
        let name = special_method(operator);
        let caller = self.caller().to_owned();
        if let (Operator::Mod, Some(left), Some(right)) = (operator, left, right) {
            self.analysis.add_percent(left, right, &caller, site);
        }
        let result = self.analysis.node(None);
        self.analysis.add_operator(&Operation {
            left,
            right,
            method: &format!("__{name}__"),
            reflected: Some(&format!("__r{name}__")),
            inplace,
            dst: result,
            caller: &caller,
            site,
            unary: false,
            constants,
        });
        Some(result)
    }
}

fn is_expression(node: &Node<'_>) -> bool {
    matches!(
        node,
        Node::Expr(_)
            | Node::GeneratorArgument(..)
            | Node::StringPiece(_)
            | Node::Interpolation(..)
            | Node::FormatSpec(..)
    )
}

fn dynamic_operands(operands: &[(&Expr, Option<NodeId>)]) -> Vec<Option<NodeId>> {
    let mut found = Vec::new();
    for &(expression, node) in operands {
        match expression {
            Expr::StringLiteral(_)
            | Expr::BytesLiteral(_)
            | Expr::NumberLiteral(_)
            | Expr::BooleanLiteral(_)
            | Expr::NoneLiteral(_)
            | Expr::EllipsisLiteral(_) => continue,
            Expr::FString(_) => {
                let values = Node::Expr(expression).children();
                if values.len() != 1 || matches!(values[0], Node::StringPiece(_)) {
                    continue;
                }
                found.push(None);
            }
            _ => found.push(node),
        }
    }
    found
}

pub(crate) fn add_once<T: PartialEq>(items: &mut Vec<T>, item: T) {
    if !items.contains(&item) {
        items.push(item);
    }
}

fn put<K: PartialEq, V>(entries: &mut Vec<(K, V)>, key: K, value: V) {
    match entries.iter_mut().find(|(existing, _)| *existing == key) {
        Some(entry) => entry.1 = value,
        None => entries.push((key, value)),
    }
}
