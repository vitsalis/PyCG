use pycg_solver::ObjId;
use rustc_hash::FxHashSet;

use crate::engine::objects::Object;
use crate::engine::trace::Trace;
use crate::engine::{Graph, State};

impl<T: Trace> State<T> {
    pub(super) fn solve(&mut self, graph: &mut Graph) {
        self.solve_round(graph);
        while self.complete(graph) {
            self.solve_round(graph);
        }
    }

    fn solve_round(&mut self, graph: &mut Graph) {
        self.trace.solve();
        graph.solve(self);
        self.trace.solved(graph.phase);
    }

    fn complete(&mut self, graph: &mut Graph) -> bool {
        let mut added = false;
        let absorbed = self.absorbed_functions(graph);
        let pending = self.functions[self.completed_functions..].to_vec();
        for function in pending {
            if self.called.contains(&function) || absorbed.contains(&function) {
                continue;
            }
            let made = self.objects.function(function);
            let bindings: Vec<_> = made
                .defaults
                .iter()
                .map(|&(parameter, default)| (default, made.parameter(parameter)))
                .collect();
            for (default, parameter) in bindings {
                self.add_edge(graph, default, parameter);
                added = true;
            }
        }
        self.completed_functions = self.functions.len();
        added
    }

    fn absorbed_functions(&mut self, graph: &mut Graph) -> FxHashSet<ObjId> {
        let mut functions = FxHashSet::default();
        let mut pending = graph.absorbed();
        let mut seen = FxHashSet::default();
        while let Some(object) = pending.pop() {
            if !seen.insert(object) {
                continue;
            }
            match self.objects.get(object) {
                &Object::BoundMethod { function, .. } => pending.push(function),
                Object::Function(_) => {
                    functions.insert(object);
                }
                Object::Saturated
                | Object::Module(_)
                | Object::External(_)
                | Object::UnknownExternal(_)
                | Object::Const { .. }
                | Object::Container(_)
                | Object::Generator { .. }
                | Object::Coroutine { .. } => {}
            }
        }
        functions
    }
}
