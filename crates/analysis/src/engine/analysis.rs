use indexmap::IndexMap;
use num_bigint::BigInt;
use pycg_solver::{NodeId, ObjId};

use crate::builder::calls::CallId as BuilderCallId;
use crate::builder::calls::{
    Analysis, BuilderTables, Call, ClassFields, ClassStatement, Constant, FunctionFields, Key,
    MadeFunction, MethodKind, NewClass, Operation, Passthrough, Shape, Slice, Subscript,
};
use crate::engine::hierarchy::Unless;
use crate::engine::objects::{self, Literal, Object};
use crate::engine::protocols::{Conversion, OperatorCall};
use crate::engine::semantics::{Role, SiteKey};
use crate::engine::symbols::Sym;
use crate::engine::trace::Trace;
use crate::engine::{BuilderFields, Engine, containers, not_ported};
use crate::model::Signature;
use crate::program::imports::ImportManager;

impl<T: Trace> Engine<T> {
    fn caller_site(&mut self, caller: &str, site: &str) -> (Sym, Sym) {
        (
            self.state.symbols.intern(caller),
            self.state.symbols.intern(site),
        )
    }

    pub(super) fn sync(&mut self) {
        let handed = std::mem::take(&mut self.state.handed);
        for object in handed {
            let fields = self
                .state
                .builder_fields
                .get(&object)
                .cloned()
                .expect("the fields handed to the builder");
            match fields {
                BuilderFields::Function(fields) => self.set_function_fields(object, &fields),
                BuilderFields::Class(fields) => self.set_class_fields(object, &fields),
                BuilderFields::Module(defines) => {
                    let defines = defines
                        .iter()
                        .map(|name| self.state.symbols.intern(name))
                        .collect();
                    match self.state.objects.get_mut(object) {
                        Object::Module(module) => module.defines = defines,
                        _ => panic!("the defines of a module"),
                    }
                }
            }
        }
        let fresh: Vec<_> =
            self.state.tables.none_arguments[self.state.synced_none_arguments..].to_vec();
        self.state.synced_none_arguments = self.state.tables.none_arguments.len();
        for ((caller, site), indices) in fresh {
            let key = (
                self.state.symbols.intern(&caller),
                self.state.symbols.intern(&site),
            );
            self.state
                .none_arguments
                .entry(key)
                .or_default()
                .extend(indices);
        }
        let sites: Vec<Box<str>> = self.state.tables.zero_argument_super.clone();
        for site in sites {
            let site = self.state.symbols.intern(&site);
            self.state.zero_argument_super.insert(site);
        }
        let names: Vec<Box<str>> = self.state.tables.read_namespaces.clone();
        for name in names {
            let name = self.state.symbols.intern(&name);
            self.state.read_namespaces.insert(name);
        }
        let tables = &self.state.tables;
        if !tables.literal_imports.is_empty() {
            not_ported("the builder table literal_imports");
        }
    }

    fn set_function_fields(&mut self, object: ObjId, fields: &FunctionFields) {
        if fields.annotations.is_some() {
            not_ported("annotations");
        }
        let passthrough = fields
            .passthrough
            .iter()
            .map(|entry| match entry {
                Passthrough::Name(name) => {
                    objects::Passthrough::Name(self.state.symbols.intern(name))
                }
                Passthrough::Element(name, index) => {
                    objects::Passthrough::Element(self.state.symbols.intern(name), *index)
                }
            })
            .collect();
        let function = self.state.objects.function_mut(object);
        function.passthrough = passthrough;
        function.decorated = fields.decorated;
        function.is_async = fields.is_async;
        function.lineno = fields.lineno;
        function.col_offset = fields.col_offset;
        function.end_lineno = fields.end_lineno;
        function.end_col_offset = fields.end_col_offset;
    }

