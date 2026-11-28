use pycg_solver::{NodeId, ObjId};
use rustc_hash::FxHashMap;

use crate::engine::attributes::{AccessId, AccessKind};
use crate::engine::containers::ContainerOrigin;
use crate::engine::hierarchy::{LookupAttr, LookupKey, Namespace, Unless};
use crate::engine::objects::{Literal, Object};
use crate::engine::outside::OutsideGives;
use crate::engine::outside_calls::BoundId;
use crate::engine::rules::Rule;
use crate::engine::semantics::CallId;
use crate::engine::symbols::Sym;
use crate::engine::{Graph, State, not_ported};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct GetmembersId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum DefaultAction {
    AddNamespace(NodeId),
    MembersListed(GetmembersId),
}

pub struct Getmembers {
    call: CallId,
    names: Option<NodeId>,
    values: Option<NodeId>,
    loaders: FxHashMap<Sym, AccessId>,
}

impl State {
    fn when_default_member(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        name: &str,
        action: DefaultAction,
        result: Option<NodeId>,
    ) {
        let name = self.symbols.intern(name);
        let rule = self.rule(Rule::WhenDefaultMemberOnType {
            object,
            name,
            action,
            result,
        });
        let types = match self.objects.get(object) {
            &Object::Instance { class, .. } => self.constant(graph, class),
            Object::Class(class) => class.metaclass,
            _ => panic!("the types of an instance or a class"),
        };
        self.attach(graph, types, rule);
    }

    pub(super) fn when_default_member_on_type(
        &mut self,
        graph: &mut Graph,
        kind: ObjId,
        object: ObjId,
        name: Sym,
        action: DefaultAction,
        result: Option<NodeId>,
    ) {
        if !self.objects.is_class(kind) {
            if self.outside_member(kind, name) != OutsideGives::Override {
                self.run_default_action(graph, object, action);
            }
            return;
        }
        let rule = self.rule(Rule::RunDefaultAction {
            object,
            action,
            result,
        });
        let key = LookupKey {
            attr: LookupAttr::Name(name),
            receiver: None,
            after: None,
            unless: Unless::DefaultMember,
        };
        let found = self.lookup(graph, kind, key);
        self.attach(graph, found, rule);
    }

    pub(super) fn run_default_action(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        action: DefaultAction,
    ) {
        match action {
            DefaultAction::AddNamespace(dst) => {
                let namespace = self.namespace(graph, object);
                self.add_object(graph, dst, namespace);
            }
            DefaultAction::MembersListed(access) => self.members_listed(graph, object, access),
        }
    }

    fn subclasses_listed(&mut self, graph: &mut Graph, class: ObjId) -> NodeId {
        if let Some(&node) = self.namespace_nodes.get(&(class, Namespace::Subclasses)) {
            return node;
        }
        let node = self.node(graph, None);
        self.namespace_nodes
            .insert((class, Namespace::Subclasses), node);
        let subclasses: Vec<ObjId> = self
            .objects
            .class(class)
            .subclasses
            .iter()
            .copied()
            .collect();
        for subclass in subclasses {
            self.add_object(graph, node, subclass);
        }
        node
    }

    pub(super) fn subclasses(&mut self, graph: &mut Graph, class: ObjId, call: CallId) {
        let details = &self.calls[call.index()];
        let Some(dst) = details.dst else {
            return;
        };
        let (origin, site) = (details.origin, details.site);
        let origin = ContainerOrigin::Rule(origin, "subclasses", None);
        let found = self.container_at(graph, "list", origin, site, None, false);
        let listed = self.subclasses_listed(graph, class);
        let unknown = self.unknown(graph, found);
        self.add_edge(graph, listed, unknown);
        self.add_object(graph, dst, found);
    }

    pub(super) fn add_namespace(&mut self, graph: &mut Graph, object: ObjId, dst: NodeId) {
        if self.objects.is_class(object) {
            self.when_default_member(
                graph,
                object,
                "__dict__",
                DefaultAction::AddNamespace(dst),
                Some(dst),
            );
        }
    }

