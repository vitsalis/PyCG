use indexmap::IndexMap;
use num_bigint::BigInt;
use pycg_solver::NodeId;

use crate::builder::calls::Analysis;

pub type Truth = u8;
pub const TRUE: Truth = 1;
pub const FALSE: Truth = 2;
pub const UNKNOWN: Truth = TRUE | FALSE;

#[derive(Clone, Debug)]
pub enum Literal {
    Str(Box<[u32]>),
    Bytes(Box<[u8]>),
    Int(BigInt),
    Float(f64),
    Bool(bool),
    None,
}

impl PartialEq for Literal {
    fn eq(&self, other: &Self) -> bool {
        match (self, other) {
            (Literal::Str(a), Literal::Str(b)) => a == b,
            (Literal::Bytes(a), Literal::Bytes(b)) => a == b,
            (Literal::Int(a), Literal::Int(b)) => a == b,
            (Literal::Float(a), Literal::Float(b)) => a == b,
            (Literal::Bool(a), Literal::Bool(b)) => a == b,
            (Literal::None, Literal::None) => true,
            _ => false,
        }
    }
}

impl Literal {
    pub fn is_true(&self) -> bool {
        match self {
            Literal::Str(text) => !text.is_empty(),
            Literal::Bytes(bytes) => !bytes.is_empty(),
            Literal::Int(value) => *value != BigInt::ZERO,
            Literal::Float(value) => *value != 0.0,
            Literal::Bool(value) => *value,
            Literal::None => false,
        }
    }
}

#[derive(Clone, Debug, Default)]
pub struct Literals(Vec<Literal>);

impl Literals {
    pub fn of(values: impl IntoIterator<Item = Literal>) -> Literals {
        let mut literals = Literals::default();
        for value in values {
            literals.insert(value);
        }
        literals
    }

    fn insert(&mut self, value: Literal) {
        if !self.0.contains(&value) {
            self.0.push(value);
        }
    }

    pub fn union(&self, other: &Literals) -> Literals {
        let mut joined = self.clone();
        for value in &other.0 {
            joined.insert(value.clone());
        }
        joined
    }

    pub fn values(&self) -> &[Literal] {
        &self.0
    }
}

impl PartialEq for Literals {
    fn eq(&self, other: &Self) -> bool {
        self.0.len() == other.0.len() && self.0.iter().all(|value| other.0.contains(value))
    }
}

pub fn truth_of(values: &[Literal]) -> Truth {
    values.iter().fold(0, |truth, value| {
        truth | if value.is_true() { TRUE } else { FALSE }
    })
}

#[derive(Clone, Debug, PartialEq)]
pub struct Definition {
    pub node: Option<NodeId>,
    pub unbound: bool,
    pub truth: Truth,
    pub values: Option<Literals>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct DefinitionId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct StateId(u32);

#[derive(Debug)]
struct State {
    parent: Option<StateId>,
    changes: IndexMap<String, DefinitionId>,
    reachable: bool,
    narrowed: Option<IndexMap<String, (DefinitionId, DefinitionId)>>,
}

#[derive(Debug)]
struct Loop {
    heads: IndexMap<String, NodeId>,
    entry: StateId,
    breaks: Vec<StateId>,
}

type Jump = (bool, IndexMap<String, DefinitionId>);
pub type Recorder = IndexMap<String, Vec<DefinitionId>>;

#[derive(Debug)]
pub struct Flow {
    definitions: Vec<Definition>,
    states: Vec<State>,
    pub state: StateId,
    loops: Vec<Loop>,
    pending_finally_blocks: Vec<(usize, Vec<Jump>)>,
    recorders: Vec<Recorder>,
}

pub const UNBOUND: DefinitionId = DefinitionId(0);

impl Default for Flow {
    fn default() -> Self {
        Flow::new()
    }
}

impl Flow {
    pub fn new() -> Flow {
        let unbound = Definition {
            node: None,
            unbound: true,
            truth: 0,
            values: Some(Literals::default()),
        };
        let mut flow = Flow {
            definitions: vec![unbound],
            states: Vec::new(),
            state: StateId(0),
            loops: Vec::new(),
            pending_finally_blocks: Vec::new(),
            recorders: Vec::new(),
        };
        flow.state = flow.new_state(None);
        flow
    }

