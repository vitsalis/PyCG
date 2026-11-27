use pycg_solver::NodeId;
use ruff_python_ast::{Expr, ExprCall};

use crate::builder::ModuleBuilder;
use crate::builder::calls::Analysis;
use crate::builder::flow::StateId;

impl<A: Analysis> ModuleBuilder<'_, '_, A> {
    pub(crate) fn class_test(&mut self, _call: &ExprCall, _args: &[Option<NodeId>]) {}

    pub(crate) fn narrow(&mut self, _test: &Expr, _holds: bool, _state: Option<StateId>) {}
}
