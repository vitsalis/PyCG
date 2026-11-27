use std::collections::{BTreeMap, BTreeSet};

use num_bigint::BigInt;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AnalysisPart {
    pub cap: Option<BigInt>,
    pub functions: Vec<FunctionDefinition>,
    pub classes: Vec<ClassDefinition>,
    pub fields: BTreeMap<String, BTreeMap<String, Vec<String>>>,
    pub site_edges: Vec<SiteEdge>,
    pub call_expressions: BTreeSet<(String, String)>,
    pub iterated_expressions: BTreeSet<(String, String)>,
    pub unresolved: Vec<Unresolved>,
    pub external_callees: BTreeMap<String, String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FunctionDefinition {
    pub name: String,
    pub module: String,
    pub lineno: u64,
    pub end_lineno: u64,
    pub col_offset: u64,
    pub end_col_offset: u64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ClassDefinition {
    pub name: String,
    pub module: String,
    pub index: u64,
    pub lineno: u64,
    pub end_lineno: u64,
    pub unknown: bool,
    pub mro: Vec<MroBase>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MroBase {
    pub analysed: bool,
    pub name: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SiteEdge {
    pub caller: String,
    pub site: String,
    pub construct: Construct,
    pub callees: Vec<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Construct {
    Call,
    Decorator,
    Role(Vec<RolePart>),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum RolePart {
    Text(String),
    Flag(bool),
    Number(i64),
    Parts(Vec<RolePart>),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Unresolved {
    pub caller: String,
    pub site: String,
    pub cause: String,
}