    fn new_state(&mut self, parent: Option<StateId>) -> StateId {
        let reachable = parent.is_none_or(|parent| self.states[parent.0 as usize].reachable);
        let id = StateId(u32::try_from(self.states.len()).expect("states fit u32"));
        self.states.push(State {
            parent,
            changes: IndexMap::new(),
            reachable,
            narrowed: None,
        });
        id
    }

    pub fn definition_of(&self, id: DefinitionId) -> &Definition {
        &self.definitions[id.0 as usize]
    }

    pub fn new_definition(&mut self, definition: Definition) -> DefinitionId {
        let id = DefinitionId(u32::try_from(self.definitions.len()).expect("definitions fit u32"));
        self.definitions.push(definition);
        id
    }

    pub fn reachable(&self, state: StateId) -> bool {
        self.states[state.0 as usize].reachable
    }

    pub fn set_reachable(&mut self, state: StateId, reachable: bool) {
        self.states[state.0 as usize].reachable = reachable;
    }

    pub fn new_child(&mut self, parent: StateId) -> StateId {
        self.new_state(Some(parent))
    }

    pub fn changed_between(&self, from: StateId, base: StateId) -> Vec<String> {
        self.changed(from, base)
    }

    pub fn is_reachable(&self) -> bool {
        self.reachable(self.state)
    }

    pub fn set_change(&mut self, state: StateId, name: &str, definition: DefinitionId) {
        self.states[state.0 as usize]
            .changes
            .insert(name.to_owned(), definition);
    }

    pub fn get_in(&self, state: StateId, name: &str) -> DefinitionId {
        let mut current = Some(state);
        while let Some(id) = current {
            let state = &self.states[id.0 as usize];
            if let Some(&definition) = state.changes.get(name) {
                return definition;
            }
            current = state.parent;
        }
        UNBOUND
    }

    pub fn get(&self, name: &str) -> DefinitionId {
        self.get_in(self.state, name)
    }

    fn changed(&self, from: StateId, base: StateId) -> Vec<String> {
        let mut names: IndexMap<String, ()> = IndexMap::new();
        let mut current = from;
        while current != base {
            let state = &self.states[current.0 as usize];
            for name in state.changes.keys() {
                names.entry(name.clone()).or_insert(());
            }
            current = state
                .parent
                .expect("the base of a merge is an ancestor of its ends");
        }
        names.into_keys().collect()
    }

    pub fn changed_from_root(&self, from: StateId) -> Vec<String> {
        let mut names: IndexMap<String, ()> = IndexMap::new();
        let mut current = Some(from);
        while let Some(id) = current {
            let state = &self.states[id.0 as usize];
            for name in state.changes.keys() {
                names.entry(name.clone()).or_insert(());
            }
            current = state.parent;
        }
        names.into_keys().collect()
    }

    pub fn read(&self, name: &str) -> DefinitionId {
        let definition = self.get(name);
        let mut current = Some(self.state);
        while let Some(id) = current {
            let state = &self.states[id.0 as usize];
            if let Some(narrowed) = &state.narrowed
                && let Some(&(tested, narrowed)) = narrowed.get(name)
                && tested == definition
            {
                return narrowed;
            }
            current = state.parent;
        }
        definition
    }

    pub fn narrow(
        &mut self,
        name: &str,
        tested: DefinitionId,
        definition: DefinitionId,
        state: Option<StateId>,
    ) {
        let state = state.unwrap_or(self.state);
        self.states[state.0 as usize]
            .narrowed
            .get_or_insert_with(IndexMap::new)
            .insert(name.to_owned(), (tested, definition));
    }

    pub fn define(
        &mut self,
        name: &str,
        node: Option<NodeId>,
        truth: Truth,
        values: Option<Literals>,
    ) {
        let definition = self.new_definition(Definition {
            node,
            unbound: false,
            truth,
            values,
        });
        self.set(name, definition);
    }

    pub fn unbind(&mut self, name: &str) {
        self.set(name, UNBOUND);
    }