    fn set_class_fields(&mut self, object: ObjId, fields: &ClassFields) {
        if fields.annotations.is_some() {
            not_ported("annotations");
        }
        let symbols = &mut self.state.symbols;
        let defines = fields
            .defines
            .iter()
            .map(|name| symbols.intern(name))
            .collect();
        let bound = fields
            .bound
            .iter()
            .map(|name| symbols.intern(name))
            .collect();
        let slots = fields
            .slots
            .iter()
            .map(|name| symbols.intern(name))
            .collect();
        let class = self.state.objects.class_mut(object);
        class.defines = defines;
        class.bound = bound;
        class.slots = slots;
        class.allocator = fields.allocator;
        class.lineno = fields.lineno;
        class.end_lineno = fields.end_lineno;
    }

    fn hand(&mut self, object: ObjId, fields: BuilderFields) -> &mut BuilderFields {
        self.state.handed.push(object);
        self.state.builder_fields.entry(object).or_insert(fields)
    }
}

fn literal(value: &Constant) -> Literal {
    match value {
        Constant::Str(code_points) => Literal::Str(code_points.clone()),
        Constant::Bytes(bytes) => Literal::Bytes(bytes.clone()),
        Constant::Int(value) => Literal::Int(value.clone()),
    }
}

impl<T: Trace> Analysis for Engine<T> {
    fn node(&mut self, label: Option<&str>) -> NodeId {
        self.sync();
        self.state.node(&mut self.graph, label)
    }

    fn node_label(&self, node: NodeId) -> Option<&str> {
        self.label(node)
    }

    fn constant(&mut self, object: ObjId) -> NodeId {
        self.sync();
        self.state.constant(&mut self.graph, object)
    }

    fn const_object(&mut self, value: &Constant) -> ObjId {
        self.sync();
        self.state.const_object(&mut self.graph, &literal(value))
    }

    fn field(&mut self, object: ObjId, name: &str) -> NodeId {
        self.sync();
        let name = self.state.symbols.intern(name);
        self.state.field(&mut self.graph, object, name)
    }

    fn add_edge(&mut self, source: NodeId, target: NodeId) {
        self.sync();
        self.state.add_edge(&mut self.graph, source, target);
    }

    fn add_object(&mut self, node: NodeId, object: ObjId) {
        self.sync();
        self.state.add_object(&mut self.graph, node, object);
    }

    fn module(&mut self, name: &str) -> ObjId {
        self.sync();
        self.state.module(&mut self.graph, name)
    }

    fn external(&mut self, name: &str, steps: u32, inexact: bool) -> ObjId {
        self.sync();
        self.state.external(&mut self.graph, name, steps, inexact)
    }

    fn imported_value(&mut self, name: &str) -> NodeId {
        self.sync();
        self.state.imported_value(&mut self.graph, name)
    }

    fn add_external_module(&mut self, name: &str) {
        self.sync();
        self.state.add_external_module(name);
    }

    fn function(
        &mut self,
        name: &str,
        module: &str,
        signature: &Signature,
        defaults: &[(Box<str>, Option<NodeId>)],
        generator: bool,
    ) -> MadeFunction {
        self.sync();
        let object = self.state.function(
            &mut self.graph,
            name,
            module,
            signature,
            defaults,
            generator,
        );
        let made = self.state.objects.function(object);
        let parameters: IndexMap<Box<str>, NodeId> = made
            .parameters
            .iter()
            .map(|&(name, node)| (Box::from(self.state.symbols.text(name)), node))
            .collect();
        MadeFunction {
            object,
            signature: made.signature.clone(),
            parameters,
            return_node: made.return_node.expect("an analysed function returns"),
            yield_node: made.yield_node,
            sent_node: made.sent_node,
        }
    }

    fn new_class(&mut self, class: &NewClass<'_>) -> ObjId {
        self.sync();
        self.state.new_class(&mut self.graph, class)
    }

    fn add_method(&mut self, class: ObjId, name: &str, function: ObjId, kind: Option<MethodKind>) {
        self.sync();
        self.state
            .add_method(&mut self.graph, class, name, function, kind);
    }