    fn namespace(&mut self, graph: &mut Graph, object: ObjId) -> ObjId {
        let site = format!("{}.__dict__", self.object_name(object));
        let site = self.symbols.intern(&site);
        let container = self.container_at(
            graph,
            "dict",
            ContainerOrigin::Object(object, "namespace"),
            site,
            None,
            false,
        );
        if self.namespaces.insert(object) {
            let names = self.namespace_names(graph, object);
            let keys = self.keys(graph, container);
            self.add_edge(graph, names, keys);
            let unknown = self.unknown(graph, container);
            let rule = self.rule(Rule::NamespaceElement {
                object,
                container,
                unknown,
            });
            self.attach(graph, names, rule);
        }
        container
    }

    pub(super) fn namespace_element(
        &mut self,
        graph: &mut Graph,
        name: ObjId,
        object: ObjId,
        container: ObjId,
    ) {
        let (attr, value) = self.const_name(name);
        let field = self.field(graph, object, attr);
        let element = self.element(graph, container, &value);
        self.add_edge(graph, field, element);
    }

    fn const_name(&mut self, name: ObjId) -> (Sym, Literal) {
        let Object::Const { value, .. } = self.objects.get(name) else {
            panic!("a namespace name is a constant")
        };
        let value = value.clone();
        let Literal::Str(code_points) = &value else {
            panic!("a namespace name is a string")
        };
        let text: Option<String> = code_points
            .iter()
            .map(|&point| char::from_u32(point))
            .collect();
        let Some(text) = text else {
            not_ported("an attribute name with a lone surrogate")
        };
        (self.symbols.intern(&text), value)
    }

    pub(super) fn rule_namespace(&mut self, graph: &mut Graph, call: CallId, args: BoundId) {
        let Some(dst) = self.calls[call.index()].dst else {
            return;
        };
        if !self.bound_given(args, "object") || !self.namespace_calls.insert(call) {
            return;
        }
        let rule = self.rule(Rule::AddNamespace { dst });
        let object = self.bound_parameter(graph, args, "object");
        self.attach(graph, object, rule);
    }

    pub(super) fn member_names(&mut self, graph: &mut Graph, class: ObjId) -> NodeId {
        if let Some(&node) = self.namespace_nodes.get(&(class, Namespace::Members)) {
            return node;
        }
        let mut made = Vec::new();
        let mut pending = vec![class];
        while let Some(member) = pending.pop() {
            if self
                .namespace_nodes
                .contains_key(&(member, Namespace::Members))
            {
                continue;
            }
            let node = self.node(graph, None);
            self.namespace_nodes
                .insert((member, Namespace::Members), node);
            let names = self.namespace_names(graph, member);
            self.add_edge(graph, names, node);
            made.push(member);
            pending.extend(self.analysed_candidate_bases(member));
        }
        for member in made {
            for base in self.analysed_candidate_bases(member) {
                let source = self.namespace_nodes[&(base, Namespace::Members)];
                let target = self.namespace_nodes[&(member, Namespace::Members)];
                self.add_edge(graph, source, target);
            }
        }
        self.namespace_nodes[&(class, Namespace::Members)]
    }

    fn analysed_candidate_bases(&self, class: ObjId) -> Vec<ObjId> {
        let mut bases: Vec<ObjId> = Vec::new();
        for candidates in &self.objects.class(class).bases {
            for &base in candidates.iter().flatten() {
                if self.objects.is_class(base) && !bases.contains(&base) {
                    bases.push(base);
                }
            }
        }
        bases.sort_by_cached_key(|&base| self.base_order(Some(base)));
        bases
    }

    pub(super) fn members_base(&mut self, graph: &mut Graph, base: ObjId, class: ObjId) {
        if let Some(&members) = self.namespace_nodes.get(&(class, Namespace::Members)) {
            let names = self.member_names(graph, base);
            self.add_edge(graph, names, members);
        }
    }

