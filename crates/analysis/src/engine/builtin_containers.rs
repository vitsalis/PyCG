use pycg_solver::{NodeId, ObjId};

use crate::engine::containers::{ContainerOrigin, Keeps, KeysConstruct};
use crate::engine::hierarchy::Unless;
use crate::engine::objects::{Literal, Object};
use crate::engine::outside_calls::BoundId;
use crate::engine::rules::Rule;
use crate::engine::semantics::{CallId, Role, SiteKey};
use crate::engine::symbols::Sym;
use crate::engine::{Graph, State};
use crate::models::{LENGTH_HINT, LengthPlan, REVERSED_LENGTH, SEQUENCE_LENGTH};

const SEQUENCES: [&str; 2] = ["list", "tuple"];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Iterated {
    Bound(BoundId),
    Enumerate(CallId),
    Zip(CallId),
    ZipAt(CallId, usize),
    Map(CallId, usize),
    MapStar(CallId, usize),
    Filter(CallId),
}

impl State {
    fn caller_site(&self, call: CallId) -> (Sym, Sym) {
        let details = &self.calls[call.index()];
        (details.caller, details.site)
    }

    fn rule_container(
        &mut self,
        graph: &mut Graph,
        kind: &str,
        call: CallId,
        rule: &'static str,
        length: Option<u32>,
        exact: bool,
    ) -> ObjId {
        let details = &self.calls[call.index()];
        let (origin, site) = (details.origin, details.site);
        self.container_at(
            graph,
            kind,
            ContainerOrigin::Rule(origin, rule, length),
            site,
            length,
            exact,
        )
    }

    pub(super) fn result_node(&mut self, graph: &mut Graph, call: CallId) -> NodeId {
        match self.calls[call.index()].dst {
            Some(dst) => dst,
            None => self.node(graph, None),
        }
    }

    fn iterated(
        &mut self,
        graph: &mut Graph,
        iterable: NodeId,
        construct: Iterated,
        call: CallId,
    ) -> NodeId {
        if let Some(&(found, node)) = self.iterated_nodes.get(&construct) {
            assert_eq!(found, iterable, "{construct:?} iterates another node");
            return node;
        }
        let node = self.node(graph, None);
        self.iterated_nodes.insert(construct, (iterable, node));
        let (caller, site) = self.caller_site(call);
        self.add_iteration(graph, iterable, node, caller, site, false);
        node
    }

    pub(super) fn rule_collection(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        receiver: Option<ObjId>,
        args: BoundId,
        kind: &str,
    ) {
        let new = self.rule_container(graph, kind, call, "collection", None, receiver.is_none());
        if self.bound_given(args, "iterable") {
            let iterable = self.bound_parameter(graph, args, "iterable");
            let (caller, site) = self.caller_site(call);
            if self.hashes_keys(new) {
                self.add_keys(
                    graph,
                    new,
                    iterable,
                    KeysConstruct::Bound(args),
                    caller,
                    site,
                    Keeps::Hashes,
                );
            } else {
                self.add_elements(graph, new, iterable, caller, site);
            }
            if SEQUENCES.contains(&kind) {
                self.add_length_hint(graph, iterable, caller, site, LENGTH_HINT);
            }
        }
        self.result(graph, call, new);
    }

    pub(super) fn add_length_hint(
        &mut self,
        graph: &mut Graph,
        iterable: NodeId,
        caller: Sym,
        site: Sym,
        plan: LengthPlan,
    ) {
        let key = (
            caller,
            site,
            iterable,
            std::ptr::from_ref(plan) as *const () as usize,
        );
        if !self.length_hints.insert(key) {
            return;
        }
        let plan = self.length_plan(plan);
        let rule = self.rule(Rule::CallProtocol { plan, caller, site });
        self.attach(graph, iterable, rule);
        let rule = self.rule(Rule::SequenceLength { caller, site });
        self.attach(graph, iterable, rule);
    }

