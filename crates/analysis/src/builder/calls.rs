use indexmap::IndexMap;
use num_bigint::BigInt;
use pycg_solver::{NodeId, ObjId};

use crate::model::Signature;
use crate::program::imports::ImportManager;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct CallId(pub u32);

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Constant {
    Str(Box<[u32]>),
    Bytes(Box<[u8]>),
    Int(BigInt),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Key {
    Index(i64),
    Name(Box<str>),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MethodKind {
    StaticMethod,
    ClassMethod,
}

impl MethodKind {
    pub fn name(self) -> &'static str {
        match self {
            MethodKind::StaticMethod => "staticmethod",
            MethodKind::ClassMethod => "classmethod",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Shape {
    Instance,
    Element,
    Class,
}

impl Shape {
    pub fn name(self) -> &'static str {
        match self {
            Shape::Instance => "instance",
            Shape::Element => "element",
            Shape::Class => "class",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MadeFunction {
    pub object: ObjId,
    pub signature: Signature,
    pub parameters: IndexMap<Box<str>, NodeId>,
    pub return_node: NodeId,
    pub yield_node: Option<NodeId>,
    pub sent_node: Option<NodeId>,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct FunctionFields {
    pub decorated: bool,
    pub lineno: Option<u32>,
    pub col_offset: Option<u32>,
    pub end_lineno: Option<u32>,
    pub end_col_offset: Option<u32>,
    pub is_async: bool,
    pub annotations: Option<IndexMap<Box<str>, NodeId>>,
    pub passthrough: Vec<Passthrough>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Allocator {
    Object,
    Super,
}

impl Allocator {
    pub fn name(self) -> &'static str {
        match self {
            Allocator::Object => "object",
            Allocator::Super => "super",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum Passthrough {
    Name(Box<str>),
    Element(Box<str>, BigInt),
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ClassFields {
    pub lineno: Option<u32>,
    pub end_lineno: Option<u32>,
    pub allocator: Option<Allocator>,
    pub slots: Vec<Box<str>>,
    pub bound: Vec<Box<str>>,
    pub defines: Vec<Box<str>>,
    pub annotations: Option<IndexMap<Box<str>, NodeId>>,
}

pub type CallSite = (Box<str>, Box<str>);

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct BuilderTables {
    pub iterated_expressions: Vec<CallSite>,
    pub literal_imports: Vec<(Box<str>, NodeId)>,
    pub none_arguments: Vec<(CallSite, Vec<u32>)>,
    pub none_keywords: Vec<(CallSite, Vec<Box<str>>)>,
    pub read_namespaces: Vec<Box<str>>,
    pub zero_argument_super: Vec<Box<str>>,
}

pub struct ClassStatement<'a> {
    pub name: &'a str,
    pub bases: &'a [Option<NodeId>],
    pub namespace: &'a [(Box<str>, NodeId)],
    pub keywords: &'a [(Box<str>, Option<NodeId>)],
    pub double_star: &'a [Option<NodeId>],
}

pub struct Call<'a> {
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

pub struct NewClass<'a> {
    pub name: &'a str,
    pub module: &'a str,
    pub defines: &'a [Box<str>],
    pub base_nodes: &'a [Option<NodeId>],
    pub protocol: bool,
    pub abstract_methods: &'a [Box<str>],
    pub metaclass: Option<NodeId>,
    pub uses_namespace: bool,
}

pub struct Operation<'a> {
    pub left: Option<NodeId>,
    pub right: Option<NodeId>,
    pub method: &'a str,
    pub reflected: Option<&'a str>,
    pub inplace: bool,
    pub dst: NodeId,
    pub caller: &'a str,
    pub site: &'a str,
    pub unary: bool,
    pub constants: bool,
}

pub struct Subscript<'a> {
    pub base: NodeId,
    pub key: Option<NodeId>,
    pub dst: Option<NodeId>,
    pub src: Option<NodeId>,
    pub caller: &'a str,
    pub site: &'a str,
    pub delete: bool,
}

pub struct Slice<'a> {
    pub base: NodeId,
    pub bounds: Option<&'a (Option<BigInt>, Option<BigInt>)>,
    pub dst: Option<NodeId>,
    pub src: Option<NodeId>,
    pub caller: &'a str,
    pub site: &'a str,
    pub delete: bool,
}

pub trait Analysis {
    fn node(&mut self, label: Option<&str>) -> NodeId;
    fn node_label(&self, node: NodeId) -> Option<&str>;
    fn constant(&mut self, object: ObjId) -> NodeId;
    fn const_object(&mut self, value: &Constant) -> ObjId;
    fn field(&mut self, object: ObjId, name: &str) -> NodeId;
    fn add_edge(&mut self, source: NodeId, target: NodeId);
    fn add_object(&mut self, node: NodeId, object: ObjId);

    fn module(&mut self, name: &str) -> ObjId;
    fn external(&mut self, name: &str, steps: u32, inexact: bool) -> ObjId;
    fn imported_value(&mut self, name: &str) -> NodeId;
    fn add_external_module(&mut self, name: &str);

    fn function(
        &mut self,
        name: &str,
        module: &str,
        signature: &Signature,
        defaults: &[(Box<str>, Option<NodeId>)],
        generator: bool,
    ) -> MadeFunction;
    fn new_class(&mut self, class: &NewClass<'_>) -> ObjId;
    fn add_method(&mut self, class: ObjId, name: &str, function: ObjId, kind: Option<MethodKind>);
    fn add_implicit_method(&mut self, value: NodeId, field: NodeId, kind: MethodKind, site: &str);
    fn add_class_member(&mut self, value: NodeId, field: NodeId);
    fn add_set_name(&mut self, value: NodeId, class: ObjId, name: &str, caller: &str, site: &str);
    fn add_init_subclass(
        &mut self,
        class: ObjId,
        keywords: &[(Box<str>, Option<NodeId>)],
        double_star: &[Option<NodeId>],
        caller: &str,
        site: &str,
    );
    fn add_metaclass_call(
        &mut self,
        class: ObjId,
        statement: &ClassStatement<'_>,
        caller: &str,
        site: &str,
    );
    fn add_structure_class(
        &mut self,
        class: ObjId,
        fields: &[(Box<str>, Option<NodeId>)],
        bases: &[NodeId],
    );
    fn add_annotated_class(&mut self, class: ObjId, decorators: &[NodeId], bases: &[NodeId]);

    fn add_call(&mut self, call: &Call<'_>);
    fn add_load(&mut self, base: NodeId, attr: &str, dst: NodeId, caller: &str, site: &str);
    fn add_load_text(&mut self, base: NodeId, attr: &[u32], dst: NodeId, caller: &str, site: &str);
    fn add_store(
        &mut self,
        base: NodeId,
        attr: &str,
        src: Option<NodeId>,
        caller: &str,
        site: &str,
    );
    fn add_delete(&mut self, base: NodeId, attr: &str, caller: &str, site: &str);
    fn add_unpack(
        &mut self,
        value: NodeId,
        before: &[NodeId],
        starred: Option<NodeId>,
        after: &[NodeId],
        caller: &str,
        site: &str,
    );
    fn add_with(
        &mut self,
        manager: NodeId,
        dst: Option<NodeId>,
        caller: &str,
        site: &str,
        is_async: bool,
    );
    fn add_raise(&mut self, exception: NodeId, caller: &str, site: &str);
    fn add_truth(&mut self, value: NodeId, caller: &str, site: &str);
    fn add_handler(&mut self, types: Option<NodeId>, dst: NodeId);

    fn imports(&mut self) -> &mut ImportManager;
    fn handle_import(&mut self, name: &str, level: u32, record: bool) -> Option<String> {
        self.imports().handle_import(name, level, record)
    }
    fn locate(&mut self, name: &str) -> Option<(String, Option<String>)> {
        self.imports().locate(name)
    }

    fn type_form(&mut self, operator: &str, parts: &[Option<NodeId>], site: &str) -> ObjId;
    fn gate_type_form(&mut self, form: ObjId, gate: NodeId);
    fn annotated(&mut self, node: NodeId, dst: NodeId, shape: Shape, owner: ObjId, name: &str);
    fn bind_annotations(&mut self, function: ObjId);
    fn add_name_lookup(&mut self, base: NodeId, attr: &str, dst: NodeId);
    fn add_stub_bases(&mut self, cls: ObjId, node: NodeId);

    fn function_fields(&mut self, function: ObjId) -> &mut FunctionFields;
    fn class_fields(&mut self, class: ObjId) -> &mut ClassFields;
    fn module_defines(&mut self, module: ObjId) -> &mut Vec<Box<str>>;
    fn tables(&mut self) -> &mut BuilderTables;

    fn container(&mut self, kind: &str, site: &str, length: Option<usize>) -> ObjId;
    fn element(&mut self, container: ObjId, key: &Key) -> NodeId;
    fn unknown(&mut self, container: ObjId) -> NodeId;
    fn keys(&mut self, container: ObjId) -> NodeId;
    fn elements(&mut self, container: ObjId) -> NodeId;
    fn write_keyed(&mut self, container: ObjId, key: Option<NodeId>, src: Option<NodeId>);
    fn typed(&mut self, cls: &str) -> ObjId;
    fn add_operator(&mut self, operation: &Operation<'_>);
    fn add_percent(&mut self, fmt: NodeId, value: NodeId, caller: &str, site: &str);
    fn add_conversion(
        &mut self,
        value: NodeId,
        kind: &str,
        caller: &str,
        site: &str,
        spec: Option<NodeId>,
    );
    fn add_hash(&mut self, key: NodeId, caller: &str, site: &str, stored: Option<NodeId>);
    fn add_subscript(&mut self, subscript: &Subscript<'_>);
    fn add_slice(&mut self, slice: &Slice<'_>);
    fn add_iteration(
        &mut self,
        iterable: NodeId,
        dst: NodeId,
        caller: &str,
        site: &str,
        is_async: bool,
    );
    fn add_length_hint(&mut self, iterable: NodeId, caller: &str, site: &str);
    fn entering_keys(
        &mut self,
        source: NodeId,
        construct: (&str, &str),
        caller: &str,
        site: &str,
    ) -> (NodeId, NodeId);
    fn add_dict_items(&mut self, target: ObjId, source: NodeId, caller: &str, site: &str);
    fn add_await(&mut self, value: NodeId, dst: NodeId, caller: &str, site: &str);
    fn add_yield_from(
        &mut self,
        iterable: NodeId,
        function: ObjId,
        dst: NodeId,
        caller: &str,
        site: &str,
    );
    fn add_pattern_operand(&mut self, operand: Option<NodeId>, result: NodeId);
    fn pattern(&mut self, prefix: &[u32], suffix: &[u32]) -> ObjId;
    fn site_call(&mut self, caller: &str, site: &str, role: &[&str]) -> CallId;
    fn add_special_call(&mut self, value: NodeId, name: &str, call: CallId);
    fn add_named_load(&mut self, obj: NodeId, name: NodeId, dst: NodeId, caller: &str, site: &str);
    fn callable_filter(&mut self, source: NodeId, dst: NodeId, holds: bool);
    fn class_filter(
        &mut self,
        source: NodeId,
        classes: Option<NodeId>,
        dst: NodeId,
        as_class: bool,
        holds: bool,
    );
    fn tested_classes(
        &mut self,
        classes: NodeId,
        dst: NodeId,
        as_class: bool,
        module: ObjId,
        site: &str,
    );
}
