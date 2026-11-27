use pycg_solver::{NodeId, ObjId};
use rustc_hash::FxHashSet;

use crate::engine::objects::Object;
use crate::engine::symbols::Sym;
use crate::engine::trace::Trace;
use crate::engine::{Graph, State};

impl<T: Trace> State<T> {
    pub(super) fn solve(&mut self, graph: &mut Graph) {
        self.solve_round(graph);
        while self.decide_hierarchies(graph) || self.complete(graph) {
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
        for index in self.completed_receivers..self.receivers.len() {
            let entry = self.receivers[index];
            let (receiver, _, function, _, _) = entry;
            if self.objects_of(graph, receiver).is_empty() && !absorbed.contains(&function) {
                self.entry_receivers.push(entry);
            }
        }
        self.completed_receivers = self.receivers.len();
        for (receiver, source, function, class, name) in self.entry_receivers.clone() {
            for object in self.objects_of(graph, source) {
                if !self.holds(graph, receiver, object)
                    && self.inherits_method(graph, object, class, name, function)
                {
                    self.add_object(graph, receiver, object);
                    added = self.holds(graph, receiver, object) || added;
                }
            }
        }
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
                &Object::Instance { class, .. } => pending.push(class),
                Object::Function(_) => {
                    functions.insert(object);
                }
                Object::Class(_) => {
                    for owner in self.class_mro(object) {
                        let fields: Vec<NodeId> = self
                            .fields
                            .get(&owner)
                            .map(|fields| fields.values().copied().collect())
                            .unwrap_or_default();
                        for field in fields {
                            for value in self.objects_of(graph, field) {
                                if matches!(
                                    self.objects.get(value),
                                    Object::Function(_) | Object::Wrapper { .. }
                                ) {
                                    pending.push(value);
                                }
                            }
                        }
                    }
                }
                Object::Wrapper { .. } => {
                    let func = self.symbols.intern("__func__");
                    if let Some(&field) = self
                        .fields
                        .get(&object)
                        .and_then(|fields| fields.get(&func))
                    {
                        pending.extend(self.objects_of(graph, field));
                    }
                }
                Object::Saturated
                | Object::Module(_)
                | Object::External(_)
                | Object::UnknownExternal(_)
                | Object::BuiltinMethod { .. }
                | Object::Fallback { .. }
                | Object::Const { .. }
                | Object::Container(_)
                | Object::Generator { .. }
                | Object::Coroutine { .. } => {}
            }
        }
        functions
    }

    fn inherits_method(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        class: ObjId,
        name: Sym,
        function: ObjId,
    ) -> bool {
        let owner = match self.objects.get(object) {
            _ if self.opaque(object) => return true,
            &Object::Instance { class, .. } => class,
            Object::Class(_) => object,
            _ => return true,
        };
        if owner == class
            || (self.objects.is_class(object)
                && !self.objects.class(object).ancestors.contains(&class))
        {
            return true;
        }
        let found = self.objects.class(owner);
        if found.exhaustive {
            return found.mros[0].contains(&class);
        }
        for mro in found.mros.clone() {
            let definer = mro.iter().copied().find(|&base| {
                matches!(self.objects.get(base), Object::Class(base) if base.defines.contains(&name))
            });
            if definer == Some(class) || self.binds_function(graph, definer, name, function) {
                return true;
            }
        }
        false
    }

    fn binds_function(
        &mut self,
        graph: &mut Graph,
        class: Option<ObjId>,
        name: Sym,
        function: ObjId,
    ) -> bool {
        let Some(class) = class else {
            return false;
        };
        let field = self.field(graph, class, name);
        let func = self.symbols.intern("__func__");
        for value in self.objects_of(graph, field) {
            if value == function {
                return true;
            }
            if matches!(self.objects.get(value), Object::Wrapper { .. }) {
                let wrapped = self.field(graph, value, func);
                if self.objects_of(graph, wrapped).contains(&function) {
                    return true;
                }
            }
        }
        false
    }
}