    fn length_plan(&mut self, plan: LengthPlan) -> crate::engine::outside_calls::PlanId {
        let key = std::ptr::from_ref(plan) as *const () as usize;
        if let Some(&found) = self.length_plans.get(&key) {
            return found;
        }
        let steps = plan
            .iter()
            .map(|&(name, unless)| {
                let name = self.symbols.intern(name);
                let unless = if unless.is_empty() {
                    Unless::Nothing
                } else {
                    Unless::Names(
                        unless
                            .iter()
                            .map(|name| self.symbols.intern(name))
                            .collect(),
                    )
                };
                (name, unless)
            })
            .collect();
        let found = self.new_plan(steps);
        self.length_plans.insert(key, found);
        found
    }

    pub(super) fn sequence_length(
        &mut self,
        graph: &mut Graph,
        iterator: ObjId,
        caller: Sym,
        site: Sym,
    ) {
        let plan = match self.kind_text_of(iterator) {
            "iterator" => SEQUENCE_LENGTH,
            "reversed" => REVERSED_LENGTH,
            _ => return,
        };
        let plan = self.length_plan(plan);
        let rule = self.rule(Rule::CallProtocol { plan, caller, site });
        let source = self.keys(graph, iterator);
        self.attach(graph, source, rule);
    }

    fn kind_text_of(&self, container: ObjId) -> &str {
        match self.objects.get(container) {
            Object::Container(container) => self.symbols.text(container.kind),
            _ => panic!("a container"),
        }
    }

    pub(super) fn rule_dict(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        receiver: Option<ObjId>,
        args: BoundId,
        kind: &str,
        rule: &'static str,
    ) -> ObjId {
        let new = self.rule_container(graph, kind, call, rule, None, receiver.is_none());
        self.rule_update(graph, call, new, args);
        new
    }

    pub(super) fn rule_defaultdict(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        receiver: Option<ObjId>,
        args: BoundId,
    ) {
        let new = self.rule_dict(
            graph,
            call,
            receiver,
            args,
            "collections.defaultdict",
            "defaultdict",
        );
        if self.bound_given(args, "default_factory") {
            let factory = self.bound_parameter(graph, args, "default_factory");
            let own = self.factory(graph, new);
            self.add_edge(graph, factory, own);
        }
        self.result(graph, call, new);
    }

    pub(super) fn rule_counter(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        receiver: Option<ObjId>,
        args: BoundId,
    ) {
        let new = self.rule_container(
            graph,
            "collections.Counter",
            call,
            "counter",
            None,
            receiver.is_none(),
        );
        self.rule_count(graph, call, new, args);
        self.result(graph, call, new);
    }

    pub(super) fn rule_count(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        receiver: ObjId,
        args: BoundId,
    ) {
        if self.bound_given(args, "iterable") {
            let iterable = self.bound_parameter(graph, args, "iterable");
            let (caller, site) = self.caller_site(call);
            self.add_keys(
                graph,
                receiver,
                iterable,
                KeysConstruct::Bound(args),
                caller,
                site,
                Keeps::MappingHashes,
            );
        }
        let keywords = self
            .bound_varkeywords(args)
            .expect("the keywords of a counter");
        let from = self.keys(graph, keywords);
        let to = self.keys(graph, receiver);
        self.add_edge(graph, from, to);
    }

    pub(super) fn rule_add(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        receiver: ObjId,
        args: BoundId,
        parameter: &str,
    ) {
        let value = self.bound_parameter(graph, args, parameter);
        let unknown = self.unknown(graph, receiver);
        self.add_edge(graph, value, unknown);
        if self.hashes_keys(receiver) {
            let stored = self.elements(graph, receiver);
            let value = self.bound_parameter(graph, args, parameter);
            let (caller, site) = self.caller_site(call);
            self.add_hash(graph, value, caller, site, Some(stored));
        }
    }

