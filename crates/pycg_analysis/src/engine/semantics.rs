use pycg_solver::{NodeId, ObjId};

use crate::engine::objects::Object;
use crate::engine::symbols::Sym;
use crate::engine::trace::{RuleInfo, Trace};
use crate::engine::{Graph, Rule, RuleId, State, not_ported};
use crate::models::RETURNS_ARGUMENT;

pub const RECEIVERS_PER_CALL_MAX: usize = 3;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct CallId(u32);

impl CallId {
    pub fn index(self) -> usize {
        self.0 as usize
    }
}

pub type Receivers = Vec<ObjId>;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Origin {
    Call(CallId),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Construct {
    Call,
    Decorator,
}

#[derive(Clone)]
pub struct Call {
    pub caller: Sym,
    pub args: Vec<Option<NodeId>>,
    pub keywords: Vec<(Sym, Option<NodeId>)>,
    pub dst: Option<NodeId>,
    pub site: Sym,
    pub origin: Origin,
    pub star: Vec<(Option<NodeId>, bool)>,
    pub double_star: Vec<Option<NodeId>>,
    pub implicit: bool,
    pub decorator: bool,
    pub rule: RuleId,
}

pub struct NewCall<'a> {
    pub callee: Option<NodeId>,
    pub caller: &'a str,
    pub args: &'a [Option<NodeId>],
    pub keywords: &'a [(Box<str>, Option<NodeId>)],
    pub dst: Option<NodeId>,
    pub site: &'a str,
    pub star: &'a [(Option<NodeId>, bool)],
    pub double_star: &'a [Option<NodeId>],
    pub decorator: bool,
    pub applies: bool,
}

impl<T: Trace> State<T> {
    pub(super) fn new_call(&mut self, mut call: Call, origin: Option<Origin>) -> CallId {
        let id = CallId(u32::try_from(self.calls.len()).expect("fewer than 2^32 calls"));
        call.origin = origin.unwrap_or(Origin::Call(id));
        let key = format!("Call:{}", self.symbols.text(call.site));
        call.rule = self.new_rule(
            Rule::Call(id),
            &RuleInfo {
                key: &key,
                kinds: None,
                each: false,
                captured: &[],
            },
        );
        self.calls.push(call);
        id
    }

    pub(super) fn add_call(&mut self, graph: &mut Graph, new: &NewCall<'_>) {
        let caller = self.symbols.intern(new.caller);
        let site = self.symbols.intern(new.site);
        if !new.decorator {
            self.call_expressions.push((caller, site, new.callee));
        }
        let Some(callee) = new.callee else {
            return;
        };
        let keywords = new
            .keywords
            .iter()
            .map(|(name, value)| (self.symbols.intern(name), *value))
            .collect();
        let call = Call {
            caller,
            args: new.args.to_vec(),
            keywords,
            dst: new.dst,
            site,
            origin: Origin::Call(CallId(0)),
            star: new.star.to_vec(),
            double_star: new.double_star.to_vec(),
            implicit: false,
            decorator: new.decorator,
            rule: RuleId(0),
        };
        let call = self.new_call(call, None);
        let rule = self.calls[call.index()].rule;
        self.attach(graph, callee, rule);
    }

    pub(super) fn call(&mut self, graph: &mut Graph, object: ObjId, call: CallId) {
        match self.objects.get(object) {
            Object::Function(_) => {
                if !self.returns_argument(object) {
                    self.call_function(graph, object, call, None);
                }
            }
            Object::UnknownExternal(_) => self.outside_result(graph, call),
            &Object::BoundMethod { receiver, function } => {
                self.call_bound(graph, function, vec![receiver], call);
            }
            Object::External(_) => not_ported("calls of outside values"),
            Object::Saturated
            | Object::Module(_)
            | Object::Const { .. }
            | Object::Container(_)
            | Object::Generator { .. }
            | Object::Coroutine { .. } => {}
        }
    }

    fn returns_argument(&self, callee: ObjId) -> bool {
        let name = self.objects.name(callee, &self.symbols);
        if RETURNS_ARGUMENT.iter().any(|&(model, _)| model == name) {
            not_ported("the models of functions that return an argument");
        }
        false
    }

    fn outside_result(&mut self, graph: &mut Graph, call: CallId) {
        let Call {
            dst,
            decorator,
            ref args,
            ..
        } = self.calls[call.index()];
        let Some(dst) = dst else {
            return;
        };
        let last = args.last().copied();
        let unknown = self.unknown_external;
        self.add_object(graph, dst, unknown);
        if decorator && let Some(Some(decorated)) = last {
            self.add_edge(graph, decorated, dst);
        }
    }

