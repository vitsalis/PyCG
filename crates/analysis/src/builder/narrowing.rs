use pycg_solver::NodeId;
use pycg_syntax::names::identifier;
use pycg_syntax::tree::Node;
use ruff_python_ast::{BoolOp, Expr, ExprCall, UnaryOp};
use rustc_hash::FxHashMap;

use crate::builder::ModuleBuilder;
use crate::builder::calls::Analysis;
use crate::builder::flow::{Definition, DefinitionId, StateId, UNKNOWN};

const CLASS_TESTS: [(&str, bool); 2] = [("isinstance", false), ("issubclass", true)];
const CLASS_PREDICATES: [(&str, &str); 1] = [("inspect.iscoroutine", "types.CoroutineType")];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Tested {
    Classes(Option<NodeId>),
    Callable,
}

#[derive(Clone, Debug)]
struct ClassTest {
    name: String,
    definition: DefinitionId,
    value: Option<NodeId>,
    tested: Tested,
    as_class: bool,
}

#[derive(Debug, Default)]
pub(crate) struct ClassTests {
    by_call: FxHashMap<usize, ClassTest>,
    narrowed: FxHashMap<(usize, bool), NodeId>,
}

fn call_key(call: &ExprCall) -> usize {
    std::ptr::from_ref(call).addr()
}

fn names_classes(node: &Expr) -> bool {
    let mut pending = vec![node];
    while let Some(node) = pending.pop() {
        let mut node = node;
        if let Expr::Tuple(tuple) = node {
            pending.extend(tuple.elts.iter());
            continue;
        }
        while let Expr::Attribute(attribute) = node {
            node = &attribute.value;
        }
        if !matches!(node, Expr::Name(_)) {
            return false;
        }
    }
    true
}

impl<A: Analysis> ModuleBuilder<'_, '_, A> {
    pub(crate) fn class_test(&mut self, call: &ExprCall, args: &[Option<NodeId>]) {
        let positional = &call.arguments.args;
        if !call.arguments.keywords.is_empty()
            || positional.is_empty()
            || positional.len() != args.len()
        {
            return;
        }
        let Some((tested, as_class)) = self.tested_classes(call, args) else {
            return;
        };
        let Expr::Name(subject) = &positional[0] else {
            return;
        };
        let name = self.mangle(&identifier(&subject.id));
        let scope = self.scopes.resolve(self.scope, &name);
        if scope != self.scope || !self.scopes.tracked(scope, &name) {
            return;
        }
        let definition = self.current_flow().get(&name);
        self.class_tests.by_call.insert(
            call_key(call),
            ClassTest {
                name,
                definition,
                value: args[0],
                tested,
                as_class,
            },
        );
    }

    fn tested_classes(
        &mut self,
        call: &ExprCall,
        args: &[Option<NodeId>],
    ) -> Option<(Tested, bool)> {
        if args.len() == 2 && names_classes(&call.arguments.args[1]) {
            for (checker, as_class) in CLASS_TESTS {
                if self.is_builtin_reference(&call.func, checker) {
                    return Some((Tested::Classes(args[1]), as_class));
                }
            }
        }
        if args.len() == 1 && self.is_builtin_reference(&call.func, "callable") {
            return Some((Tested::Callable, false));
        }
        if args.len() == 1 {
            let function = self.imported_function(&call.func)?;
            let (_, path) = CLASS_PREDICATES
                .iter()
                .find(|(predicate, _)| *predicate == function)?;
            let external = self.analysis.external(path, 0, false);
            let tested = self.analysis.constant(external);
            return Some((Tested::Classes(Some(tested)), false));
        }
        None
    }

    pub(crate) fn narrow(&mut self, test: &Expr, holds: bool, state: Option<StateId>) {
        let mut pending = vec![(test, holds)];
        while let Some((test, holds)) = pending.pop() {
            match test {
                Expr::UnaryOp(unary) if unary.op == UnaryOp::Not => {
                    pending.push((&unary.operand, !holds));
                }
                Expr::BoolOp(boolean)
                    if (boolean.op == BoolOp::And && holds)
                        || (boolean.op == BoolOp::Or && !holds) =>
                {
                    pending.extend(boolean.values.iter().rev().map(|value| (value, holds)));
                }
                Expr::Call(call) => {
                    let Some(class_test) = self.class_tests.by_call.get(&call_key(call)).cloned()
                    else {
                        continue;
                    };
                    let node = self.narrowed_node(test, call, &class_test, holds);
                    let flow = self.flow();
                    let definition = if holds {
                        Definition {
                            node: Some(node),
                            unbound: false,
                            truth: UNKNOWN,
                            values: None,
                        }
                    } else {
                        let tested = flow.definition_of(class_test.definition);
                        Definition {
                            node: Some(node),
                            unbound: false,
                            truth: if tested.truth == 0 {
                                UNKNOWN
                            } else {
                                tested.truth
                            },
                            values: tested.values.clone(),
                        }
                    };
                    let definition = flow.new_definition(definition);
                    flow.narrow(&class_test.name, class_test.definition, definition, state);
                }
                _ => {}
            }
        }
    }

    fn narrowed_node(
        &mut self,
        test: &Expr,
        call: &ExprCall,
        class_test: &ClassTest,
        holds: bool,
    ) -> NodeId {
        let key = (call_key(call), holds);
        if let Some(&narrowed) = self.class_tests.narrowed.get(&key) {
            return narrowed;
        }
        let narrowed = self.analysis.node(None);
        match class_test.tested {
            Tested::Callable => {
                if let Some(value) = class_test.value {
                    self.analysis.callable_filter(value, narrowed, holds);
                }
            }
            Tested::Classes(classes) => {
                if let Some(value) = class_test.value {
                    self.analysis.class_filter(
                        value,
                        classes,
                        narrowed,
                        class_test.as_class,
                        holds,
                    );
                }
                if holds && let Some(classes) = classes {
                    let site = self.site(&Node::Expr(test));
                    let module = self.module;
                    self.analysis.tested_classes(
                        classes,
                        narrowed,
                        class_test.as_class,
                        module,
                        &site,
                    );
                }
            }
        }
        self.class_tests.narrowed.insert(key, narrowed);
        narrowed
    }
}