    pub(super) fn rule_members(&mut self, graph: &mut Graph, call: CallId, args: BoundId) {
        let Some(dst) = self.calls[call.index()].dst else {
            return;
        };
        if !self.getmembers_calls.insert(call) {
            return;
        }
        let access = GetmembersId(u32::try_from(self.getmembers.len()).expect("fewer accesses"));
        self.getmembers.push(Getmembers {
            call,
            names: None,
            values: None,
            loaders: FxHashMap::default(),
        });
        let rule = self.rule(Rule::MembersOf { access, dst });
        let object = self.bound_parameter(graph, args, "object");
        self.attach(graph, object, rule);
    }

    pub(super) fn members_of(&mut self, graph: &mut Graph, object: ObjId, access: GetmembersId) {
        let call = self.getmembers[access.0 as usize].call;
        let dst = self.calls[call.index()].dst;
        self.when_default_member(
            graph,
            object,
            "__dir__",
            DefaultAction::MembersListed(access),
            dst,
        );
    }

    fn members_listed(&mut self, graph: &mut Graph, object: ObjId, access: GetmembersId) {
        if !self.members_listed.insert((object, access)) {
            return;
        }
        let call = self.getmembers[access.0 as usize].call;
        let details = &self.calls[call.index()];
        let (origin, site, dst) = (details.origin, details.site, details.dst.expect("a result"));
        let found = self.container_at(
            graph,
            "list",
            ContainerOrigin::Rule(origin, "members", None),
            site,
            None,
            true,
        );
        let pair = self.container_at(
            graph,
            "tuple",
            ContainerOrigin::Rule(origin, "member", Some(2)),
            site,
            Some(2),
            true,
        );
        let unknown = self.unknown(graph, found);
        self.add_object(graph, unknown, pair);
        let names = self.element(graph, pair, &Literal::Int(0.into()));
        let values = self.element(graph, pair, &Literal::Int(1.into()));
        let record = &mut self.getmembers[access.0 as usize];
        record.names = Some(names);
        record.values = Some(values);
        self.add_object(graph, dst, found);
        let class = match self.objects.get(object) {
            &Object::Instance { class, .. } => class,
            _ => object,
        };
        let members = self.member_names(graph, class);
        self.add_edge(graph, members, names);
        let rule = self.rule(Rule::LoadMember {
            object,
            access,
            values,
        });
        self.attach(graph, members, rule);
        if matches!(self.objects.get(object), Object::Instance { .. }) {
            let own = self.namespace_names(graph, object);
            self.add_edge(graph, own, names);
            let rule = self.rule(Rule::MemberField { object, values });
            self.attach(graph, own, rule);
        }
    }

    pub(super) fn load_member(
        &mut self,
        graph: &mut Graph,
        name: ObjId,
        object: ObjId,
        access: GetmembersId,
    ) {
        let (attr, _) = self.const_name(name);
        let load = match self.getmembers[access.0 as usize].loaders.get(&attr) {
            Some(&load) => load,
            None => {
                let record = &self.getmembers[access.0 as usize];
                let (call, values) = (record.call, record.values.expect("listed members"));
                let details = &self.calls[call.index()];
                let caller = self.symbols.text(details.caller).to_string();
                let site = self.symbols.text(details.site).to_string();
                let text = self.symbols.text(attr).to_string();
                let load =
                    self.new_access(AccessKind::Load, &text, Some(values), None, &caller, &site);
                self.getmembers[access.0 as usize]
                    .loaders
                    .insert(attr, load);
                load
            }
        };
        self.apply_access(graph, object, load);
    }

    pub(super) fn member_field(
        &mut self,
        graph: &mut Graph,
        name: ObjId,
        object: ObjId,
        values: NodeId,
    ) {
        let (attr, _) = self.const_name(name);
        let field = self.field(graph, object, attr);
        self.add_edge(graph, field, values);
    }
}
