use pycg_solver::{NodeId, ObjId};

use crate::builder::calls::MethodKind;
use crate::engine::attributes::AccessKind;
use crate::engine::hierarchy::{LookupAttr, LookupKey, Unless};
use crate::engine::objects::{Literal, Object};
use crate::engine::outside::outside_name;
use crate::engine::outside_calls::BoundId;
use crate::engine::rules::Rule;
use crate::engine::semantics::{CallId, Origin, Role, SiteKey};
use crate::engine::symbols::Sym;
use crate::engine::trace::Trace;
use crate::engine::{Graph, State, not_ported};
use crate::model::BUILTIN_MODULE;
use crate::models::{
    DefaultConstant, Model, PROPERTY_ACCESSORS, Rule as ModelRule, WRAPPED_ATTRIBUTES_BY_TYPE,
    lookup, method_model, parse_signature,
};

const KIND_CLASSES: &[(&str, (&str, &str))] = &[
    ("generator", ("types.GeneratorType", "types.GeneratorType")),
    (
        "async_generator",
        ("types.AsyncGeneratorType", "types.AsyncGeneratorType"),
    ),
    (
        "dict_keys",
        ("_collections_abc.dict_keys", "<builtin>.dict_keys"),
    ),
    (
        "dict_values",
        ("_collections_abc.dict_values", "<builtin>.dict_values"),
    ),
    (
        "dict_items",
        ("_collections_abc.dict_items", "<builtin>.dict_items"),
    ),
];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum WrapperKey {
    Call(Sym, Origin),
    Field(Sym, NodeId),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum PropertyRule {
    StoreAccessors(BoundId),
    With {
        args: BoundId,
        accessor: Sym,
        call: CallId,
    },
    Give(CallId),
    Run {
        accessor: Sym,
        run: CallId,
    },
}

impl<T: Trace> State<T> {
    pub(super) fn apply_rule(
        &mut self,
        graph: &mut Graph,
        model: &'static Model,
        call: CallId,
        receiver: Option<ObjId>,
    ) {
        let args = self.bind_model(graph, call, model);
        match model.rule {
            ModelRule::Wrap => self.rule_wrap(graph, call, args, model.arguments[0]),
            ModelRule::Property => self.rule_property(graph, call, args),
            ModelRule::PropertyInit => {
                if self.may_init_property(call) {
                    self.properties(graph, call, args, PropertyRule::StoreAccessors(args));
                }
            }
            ModelRule::PropertyWith => {
                let accessor = self.symbols.intern(model.arguments[0]);
                self.properties(
                    graph,
                    call,
                    args,
                    PropertyRule::With {
                        args,
                        accessor,
                        call,
                    },
                );
            }
            ModelRule::PropertyRun => self.rule_property_run(graph, call, args, model.arguments[0]),
            ModelRule::Bind => {
                self.rule_bind(graph, call, receiver.expect("a bound wrapper"), args)
            }
            rule => not_ported(&format!("builtin rules: the rule {}", rule.name())),
        }
    }

    fn bind_model(&mut self, graph: &mut Graph, call: CallId, model: &'static Model) -> BoundId {
        let key = (call, std::ptr::from_ref(model) as usize);
        if let Some(&bound) = self.model_bindings.get(&key) {
            return bound;
        }
        let parsed = parse_signature(model.signature);
        let constants: Vec<(Box<str>, Literal)> = parsed
            .constants
            .iter()
            .map(|(name, constant)| {
                let literal = match constant {
                    DefaultConstant::Str(text) => {
                        Literal::Str(text.chars().map(u32::from).collect())
                    }
                    DefaultConstant::Int(value) => Literal::Int((*value).into()),
                };
                (name.clone(), literal)
            })
            .collect();
        let bound = self.bind_signature(graph, call, parsed.signature, &constants);
        self.model_bindings.insert(key, bound);
        bound
    }

    fn args(&mut self, graph: &mut Graph, args: BoundId, name: &str) -> NodeId {
        self.bound_parameter(graph, args, name)
    }

    pub(super) fn result(&mut self, graph: &mut Graph, call: CallId, object: ObjId) {
        if let Some(dst) = self.calls[call.index()].dst {
            self.add_object(graph, dst, object);
        }
    }

    fn wrapper(&mut self, graph: &mut Graph, key: WrapperKey, kind: Sym, site: Sym) -> ObjId {
        if let Some(&wrapper) = self.wrappers.get(&key) {
            return wrapper;
        }
        let wrapper = self.new_object(graph, Object::Wrapper { kind, site });
        self.wrappers.insert(key, wrapper);
        wrapper
    }

    fn call_wrapper(&mut self, graph: &mut Graph, kind: &str, call: CallId) -> ObjId {
        let kind = self.symbols.intern(kind);
        let details = &self.calls[call.index()];
        let (origin, site) = (details.origin, details.site);
        self.wrapper(graph, WrapperKey::Call(kind, origin), kind, site)
    }

    fn func_field(&mut self, graph: &mut Graph, wrapper: ObjId) -> NodeId {
        let name = self.symbols.intern("__func__");
        self.field(graph, wrapper, name)
    }

    fn rule_wrap(&mut self, graph: &mut Graph, call: CallId, args: BoundId, kind: &str) {
        let wrapper = self.call_wrapper(graph, kind, call);
        let function = self.args(graph, args, "function");
        let field = self.func_field(graph, wrapper);
        self.add_edge(graph, function, field);
        self.result(graph, call, wrapper);
    }

    pub(super) fn add_implicit_method(
        &mut self,
        graph: &mut Graph,
        value: NodeId,
        field: NodeId,
        kind: MethodKind,
        site: &str,
    ) {
        let kind = self.symbols.intern(kind.name());
        let site = self.symbols.intern(site);
        let rule = self.rule(Rule::ImplicitMethod { field, kind, site });
        self.attach(graph, value, rule);
    }

    pub(super) fn implicit_method(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        field: NodeId,
        kind: Sym,
        site: Sym,
    ) {
        let mut value = object;
        if matches!(self.objects.get(object), Object::Function(_)) {
            let wrapper = self.wrapper(graph, WrapperKey::Field(kind, field), kind, site);
            let func = self.func_field(graph, wrapper);
            self.add_object(graph, func, object);
            value = wrapper;
        }
        self.add_object(graph, field, value);
    }

    fn rule_property(&mut self, graph: &mut Graph, call: CallId, args: BoundId) {
        let property = self.call_wrapper(graph, "property", call);
        self.store_accessors(graph, property, args);
        self.result(graph, call, property);
    }

    fn store_accessors(&mut self, graph: &mut Graph, property: ObjId, args: BoundId) {
        let names = lookup(WRAPPED_ATTRIBUTES_BY_TYPE, "property").expect("the property accessors");
        for &name in *names {
            if self.bound_given(args, name) {
                let value = self.args(graph, args, name);
                let name = self.symbols.intern(name);
                let field = self.field(graph, property, name);
                self.add_edge(graph, value, field);
            }
        }
    }

    fn properties(&mut self, graph: &mut Graph, call: CallId, args: BoundId, rule: PropertyRule) {
        let dst = self.calls[call.index()].dst;
        let rule = self.rule(Rule::PropertyReceiver { rule, dst });
        let receiver = self.args(graph, args, "self");
        self.attach(graph, receiver, rule);
    }

    pub(super) fn property_receiver(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        rule: PropertyRule,
        dst: Option<NodeId>,
    ) {
        match self.objects.get(object) {
            Object::Wrapper { kind, .. } => {
                if self.symbols.text(*kind) == "property" {
                    self.run_property_rule(graph, object, rule);
                }
            }
            Object::Instance { class, .. } => {
                let class = *class;
                let builtin = self.external(graph, &format!("{BUILTIN_MODULE}.property"), 0, false);
                let key = LookupKey {
                    attr: LookupAttr::Object(builtin),
                    receiver: None,
                    after: None,
                    unless: Unless::MayDerive,
                };
                let derives = self.lookup(graph, class, key);
                let each = self.rule(Rule::DerivedProperty {
                    rule,
                    property: object,
                    dst,
                });
                self.attach(graph, derives, each);
            }
            _ => panic!("a property receiver is a wrapper or an instance"),
        }
    }

    pub(super) fn run_property_rule(
        &mut self,
        graph: &mut Graph,
        property: ObjId,
        rule: PropertyRule,
    ) {
        match rule {
            PropertyRule::StoreAccessors(args) => self.store_accessors(graph, property, args),
            PropertyRule::With {
                args,
                accessor,
                call,
            } => {
                let function = self.args(graph, args, "function");
                let field = self.field(graph, property, accessor);
                self.add_edge(graph, function, field);
                self.result(graph, call, property);
            }
            PropertyRule::Give(call) => self.result(graph, call, property),
            PropertyRule::Run { accessor, run } => {
                let field = self.field(graph, property, accessor);
                let rule = self.rule(Rule::CallEach { call: run });
                self.attach(graph, field, rule);
            }
        }
    }

    fn may_init_property(&self, call: CallId) -> bool {
        let names = ["fget", "fset", "fdel", "doc"];
        let details = &self.calls[call.index()];
        let given = details.args.len();
        if given > names.len() + 1 || (given == 0 && details.star.is_empty()) {
            return false;
        }
        let mut taken: Vec<&str> = names[..given.saturating_sub(1).min(names.len())].to_vec();
        for &(name, _) in &details.keywords {
            let name = self.symbols.text(name);
            if !names.contains(&name) || taken.contains(&name) {
                return false;
            }
            taken.push(name);
        }
        true
    }

    fn positional_call(&self, call: CallId, least: usize, most: usize) -> bool {
        let details = &self.calls[call.index()];
        if !details.keywords.is_empty() || !details.double_star.is_empty() {
            return false;
        }
        if !details.star.is_empty() {
            return details.args.len() <= most;
        }
        (least..=most).contains(&details.args.len())
    }

    fn supplies(&self, call: CallId, index: usize) -> bool {
        let details = &self.calls[call.index()];
        index < details.args.len() || !details.star.is_empty()
    }

    fn rule_property_run(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        args: BoundId,
        accessor: &str,
    ) {
        let (least, most, kind) = match accessor {
            "fget" => (2, 3, AccessKind::Load),
            "fset" => (3, 3, AccessKind::Store),
            "fdel" => (2, 2, AccessKind::Delete),
            _ => panic!("a property accessor: {accessor}"),
        };
        if !self.positional_call(call, least, most) {
            return;
        }
        if accessor == "fget" && self.literal_none(call, 1) {
            if self.literal_none(call, 2) || !self.supplies(call, 2) {
                return;
            }
            self.properties(graph, call, args, PropertyRule::Give(call));
            return;
        }
        let mut values = vec![Some(self.args(graph, args, "instance"))];
        if accessor == "fset" {
            values.push(Some(self.args(graph, args, "value")));
        }
        let dst = if accessor == "fget" {
            self.calls[call.index()].dst
        } else {
            None
        };
        let details = &self.calls[call.index()];
        let accessor = self.symbols.intern(accessor);
        let key = SiteKey {
            caller: details.caller,
            site: details.site,
            role: Role::Property(kind, accessor),
            implicit: true,
        };
        let run = self.site_call(graph, key, &values, dst, None);
        self.properties(graph, call, args, PropertyRule::Run { accessor, run });
    }

    fn rule_bind(&mut self, graph: &mut Graph, call: CallId, receiver: ObjId, args: BoundId) {
        let Some(dst) = self.calls[call.index()].dst else {
            return;
        };
        if !self.positional_call(call, 1, 2) {
            return;
        }
        let no_instance = self.literal_none(call, 0);
        let owner_none = self.literal_none(call, 1);
        let may_have_owner = self.supplies(call, 1) && !owner_none;
        let may_lack_owner = self.calls[call.index()].args.len() < 2 || owner_none;
        if no_instance && !may_have_owner {
            return;
        }
        let &Object::Wrapper { kind, .. } = self.objects.get(receiver) else {
            panic!("__get__ of a wrapper")
        };
        if self.symbols.text(kind) == "staticmethod" {
            let func = self.func_field(graph, receiver);
            self.add_edge(graph, func, dst);
            return;
        }
        if may_have_owner {
            let rule = self.rule(Rule::BindClass {
                method: receiver,
                dst,
            });
            let owner = self.args(graph, args, "owner");
            self.attach(graph, owner, rule);
        }
        if may_lack_owner && !no_instance {
            let rule = self.rule(Rule::BindType {
                method: receiver,
                dst,
            });
            let instance = self.args(graph, args, "instance");
            self.attach(graph, instance, rule);
        }
    }

    pub(super) fn bind_type(
        &mut self,
        graph: &mut Graph,
        instance: ObjId,
        method: ObjId,
        dst: NodeId,
    ) {
        if matches!(self.objects.get(instance), Object::Instance { .. }) {
            self.bind(graph, method, Some(instance), dst, None);
            return;
        }
        let rule = self.rule(Rule::BindClass { method, dst });
        let metaclass = self.objects.class(instance).metaclass;
        self.attach(graph, metaclass, rule);
    }

    pub(super) fn literal_none(&self, call: CallId, index: usize) -> bool {
        let (base, receivers) = match self.prefixes.get(&call) {
            None => (call, 0),
            Some((base, crate::engine::semantics::Prefix::Receivers(receivers))) => {
                (*base, receivers.len())
            }
            Some((base, crate::engine::semantics::Prefix::Group(group))) => {
                (*base, self.group_width(*group))
            }
        };
        let root = self.roots.get(&base).copied().unwrap_or(base);
        if self.calls[root.index()].origin != Origin::Call(root) {
            return false;
        }
        let details = &self.calls[root.index()];
        let Some(index) = index.checked_sub(receivers) else {
            return false;
        };
        self.none_arguments
            .get(&(details.caller, details.site))
            .is_some_and(|nones| nones.contains(&(index as u32)))
    }

    pub(super) fn load_builtin_attribute(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        type_name: &str,
        attr: Sym,
        dst: NodeId,
    ) {
        let text = self.symbols.text(attr).to_string();
        if lookup(WRAPPED_ATTRIBUTES_BY_TYPE, type_name)
            .is_some_and(|names| names.contains(&text.as_str()))
        {
            let field = self.field(graph, object, attr);
            self.add_edge(graph, field, dst);
        } else if method_model(type_name, &text).is_some() {
            let method = self.builtin_method(graph, object, type_name, attr);
            self.add_object(graph, dst, method);
        } else {
            let (class, prefix) = self.kind_class(type_name);
            self.stub_member(graph, object, &class, &prefix, attr, dst);
        }
    }

    pub(super) fn kind_class(&mut self, kind: &str) -> (String, String) {
        if let Some(&(class, prefix)) = lookup(KIND_CLASSES, kind) {
            return (class.to_string(), prefix.to_string());
        }
        if kind.contains('.') {
            return (
                kind.to_string(),
                outside_name(&self.stubs.public_name(kind)),
            );
        }
        (
            format!("builtins.{kind}"),
            format!("{BUILTIN_MODULE}.{kind}"),
        )
    }

    fn builtin_method(
        &mut self,
        graph: &mut Graph,
        receiver: ObjId,
        type_name: &str,
        method: Sym,
    ) -> ObjId {
        if let Some(&found) = self.builtin_methods.get(&(receiver, method)) {
            return found;
        }
        let (_, prefix) = self.kind_class(type_name);
        let name = format!("{prefix}.{}", self.symbols.text(method));
        let object = Object::BuiltinMethod {
            receiver,
            type_name: self.symbols.intern(type_name),
            method,
            name: self.symbols.intern(&name),
        };
        let found = self.new_object(graph, object);
        self.builtin_methods.insert((receiver, method), found);
        found
    }

    pub(super) fn call_builtin_method(&mut self, graph: &mut Graph, object: ObjId, call: CallId) {
        let &Object::BuiltinMethod {
            receiver,
            type_name,
            method,
            name,
        } = self.objects.get(object)
        else {
            panic!("a builtin method")
        };
        self.add_external_call_edge(call, name, crate::engine::outside_calls::Known::Stub);
        let model = method_model(self.symbols.text(type_name), self.symbols.text(method))
            .expect("a builtin method has a model");
        self.apply_rule(graph, model, call, Some(receiver));
    }

    pub(super) fn object_type_name(&self, object: ObjId) -> String {
        match self.objects.get(object) {
            Object::Wrapper { kind, .. } => self.symbols.text(*kind).to_string(),
            Object::Container(container) => self.symbols.text(container.kind).to_string(),
            &Object::Generator { function, .. } => {
                if self.objects.function(function).is_async {
                    "async_generator".to_string()
                } else {
                    "generator".to_string()
                }
            }
            Object::Const { value, .. } => {
                crate::model::constant_type_name(&value.view()).to_string()
            }
            _ => panic!("a builtin value"),
        }
    }

    pub(super) fn property_accessor(&self, method: &str) -> &'static str {
        lookup(PROPERTY_ACCESSORS, method).expect("a property accessor")
    }

    pub(super) fn wrapper_kind_is(&self, object: ObjId, wanted: &str) -> bool {
        matches!(self.objects.get(object), &Object::Wrapper { kind, .. } if self.symbols.text(kind) == wanted)
    }
}
