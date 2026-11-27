use pycg_solver::NodeId;
use ruff_python_ast::Expr;

use crate::builder::ModuleBuilder;
use crate::builder::calls::Analysis;

impl<A: Analysis> ModuleBuilder<'_, '_, A> {
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

    pub(crate) fn annotation(&mut self, _expression: &Expr) -> Option<NodeId> {
        None
    }
}