    fn add_implicit_method(&mut self, value: NodeId, field: NodeId, kind: MethodKind, site: &str) {
        self.sync();
        self.state
            .add_implicit_method(&mut self.graph, value, field, kind, site);
    }

    fn add_class_member(&mut self, value: NodeId, field: NodeId) {
        self.sync();
        self.state.add_inexact(&mut self.graph, value, field);
    }

    fn add_set_name(&mut self, value: NodeId, class: ObjId, name: &str, caller: &str, site: &str) {
        self.sync();
        self.state
            .add_set_name(&mut self.graph, value, class, name, caller, site);
    }

    fn add_init_subclass(
        &mut self,
        class: ObjId,
        keywords: &[(Box<str>, Option<NodeId>)],
        double_star: &[Option<NodeId>],
        caller: &str,
        site: &str,
    ) {
        self.sync();
        self.state
            .add_init_subclass(&mut self.graph, class, keywords, double_star, caller, site);
    }

    fn add_metaclass_call(
        &mut self,
        class: ObjId,
        _statement: &ClassStatement<'_>,
        _caller: &str,
        _site: &str,
    ) {
        self.sync();
        self.state.add_metaclass_call(&mut self.graph, class);
    }

    fn add_structure_class(
        &mut self,
        _class: ObjId,
        _fields: &[(Box<str>, Option<NodeId>)],
        _bases: &[NodeId],
    ) {
        not_ported("the builder call add_structure_class")
    }

    fn add_annotated_class(&mut self, _class: ObjId, _decorators: &[NodeId], _bases: &[NodeId]) {
        not_ported("the builder call add_annotated_class")
    }

    fn add_call(&mut self, call: &Call<'_>) {
        self.sync();
        self.state.add_call(&mut self.graph, call);
    }

    fn add_load(&mut self, base: NodeId, attr: &str, dst: NodeId, caller: &str, site: &str) {
        self.sync();
        self.state
            .add_load(&mut self.graph, base, attr, dst, caller, site);
    }

    fn add_load_text(&mut self, base: NodeId, attr: &[u32], dst: NodeId, caller: &str, site: &str) {
        let Some(attr) = attr
            .iter()
            .map(|&code_point| char::from_u32(code_point))
            .collect::<Option<String>>()
        else {
            not_ported("an attribute name with a lone surrogate")
        };
        self.add_load(base, &attr, dst, caller, site);
    }

    fn add_store(
        &mut self,
        base: NodeId,
        attr: &str,
        src: Option<NodeId>,
        caller: &str,
        site: &str,
    ) {
        self.sync();
        self.state
            .add_store(&mut self.graph, base, attr, src, caller, site);
    }

    fn add_delete(&mut self, base: NodeId, attr: &str, caller: &str, site: &str) {
        self.sync();
        self.state
            .add_delete(&mut self.graph, base, attr, caller, site);
    }

    fn add_unpack(
        &mut self,
        value: NodeId,
        before: &[NodeId],
        starred: Option<NodeId>,
        after: &[NodeId],
        caller: &str,
        site: &str,
    ) {
        self.sync();
        let (caller, site) = (
            self.state.symbols.intern(caller),
            self.state.symbols.intern(site),
        );
        self.state
            .add_unpack(&mut self.graph, value, before, starred, after, caller, site);
    }

    fn add_with(
        &mut self,
        manager: NodeId,
        dst: Option<NodeId>,
        caller: &str,
        site: &str,
        is_async: bool,
    ) {
        self.sync();
        let (caller, site) = self.caller_site(caller, site);
        self.state
            .add_with(&mut self.graph, manager, dst, caller, site, is_async);
    }

    fn add_raise(&mut self, exception: NodeId, caller: &str, site: &str) {
        self.sync();
        let (caller, site) = self.caller_site(caller, site);
        self.state
            .add_raise(&mut self.graph, exception, caller, site);
    }

    fn add_truth(&mut self, value: NodeId, caller: &str, site: &str) {
        self.sync();
        let (caller, site) = self.caller_site(caller, site);
        self.state.add_truth(&mut self.graph, value, caller, site);
    }