    pub(super) fn rule_extend(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        receiver: ObjId,
        args: BoundId,
    ) {
        let iterables = match self.bound_varargs(args) {
            None => self.bound_parameter(graph, args, "iterable"),
            Some(varargs) => self.every(graph, varargs),
        };
        let (caller, site) = self.caller_site(call);
        if self.hashes_keys(receiver) {
            self.add_keys(
                graph,
                receiver,
                iterables,
                KeysConstruct::Bound(args),
                caller,
                site,
                Keeps::Hashes,
            );
            return;
        }
        let elements = self.iterated(graph, iterables, Iterated::Bound(args), call);
        let unknown = self.unknown(graph, receiver);
        self.add_edge(graph, elements, unknown);
        if self.kind_text_of(receiver) == "list" {
            self.add_length_hint(graph, iterables, caller, site, LENGTH_HINT);
        }
    }

    pub(super) fn rule_any_element(&mut self, graph: &mut Graph, call: CallId, receiver: ObjId) {
        if let Some(dst) = self.calls[call.index()].dst {
            let every = self.every(graph, receiver);
            self.add_edge(graph, every, dst);
        }
    }

    pub(super) fn rule_copy(&mut self, graph: &mut Graph, call: CallId, receiver: ObjId) {
        let (kind, exact) = match self.objects.get(receiver) {
            Object::Container(container) => (
                self.symbols.text(container.kind).to_string(),
                container.exact,
            ),
            _ => panic!("the copy of a container"),
        };
        let new = self.rule_container(graph, &kind, call, "copy", None, exact);
        if SEQUENCES.contains(&kind.as_str()) {
            self.copy_range(graph, receiver, new, Some((Some(0.into()), None)));
        } else if self.is_dict(receiver) {
            self.copy_items(graph, receiver, new);
            if let Some(factory) = self.container_factory(receiver) {
                let own = self.factory(graph, new);
                self.add_edge(graph, factory, own);
            }
        } else {
            let every = self.every(graph, receiver);
            let unknown = self.unknown(graph, new);
            self.add_edge(graph, every, unknown);
        }
        self.result(graph, call, new);
    }

    pub(super) fn rule_update(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        receiver: ObjId,
        args: BoundId,
    ) {
        if self.bound_given(args, "mapping") {
            let mapping = self.bound_parameter(graph, args, "mapping");
            let (caller, site) = self.caller_site(call);
            self.add_dict_items(graph, receiver, mapping, caller, site);
        }
        let keywords = self
            .bound_varkeywords(args)
            .expect("the keywords of an update");
        self.copy_items(graph, keywords, receiver);
    }

    pub(super) fn rule_lookup(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        receiver: ObjId,
        args: BoundId,
    ) {
        let key = self.bound_parameter(graph, args, "key");
        let keys = self.keys(graph, receiver);
        let (caller, site) = self.caller_site(call);
        self.add_hash(graph, key, caller, site, Some(keys));
    }

    pub(super) fn rule_setdefault(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        receiver: ObjId,
        args: BoundId,
    ) {
        self.rule_lookup(graph, call, receiver, args);
        let key = self.bound_parameter(graph, args, "key");
        let default = self.bound_parameter(graph, args, "default");
        self.write_keyed(graph, receiver, Some(key), Some(default));
        let dst = self.calls[call.index()].dst;
        self.read_keyed(graph, receiver, Some(key), dst);
    }

    pub(super) fn rule_get(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        receiver: ObjId,
        args: BoundId,
    ) {
        self.rule_lookup(graph, call, receiver, args);
        let key = self.bound_parameter(graph, args, "key");
        let dst = self.calls[call.index()].dst;
        self.read_keyed(graph, receiver, Some(key), dst);
        if let Some(dst) = dst {
            let default = self.bound_parameter(graph, args, "default");
            self.add_edge(graph, default, dst);
        }
    }

