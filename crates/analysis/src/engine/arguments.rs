use num_bigint::{BigInt, Sign};
use pycg_solver::{NodeId, ObjId};
use rustc_hash::FxHashMap;

use crate::engine::containers::{ContainerRule, IterationId, Observer, StorageId, is_sequence};
use crate::engine::hierarchy::Unless;
use crate::engine::objects::{Literal, Passthrough};
use crate::engine::semantics::{CallId, Origin};
use crate::engine::symbols::Sym;
use crate::engine::trace::Trace;
use crate::engine::{Graph, State};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct SpreadId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct BindingId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
enum SpreadPart {
    Star,
    Index(usize),
    DoubleStar(usize),
}

#[derive(Clone, Copy, Debug)]
enum Waiting {
    Anywhere(BindingId),
    UnknownKeywords {
        spread: SpreadId,
        function: ObjId,
        call: CallId,
    },
}

struct Spread {
    source: NodeId,
    storage: StorageId,
    unknown: NodeId,
    aliased: Option<NodeId>,
    keys: Option<NodeId>,
    dicts: Vec<ObjId>,
    waiting: Option<Vec<Waiting>>,
}

struct Binding {
    function: ObjId,
    call: CallId,
    positional: Vec<Sym>,
    start: usize,
    unknown: NodeId,
}

#[derive(Default)]
pub(crate) struct Spreads {
    spreads: Vec<Spread>,
    spread_of: FxHashMap<(Origin, SpreadPart), SpreadId>,
    bindings: Vec<Binding>,
}