    fn add_handler(&mut self, types: Option<NodeId>, dst: NodeId) {
        self.sync();
        let types = types.expect("a handler with a type");
        self.state.add_handler(&mut self.graph, types, dst);
    }

    fn imports(&mut self) -> &mut ImportManager {
        &mut self.state.imports
    }

    fn begin_module(&mut self, name: &str) {
        self.state.trace.module(Some(name));
    }

    fn end_module(&mut self, _name: &str, _analysed: bool) {
        self.state.trace.module(None);
    }

    fn function_fields(&mut self, function: ObjId) -> &mut FunctionFields {
        let made = self.state.objects.function(function);
        let symbols = &self.state.symbols;
        let current = FunctionFields {
            decorated: made.decorated,
            lineno: made.lineno,
            col_offset: made.col_offset,
            end_lineno: made.end_lineno,
            end_col_offset: made.end_col_offset,
            is_async: made.is_async,
            annotations: None,
            passthrough: made
                .passthrough
                .iter()
                .map(|entry| match *entry {
                    objects::Passthrough::Name(name) => {
                        Passthrough::Name(symbols.text(name).into())
                    }
                    objects::Passthrough::Element(name, index) => {
                        Passthrough::Element(symbols.text(name).into(), index)
                    }
                })
                .collect(),
        };
        match self.hand(function, BuilderFields::Function(current)) {
            BuilderFields::Function(fields) => fields,
            _ => panic!("the fields of a function"),
        }
    }

    fn class_fields(&mut self, class: ObjId) -> &mut ClassFields {
        let found = self.state.objects.class(class);
        let symbols = &self.state.symbols;
        let names = |names: &rustc_hash::FxHashSet<crate::engine::symbols::Sym>| -> Vec<Box<str>> {
            let mut texts: Vec<Box<str>> = names
                .iter()
                .map(|&name| symbols.text(name).into())
                .collect();
            texts.sort_unstable();
            texts
        };
        let current = ClassFields {
            lineno: found.lineno,
            end_lineno: found.end_lineno,
            allocator: found.allocator,
            slots: names(&found.slots),
            bound: names(&found.bound),
            defines: names(&found.defines),
            annotations: None,
        };
        match self.hand(class, BuilderFields::Class(current)) {
            BuilderFields::Class(fields) => fields,
            _ => panic!("the fields of a class"),
        }
    }

    fn module_defines(&mut self, module: ObjId) -> &mut Vec<Box<str>> {
        let Object::Module(found) = self.state.objects.get(module) else {
            panic!("the defines of a module")
        };
        let mut current: Vec<Box<str>> = found
            .defines
            .iter()
            .map(|&name| self.state.symbols.text(name).into())
            .collect();
        current.sort_unstable();
        match self.hand(module, BuilderFields::Module(current)) {
            BuilderFields::Module(defines) => defines,
            _ => panic!("the defines of a module"),
        }
    }

    fn tables(&mut self) -> &mut BuilderTables {
        &mut self.state.tables
    }

    fn container(&mut self, kind: &str, site: &str, length: Option<usize>) -> ObjId {
        self.sync();
        let length = length.map(|length| u32::try_from(length).expect("a length fits u32"));
        self.state
            .new_container(&mut self.graph, kind, site, length, true)
    }

    fn element(&mut self, container: ObjId, key: &Key) -> NodeId {
        self.sync();
        let key = match key {
            Key::Index(index) => Literal::Int(BigInt::from(*index)),
            Key::Name(name) => Literal::Str(name.chars().map(u32::from).collect()),
        };
        self.state.element(&mut self.graph, container, &key)
    }

    fn unknown(&mut self, container: ObjId) -> NodeId {
        self.sync();
        self.state.unknown(&mut self.graph, container)
    }

    fn keys(&mut self, container: ObjId) -> NodeId {
        self.sync();
        self.state.keys(&mut self.graph, container)
    }

    fn elements(&mut self, container: ObjId) -> NodeId {
        self.sync();
        self.state.elements(&mut self.graph, container)
    }

