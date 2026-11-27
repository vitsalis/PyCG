use pycg_solver::{NodeId, ObjId};

use crate::engine::objects::Object;
use crate::engine::rules::Rule;
use crate::engine::trace::Trace;
use crate::engine::{Graph, State, not_ported};

impl<T: Trace> State<T> {
    pub(super) fn add_inexact(&mut self, graph: &mut Graph, source: NodeId, dst: NodeId) {
        let rule = self.rule(Rule::AddInexact { dst });
        self.attach(graph, source, rule);
    }

    pub(super) fn inexact_object(&mut self, graph: &mut Graph, object: ObjId) -> ObjId {
        let inexact = match self.objects.get(object) {
            Object::Const { value, exact: true } => Object::Const {
                value: value.clone(),
                exact: false,
            },
            &Object::Generator {
                function,
                exact: true,
            } => Object::Generator {
                function,
                exact: false,
            },
            &Object::Coroutine {
                function,
                exact: true,
            } => Object::Coroutine {
                function,
                exact: false,
            },
            Object::Container(container) if container.exact => {
                not_ported("containers: the inexact alias of a container")
            }
            _ => return object,
        };
        if let Some(&found) = self.inexact.get(&object) {
            return found;
        }
        let found = self.new_object(graph, inexact);
        self.inexact.insert(object, found);
        found
    }
}
