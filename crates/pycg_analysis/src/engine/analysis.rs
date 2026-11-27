use indexmap::IndexMap;
use pycg_solver::{NodeId, ObjId};

use crate::builder::calls::CallId as BuilderCallId;
use crate::builder::calls::{
    Analysis, BuilderTables, Call, ClassFields, ClassStatement, Constant, FunctionFields, Key,
    MadeFunction, MethodKind, NewClass, Operation, Passthrough, Shape, Slice, Subscript,
};
use crate::engine::objects::{self, Literal, Object};
use crate::engine::trace::Trace;
use crate::engine::{BuilderFields, Engine, not_ported};
use crate::model::Signature;

impl<T: Trace> Engine<T> {
    fn sync(&mut self) {
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
        let tables = &self.state.tables;
        if !tables.literal_imports.is_empty() {
            not_ported("the builder table literal_imports");
        }
        if !tables.read_namespaces.is_empty() {
            not_ported("the builder table read_namespaces");
        }
        if !tables.zero_argument_super.is_empty() {
            not_ported("the builder table zero_argument_super");
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
            return_node: made.return_node,
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

    fn add_implicit_method(
        &mut self,
        _value: NodeId,
        _field: NodeId,
        _kind: MethodKind,
        _site: &str,
    ) {
        not_ported("the builder call add_implicit_method")
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
        _value: NodeId,
        _before: &[NodeId],
        _starred: Option<NodeId>,
        _after: &[NodeId],
        _caller: &str,
        _site: &str,
    ) {
        not_ported("the builder call add_unpack")
    }

    fn add_with(
        &mut self,
        _manager: NodeId,
        _dst: Option<NodeId>,
        _caller: &str,
        _site: &str,
        _is_async: bool,
    ) {
        not_ported("the builder call add_with")
    }

    fn add_raise(&mut self, _exception: NodeId, _caller: &str, _site: &str) {
        not_ported("the builder call add_raise")
    }

    fn add_truth(&mut self, _value: NodeId, _caller: &str, _site: &str) {
        not_ported("the builder call add_truth")
    }

    fn add_handler(&mut self, _types: Option<NodeId>, _dst: NodeId) {
        not_ported("the builder call add_handler")
    }

    fn handle_import(&mut self, _name: &str, _level: u32, _record: bool) -> Option<String> {
        not_ported("the import manager")
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

    fn container(&mut self, _kind: &str, _site: &str, _length: Option<usize>) -> ObjId {
        not_ported("the builder call container")
    }

    fn element(&mut self, _container: ObjId, _key: &Key) -> NodeId {
        not_ported("the builder call element")
    }

    fn unknown(&mut self, _container: ObjId) -> NodeId {
        not_ported("the builder call unknown")
    }

    fn keys(&mut self, _container: ObjId) -> NodeId {
        not_ported("the builder call keys")
    }

    fn elements(&mut self, _container: ObjId) -> NodeId {
        not_ported("the builder call elements")
    }

    fn write_keyed(&mut self, _container: ObjId, _key: Option<NodeId>, _src: Option<NodeId>) {
        not_ported("the builder call write_keyed")
    }

    fn typed(&mut self, _cls: &str) -> ObjId {
        not_ported("the builder call typed")
    }

    fn add_operator(&mut self, _operation: &Operation<'_>) {
        not_ported("the builder call add_operator")
    }

    fn add_percent(&mut self, _fmt: NodeId, _value: NodeId, _caller: &str, _site: &str) {
        not_ported("the builder call add_percent")
    }

    fn add_conversion(
        &mut self,
        _value: NodeId,
        _kind: &str,
        _caller: &str,
        _site: &str,
        _spec: Option<NodeId>,
    ) {
        not_ported("the builder call add_conversion")
    }

    fn add_hash(&mut self, _key: NodeId, _caller: &str, _site: &str, _stored: Option<NodeId>) {
        not_ported("the builder call add_hash")
    }

    fn add_subscript(&mut self, _subscript: &Subscript<'_>) {
        not_ported("the builder call add_subscript")
    }

    fn add_slice(&mut self, _slice: &Slice<'_>) {
        not_ported("the builder call add_slice")
    }

    fn add_iteration(
        &mut self,
        _iterable: NodeId,
        _dst: NodeId,
        _caller: &str,
        _site: &str,
        _is_async: bool,
    ) {
        not_ported("the builder call add_iteration")
    }

    fn add_length_hint(&mut self, _iterable: NodeId, _caller: &str, _site: &str) {
        not_ported("the builder call add_length_hint")
    }

    fn entering_keys(
        &mut self,
        _source: NodeId,
        _construct: (&str, &str),
        _caller: &str,
        _site: &str,
    ) -> (NodeId, NodeId) {
        not_ported("the builder call entering_keys")
    }

    fn add_dict_items(&mut self, _target: ObjId, _source: NodeId, _caller: &str, _site: &str) {
        not_ported("the builder call add_dict_items")
    }

    fn add_await(&mut self, _value: NodeId, _dst: NodeId, _caller: &str, _site: &str) {
        not_ported("the builder call add_await")
    }

    fn add_yield_from(
        &mut self,
        _iterable: NodeId,
        _function: ObjId,
        _dst: NodeId,
        _caller: &str,
        _site: &str,
    ) {
        not_ported("the builder call add_yield_from")
    }

    fn add_pattern_operand(&mut self, _operand: Option<NodeId>, _result: NodeId) {
        not_ported("the builder call add_pattern_operand")
    }

    fn pattern(&mut self, _prefix: &[u32], _suffix: &[u32]) -> ObjId {
        not_ported("the builder call pattern")
    }

    fn locate(&mut self, _name: &str) -> Option<(String, Option<String>)> {
        not_ported("the import manager")
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

    fn site_call(&mut self, _caller: &str, _site: &str, _role: &[&str]) -> BuilderCallId {
        not_ported("the builder call site_call")
    }

    fn add_special_call(&mut self, _value: NodeId, _name: &str, _call: BuilderCallId) {
        not_ported("the builder call add_special_call")
    }

    fn add_named_load(
        &mut self,
        _obj: NodeId,
        _name: NodeId,
        _dst: NodeId,
        _caller: &str,
        _site: &str,
    ) {
        not_ported("the builder call add_named_load")
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
