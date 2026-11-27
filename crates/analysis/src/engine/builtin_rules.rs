use num_bigint::BigInt;
use pycg_solver::{NodeId, ObjId};
use rustc_hash::FxHashSet;

use crate::builder::calls::MethodKind;
use crate::engine::attributes::AccessKind;
use crate::engine::hierarchy::{LookupAttr, LookupKey, Unless};
use crate::engine::objects::{Literal, Object};
use crate::engine::outside::outside_name;
use crate::engine::outside_calls::{BoundId, Known};
use crate::engine::protocols::{Conversion, OperatorCall};
use crate::engine::rules::Rule;
use crate::engine::semantics::{CallId, Origin, Role, SiteKey};
use crate::engine::symbols::Sym;
use crate::engine::trace::Trace;
use crate::engine::{Graph, State, not_ported};
use crate::model::BUILTIN_MODULE;
use crate::models::{
    DefaultConstant, Model, PROPERTY_ACCESSORS, RETURNS_ARGUMENT, ReturnsArgument,
    Rule as ModelRule, WRAPPED_ATTRIBUTES_BY_TYPE, lookup, method_model, parse_signature,
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
            ModelRule::Getattr => self.rule_getattr(graph, call, args, model.arguments[0]),
            ModelRule::Setattr => {
                let object = self.args(graph, args, "obj");
                let name = self.args(graph, args, "name");
                let value = self.args(graph, args, "value");
                self.named_access(graph, object, name, None, Some(value), call, false);
            }
            ModelRule::Delattr => {
                let object = self.args(graph, args, "obj");
                let name = self.args(graph, args, "name");
                self.named_access(graph, object, name, None, None, call, true);
            }
            ModelRule::Super => self.rule_super(graph, call, args),
            ModelRule::Type => self.rule_type(graph, call, args),
            ModelRule::Collection => {
                self.rule_collection(graph, call, receiver, args, model.arguments[0])
            }
            ModelRule::Dict => {
                let kind = model.arguments.first().copied().unwrap_or("dict");
                let new = self.rule_dict(graph, call, receiver, args, kind, "dict");
                self.result(graph, call, new);
            }
            ModelRule::Defaultdict => self.rule_defaultdict(graph, call, receiver, args),
            ModelRule::Counter => self.rule_counter(graph, call, receiver, args),
            ModelRule::Count => self.rule_count(graph, call, container(receiver), args),
            ModelRule::Add => {
                self.rule_add(graph, call, container(receiver), args, model.arguments[0])
            }
            ModelRule::Extend => self.rule_extend(graph, call, container(receiver), args),
            ModelRule::AnyElement => self.rule_any_element(graph, call, container(receiver)),
            ModelRule::Copy => self.rule_copy(graph, call, container(receiver)),
            ModelRule::Update => self.rule_update(graph, call, container(receiver), args),
            ModelRule::Setdefault => self.rule_setdefault(graph, call, container(receiver), args),
            ModelRule::Get => self.rule_get(graph, call, container(receiver), args),
            ModelRule::Lookup => self.rule_lookup(graph, call, container(receiver), args),
            ModelRule::View => self.rule_view(graph, call, container(receiver), model.arguments[0]),
            ModelRule::Iter => self.rule_iter(graph, call, args),
            ModelRule::Enumerate => self.rule_enumerate(graph, call, args),
            ModelRule::Zip => self.rule_zip(graph, call, args),
            ModelRule::Map => self.rule_map(graph, call, args),
            ModelRule::Filter => self.rule_filter(graph, call, args),
            ModelRule::Next => self.rule_next(graph, call, args),
            ModelRule::Advance => self.rule_advance(graph, call, container(receiver), args),
            ModelRule::Reversed => self.rule_reversed(graph, call, args),
            ModelRule::Namespace => self.rule_namespace(graph, call, args),
            ModelRule::Members => self.rule_members(graph, call, args),
            ModelRule::Bind => {
                self.rule_bind(graph, call, receiver.expect("a bound wrapper"), args)
            }
            ModelRule::Convert => self.rule_convert(graph, call, args, model.arguments),
            ModelRule::Pow => self.rule_pow(graph, call, args),
            ModelRule::Print => self.rule_print(graph, call, args),
            rule => not_ported(&format!("builtin rules: the rule {}", rule.name())),
        }
    }

    fn bind_model(&mut self, graph: &mut Graph, call: CallId, model: &'static Model) -> BoundId {
        let key = std::ptr::from_ref(model) as usize;
        self.bind_entry(graph, call, key, model.signature)
    }

    fn bind_entry(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        entry: usize,
        signature: &str,
    ) -> BoundId {
        let key = (call, entry);
        if let Some(&bound) = self.model_bindings.get(&key) {
            return bound;
        }
        let parsed = parse_signature(signature);
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

    pub(super) fn returns_argument(
        &mut self,
        graph: &mut Graph,
        callee: ObjId,
        call: CallId,
    ) -> bool {
        let name = self.objects.name(callee, &self.symbols);
        let Some(entry) = lookup(RETURNS_ARGUMENT, &name) else {
            return false;
        };
        let analysed = matches!(self.objects.get(callee), Object::Function(_));
        let name = self.symbols.intern(&name);
        self.model_edge(name, analysed, call);
        self.return_argument(graph, entry, name, analysed, call);
        true
    }

    pub(super) fn model_edge(&mut self, name: Sym, analysed: bool, call: CallId) {
        if analysed {
            self.add_call_edge(call, name);
        } else {
            self.add_external_call_edge(call, name, Known::Stub);
        }
    }

    pub(super) fn return_argument(
        &mut self,
        graph: &mut Graph,
        entry: &'static ReturnsArgument,
        name: Sym,
        analysed: bool,
        call: CallId,
    ) {
        let Some(dst) = self.calls[call.index()].dst else {
            return;
        };
        let key = std::ptr::from_ref(entry) as usize;
        let args = self.bind_entry(graph, call, key, entry.signature);
        if let Some(parameter) = entry.argument
            && self.bound_given(args, parameter)
        {
            let given = self.bound_parameter(graph, args, parameter);
            self.add_edge(graph, given, dst);
        }
        if entry
            .argument
            .is_none_or(|parameter| !self.bound_surely(args, parameter))
        {
            let named = match entry.wrapper {
                Some(wrapper) => self.symbols.intern(wrapper),
                None => name,
            };
            let decorator = self.returning_argument(graph, named, analysed);
            self.add_object(graph, dst, decorator);
        }
    }

    fn returning_argument(&mut self, graph: &mut Graph, name: Sym, analysed: bool) -> ObjId {
        if let Some(&found) = self.returning.get(&(name, analysed)) {
            return found;
        }
        let made = self.new_object(graph, Object::ReturnsArgument { name, analysed });
        self.returning.insert((name, analysed), made);
        made
    }

    fn args(&mut self, graph: &mut Graph, args: BoundId, name: &str) -> NodeId {
        self.bound_parameter(graph, args, name)
    }

    fn rule_convert(&mut self, graph: &mut Graph, call: CallId, args: BoundId, arguments: &[&str]) {
        let (caller, site) = (
            self.calls[call.index()].caller,
            self.calls[call.index()].site,
        );
        let &[kind, parameter, ref spec @ ..] = arguments else {
            panic!("a conversion names its kind and parameter")
        };
        let spec = spec
            .first()
            .map(|&spec| self.bound_parameter(graph, args, spec));
        let value = self.bound_parameter(graph, args, parameter);
        self.add_conversion(graph, value, Conversion::of(kind), caller, site, spec);
        let typed = self.typed(graph, "builtins.str");
        self.result(graph, call, typed);
    }

    fn rule_pow(&mut self, graph: &mut Graph, call: CallId, args: BoundId) {
        let (caller, site) = (
            self.calls[call.index()].caller,
            self.calls[call.index()].site,
        );
        let mut extra = Vec::new();
        if self.bound_given(args, "mod") {
            extra.push(self.bound_parameter(graph, args, "mod"));
        }
        let base = self.bound_parameter(graph, args, "base");
        let exp = self.bound_parameter(graph, args, "exp");
        let dst = self.result_node(graph, call);
        self.add_operator(
            graph,
            OperatorCall {
                left: Some(base),
                right: Some(exp),
                method: "__pow__",
                reflected: Some("__rpow__"),
                inplace: false,
                dst,
                caller,
                site,
                unary: false,
                constants: false,
                extra,
            },
        );
    }

    fn rule_print(&mut self, graph: &mut Graph, call: CallId, args: BoundId) {
        let (caller, site) = (
            self.calls[call.index()].caller,
            self.calls[call.index()].site,
        );
        let varargs = self.bound_varargs(args).expect("print binds its varargs");
        let values = self.every(graph, varargs);
        self.add_conversion(graph, values, Conversion::Str, caller, site, None);
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
            Object::Pattern { .. } => "str".to_string(),
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

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct DynamicId(u32);

pub struct DynamicAccess {
    name: NodeId,
    pub(super) object: NodeId,
    pub(super) dst: Option<NodeId>,
    src: Option<NodeId>,
    pub(super) call: CallId,
    delete: bool,
    dynamic: bool,
    done: Vec<Sym>,
}

impl<T: Trace> State<T> {
    fn rule_getattr(&mut self, graph: &mut Graph, call: CallId, args: BoundId, builtin: &str) {
        let (dst, object) = if builtin == "getattr" {
            let dst = match self.calls[call.index()].dst {
                Some(dst) => dst,
                None => self.node(graph, None),
            };
            let default = self.args(graph, args, "default");
            self.add_edge(graph, default, dst);
            (dst, self.args(graph, args, "object"))
        } else {
            let dst = self.node(graph, None);
            (dst, self.args(graph, args, "obj"))
        };
        let name = self.args(graph, args, "name");
        self.named_access(graph, object, name, Some(dst), None, call, false);
    }

    #[allow(clippy::too_many_arguments)]
    fn named_access(
        &mut self,
        graph: &mut Graph,
        object: NodeId,
        name: NodeId,
        dst: Option<NodeId>,
        src: Option<NodeId>,
        call: CallId,
        delete: bool,
    ) {
        let argument = self.calls[call.index()].args.get(1).copied().flatten();
        let literal = match argument {
            Some(node) => self.literal_name(graph, node),
            None => None,
        };
        if let Some(attr) = literal {
            let text = self.symbols.text(attr).to_string();
            self.access_named(graph, &text, object, dst, src, call, delete);
            return;
        }
        let id = DynamicId(
            u32::try_from(self.dynamic_accesses.len()).expect("fewer than 2^32 accesses"),
        );
        self.dynamic_accesses.push(DynamicAccess {
            name,
            object,
            dst,
            src,
            call,
            delete,
            dynamic: false,
            done: Vec::new(),
        });
        if src.is_none() && !delete {
            let rule = self.rule(Rule::LoadByPattern(id));
            self.attach(graph, name, rule);
        }
    }

    fn literal_name(&mut self, graph: &mut Graph, node: NodeId) -> Option<Sym> {
        let objects = self.objects_of(graph, node);
        let [object] = objects[..] else {
            return None;
        };
        let Object::Const {
            value: Literal::Str(code_points),
            ..
        } = self.objects.get(object)
        else {
            return None;
        };
        if self.constants.get(&object) != Some(&node) {
            return None;
        }
        let text: Option<String> = code_points
            .iter()
            .map(|&point| char::from_u32(point))
            .collect();
        let Some(text) = text else {
            not_ported("an attribute name with a lone surrogate")
        };
        Some(self.symbols.intern(&text))
    }

    #[allow(clippy::too_many_arguments)]
    fn access_named(
        &mut self,
        graph: &mut Graph,
        attr: &str,
        object: NodeId,
        dst: Option<NodeId>,
        src: Option<NodeId>,
        call: CallId,
        delete: bool,
    ) {
        let details = &self.calls[call.index()];
        let caller = self.symbols.text(details.caller).to_string();
        let site = self.symbols.text(details.site).to_string();
        if let Some(dst) = dst {
            self.add_load(graph, object, attr, dst, &caller, &site);
        }
        if src.is_some() {
            self.add_store(graph, object, attr, src, &caller, &site);
        }
        if delete {
            self.add_delete(graph, object, attr, &caller, &site);
        }
    }

    pub(super) fn add_named_load(
        &mut self,
        graph: &mut Graph,
        object: NodeId,
        name: NodeId,
        dst: NodeId,
        caller: &str,
        site: &str,
    ) {
        let key = SiteKey {
            caller: self.symbols.intern(caller),
            site: self.symbols.intern(site),
            role: Role::NamedLoad,
            implicit: true,
        };
        let call = self.site_call(graph, key, &[], None, None);
        self.dynamic_accesses.push(DynamicAccess {
            name,
            object,
            dst: Some(dst),
            src: None,
            call,
            delete: false,
            dynamic: false,
            done: Vec::new(),
        });
    }

    pub(super) fn dynamic_access(&self, id: DynamicId) -> &DynamicAccess {
        &self.dynamic_accesses[id.0 as usize]
    }

    pub(super) fn computed_name_nodes(&self, graph: &mut Graph) -> FxHashSet<NodeId> {
        let mut computed = FxHashSet::default();
        for access in &self.dynamic_accesses {
            let names = graph.objects(access.name);
            let known = !access.dynamic
                && !names.is_empty()
                && names.iter().all(|&name| {
                    matches!(
                        self.objects.get(name),
                        Object::Const {
                            value: Literal::Str(_),
                            ..
                        }
                    )
                });
            if !known && let Some(dst) = access.dst {
                computed.insert(dst);
            }
        }
        computed
    }

    pub(super) fn complete_dynamic_accesses(&mut self, graph: &mut Graph) -> bool {
        let mut added = false;
        for index in 0..self.dynamic_accesses.len() {
            if self.dynamic_accesses[index].dynamic {
                continue;
            }
            let name = self.dynamic_accesses[index].name;
            let mut names: Vec<Sym> = Vec::new();
            for object in self.objects_of(graph, name) {
                if let Object::Const {
                    value: Literal::Str(code_points),
                    ..
                } = self.objects.get(object)
                {
                    let text: Option<String> = code_points
                        .iter()
                        .map(|&point| char::from_u32(point))
                        .collect();
                    let Some(text) = text else {
                        not_ported("an attribute name with a lone surrogate")
                    };
                    let sym = self.symbols.intern(&text);
                    if !names.contains(&sym) {
                        names.push(sym);
                    }
                }
            }
            let access = &self.dynamic_accesses[index];
            let counted = if access.src.is_none() && !access.delete {
                names
                    .iter()
                    .filter(|name| !self.namespace_names_read.contains(name))
                    .count()
            } else {
                names.len()
            };
            if counted > crate::models::DYNAMIC_NAMES_MAX {
                self.dynamic_accesses[index].dynamic = true;
                continue;
            }
            for attr in names {
                if self.dynamic_accesses[index].done.contains(&attr) {
                    continue;
                }
                self.dynamic_accesses[index].done.push(attr);
                let access = &self.dynamic_accesses[index];
                let (object, dst, src, call, delete) = (
                    access.object,
                    access.dst,
                    access.src,
                    access.call,
                    access.delete,
                );
                let text = self.symbols.text(attr).to_string();
                self.access_named(graph, &text, object, dst, src, call, delete);
                added = true;
            }
        }
        added
    }

    fn rule_super(&mut self, graph: &mut Graph, call: CallId, args: BoundId) {
        if self.calls[call.index()].dst.is_none() {
            return;
        }
        let class = self.args(graph, args, "type");
        let object = self.args(graph, args, "object_or_type");
        let site = self.calls[call.index()].site;
        let explicit = !self.zero_argument_super.contains(&site);
        let rule = self.rule(Rule::SuperClass {
            object,
            call,
            explicit,
        });
        self.attach(graph, class, rule);
    }

    pub(super) fn super_class(
        &mut self,
        graph: &mut Graph,
        class: ObjId,
        object: NodeId,
        call: CallId,
        explicit: bool,
    ) {
        let dst = self.calls[call.index()]
            .dst
            .expect("a super call has a result");
        if explicit
            && matches!(
                self.objects.get(class),
                Object::External(_) | Object::UnknownExternal(_)
            )
        {
            let rule = self.rule(Rule::SuperAfterOutside { class, dst });
            self.attach(graph, object, rule);
            return;
        }
        if !self.objects.is_class(class) {
            return;
        }
        if explicit {
            self.super_with_arguments(graph, class, object, call);
        } else {
            let rule = self.rule(Rule::SuperObject { class, dst });
            self.attach(graph, object, rule);
        }
    }

    pub(super) fn super_after_outside(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        class: ObjId,
        dst: NodeId,
    ) {
        let owner = match self.objects.get(object) {
            &Object::Instance { class, .. } => class,
            _ => object,
        };
        if let Object::Class(owner) = self.objects.get(owner)
            && owner.mros.iter().any(|mro| mro.contains(&class))
        {
            let made = self.super_object(graph, class, object);
            self.add_object(graph, dst, made);
        }
    }

    pub(super) fn super_object_rule(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        class: ObjId,
        dst: NodeId,
    ) {
        if matches!(
            self.objects.get(object),
            Object::Instance { .. } | Object::Class(_)
        ) {
            let made = self.super_object(graph, class, object);
            self.add_object(graph, dst, made);
        }
    }

    fn super_with_arguments(
        &mut self,
        graph: &mut Graph,
        class: ObjId,
        object: NodeId,
        call: CallId,
    ) {
        if !self.super_pairs.insert((call, class)) {
            return;
        }
        self.super_accepted.entry(class).or_default();
        let dst = self.calls[call.index()]
            .dst
            .expect("a super call has a result");
        let rule = self.rule(Rule::SuperGiven { class, dst });
        self.attach(graph, object, rule);
        let instances = self.objects.class(class).instances;
        let family = self.family(graph, class);
        for node in [instances, family] {
            let rule = self.rule(Rule::SuperAcceptedBy {
                class,
                given: object,
                dst,
            });
            self.attach(graph, node, rule);
        }
    }

    pub(super) fn super_given(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        class: ObjId,
        dst: NodeId,
    ) {
        if self.super_accepted[&class].contains(&object) {
            let made = self.super_object(graph, class, object);
            self.add_object(graph, dst, made);
        }
    }

    pub(super) fn super_accepted_by(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        class: ObjId,
        given: NodeId,
        dst: NodeId,
    ) {
        self.super_accepted
            .get_mut(&class)
            .expect("the accepted of a super class")
            .insert(object);
        if self.objects_of(graph, given).contains(&object) {
            let made = self.super_object(graph, class, object);
            self.add_object(graph, dst, made);
        }
    }

    fn super_object(&mut self, graph: &mut Graph, class: ObjId, receiver: ObjId) -> ObjId {
        if let Some(&found) = self.supers.get(&(class, receiver)) {
            return found;
        }
        let found = self.new_object(graph, Object::Super { class, receiver });
        self.supers.insert((class, receiver), found);
        found
    }

    fn rule_type(&mut self, graph: &mut Graph, call: CallId, args: BoundId) {
        let Some(dst) = self.calls[call.index()].dst else {
            return;
        };
        let typed = self.typed(graph, "builtins.type");
        self.add_object(graph, dst, typed);
        let details = &self.calls[call.index()];
        let written = details.args.len() == 3
            && details.keywords.is_empty()
            && details.star.is_empty()
            && details.double_star.is_empty();
        if written {
            let made = [
                self.args(graph, args, "object"),
                self.args(graph, args, "bases"),
                self.args(graph, args, "dict"),
            ];
            let rule = self.rule(Rule::TypeBases { call, made });
            self.attach(graph, made[1], rule);
        }
    }

    pub(super) fn type_bases(
        &mut self,
        graph: &mut Graph,
        bases: ObjId,
        call: CallId,
        made: [NodeId; 3],
    ) {
        let Object::Container(container) = self.objects.get(bases) else {
            unreachable!("the bases rule takes containers")
        };
        if self.symbols.text(container.kind) == "tuple" && container.length == Some(1) {
            let first = self.element(graph, bases, &Literal::Int(BigInt::ZERO));
            let rule = self.rule(Rule::TypeBase { call, made });
            self.attach(graph, first, rule);
        }
    }

    pub(super) fn type_base(
        &mut self,
        graph: &mut Graph,
        base: ObjId,
        call: CallId,
        made: [NodeId; 3],
    ) {
        let details = &self.calls[call.index()];
        let key = SiteKey {
            caller: details.caller,
            site: details.site,
            role: Role::TypeMetaclass,
            implicit: true,
        };
        let args = made.map(Some);
        let metaclass = self.site_call(graph, key, &args, None, None);
        let rule = self.rule(Rule::CallTypeMetaclass { call: metaclass });
        let found = self.objects.class(base).metaclass;
        self.attach(graph, found, rule);
    }
}

fn container(receiver: Option<ObjId>) -> ObjId {
    receiver.expect("a method of a container has its receiver")
}