impl Spreads {
    pub(crate) fn table_sizes(&self, sizes: &mut Vec<(&'static str, usize)>) {
        let Spreads {
            spreads,
            spread_of: _,
            bindings: _,
        } = self;
        sizes.push(("spreads", spreads.len()));
    }

    pub(crate) fn unknown(&self, spread: SpreadId) -> NodeId {
        self.spreads[spread.0 as usize].unknown
    }
}

fn spread_index(spread: SpreadId) -> usize {
    spread.0 as usize
}

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
        let varargs = made.varargs;
        let vararg = made.signature.vararg.clone();
        let passthrough = made.passthrough.clone();
        let defaults = made.defaults.clone();
        let details = self.calls[call.index()].clone();
        let mut surely_supplied = Vec::new();
        let mut varargs_taken_by_receiver = 0;
        if let Some(receiver) = receiver {
            if !positional.is_empty() {
                let first = positional.remove(0);
                let parameter = self.objects.function(function).parameter(first);
                self.add_object(graph, parameter, receiver);
                if let Some(dst) = details.dst
                    && passthrough.contains(&Passthrough::Name(first))
                {
                    self.add_object(graph, dst, receiver);
                }
                surely_supplied.push(first);
            } else if let Some(varargs) = varargs {
                let first = self.element(graph, varargs, &Literal::Int(BigInt::ZERO));
                self.add_object(graph, first, receiver);
                let vararg = vararg.as_deref().map(|name| self.symbols.intern(name));
                if let (Some(dst), Some(vararg)) = (details.dst, vararg)
                    && passthrough.contains(&Passthrough::Element(vararg, BigInt::ZERO))
                {
                    self.add_object(graph, dst, receiver);
                }
                varargs_taken_by_receiver = 1;
            }
        }
        for (index, arg) in details.args.iter().enumerate() {
            if index < positional.len() {
                surely_supplied.push(positional[index]);
            }
            if let Some(arg) = *arg {
                self.bind_position(
                    graph,
                    function,
                    &positional,
                    BigInt::from(index + varargs_taken_by_receiver),
                    arg,
                    call,
                );
            }
        }
        if !details.star.is_empty() {
            let start = details.args.len() + varargs_taken_by_receiver;
            self.bind_unpacked(graph, function, &positional, start, call);
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
        for (index, mapping) in details.double_star.iter().enumerate() {
            if let Some(mapping) = *mapping {
                let spread = self.spread(graph, call, SpreadPart::DoubleStar(index), mapping);
                self.bind_mapping(graph, spread, function, call);
            }
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
        index: BigInt,
        source: NodeId,
        call: CallId,
    ) {
        let count = BigInt::from(positional.len());
        if index < count {
            let position = usize::try_from(&index).expect("a position below the count");
            self.bind_parameter(graph, function, positional[position], source, call);
        } else if self.objects.function(function).varargs.is_some() {
            self.bind_varargs(graph, function, Some(index - count), source, call);
        }
    }

    fn bind_varargs(
        &mut self,
        graph: &mut Graph,
        function: ObjId,
        index: Option<BigInt>,
        source: NodeId,
        call: CallId,
    ) {
        let varargs = self
            .objects
            .function(function)
            .varargs
            .expect("a function with varargs");
        let target = match index {
            None => self.unknown(graph, varargs),
            Some(ref index) => self.element(graph, varargs, &Literal::Int(index.clone())),
        };
        self.add_edge(graph, source, target);
        let Some(dst) = self.calls[call.index()].dst else {
            return;
        };
        let made = self.objects.function(function);
        let returned = match index {
            None => made
                .passthrough
                .iter()
                .any(|entry| matches!(entry, Passthrough::Element(..))),
            Some(index) => {
                let vararg = made
                    .signature
                    .vararg
                    .clone()
                    .expect("a function with varargs names them");
                let vararg = self.symbols.intern(&vararg);
                self.objects
                    .function(function)
                    .passthrough
                    .contains(&Passthrough::Element(vararg, index))
            }
        };
        if returned {
            self.add_edge(graph, source, dst);
        }
    }

    fn bind_unpacked(
        &mut self,
        graph: &mut Graph,
        function: ObjId,
        positional: &[Sym],
        start: usize,
        call: CallId,
    ) {
        let star = self.calls[call.index()].star.clone();
        let (first, _) = star[0];
        if let Some(first) = first {
            let spread = self.spread(graph, call, SpreadPart::Star, first);
            let unknown = self.containers.spreads.unknown(spread);
            let binding = BindingId(
                u32::try_from(self.containers.spreads.bindings.len()).expect("bindings fit u32"),
            );
            self.containers.spreads.bindings.push(Binding {
                function,
                call,
                positional: positional.to_vec(),
                start,
                unknown,
            });
            let storage = self.containers.spreads.spreads[spread_index(spread)].storage;
            self.observe_storage(graph, storage, Observer::BindUnpacked(binding));
            self.bind_once_gathered(graph, spread, Waiting::Anywhere(binding));
        }
        for (index, &(value, starred)) in star.iter().enumerate().skip(1) {
            let Some(mut value) = value else {
                continue;
            };
            if starred {
                let spread = self.spread(graph, call, SpreadPart::Index(index), value);
                value = self.containers.spreads.unknown(spread);
            }
            self.bind_anywhere(graph, function, positional, start, value, call);
        }
    }

    pub(super) fn bind_unpacked_field(
        &mut self,
        graph: &mut Graph,
        binding: BindingId,
        key: &Literal,
        node: NodeId,
    ) {
        let found = &self.containers.spreads.bindings[binding.0 as usize];
        let (function, call, start) = (found.function, found.call, found.start);
        let positional = found.positional.clone();
        let Literal::Int(key) = key else {
            unreachable!("a sequence spread is keyed by positions")
        };
        assert!(
            key.sign() != Sign::Minus,
            "a gathered position is not negative"
        );
        if start > positional.len() {
            if self.objects.function(function).varargs.is_some() {
                self.bind_varargs(graph, function, None, node, call);
            }
            return;
        }
        self.bind_position(
            graph,
            function,
            &positional,
            BigInt::from(start) + key,
            node,
            call,
        );
    }

    fn spread(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        part: SpreadPart,
        value: NodeId,
    ) -> SpreadId {
        let origin = self.calls[call.index()].origin;
        let key = (origin, part);
        if let Some(&spread) = self.containers.spreads.spread_of.get(&key) {
            let found = &self.containers.spreads.spreads[spread_index(spread)];
            assert_eq!(found.source, value, "{key:?} unpacks another node");
            return spread;
        }
        let aliased = match part {
            SpreadPart::DoubleStar(_) => Some(self.node(graph, None)),
            SpreadPart::Star | SpreadPart::Index(_) => None,
        };
        let unknown = self.node(graph, None);
        let storage = self.new_storage();
        let spread = SpreadId(
            u32::try_from(self.containers.spreads.spreads.len()).expect("spreads fit u32"),
        );
        self.containers.spreads.spreads.push(Spread {
            source: value,
            storage,
            unknown,
            aliased,
            keys: None,
            dicts: Vec::new(),
            waiting: Some(Vec::new()),
        });
        self.containers.spreads.spread_of.insert(key, spread);
        let details = &self.calls[call.index()];
        let (caller, site) = (details.caller, details.site);
        let rule = match part {
            SpreadPart::Star => {
                let iteration = self.new_iteration(
                    graph,
                    unknown,
                    caller,
                    site,
                    false,
                    Unless::Nothing,
                    "arguments",
                );
                self.container_rule(ContainerRule::SpreadSequence { spread, iteration })
            }
            SpreadPart::Index(_) => {
                let iteration =
                    self.new_iteration(graph, unknown, caller, site, false, Unless::Nothing, "for");
                self.container_rule(ContainerRule::Iterate(iteration))
            }
            SpreadPart::DoubleStar(_) => self.container_rule(ContainerRule::SpreadMapping(spread)),
        };
        self.attach(graph, value, rule);
        spread
    }

    pub(super) fn spread_field(
        &mut self,
        graph: &mut Graph,
        spread: SpreadId,
        key: &Literal,
    ) -> NodeId {
        let storage = self.containers.spreads.spreads[spread_index(spread)].storage;
        self.storage_field(graph, storage, key)
    }

    pub(super) fn spread_sequence(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        spread: SpreadId,
        iteration: IterationId,
    ) {
        let sequence = self
            .container_of(object)
            .is_some_and(|container| is_sequence(self.symbols.text(container.kind)));
        if sequence {
            self.observe_container(graph, object, Observer::GatherSequence(spread));
            let unknown = self.unknown(graph, object);
            let gathered = self.containers.spreads.unknown(spread);
            self.add_edge(graph, unknown, gathered);
        } else {
            self.iterate(graph, object, iteration);
        }
        self.wake_bindings_waiting(graph, spread);
    }

    pub(super) fn spread_mapping(&mut self, graph: &mut Graph, object: ObjId, spread: SpreadId) {
        if !(self.container_of(object).is_some() && self.is_dict(object)) {
            return;
        }
        self.observe_container(graph, object, Observer::GatherMapping(spread));
        let unknown = self.unknown(graph, object);
        let gathered = self.containers.spreads.unknown(spread);
        self.add_edge(graph, unknown, gathered);
        let aliased = self.aliased(graph, object);
        let spread_aliased = self.containers.spreads.spreads[spread_index(spread)]
            .aliased
            .expect("a mapping spread has an aliased node");
        self.add_edge(graph, aliased, spread_aliased);
        self.containers.spreads.spreads[spread_index(spread)]
            .dicts
            .push(object);
        if let Some(keys) = self.containers.spreads.spreads[spread_index(spread)].keys {
            let dict_keys = self.keys(graph, object);
            self.add_edge(graph, dict_keys, keys);
        }
        self.wake_bindings_waiting(graph, spread);
    }

    fn observe_container(&mut self, graph: &mut Graph, container: ObjId, observer: Observer) {
        let storage = self.container_storage(container);
        self.observe_storage(graph, storage, observer);
    }

    fn bind_once_gathered(&mut self, graph: &mut Graph, spread: SpreadId, bind: Waiting) {
        match &mut self.containers.spreads.spreads[spread_index(spread)].waiting {
            None => self.bind_waiting(graph, bind),
            Some(waiting) => waiting.push(bind),
        }
    }

    fn wake_bindings_waiting(&mut self, graph: &mut Graph, spread: SpreadId) {
        let waiting = self.containers.spreads.spreads[spread_index(spread)]
            .waiting
            .take();
        for bind in waiting.unwrap_or_default() {
            self.bind_waiting(graph, bind);
        }
    }

    fn bind_waiting(&mut self, graph: &mut Graph, bind: Waiting) {
        match bind {
            Waiting::Anywhere(binding) => {
                let found = &self.containers.spreads.bindings[binding.0 as usize];
                let (function, call, start, unknown) =
                    (found.function, found.call, found.start, found.unknown);
                let positional = found.positional.clone();
                self.bind_anywhere(graph, function, &positional, start, unknown, call);
            }
            Waiting::UnknownKeywords {
                spread,
                function,
                call,
            } => self.bind_unknown_keywords(graph, spread, function, call),
        }
    }

    fn bind_anywhere(
        &mut self,
        graph: &mut Graph,
        function: ObjId,
        positional: &[Sym],
        start: usize,
        source: NodeId,
        call: CallId,
    ) {
        for &parameter in positional.iter().skip(start) {
            self.bind_parameter(graph, function, parameter, source, call);
        }
        if self.objects.function(function).varargs.is_some() {
            self.bind_varargs(graph, function, None, source, call);
        }
    }

    pub(super) fn bind_keyword(
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
        } else if let Some(varkeywords) = made.varkeywords {
            let key = Literal::Str(self.symbols.text(name).chars().map(u32::from).collect());
            let element = self.element(graph, varkeywords, &key);
            self.add_edge(graph, value, element);
            let keys = self.keys(graph, varkeywords);
            let constant = self.const_object(graph, &key);
            self.add_object(graph, keys, constant);
        }
    }

