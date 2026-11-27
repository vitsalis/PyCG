use pycg_solver::NodeId;
use pycg_syntax::constants::{Constant as Literal, literal};
use pycg_syntax::names::identifier;
use pycg_syntax::tree::Node;
use ruff_python_ast::Expr;

use crate::builder::calls::{Analysis, Constant};
use crate::builder::flow::StateId;
use crate::builder::{Facts, ModuleBuilder, UNKNOWN_FACTS};

pub(crate) type SubscriptIndex = Option<NodeId>;

impl<A: Analysis> ModuleBuilder<'_, '_, A> {
    pub(crate) fn expression(&mut self, expression: &Expr) -> Option<NodeId> {
        match expression {
            Expr::Name(name) => self.load_name(&identifier(name.id.as_str())),
            Expr::Call(call) => {
                self.walk(&Node::Expr(expression));
                self.literal_import(call)
            }
            _ => match literal(expression, self.source.text) {
                Some(Literal::Str(text)) => {
                    Some(self.constant_node(Constant::Str(text.code_points().into())))
                }
                Some(Literal::Bytes(bytes)) => {
                    Some(self.constant_node(Constant::Bytes(bytes.into())))
                }
                Some(Literal::Int(value)) => Some(self.constant_node(Constant::Int(value))),
                Some(_) => None,
                None => {
                    self.walk(&Node::Expr(expression));
                    None
                }
            },
        }
    }

    fn constant_node(&mut self, value: Constant) -> NodeId {
        let object = self.analysis.const_object(&value);
        self.analysis.constant(object)
    }

    pub(crate) fn walk(&mut self, node: &Node<'_>) {
        for child in node.children() {
            match child {
                Node::Expr(expression) => {
                    self.expression(expression);
                }
                other => self.walk(&other),
            }
        }
    }

    pub(crate) fn choice(
        &mut self,
        node: &Expr,
        mut evaluate: impl FnMut(&mut Self, &Expr) -> Option<NodeId>,
    ) -> Option<NodeId> {
        evaluate(self, node)
    }

    pub(crate) fn condition(&mut self, test: &Expr) -> Option<NodeId> {
        let value = self.expression(test);
        if let Some(value) = value {
            let caller = self.caller().to_owned();
            let site = self.site(&Node::Expr(test));
            self.analysis.add_truth(value, &caller, &site);
        }
        value
    }

    pub(crate) fn facts(&self, _expression: &Expr) -> Facts {
        UNKNOWN_FACTS
    }

    pub(crate) fn truth(&self, expression: &Expr) -> u8 {
        self.facts(expression).0
    }

    pub(crate) fn alias_form(&mut self, _value: &Expr) -> Option<NodeId> {
        None
    }

    pub(crate) fn stub_variable(&mut self, _target: &Expr) -> Option<NodeId> {
        None
    }

    pub(crate) fn declared(
        &mut self,
        _annotation: Option<NodeId>,
        _target: &Expr,
    ) -> Option<NodeId> {
        None
    }

    pub(crate) fn operator(
        &mut self,
        _left: Option<NodeId>,
        _right: Option<NodeId>,
        _statement: &ruff_python_ast::StmtAugAssign,
    ) -> Option<NodeId> {
        None
    }

    pub(crate) fn subscript_parts(&mut self, target: &Expr) -> (Option<NodeId>, SubscriptIndex) {
        if let Expr::Subscript(subscript) = target {
            let base = self.expression(&subscript.value);
            let index = self.expression(&subscript.slice);
            return (base, index);
        }
        (None, None)
    }

    pub(crate) fn subscript(
        &mut self,
        _base: NodeId,
        _index: &SubscriptIndex,
        _dst: Option<NodeId>,
        _src: Option<NodeId>,
        _target: &Expr,
        _delete: bool,
    ) {
    }

    pub(crate) fn elements_of(&mut self, iterable: &Expr, _is_async: bool) -> Option<NodeId> {
        self.expression(iterable)
    }

    pub(crate) fn annotation(&mut self, _expression: &Expr) -> Option<NodeId> {
        None
    }

    pub(crate) fn narrow(&mut self, _test: &Expr, _positive: bool, _state: Option<StateId>) {}
}