    pub(super) fn rule_view(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        receiver: ObjId,
        kind: &str,
    ) {
        let view = self.rule_container(graph, kind, call, "view", None, false);
        match kind {
            "dict_keys" => {
                let keys = self.keys(graph, receiver);
                let unknown = self.unknown(graph, view);
                self.add_edge(graph, keys, unknown);
            }
            "dict_values" => {
                let every = self.every(graph, receiver);
                let unknown = self.unknown(graph, view);
                self.add_edge(graph, every, unknown);
            }
            _ => {
                let exact = match self.objects.get(receiver) {
                    Object::Container(container) => container.exact,
                    _ => panic!("the view of a container"),
                };
                let pair = self.rule_container(graph, "tuple", call, "pair", Some(2), exact);
                let keys = self.keys(graph, receiver);
                let first = self.element(graph, pair, &Literal::Int(0.into()));
                self.add_edge(graph, keys, first);
                let every = self.every(graph, receiver);
                let second = self.element(graph, pair, &Literal::Int(1.into()));
                self.add_edge(graph, every, second);
                let unknown = self.unknown(graph, view);
                self.add_object(graph, unknown, pair);
            }
        }
        self.result(graph, call, view);
    }

    pub(super) fn rule_iter(&mut self, graph: &mut Graph, call: CallId, args: BoundId) {
        let dst = self.result_node(graph, call);
        let (caller, site) = self.caller_site(call);
        if !self.bound_surely(args, "sentinel") {
            let object = self.bound_parameter(graph, args, "object");
            self.add_iter(graph, object, dst, caller, site);
        }
        if self.bound_given(args, "sentinel") {
            let iterator =
                self.rule_container(graph, "callable_iterator", call, "iter", None, false);
            let object = self.bound_parameter(graph, args, "object");
            let source = self.keys(graph, iterator);
            self.add_edge(graph, object, source);
            self.add_object(graph, dst, iterator);
        }
    }

    pub(super) fn rule_enumerate(&mut self, graph: &mut Graph, call: CallId, args: BoundId) {
        let result = self.rule_container(graph, "enumerate", call, "enumerate", None, false);
        let pair = self.rule_container(graph, "tuple", call, "enumerate", Some(2), true);
        let iterable = self.bound_parameter(graph, args, "iterable");
        let elements = self.iterated(graph, iterable, Iterated::Enumerate(call), call);
        let second = self.element(graph, pair, &Literal::Int(1.into()));
        self.add_edge(graph, elements, second);
        let unknown = self.unknown(graph, result);
        self.add_object(graph, unknown, pair);
        self.result(graph, call, result);
    }

    pub(super) fn rule_zip(&mut self, graph: &mut Graph, call: CallId, args: BoundId) {
        let result = self.rule_container(graph, "zip", call, "zip", None, false);
        let details = self.calls[call.index()].clone();
        let starred = !details.star.is_empty();
        let length = if starred {
            None
        } else {
            Some(u32::try_from(details.args.len()).expect("a short call"))
        };
        let items = self.rule_container(graph, "tuple", call, "zip", length, true);
        if starred {
            let varargs = self.bound_varargs(args).expect("the iterables of zip");
            let iterables = self.every(graph, varargs);
            let elements = self.iterated(graph, iterables, Iterated::Zip(call), call);
            let unknown = self.unknown(graph, items);
            self.add_edge(graph, elements, unknown);
        } else {
            for (index, node) in details.args.iter().enumerate() {
                if let Some(node) = *node {
                    let elements = self.iterated(graph, node, Iterated::ZipAt(call, index), call);
                    let element = self.element(graph, items, &Literal::Int(index.into()));
                    self.add_edge(graph, elements, element);
                }
            }
        }
        let unknown = self.unknown(graph, result);
        self.add_object(graph, unknown, items);
        self.result(graph, call, result);
    }

