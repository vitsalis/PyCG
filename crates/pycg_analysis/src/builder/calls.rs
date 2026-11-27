use indexmap::IndexMap;
use num_bigint::BigInt;
use pycg_solver::{NodeId, ObjId};

use crate::model::Signature;

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
    Element(Box<str>, i64),
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

    fn handle_import(&mut self, name: &str, level: u32, record: bool) -> Option<String>;

    fn function_fields(&mut self, function: ObjId) -> &mut FunctionFields;
    fn class_fields(&mut self, class: ObjId) -> &mut ClassFields;
    fn module_defines(&mut self, module: ObjId) -> &mut Vec<Box<str>>;
    fn tables(&mut self) -> &mut BuilderTables;
}