    fn call_bound(&mut self, graph: &mut Graph, callee: ObjId, receivers: Receivers, call: CallId) {
        let (base, prefix) = self
            .prefixes
            .get(&call)
            .cloned()
            .unwrap_or((call, Vec::new()));
        let mut receivers = receivers;
        receivers.extend(prefix);
        receivers.truncate(RECEIVERS_PER_CALL_MAX);
        match self.objects.get(callee) {
            Object::Function(_) => {
                let rest = self.prefixed_call(graph, base, receivers[1..].to_vec());
                self.call_function(graph, callee, rest, Some(receivers[0]));
            }
            Object::External(_) => not_ported("bound calls of outside values"),
            _ => {
                let prefixed = self.prefixed_call(graph, base, receivers);
                self.call(graph, callee, prefixed);
            }
        }
    }

    fn prefixed_call(&mut self, graph: &mut Graph, base: CallId, receivers: Receivers) -> CallId {
        if receivers.is_empty() {
            return base;
        }
        let key = (base, receivers);
        if let Some(&call) = self.receiver_calls.get(&key) {
            return call;
        }
        let (base, receivers) = key;
        let mut args: Vec<Option<NodeId>> = receivers
            .iter()
            .map(|&receiver| Some(self.constant(graph, receiver)))
            .collect();
        let template = self.calls[base.index()].clone();
        args.extend(template.args.iter().copied());
        let call = self.new_call(
            Call { args, ..template },
            Some(self.calls[base.index()].origin),
        );
        self.receiver_calls.insert((base, receivers.clone()), call);
        self.prefixes.insert(call, (base, receivers));
        call
    }

    fn call_function(
        &mut self,
        graph: &mut Graph,
        function: ObjId,
        call: CallId,
        receiver: Option<ObjId>,
    ) {
        if !self.may_bind(function, call, receiver) {
            return;
        }
        let name = self.objects.function(function).name;
        self.add_call_edge(call, name);
        if self.calls[call.index()].caller != name {
            self.called.insert(function);
        }
        self.function_result(graph, function, call, receiver);
    }

    fn function_result(
        &mut self,
        graph: &mut Graph,
        function: ObjId,
        call: CallId,
        receiver: Option<ObjId>,
    ) {
        self.bind_arguments(graph, function, call, receiver);
        let Some(dst) = self.calls[call.index()].dst else {
            return;
        };
        let made = self.objects.function(function);
        if made.yield_node.is_some() {
            let generator = self.generator(graph, function);
            self.add_object(graph, dst, generator);
        } else if made.is_async {
            let coroutine = self.coroutine(graph, function);
            self.add_object(graph, dst, coroutine);
        } else {
            let returned = made.return_node;
            self.add_edge(graph, returned, dst);
        }
    }

    fn generator(&mut self, graph: &mut Graph, function: ObjId) -> ObjId {
        if let Some(&generator) = self.generators.get(&function) {
            return generator;
        }
        let generator = self.new_object(
            graph,
            Object::Generator {
                function,
                exact: true,
            },
        );
        self.generators.insert(function, generator);
        generator
    }

    fn coroutine(&mut self, graph: &mut Graph, function: ObjId) -> ObjId {
        if let Some(&coroutine) = self.coroutines.get(&function) {
            return coroutine;
        }
        let coroutine = self.new_object(
            graph,
            Object::Coroutine {
                function,
                exact: true,
            },
        );
        self.coroutines.insert(function, coroutine);
        coroutine
    }

    fn may_bind(&self, function: ObjId, call: CallId, receiver: Option<ObjId>) -> bool {
        let made = self.objects.function(function);
        let details = &self.calls[call.index()];
        if !details.star.is_empty() || !details.double_star.is_empty() || made.decorated {
            return true;
        }
        let base = self.prefixes.get(&call).map_or(call, |&(base, _)| base);
        if self.calls[base.index()].implicit {
            return true;
        }
        let given = details.args.len() + usize::from(receiver.is_some());
        let keywords: Vec<&str> = details
            .keywords
            .iter()
            .map(|&(name, _)| self.symbols.text(name))
            .collect();
        let optional: Vec<&str> = made
            .optional
            .iter()
            .map(|&name| self.symbols.text(name))
            .collect();
        made.signature.binds(given, &keywords, &optional)
    }

    fn add_call_edge(&mut self, call: CallId, callee: Sym) {
        let details = &self.calls[call.index()];
        let construct = match details.origin {
            Origin::Call(origin) if self.calls[origin.index()].decorator => Construct::Decorator,
            Origin::Call(_) => Construct::Call,
        };
        let key = (details.caller, details.site, construct);
        self.site_edges.entry(key).or_default().insert(callee);
    }
}