    pub(super) fn rule_map(&mut self, graph: &mut Graph, call: CallId, args: BoundId) {
        let result = self.rule_container(graph, "map", call, "map", None, false);
        let base = self.prefixes.get(&call).map_or(call, |(base, _)| *base);
        let base_count = self.calls[base.index()].args.len();
        let details = self.calls[call.index()].clone();
        let mut elements = Vec::new();
        let mut surplus = Vec::new();
        for (index, node) in details.args.iter().skip(1).enumerate() {
            let node =
                node.map(|node| self.iterated(graph, node, Iterated::Map(call, index), call));
            if index + 1 < base_count {
                elements.push(node);
            } else {
                surplus.push(node);
            }
        }
        let starred = !details.star.is_empty();
        let mut rest = None;
        if starred || !surplus.is_empty() {
            let node = self.node(graph, None);
            for found in surplus.iter().flatten() {
                self.add_edge(graph, *found, node);
            }
            rest = Some(node);
        }
        if starred {
            let varargs = self.bound_varargs(args).expect("the iterables of map");
            let mut iterables = vec![self.every(graph, varargs)];
            if details.args.len() < 2 {
                iterables.push(self.bound_parameter(graph, args, "iterable"));
            }
            for (part, node) in iterables.into_iter().enumerate() {
                let found = self.iterated(graph, node, Iterated::MapStar(call, part), call);
                self.add_edge(graph, found, rest.expect("a rest"));
            }
        }
        let width = u32::try_from(elements.len()).expect("a short map");
        let key = SiteKey {
            caller: details.caller,
            site: details.site,
            role: Role::Map(width, rest.is_some()),
            implicit: true,
        };
        let dst = self.unknown(graph, result);
        let back = self.site_call(graph, key, &elements, Some(dst), rest);
        let function = self.bound_parameter(graph, args, "function");
        let callee = self.callee(graph, back);
        self.add_edge(graph, function, callee);
        self.result(graph, call, result);
    }

    pub(super) fn rule_filter(&mut self, graph: &mut Graph, call: CallId, args: BoundId) {
        let result = self.rule_container(graph, "filter", call, "filter", None, false);
        let iterable = self.bound_parameter(graph, args, "iterable");
        let elements = self.iterated(graph, iterable, Iterated::Filter(call), call);
        let unknown = self.unknown(graph, result);
        self.add_edge(graph, elements, unknown);
        let verdict = self.node(graph, None);
        let (caller, site) = self.caller_site(call);
        let key = SiteKey {
            caller,
            site,
            role: Role::Filter,
            implicit: true,
        };
        let back = self.site_call(graph, key, &[Some(elements)], Some(verdict), None);
        let function = self.bound_parameter(graph, args, "function");
        let callee = self.callee(graph, back);
        self.add_edge(graph, function, callee);
        self.add_truth(graph, verdict, caller, site);
        self.result(graph, call, result);
    }

    pub(super) fn rule_next(&mut self, graph: &mut Graph, call: CallId, args: BoundId) {
        let dst = self.result_node(graph, call);
        let iterator = self.bound_parameter(graph, args, "iterator");
        let (caller, site) = self.caller_site(call);
        self.add_next(graph, iterator, dst, caller, site);
        let default = self.bound_parameter(graph, args, "default");
        self.add_edge(graph, default, dst);
    }

    pub(super) fn rule_advance(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        receiver: ObjId,
        args: BoundId,
    ) {
        if let &Object::Generator { function, .. } = self.objects.get(receiver)
            && self.bound_has(args, "value")
        {
            let value = self.bound_parameter(graph, args, "value");
            let sent = self
                .objects
                .function(function)
                .sent_node
                .expect("a generator's sent node");
            self.add_edge(graph, value, sent);
        }
        let dst = self.result_node(graph, call);
        let (caller, site) = self.caller_site(call);
        let iteration =
            self.new_iteration(graph, dst, caller, site, false, Unless::Nothing, "advance");
        self.next_element(graph, receiver, iteration);
    }

