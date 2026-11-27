use pycg_solver::{NodeId, ObjId};

use crate::engine::objects::Passthrough;
use crate::engine::semantics::CallId;
use crate::engine::symbols::Sym;
use crate::engine::trace::Trace;
use crate::engine::{Graph, State, not_ported};

impl<T: Trace> State<T> {
    pub(super) fn bind_arguments(
        &mut self,
        graph: &mut Graph,
        function: ObjId,
        call: CallId,
        receiver: Option<ObjId>,
    ) -> Vec<Sym> {
        let made = self.objects.function(function);
        let mut positional: Vec<Sym> = made
            .signature
            .positional
            .iter()
            .map(|name| self.symbols.intern(name))
            .collect();
        let has_varargs = made.varargs.is_some();
        let passthrough = made.passthrough.clone();
        let defaults = made.defaults.clone();
        let details = self.calls[call.index()].clone();
        let mut surely_supplied = Vec::new();
        if let Some(receiver) = receiver {
            if positional.is_empty() {
                if has_varargs {
                    not_ported("binding a receiver to varargs");
                }
            } else {
                let first = positional.remove(0);
                let parameter = self.objects.function(function).parameter(first);
                self.add_object(graph, parameter, receiver);
                if let Some(dst) = details.dst
                    && passthrough.contains(&Passthrough::Name(first))
                {
                    self.add_object(graph, dst, receiver);
                }
                surely_supplied.push(first);
            }
        }
        for (index, arg) in details.args.iter().enumerate() {
            if index < positional.len() {
                surely_supplied.push(positional[index]);
            }
            if let Some(arg) = *arg {
                self.bind_position(graph, function, &positional, index, arg, call);
            }
        }
        if !details.star.is_empty() {
            not_ported("star arguments");
        }
        for &(name, value) in &details.keywords {
            let text = self.symbols.text(name);
            if self
                .objects
                .function(function)
                .signature
                .accepts_keyword(text)
            {
                surely_supplied.push(name);
            }
            let value = match value {
                Some(value) => value,
                None => self.node(graph, None),
            };
            self.bind_keyword(graph, function, name, value, call);
        }
        if details.double_star.iter().any(Option::is_some) {
            not_ported("double star arguments");
        }
        for (parameter, default) in defaults {
            if !surely_supplied.contains(&parameter) {
                self.bind_parameter(graph, function, parameter, default, call);
            }
        }
        surely_supplied
    }

    fn bind_parameter(
        &mut self,
        graph: &mut Graph,
        function: ObjId,
        name: Sym,
        source: NodeId,
        call: CallId,
    ) {
        let made = self.objects.function(function);
        let parameter = made.parameter(name);
        let returned = made.passthrough.contains(&Passthrough::Name(name));
        self.add_edge(graph, source, parameter);
        if returned && let Some(dst) = self.calls[call.index()].dst {
            self.add_edge(graph, source, dst);
        }
    }

    fn bind_position(
        &mut self,
        graph: &mut Graph,
        function: ObjId,
        positional: &[Sym],
        index: usize,
        source: NodeId,
        call: CallId,
    ) {
        if index < positional.len() {
            self.bind_parameter(graph, function, positional[index], source, call);
        } else if self.objects.function(function).varargs.is_some() {
            not_ported("binding to varargs");
        }
    }

    fn bind_keyword(
        &mut self,
        graph: &mut Graph,
        function: ObjId,
        name: Sym,
        value: NodeId,
        call: CallId,
    ) {
        let made = self.objects.function(function);
        if made.signature.accepts_keyword(self.symbols.text(name)) {
            self.bind_parameter(graph, function, name, value, call);
        } else if made.varkeywords.is_some() {
            not_ported("binding to varkeywords");
        }
    }
}