    fn set(&mut self, name: &str, definition: DefinitionId) {
        let state = self.state;
        self.set_change(state, name, definition);
        for recorder in &mut self.recorders {
            recorder
                .entry(name.to_owned())
                .or_default()
                .push(definition);
        }
    }

    pub fn end_path(&mut self) {
        let state = self.state;
        self.states[state.0 as usize].reachable = false;
    }

    pub fn join(
        &mut self,
        analysis: &mut impl Analysis,
        definitions: &[DefinitionId],
    ) -> DefinitionId {
        let mut nodes: Vec<NodeId> = Vec::new();
        let mut unbound = false;
        let mut truth = 0;
        let mut values = Some(Literals::default());
        for &id in definitions {
            let definition = &self.definitions[id.0 as usize];
            unbound = unbound || definition.unbound;
            truth |= definition.truth;
            values = match (&values, &definition.values) {
                (Some(joined), Some(literals)) => Some(joined.union(literals)),
                _ => None,
            };
            if let Some(node) = definition.node
                && !nodes.contains(&node)
            {
                nodes.push(node);
            }
        }
        let node = if nodes.len() <= 1 {
            nodes.first().copied()
        } else {
            let joined = analysis.node(None);
            for &node in &nodes {
                analysis.add_edge(node, joined);
            }
            Some(joined)
        };
        self.new_definition(Definition {
            node,
            unbound,
            truth,
            values,
        })
    }

    pub fn branch(&mut self, start: StateId) -> StateId {
        self.state = self.new_state(Some(start));
        self.state
    }

    pub fn merge(
        &mut self,
        analysis: &mut impl Analysis,
        base: StateId,
        ends: &[StateId],
        target: Option<StateId>,
    ) {
        let target = target.unwrap_or(base);
        let reachable_ends: Vec<StateId> = ends
            .iter()
            .copied()
            .filter(|&end| self.reachable(end))
            .collect();
        let live = if reachable_ends.is_empty() {
            ends.to_vec()
        } else {
            reachable_ends
        };
        let mut names: IndexMap<String, ()> = IndexMap::new();
        for &end in &live {
            for name in self.changed(end, base) {
                names.entry(name).or_insert(());
            }
        }
        let mut changes = Vec::new();
        for name in names.into_keys() {
            let definitions: Vec<DefinitionId> =
                live.iter().map(|&end| self.get_in(end, &name)).collect();
            let joined = self.join(analysis, &definitions);
            changes.push((name, joined));
        }
        for (name, joined) in changes {
            self.set_change(target, &name, joined);
        }
        let reachable = ends.iter().any(|&end| self.reachable(end));
        self.states[target.0 as usize].reachable = reachable;
        self.state = target;
        if live.len() == 1 && self.reachable(live[0]) {
            self.keep_narrowed(base, live[0], target);
        }
    }

    fn keep_narrowed(&mut self, base: StateId, end: StateId, target: StateId) {
        let mut kept: Vec<String> = Vec::new();
        let mut current = Some(end);
        while let Some(id) = current {
            if id == base {
                break;
            }
            let narrowed: Vec<(String, DefinitionId, DefinitionId)> = self.states[id.0 as usize]
                .narrowed
                .iter()
                .flatten()
                .map(|(name, &(tested, definition))| (name.clone(), tested, definition))
                .collect();
            for (name, tested, definition) in narrowed {
                let current_definition = self.get_in(target, &name);
                if !kept.contains(&name)
                    && self.definitions[current_definition.0 as usize]
                        == self.definitions[tested.0 as usize]
                {
                    kept.push(name.clone());
                    self.narrow(&name, current_definition, definition, Some(target));
                }
            }
            current = self.states[id.0 as usize].parent;
        }
    }

    pub fn record(&mut self) -> usize {
        self.recorders.push(Recorder::new());
        self.recorders.len() - 1
    }

    pub fn stop(&mut self, recorder: usize) -> Recorder {
        assert_eq!(
            recorder + 1,
            self.recorders.len(),
            "the innermost recorder stops first"
        );
        self.recorders.pop().expect("a recorder")
    }