    pub(super) fn rule_reversed(&mut self, graph: &mut Graph, call: CallId, args: BoundId) {
        let dst = self.result_node(graph, call);
        let result = self.rule_container(graph, "reversed", call, "reversed", None, false);
        let unknown = self.unknown(graph, result);
        let (caller, site) = self.caller_site(call);
        let iteration = self.new_iteration(
            graph,
            unknown,
            caller,
            site,
            false,
            Unless::Nothing,
            "iterate",
        );
        let rule = self.rule(Rule::Reversed {
            call,
            dst,
            result,
            iteration,
        });
        let sequence = self.bound_parameter(graph, args, "sequence");
        self.attach(graph, sequence, rule);
    }

    pub(super) fn reversed(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        call: CallId,
        dst: NodeId,
        result: ObjId,
        iteration: crate::engine::containers::IterationId,
    ) {
        if matches!(
            self.objects.get(object),
            Object::Instance { .. } | Object::Class(_)
        ) {
            let (caller, site) = self.caller_site(call);
            let key = SiteKey {
                caller,
                site,
                role: Role::Reversed,
                implicit: true,
            };
            let reverse = self.site_call(graph, key, &[], None, None);
            self.call_dunder(
                graph,
                object,
                "__reversed__",
                reverse,
                Some(dst),
                Unless::Nothing,
            );
            let items = self.unknown(graph, result);
            let rule = self.rule(Rule::ReversedSequence {
                object,
                call,
                result,
                items,
            });
            let types = self.types_of(graph, object);
            self.attach(graph, types, rule);
        } else {
            self.iterate(graph, object, iteration);
        }
        self.add_object(graph, dst, result);
    }

    pub(super) fn reversed_sequence(
        &mut self,
        graph: &mut Graph,
        class: ObjId,
        object: ObjId,
        call: CallId,
        result: ObjId,
    ) {
        if !self.objects.is_class(class) {
            return;
        }
        let reversed = self.symbols.intern("__reversed__");
        let unless = Unless::Names(vec![reversed].into_boxed_slice());
        let lengths = self.lookup_name(graph, class, "__len__", Some(object), None, unless.clone());
        let getters = self.lookup_name(
            graph,
            class,
            "__getitem__",
            Some(object),
            None,
            unless.clone(),
        );
        let (caller, site) = self.caller_site(call);
        let length = self.site_call(
            graph,
            SiteKey {
                caller,
                site,
                role: Role::ReversedLen,
                implicit: true,
            },
            &[],
            None,
            None,
        );
        let index = self.site_call(
            graph,
            SiteKey {
                caller,
                site,
                role: Role::ReversedItem,
                implicit: true,
            },
            &[None],
            None,
            None,
        );
        let length = self.implicit_call(graph, object, "__len__", length, None, unless.clone());
        let items = self.unknown(graph, result);
        let index = self.implicit_call(graph, object, "__getitem__", index, Some(items), unless);
        let source = self.keys(graph, result);
        for (other, methods, implicit, reversing) in [
            (getters, lengths, length, Some(source)),
            (lengths, getters, index, None),
        ] {
            let rule = self.rule(Rule::ReverseSequence {
                object,
                methods,
                implicit,
                reversing,
            });
            self.attach(graph, other, rule);
        }
    }

    pub(super) fn reverse_sequence(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        methods: NodeId,
        implicit: CallId,
        reversing: Option<NodeId>,
    ) {
        if !self.reverse_sequences.insert((object, methods, implicit)) {
            return;
        }
        let rule = self.calls[implicit.index()].rule;
        self.attach(graph, methods, rule);
        if let Some(reversing) = reversing {
            self.add_object(graph, reversing, object);
        }
    }

    fn types_of(&mut self, graph: &mut Graph, object: ObjId) -> NodeId {
        match self.objects.get(object) {
            &Object::Instance { class, .. } => self.constant(graph, class),
            Object::Class(class) => class.metaclass,
            _ => panic!("the types of an instance or a class"),
        }
    }
}