    fn write_keyed(&mut self, container: ObjId, key: Option<NodeId>, src: Option<NodeId>) {
        self.sync();
        self.state.write_keyed(&mut self.graph, container, key, src);
    }

    fn typed(&mut self, _cls: &str) -> ObjId {
        not_ported("the builder call typed")
    }

    fn add_operator(&mut self, operation: &Operation<'_>) {
        self.sync();
        let call = OperatorCall {
            left: operation.left,
            right: operation.right,
            method: operation.method,
            reflected: operation.reflected,
            inplace: operation.inplace,
            dst: operation.dst,
            caller: self.state.symbols.intern(operation.caller),
            site: self.state.symbols.intern(operation.site),
            unary: operation.unary,
            constants: operation.constants,
            extra: Vec::new(),
        };
        self.state.add_operator(&mut self.graph, call);
    }

    fn add_percent(&mut self, fmt: NodeId, value: NodeId, caller: &str, site: &str) {
        self.sync();
        let (caller, site) = self.caller_site(caller, site);
        self.state
            .add_percent(&mut self.graph, fmt, value, caller, site);
    }

    fn add_conversion(
        &mut self,
        value: NodeId,
        kind: &str,
        caller: &str,
        site: &str,
        spec: Option<NodeId>,
    ) {
        self.sync();
        let (caller, site) = self.caller_site(caller, site);
        let kind = Conversion::of(kind);
        self.state
            .add_conversion(&mut self.graph, value, kind, caller, site, spec);
    }

    fn add_hash(&mut self, key: NodeId, caller: &str, site: &str, stored: Option<NodeId>) {
        self.sync();
        let (caller, site) = (
            self.state.symbols.intern(caller),
            self.state.symbols.intern(site),
        );
        self.state
            .add_hash(&mut self.graph, key, caller, site, stored);
    }

    fn add_subscript(&mut self, subscript: &Subscript<'_>) {
        self.sync();
        let caller = self.state.symbols.intern(subscript.caller);
        let site = self.state.symbols.intern(subscript.site);
        self.state.add_subscript(
            &mut self.graph,
            subscript.base,
            subscript.key,
            subscript.dst,
            subscript.src,
            subscript.delete,
            caller,
            site,
        );
    }

    fn add_slice(&mut self, slice: &Slice<'_>) {
        self.sync();
        let caller = self.state.symbols.intern(slice.caller);
        let site = self.state.symbols.intern(slice.site);
        self.state.add_slice(
            &mut self.graph,
            slice.base,
            slice.bounds.cloned(),
            slice.dst,
            slice.src,
            slice.delete,
            caller,
            site,
        );
    }

    fn add_iteration(
        &mut self,
        iterable: NodeId,
        dst: NodeId,
        caller: &str,
        site: &str,
        is_async: bool,
    ) {
        self.sync();
        let (caller, site) = (
            self.state.symbols.intern(caller),
            self.state.symbols.intern(site),
        );
        self.state
            .add_iteration(&mut self.graph, iterable, dst, caller, site, is_async);
    }

    fn add_length_hint(&mut self, _iterable: NodeId, _caller: &str, _site: &str) {
        not_ported("the builder call add_length_hint")
    }

    fn entering_keys(
        &mut self,
        source: NodeId,
        construct: (&str, &str),
        caller: &str,
        site: &str,
    ) -> (NodeId, NodeId) {
        self.sync();
        let symbols = &mut self.state.symbols;
        let construct = containers::KeysConstruct::Builder(
            symbols.intern(construct.0),
            symbols.intern(construct.1),
        );
        let (caller, site) = (symbols.intern(caller), symbols.intern(site));
        self.state.entering_keys(
            &mut self.graph,
            source,
            construct,
            caller,
            site,
            containers::Keeps::Hashes,
        )
    }

    fn add_dict_items(&mut self, target: ObjId, source: NodeId, caller: &str, site: &str) {
        self.sync();
        let (caller, site) = (
            self.state.symbols.intern(caller),
            self.state.symbols.intern(site),
        );
        self.state
            .add_dict_items(&mut self.graph, target, source, caller, site);
    }