    fn bind_mapping(&mut self, graph: &mut Graph, spread: SpreadId, function: ObjId, call: CallId) {
        let storage = self.containers.spreads.spreads[spread_index(spread)].storage;
        self.observe_storage(graph, storage, Observer::BindKeyword { function, call });
        self.bind_once_gathered(
            graph,
            spread,
            Waiting::UnknownKeywords {
                spread,
                function,
                call,
            },
        );
    }

    fn bind_unknown_keywords(
        &mut self,
        graph: &mut Graph,
        spread: SpreadId,
        function: ObjId,
        call: CallId,
    ) {
        let unknown = self.containers.spreads.unknown(spread);
        let signature = self.objects.function(function).signature.clone();
        for name in &signature.positional[signature.positional_only_count..] {
            let name = self.symbols.intern(name);
            self.bind_parameter(graph, function, name, unknown, call);
        }
        for name in &signature.keyword_only {
            let name = self.symbols.intern(name);
            self.bind_parameter(graph, function, name, unknown, call);
        }
        let Some(varkeywords) = self.objects.function(function).varkeywords else {
            return;
        };
        let target = self.unknown(graph, varkeywords);
        self.add_edge(graph, unknown, target);
        let aliased = self.containers.spreads.spreads[spread_index(spread)]
            .aliased
            .expect("a mapping spread has an aliased node");
        let target = self.aliased(graph, varkeywords);
        self.add_edge(graph, aliased, target);
        let keys = match self.containers.spreads.spreads[spread_index(spread)].keys {
            Some(keys) => keys,
            None => {
                let keys = self.node(graph, None);
                self.containers.spreads.spreads[spread_index(spread)].keys = Some(keys);
                let dicts = self.containers.spreads.spreads[spread_index(spread)]
                    .dicts
                    .clone();
                for dict in dicts {
                    let dict_keys = self.keys(graph, dict);
                    self.add_edge(graph, dict_keys, keys);
                }
                keys
            }
        };
        let target = self.keys(graph, varkeywords);
        self.add_edge(graph, keys, target);
    }
}
