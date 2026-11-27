use pycg_solver::{NodeId, ObjId, Solver};

use crate::engine::RuleId;
use crate::engine::objects::Kind;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Opacity {
    Never,
    Saturated,
}

pub struct RuleInfo<'a> {
    pub key: &'a str,
    pub kinds: Option<&'a [Kind]>,
    pub each: bool,
    pub captured: &'a [ObjId],
}

pub trait Trace {
    fn solver(&mut self, _cap: Option<u32>, _saturated: ObjId, _node: NodeId) {}
    fn node(&mut self, _node: NodeId, _label: Option<&str>) {}
    fn object(&mut self, _object: ObjId, _kind: Kind, _name: &str, _opacity: Opacity) {}
    fn rule(&mut self, _rule: RuleId, _info: &RuleInfo<'_>) {}
    fn constant(&mut self, _object: ObjId, _node: NodeId) {}
    fn add_object(&mut self, _node: NodeId, _object: ObjId) {}
    fn add_edge(&mut self, _source: NodeId, _target: NodeId) {}
    fn attach(&mut self, _node: NodeId, _rule: RuleId) {}
    fn objects(&mut self, _node: NodeId, _objects: &[ObjId]) {}
    fn holds(&mut self, _node: NodeId, _object: ObjId, _answer: bool) {}
    fn apply(&mut self, _rule: RuleId, _objects: &[ObjId]) {}
    fn applied(&mut self) {}
    fn saturate(&mut self, _rule: RuleId) {}
    fn saturated(&mut self) {}
    fn solve(&mut self) {}
    fn solved(&mut self, _phase: u32) {}
    fn between_rounds(&mut self) {}
    fn between_rounds_done(&mut self, _answer: bool, _unknown: &[ObjId]) {}
    fn fire(&mut self, _solver: &mut Solver<RuleId>, _named_nodes: &[NodeId]) {}
}

pub struct Untraced;

impl Trace for Untraced {}