    fn add_await(&mut self, value: NodeId, dst: NodeId, caller: &str, site: &str) {
        self.sync();
        let (caller, site) = self.caller_site(caller, site);
        self.state
            .add_await(&mut self.graph, value, dst, caller, site);
    }

    fn add_yield_from(
        &mut self,
        iterable: NodeId,
        function: ObjId,
        dst: NodeId,
        caller: &str,
        site: &str,
    ) {
        self.sync();
        let (caller, site) = (
            self.state.symbols.intern(caller),
            self.state.symbols.intern(site),
        );
        self.state
            .add_yield_from(&mut self.graph, iterable, function, dst, caller, site);
    }

    fn add_pattern_operand(&mut self, operand: Option<NodeId>, result: NodeId) {
        self.sync();
        self.state
            .add_pattern_operand(&mut self.graph, operand, result);
    }

    fn pattern(&mut self, prefix: &[u32], suffix: &[u32]) -> ObjId {
        self.sync();
        self.state
            .pattern(&mut self.graph, prefix, suffix, None, true)
    }

    fn type_form(&mut self, _operator: &str, _parts: &[Option<NodeId>], _site: &str) -> ObjId {
        not_ported("the builder call type_form")
    }

    fn gate_type_form(&mut self, _form: ObjId, _gate: NodeId) {
        not_ported("the builder call gate_type_form")
    }

    fn annotated(
        &mut self,
        _node: NodeId,
        _dst: NodeId,
        _shape: Shape,
        _owner: ObjId,
        _name: &str,
    ) {
        not_ported("the builder call annotated")
    }

    fn bind_annotations(&mut self, _function: ObjId) {
        not_ported("the builder call bind_annotations")
    }

    fn add_name_lookup(&mut self, _base: NodeId, _attr: &str, _dst: NodeId) {
        not_ported("the builder call add_name_lookup")
    }

    fn add_stub_bases(&mut self, _cls: ObjId, _node: NodeId) {
        not_ported("the builder call add_stub_bases")
    }

    fn site_call(&mut self, caller: &str, site: &str, role: &[&str]) -> BuilderCallId {
        self.sync();
        let &["special", name] = role else {
            panic!("the builder makes only special calls, not {role:?}")
        };
        let (caller, site) = self.caller_site(caller, site);
        let role = Role::Special(self.state.symbols.intern(name));
        let key = SiteKey {
            caller,
            site,
            role,
            implicit: true,
        };
        let call = self.state.site_call(&mut self.graph, key, &[], None, None);
        let id = BuilderCallId(
            u32::try_from(self.state.builder_calls.len()).expect("fewer than 2^32 calls"),
        );
        self.state.builder_calls.push(call);
        id
    }

    fn add_special_call(&mut self, value: NodeId, name: &str, call: BuilderCallId) {
        self.sync();
        let call = self.state.builder_calls[call.0 as usize];
        self.state
            .special_call(&mut self.graph, value, name, call, Unless::Nothing);
    }

    fn add_named_load(&mut self, obj: NodeId, name: NodeId, dst: NodeId, caller: &str, site: &str) {
        self.sync();
        self.state
            .add_named_load(&mut self.graph, obj, name, dst, caller, site);
    }

    fn callable_filter(&mut self, _source: NodeId, _dst: NodeId, _holds: bool) {
        not_ported("the builder call callable_filter")
    }

    fn class_filter(
        &mut self,
        _source: NodeId,
        _classes: Option<NodeId>,
        _dst: NodeId,
        _as_class: bool,
        _holds: bool,
    ) {
        not_ported("the builder call class_filter")
    }

    fn tested_classes(
        &mut self,
        _classes: NodeId,
        _dst: NodeId,
        _as_class: bool,
        _module: ObjId,
        _site: &str,
    ) {
        not_ported("the builder call tested_classes")
    }
}