    pub fn anywhere(
        &mut self,
        analysis: &mut impl Analysis,
        base: StateId,
        recorder: &Recorder,
    ) -> StateId {
        let state = self.new_state(Some(base));
        for (name, definitions) in recorder {
            let mut joined = vec![self.get_in(base, name)];
            joined.extend(definitions.iter().copied());
            let definition = self.join(analysis, &joined);
            self.set_change(state, name, definition);
        }
        state
    }

    pub fn start_loop(&mut self, analysis: &mut impl Analysis, names: &IndexMap<String, bool>) {
        let mut heads = IndexMap::new();
        for (name, &unbinds) in names {
            let current = self.definitions[self.get(name).0 as usize].clone();
            let head = analysis.node(None);
            if let Some(node) = current.node {
                analysis.add_edge(node, head);
            }
            heads.insert(name.clone(), head);
            let definition = self.new_definition(Definition {
                node: Some(head),
                unbound: current.unbound || unbinds,
                truth: UNKNOWN,
                values: None,
            });
            let state = self.state;
            self.set_change(state, name, definition);
        }
        self.loops.push(Loop {
            heads,
            entry: self.state,
            breaks: Vec::new(),
        });
    }

    pub fn next_iteration(&mut self, analysis: &mut impl Analysis, state: Option<StateId>) {
        let state = state.unwrap_or(self.state);
        let heads = self.loops.last().expect("a loop").heads.clone();
        self.join_heads(analysis, &heads, state);
    }

    fn join_heads(
        &mut self,
        analysis: &mut impl Analysis,
        heads: &IndexMap<String, NodeId>,
        state: StateId,
    ) {
        if !self.reachable(state) {
            return;
        }
        for (name, &head) in heads {
            let node = self.definitions[self.get_in(state, name).0 as usize].node;
            if let Some(node) = node
                && node != head
            {
                analysis.add_edge(node, head);
            }
        }
    }

    pub fn jump(&mut self, analysis: &mut impl Analysis, leaves: bool) {
        assert!(self.is_reachable(), "a jump from an unreachable statement");
        if let Some(innermost) = self.loops.last() {
            let definitions: IndexMap<String, DefinitionId> = innermost
                .heads
                .keys()
                .map(|name| (name.clone(), self.get(name)))
                .collect();
            self.jump_with(analysis, leaves, definitions);
        }
        self.end_path();
    }

    fn jump_with(
        &mut self,
        analysis: &mut impl Analysis,
        leaves: bool,
        definitions: IndexMap<String, DefinitionId>,
    ) {
        if let Some((depth, jumps)) = self.pending_finally_blocks.last_mut()
            && *depth == self.loops.len()
        {
            jumps.push((leaves, definitions));
            return;
        }
        let entry = self.loops.last().expect("a loop").entry;
        let state = self.new_state(Some(entry));
        self.states[state.0 as usize].changes = definitions;
        self.states[state.0 as usize].reachable = true;
        if leaves {
            self.loops.last_mut().expect("a loop").breaks.push(state);
        } else {
            let heads = self.loops.last().expect("a loop").heads.clone();
            self.join_heads(analysis, &heads, state);
        }
    }

    pub fn stop_loop(&mut self) -> Vec<StateId> {
        self.loops.pop().expect("a loop").breaks
    }

    pub fn start_finally(&mut self) {
        self.pending_finally_blocks
            .push((self.loops.len(), Vec::new()));
    }

    pub fn run_finally(&mut self) -> Vec<Jump> {
        self.pending_finally_blocks
            .pop()
            .expect("a finally block")
            .1
    }

    pub fn end_finally(&mut self, analysis: &mut impl Analysis, jumps: Vec<Jump>, start: StateId) {
        let finished = self.state;
        if !self.reachable(finished) {
            return;
        }
        let bound = self.changed(finished, start);
        for (leaves, definitions) in jumps {
            let definitions = definitions
                .into_iter()
                .map(|(name, definition)| {
                    let definition = if bound.contains(&name) {
                        self.get_in(finished, &name)
                    } else {
                        definition
                    };
                    (name, definition)
                })
                .collect();
            self.jump_with(analysis, leaves, definitions);
        }
    }
}
