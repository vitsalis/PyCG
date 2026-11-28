use std::collections::VecDeque;

use indexmap::{IndexMap, IndexSet};
use rustc_hash::{FxBuildHasher, FxHashMap, FxHashSet};

use crate::ids::{NodeId, ObjId, SetId, WatchId};
use crate::order::Order;
use crate::sets::{KIND_SELECTION_OBJECTS_MIN, KindMask, Sets};

pub const ATTACH_NESTING_MAX: u32 = 50;

type OrderedMap<K, V> = IndexMap<K, V, FxBuildHasher>;
type OrderedSet<K> = IndexSet<K, FxBuildHasher>;

pub trait Rules<C> {
    fn apply(&mut self, solver: &mut Solver<C>, constraint: C, objects: &[ObjId]);
    fn saturate(&mut self, solver: &mut Solver<C>, constraint: C);
    fn kinds(&self, constraint: C) -> Option<KindMask>;
    fn captures_opaque(&self, solver: &Solver<C>, constraint: C) -> bool;
    fn opaque(&self, object: ObjId) -> bool;
    fn between_rounds(&mut self, solver: &mut Solver<C>) -> bool;
    fn wake(&mut self, solver: &mut Solver<C>, watch: WatchId);
    fn firing(&mut self, solver: &mut Solver<C>);
    fn tick(&mut self, _solver: &Solver<C>) {}
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Attached {
    Kept,
    Released,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub struct Work {
    pub copied: u64,
    pub applied: u64,
    pub edges: u64,
    pub processed: u64,
    pub merged: u64,
    pub searched: u64,
}

enum Inbox {
    Empty,
    One(SetId),
    Many(Box<[SetId]>),
}

enum Successors {
    None,
    One(NodeId),
    Many(Box<Targets>),
}

#[derive(Default)]
struct Targets {
    order: Vec<NodeId>,
    searched: FxHashMap<NodeId, bool>,
}

impl Targets {
    fn contains(&self, target: NodeId) -> bool {
        self.searched.contains_key(&target)
    }

    fn searched(&self, target: NodeId) -> bool {
        self.searched[&target]
    }

    fn len(&self) -> usize {
        self.order.len()
    }

    fn insert(&mut self, target: NodeId, searched: bool) {
        if self.searched.insert(target, searched).is_none() {
            self.order.push(target);
        }
    }

    fn remove(&mut self, target: NodeId) -> Option<bool> {
        let searched = self.searched.remove(&target)?;
        let position = self
            .order
            .iter()
            .position(|&listed| listed == target)
            .expect("a target is in the order");
        self.order.remove(position);
        Some(searched)
    }

    fn pairs(&self) -> impl Iterator<Item = (NodeId, bool)> + '_ {
        self.order
            .iter()
            .map(|&target| (target, self.searched[&target]))
    }
}

type Groups<C> = Vec<(Vec<C>, SetId)>;

struct Node<C> {
    representative: Option<NodeId>,
    done: SetId,
    inbox: Inbox,
    successors: Successors,
    constraints: Vec<C>,
    fired: SetId,
    groups: Option<Box<Groups<C>>>,
    constant: bool,
    witness: Option<WatchId>,
}

impl<C> Node<C> {
    fn new(done: SetId, constant: bool, witness: Option<WatchId>) -> Self {
        Node {
            representative: None,
            done,
            inbox: Inbox::Empty,
            successors: Successors::None,
            constraints: Vec::new(),
            fired: SetId::EMPTY,
            groups: None,
            constant,
            witness,
        }
    }
}

pub struct Solver<C> {
    pub sets: Sets,
    nodes: Vec<Node<C>>,
    kinds_by_object: Vec<Option<KindMask>>,
    saturated: ObjId,
    saturated_node: NodeId,
    saturated_set: SetId,
    cap: Option<u32>,
    order: Order,
    worklist: VecDeque<NodeId>,
    cycle_suspects: Vec<NodeId>,
    last_search_walked: u64,
    propagated_at_last_search: u64,
    propagated_nodes_and_edges: u64,
    applications_in_progress: u32,
    added_by_node: OrderedMap<NodeId, Vec<ObjId>>,
    attach_nesting: u32,
    attach_deferred: VecDeque<(C, SetId)>,
    firing_nodes: OrderedSet<NodeId>,
    set_holders: Vec<NodeId>,
    watches_waiting: Vec<bool>,
    absorbed_sets: OrderedSet<SetId>,
    opacity: bool,
    applied: u64,
    edges: u64,
    processed: u64,
    merged: u64,
    searched: u64,
    pub phase: u32,
}

impl<C: Copy> Solver<C> {
    pub fn new(
        saturated: ObjId,
        saturated_kinds: KindMask,
        cap: Option<u32>,
        order: Order,
    ) -> Self {
        let mut solver = Solver {
            sets: Sets::new(),
            nodes: Vec::new(),
            kinds_by_object: Vec::new(),
            saturated,
            saturated_node: NodeId::new(0),
            saturated_set: SetId::EMPTY,
            cap,
            order,
            worklist: VecDeque::new(),
            cycle_suspects: Vec::new(),
            last_search_walked: 0,
            propagated_at_last_search: 0,
            propagated_nodes_and_edges: 0,
            applications_in_progress: 0,
            added_by_node: OrderedMap::default(),
            attach_nesting: 0,
            attach_deferred: VecDeque::new(),
            firing_nodes: OrderedSet::default(),
            set_holders: Vec::new(),
            watches_waiting: Vec::new(),
            absorbed_sets: OrderedSet::default(),
            opacity: false,
            applied: 0,
            edges: 0,
            processed: 0,
            merged: 0,
            searched: 0,
            phase: 0,
        };
        solver.declare(saturated, saturated_kinds);
        let node = solver.constant(saturated);
        solver.saturated_node = node;
        solver.saturated_set = solver.nodes[node.index()].done;
        solver
    }

    pub fn declare(&mut self, object: ObjId, kinds: KindMask) {
        let index = object.index();
        if index >= self.kinds_by_object.len() {
            self.kinds_by_object.resize(index + 1, None);
        }
        if let Some(known) = self.kinds_by_object[index] {
            assert_eq!(known, kinds, "an object keeps its kinds");
        }
        self.kinds_by_object[index] = Some(kinds);
    }

    pub fn saturated(&self) -> ObjId {
        self.saturated
    }

    pub fn saturated_node(&self) -> NodeId {
        self.saturated_node
    }

    pub fn enable_opacity(&mut self) {
        self.opacity = true;
    }

    pub fn census(&self, prefix: &str) {
        let live = || self.nodes.iter().filter(|x| x.representative.is_none());
        let n = self.nodes.len();
        let merged = n - live().count();
        let constant = live().filter(|x| x.constant).count();
        let empty_done = live().filter(|x| x.done == SetId::EMPTY).count();
        let saturated = live().filter(|x| x.done == self.saturated_set).count();
        let with_constraints = live().filter(|x| !x.constraints.is_empty()).count();
        let constraints: usize = self.nodes.iter().map(|x| x.constraints.len()).sum();
        let constraints_cap: usize = self.nodes.iter().map(|x| x.constraints.capacity()).sum();
        let on_constant: usize = live()
            .filter(|x| x.constant)
            .map(|x| x.constraints.len())
            .sum();
        let grouped_nodes = self.nodes.iter().filter(|x| x.groups.is_some()).count();
        let grouped: usize = self
            .nodes
            .iter()
            .filter_map(|x| x.groups.as_ref())
            .map(|g| g.iter().map(|(c, _)| c.len()).sum::<usize>())
            .sum();
        let one = self
            .nodes
            .iter()
            .filter(|x| matches!(x.successors, Successors::One(_)))
            .count();
        let many = self
            .nodes
            .iter()
            .filter(|x| matches!(x.successors, Successors::Many(_)))
            .count();
        let many_len: usize = self
            .nodes
            .iter()
            .map(|x| match &x.successors {
                Successors::Many(t) => t.len(),
                _ => 0,
            })
            .sum();
        let searched: usize = self
            .nodes
            .iter()
            .map(|x| match &x.successors {
                Successors::Many(t) => t.searched.len(),
                _ => 0,
            })
            .sum();
        let fired_differs = live()
            .filter(|x| x.fired != SetId::EMPTY && x.fired != x.done)
            .count();
        let inbox_one = live().filter(|x| matches!(x.inbox, Inbox::One(_))).count();
        let inbox_many: usize = live()
            .map(|x| match &x.inbox {
                Inbox::Many(s) => s.len(),
                _ => 0,
            })
            .sum();
        let held: usize = live().map(|x| self.sets.len(x.done)).sum();
        let mut product: u128 = 0;
        let mut product_max = (0usize, 0usize);
        let mut by_size = [(0usize, 0usize); 6];
        for x in live() {
            let objects = if x.done == self.saturated_set {
                0
            } else {
                self.sets.len(x.done)
            };
            let attached = x.constraints.len()
                + x.groups
                    .as_ref()
                    .map_or(0, |g| g.iter().map(|(c, _)| c.len()).sum::<usize>());
            product += (attached as u128) * (objects as u128);
            if attached * objects > product_max.0 * product_max.1 {
                product_max = (attached, objects);
            }
            let bucket = match objects {
                0 => 0,
                1..=10 => 1,
                11..=100 => 2,
                101..=1000 => 3,
                1001..=4999 => 4,
                _ => 5,
            };
            by_size[bucket].0 += 1;
            by_size[bucket].1 += attached;
        }
        let node_bytes = self.nodes.capacity() * std::mem::size_of::<Node<C>>();
        let succ_bytes = many * std::mem::size_of::<Targets>()
            + many_len * (std::mem::size_of::<NodeId>() * 2 + 2);
        eprintln!(
            "{prefix} NODES n={n} merged={merged} constant={constant} empty={empty_done} saturated={saturated} with_constraints={with_constraints} constraints={constraints} constraints_cap={constraints_cap} constraints_on_constant_nodes={on_constant} grouped_nodes={grouped_nodes} grouped_constraints={grouped} succ_one={one} succ_many={many} succ_many_len={many_len} searched_entries={searched} fired_differs={fired_differs} inbox_one={inbox_one} inbox_many_sets={inbox_many} held_objects={held}"
        );
        eprintln!(
            "{prefix} CROSS constraints_x_objects={product} max_node_constraints={} max_node_objects={} by_objects(0,<=10,<=100,<=1k,<5k,>=5k)=(nodes,constraints){by_size:?} applied_total={}",
            product_max.0, product_max.1, self.applied
        );
        eprintln!(
            "{prefix} SOLVER worklist={} cycle_suspects={} added_by_node={} attach_deferred={} firing_nodes={} set_holders={} watches={} absorbed_sets={} kinds_by_object={} phase={} est_bytes(nodes={node_bytes} successors={succ_bytes} constraints={})",
            self.worklist.len(),
            self.cycle_suspects.len(),
            self.added_by_node.len(),
            self.attach_deferred.len(),
            self.firing_nodes.len(),
            self.set_holders.len(),
            self.watches_waiting.len(),
            self.absorbed_sets.len(),
            self.kinds_by_object.len(),
            self.phase,
            constraints_cap * std::mem::size_of::<C>()
        );
        self.sets.census(prefix);
    }

    pub fn work(&self) -> Work {
        Work {
            copied: self.sets.copied,
            applied: self.applied,
            edges: self.edges,
            processed: self.processed,
            merged: self.merged,
            searched: self.searched,
        }
    }

    pub fn node(&mut self) -> NodeId {
        self.push_node(Node::new(SetId::EMPTY, false, None))
    }

    pub fn watch(&mut self) -> WatchId {
        let watch = WatchId::new(self.watches_waiting.len());
        self.watches_waiting.push(true);
        watch
    }

    pub fn witness(&mut self, watch: WatchId) -> NodeId {
        self.push_node(Node::new(SetId::EMPTY, false, Some(watch)))
    }

    pub fn is_waiting(&self, watch: WatchId) -> bool {
        self.watches_waiting[watch.index()]
    }

    pub fn wake(&mut self, rules: &mut impl Rules<C>, watch: WatchId) {
        assert!(self.watches_waiting[watch.index()], "a watch wakes once");
        self.watches_waiting[watch.index()] = false;
        rules.wake(self, watch);
    }

    pub fn constant(&mut self, object: ObjId) -> NodeId {
        let done = self.singleton(object);
        let node = self.push_node(Node::new(done, true, None));
        self.set_holders.push(node);
        node
    }

    pub fn follower(&mut self, rules: &mut impl Rules<C>, source: NodeId, since: u32) -> NodeId {
        let node = self.node();
        let source = self.find(source);
        let done = self.nodes[source.index()].done;
        if since == self.phase || self.sets.is_empty(done) {
            self.add_edge(rules, source, node);
            return node;
        }
        self.nodes[node.index()].done = done;
        self.set_holders.push(node);
        if !self.nodes[source.index()].constant {
            self.edges += 1;
            if done != self.saturated_set {
                self.link(source, node, false);
            }
        }
        node
    }

    pub fn add_object(&mut self, rules: &mut impl Rules<C>, node: NodeId, object: ObjId) {
        self.wake_witness(rules, node);
        let node = self.find(node);
        let kinds = self.kinds_of(object);
        let done = self.nodes[node.index()].done;
        if let Some(number) = self.sets.number_of(object)
            && self.sets.contains(done, number)
        {
            return;
        }
        if done == self.saturated_set {
            let single = self.singleton(object);
            self.absorb(single);
            return;
        }
        assert!(
            !self.nodes[node.index()].constant,
            "a constant node receives no other object"
        );
        if self.applications_in_progress > 0 {
            self.sets.number(object, kinds);
            let added = self.added_by_node.entry(node).or_default();
            if !added.contains(&object) {
                added.push(object);
            }
        } else {
            let single = self.singleton(object);
            self.receive(node, single);
        }
    }

    pub fn add_edge(&mut self, rules: &mut impl Rules<C>, source: NodeId, target: NodeId) {
        self.wake_witness(rules, target);
        let source = self.find(source);
        let target = self.find(target);
        assert!(
            !self.nodes[target.index()].constant,
            "a constant node receives no other object"
        );
        let source_done = self.nodes[source.index()].done;
        if self.nodes[source.index()].constant {
            self.receive(target, source_done);
            return;
        }
        if source == target {
            return;
        }
        match &self.nodes[source.index()].successors {
            Successors::Many(successors) if successors.contains(target) => return,
            Successors::One(only) if *only == target => return,
            _ => {}
        }
        self.edges += 1;
        let target_done = self.nodes[target.index()].done;
        if target_done == self.saturated_set {
            self.link(source, target, false);
            self.absorb(source_done);
            return;
        }
        if !self.sets.is_empty(source_done) && source_done == target_done {
            self.link(source, target, true);
            self.cycle_suspects.push(target);
            return;
        }
        self.link(source, target, false);
        if !self.sets.is_empty(source_done) {
            self.receive(target, source_done);
        }
    }

    pub fn attach(&mut self, rules: &mut impl Rules<C>, node: NodeId, constraint: C) -> Attached {
        let node = self.find(node);
        let entry = &mut self.nodes[node.index()];
        let seen = entry.done;
        if entry.constant {
            return self.apply_seen(rules, constraint, seen);
        }
        if let Some(groups) = &mut entry.groups {
            groups.push((vec![constraint], seen));
        } else if entry.constraints.is_empty() {
            entry.constraints = vec![constraint];
            entry.fired = seen;
        } else if entry.fired == seen {
            entry.constraints.push(constraint);
        } else {
            let constraints = std::mem::take(&mut entry.constraints);
            entry.groups = Some(Box::new(vec![
                (constraints, entry.fired),
                (vec![constraint], seen),
            ]));
            self.firing_nodes.insert(node);
        }
        self.apply_seen(rules, constraint, seen);
        Attached::Kept
    }

    pub fn apply_now(&mut self, rules: &mut impl Rules<C>, node: NodeId, constraint: C) {
        let node = self.find(node);
        let seen = self.nodes[node.index()].done;
        self.apply_seen(rules, constraint, seen);
    }

    pub fn objects(&mut self, node: NodeId) -> Vec<ObjId> {
        let node = self.find(node);
        let done = self.nodes[node.index()].done;
        if done == self.saturated_set {
            return vec![self.saturated];
        }
        let added = self.added_by_node.get(&node);
        let received = received_sets(&self.nodes[node.index()].inbox);
        if received.is_empty() && added.is_none() {
            return self.sets.ordered(done).collect();
        }
        let mut sets = vec![done];
        sets.extend(received);
        let mut numbers = self.sets.union_all(&sets);
        if let Some(added) = added {
            numbers.extend(added.iter().map(|&object| {
                self.sets
                    .number_of(object)
                    .expect("an added object is numbered")
            }));
            numbers.sort_unstable();
            numbers.dedup();
        }
        numbers
            .into_iter()
            .map(|number| self.sets.object(number))
            .collect()
    }

    pub fn is_saturated(&mut self, node: NodeId) -> bool {
        let node = self.find(node);
        self.nodes[node.index()].done == self.saturated_set
    }

    pub fn holds(&mut self, node: NodeId, object: ObjId) -> bool {
        let node = self.find(node);
        let done = self.nodes[node.index()].done;
        let Some(number) = self.sets.number_of(object) else {
            return false;
        };
        if self.sets.contains(done, number) {
            return true;
        }
        if done == self.saturated_set {
            return false;
        }
        if received_sets(&self.nodes[node.index()].inbox)
            .iter()
            .any(|&set| self.sets.contains(set, number))
        {
            return true;
        }
        self.added_by_node
            .get(&node)
            .is_some_and(|added| added.contains(&object))
    }

    pub fn cap(&self) -> Option<u32> {
        self.cap
    }

    pub fn opacity_enabled(&self) -> bool {
        self.opacity
    }

    pub fn has_absorbed(&self) -> bool {
        !self.absorbed_sets.is_empty()
    }

    pub fn absorbed(&self) -> Vec<ObjId> {
        let mut numbers: Vec<u32> = self
            .absorbed_sets
            .iter()
            .flat_map(|&set| self.sets.numbers(set).iter().copied())
            .collect();
        numbers.sort_unstable();
        numbers.dedup();
        numbers
            .into_iter()
            .map(|number| self.sets.object(number))
            .filter(|&object| object != self.saturated)
            .collect()
    }

    pub fn solve(&mut self, rules: &mut impl Rules<C>) {
        let mut starting = true;
        loop {
            rules.tick(self);
            if let Some((constraint, objects)) = self.attach_deferred.pop_front() {
                self.apply(rules, vec![constraint], objects);
                continue;
            }
            if self.sets.sweep_due() {
                self.sweep();
            }
            if !self.cycle_suspects.is_empty()
                && (starting
                    || self.worklist.is_empty()
                    || self.propagated_nodes_and_edges - self.propagated_at_last_search
                        >= self.last_search_walked)
            {
                self.collapse_cycles();
                continue;
            }
            let Some(node) = self.order.take(&mut self.worklist) else {
                self.phase += 1;
                if rules.between_rounds(self) {
                    starting = true;
                    continue;
                }
                if self.firing_nodes.is_empty() {
                    return;
                }
                self.fire(rules);
                starting = true;
                continue;
            };
            starting = false;
            let entry = &self.nodes[node.index()];
            if entry.representative.is_none() && !matches!(entry.inbox, Inbox::Empty) {
                self.process(node);
            }
        }
    }

    fn push_node(&mut self, node: Node<C>) -> NodeId {
        let id = NodeId::new(self.nodes.len());
        self.nodes.push(node);
        id
    }

    fn kinds_of(&self, object: ObjId) -> KindMask {
        self.kinds_by_object
            .get(object.index())
            .copied()
            .flatten()
            .expect("an object is declared before it reaches a node")
    }

    fn singleton(&mut self, object: ObjId) -> SetId {
        let kinds = self.kinds_of(object);
        self.sets.singleton(object, kinds)
    }

    fn wake_witness(&mut self, rules: &mut impl Rules<C>, node: NodeId) {
        if let Some(watch) = self.nodes[node.index()].witness
            && self.watches_waiting[watch.index()]
        {
            self.wake(rules, watch);
        }
    }

    fn find(&mut self, node: NodeId) -> NodeId {
        let Some(mut root) = self.nodes[node.index()].representative else {
            return node;
        };
        while let Some(next) = self.nodes[root.index()].representative {
            root = next;
        }
        let mut current = node;
        while current != root {
            let next = self.nodes[current.index()]
                .representative
                .expect("a node below the root has a representative");
            self.nodes[current.index()].representative = Some(root);
            current = next;
        }
        root
    }

    fn absorb(&mut self, set: SetId) {
        if !self.sets.is_empty(set) && set != self.saturated_set {
            self.absorbed_sets.insert(set);
        }
    }

    fn link(&mut self, source: NodeId, target: NodeId, searched: bool) {
        let successors = &mut self.nodes[source.index()].successors;
        match successors {
            Successors::Many(map) => {
                assert!(!map.contains(target));
                map.insert(target, searched);
            }
            Successors::One(only) => {
                assert_ne!(*only, target);
                let mut map = Targets::default();
                map.insert(*only, false);
                map.insert(target, searched);
                *successors = Successors::Many(Box::new(map));
            }
            Successors::None if searched => {
                let mut map = Targets::default();
                map.insert(target, true);
                *successors = Successors::Many(Box::new(map));
            }
            Successors::None => *successors = Successors::One(target),
        }
    }

    fn apply_seen(&mut self, rules: &mut impl Rules<C>, constraint: C, seen: SetId) -> Attached {
        if self.sets.is_empty(seen) {
            return Attached::Released;
        }
        if self.attach_nesting >= ATTACH_NESTING_MAX {
            self.attach_deferred.push_back((constraint, seen));
            return Attached::Kept;
        }
        self.attach_nesting += 1;
        self.apply(rules, vec![constraint], seen);
        self.attach_nesting -= 1;
        Attached::Released
    }

    fn receive(&mut self, node: NodeId, objects: SetId) {
        let entry = &mut self.nodes[node.index()];
        assert!(entry.representative.is_none());
        if objects == entry.done {
            return;
        }
        match &mut entry.inbox {
            Inbox::Empty => {
                entry.inbox = Inbox::One(objects);
                self.worklist.push_back(node);
            }
            Inbox::One(only) if *only == objects => {}
            Inbox::One(only) => entry.inbox = Inbox::Many(Box::new([*only, objects])),
            Inbox::Many(sets) => {
                if !sets.contains(&objects) {
                    *sets = sets.iter().copied().chain([objects]).collect();
                }
            }
        }
    }

    fn process(&mut self, node: NodeId) {
        let inbox = std::mem::replace(&mut self.nodes[node.index()].inbox, Inbox::Empty);
        let done = self.nodes[node.index()].done;
        if done == self.saturated_set {
            for set in received_sets(&inbox) {
                self.absorb(set);
            }
            return;
        }
        let delta = match inbox {
            Inbox::Many(sets) => {
                let mut fresh: Vec<SetId> = Vec::with_capacity(sets.len());
                for &set in sets.iter() {
                    let difference = self.sets.difference(set, done);
                    if !self.sets.is_empty(difference) {
                        fresh.push(difference);
                    }
                }
                match fresh.len() {
                    0 => return,
                    1 => fresh[0],
                    _ => {
                        let numbers = self.sets.union_all(&fresh);
                        self.sets.copied += numbers.len() as u64;
                        self.sets.intern(&numbers)
                    }
                }
            }
            Inbox::One(set) => {
                let delta = self.sets.difference(set, done);
                if self.sets.is_empty(delta) {
                    return;
                }
                delta
            }
            Inbox::Empty => unreachable!("a node on the worklist has an inbox"),
        };
        if self.sets.is_empty(done) {
            self.set_holders.push(node);
        }
        self.processed += 1;
        self.propagated_nodes_and_edges += match &self.nodes[node.index()].successors {
            Successors::None => 1,
            Successors::Many(map) => 1 + map.len() as u64,
            Successors::One(_) => 2,
        };
        let saturated_number = self
            .sets
            .number_of(self.saturated)
            .expect("the saturated value is numbered");
        let over_cap = self
            .cap
            .is_some_and(|cap| self.sets.len(done) + self.sets.len(delta) > cap as usize);
        if self.sets.contains(delta, saturated_number) || over_cap {
            self.absorb(done);
            self.absorb(delta);
            self.saturate_node(node);
        } else {
            let union = self.sets.union(done, delta);
            self.nodes[node.index()].done = union;
            if !matches!(self.nodes[node.index()].successors, Successors::None) {
                self.propagate(node, delta);
            }
        }
        let entry = &self.nodes[node.index()];
        if !entry.constraints.is_empty() || entry.groups.is_some() {
            self.firing_nodes.insert(node);
        }
    }

    fn saturate_node(&mut self, node: NodeId) {
        self.nodes[node.index()].done = self.saturated_set;
        let successors =
            std::mem::replace(&mut self.nodes[node.index()].successors, Successors::None);
        for (target, _) in successor_pairs(&successors) {
            let target = self.find(target);
            if target != node {
                self.receive(target, self.saturated_set);
            }
        }
    }

    fn propagate(&mut self, node: NodeId, delta: SetId) {
        let done = self.nodes[node.index()].done;
        let successors =
            std::mem::replace(&mut self.nodes[node.index()].successors, Successors::None);
        match successors {
            Successors::None => {}
            Successors::One(only) => {
                let target = self.find(only);
                if target == node {
                    return;
                }
                let target_done = self.nodes[target.index()].done;
                if target_done == self.saturated_set {
                    self.nodes[node.index()].successors = Successors::One(target);
                    self.absorb(delta);
                } else if target_done != done {
                    self.nodes[node.index()].successors = Successors::One(target);
                    self.receive(target, delta);
                } else {
                    let mut map = Targets::default();
                    map.insert(target, true);
                    self.nodes[node.index()].successors = Successors::Many(Box::new(map));
                    self.cycle_suspects.push(target);
                }
            }
            Successors::Many(mut map) => {
                let mut listed: Vec<NodeId> = map.order.clone();
                self.order.arrange(&mut listed);
                for listed_target in listed {
                    let target = self.find(listed_target);
                    if target != listed_target {
                        let searched = map
                            .remove(listed_target)
                            .expect("a listed successor is in the map");
                        if target == node || map.contains(target) {
                            continue;
                        }
                        map.insert(target, searched);
                    }
                    let target_done = self.nodes[target.index()].done;
                    if target_done == self.saturated_set {
                        self.absorb(delta);
                        continue;
                    }
                    if target_done != done {
                        self.receive(target, delta);
                    } else if !map.searched(target) {
                        map.insert(target, true);
                        self.cycle_suspects.push(target);
                    }
                }
                self.nodes[node.index()].successors = Successors::Many(map);
            }
        }
    }

    fn fire(&mut self, rules: &mut impl Rules<C>) {
        rules.firing(self);
        let mut firing: Vec<NodeId> = std::mem::take(&mut self.firing_nodes).into_iter().collect();
        self.order.arrange(&mut firing);
        self.applications_in_progress += 1;
        for node in firing {
            let node = self.find(node);
            self.fire_node(rules, node);
        }
        self.applications_in_progress -= 1;
        self.flush();
    }

    fn fire_node(&mut self, rules: &mut impl Rules<C>, node: NodeId) {
        let entry = &mut self.nodes[node.index()];
        let done = entry.done;
        let groups = match entry.groups.take() {
            None => vec![(entry.constraints.clone(), entry.fired)],
            Some(groups) => {
                entry.constraints = groups
                    .iter()
                    .flat_map(|(constraints, _)| constraints.iter().copied())
                    .collect();
                *groups
            }
        };
        entry.fired = done;
        for (constraints, fired) in groups {
            if !constraints.is_empty() && fired != done {
                let new = self.sets.difference(done, fired);
                if !self.sets.is_empty(new) {
                    self.apply(rules, constraints, new);
                }
            }
        }
    }

    fn apply(&mut self, rules: &mut impl Rules<C>, constraints: Vec<C>, objects: SetId) {
        self.applied += (constraints.len() * self.sets.len(objects)) as u64;
        let mut constraints = constraints;
        self.order.arrange(&mut constraints);
        let mut objects = objects;
        let opaque_inside = self.opacity && self.sets.ordered(objects).any(|o| rules.opaque(o));
        if objects == self.saturated_set || opaque_inside {
            for &constraint in &constraints {
                rules.saturate(self, constraint);
            }
            let kept: Vec<u32> = if self.opacity {
                self.sets
                    .numbers(objects)
                    .iter()
                    .copied()
                    .filter(|&number| !rules.opaque(self.sets.object(number)))
                    .collect()
            } else {
                Vec::new()
            };
            if kept.is_empty() {
                return;
            }
            objects = self.sets.intern(&kept);
        }
        if self.opacity {
            let mut applied = Vec::with_capacity(constraints.len());
            for constraint in constraints {
                if rules.captures_opaque(self, constraint) {
                    rules.saturate(self, constraint);
                } else {
                    applied.push(constraint);
                }
            }
            constraints = applied;
        }
        if self.sets.len(objects) == 1 {
            let object = self.sets.ordered(objects).next().expect("one object");
            for constraint in constraints {
                rules.apply(self, constraint, &[object]);
            }
            return;
        }
        self.applications_in_progress += 1;
        let ordered: Vec<ObjId> = self.sets.ordered(objects).collect();
        let select = ordered.len() >= KIND_SELECTION_OBJECTS_MIN;
        for constraint in constraints {
            match rules.kinds(constraint) {
                Some(kinds) if select => {
                    let selected = self.sets.of_kinds(objects, kinds).to_vec();
                    rules.apply(self, constraint, &selected);
                }
                _ => rules.apply(self, constraint, &ordered),
            }
        }
        self.applications_in_progress -= 1;
        self.flush();
    }

    fn flush(&mut self) {
        if self.applications_in_progress > 0 || self.added_by_node.is_empty() {
            return;
        }
        let added = std::mem::take(&mut self.added_by_node);
        for (node, objects) in added {
            let numbers = objects
                .iter()
                .map(|&object| self.sets.number_of(object).expect("numbered when added"))
                .collect();
            let set = self.sets.intern_unsorted(numbers);
            self.sets.copied += self.sets.len(set) as u64;
            let node = self.find(node);
            self.receive(node, set);
        }
    }

    fn set_done(&mut self, node: NodeId, objects: SetId) {
        if self.sets.is_empty(self.nodes[node.index()].done) && !self.sets.is_empty(objects) {
            self.set_holders.push(node);
        }
        self.nodes[node.index()].done = objects;
    }

    fn sweep(&mut self) {
        let holders: Vec<NodeId> = self
            .set_holders
            .iter()
            .copied()
            .filter(|&node| {
                let entry = &self.nodes[node.index()];
                entry.representative.is_none() && !self.sets.is_empty(entry.done)
            })
            .collect();
        let mut live: Vec<SetId> = holders
            .iter()
            .map(|&node| self.nodes[node.index()].done)
            .collect();
        for &node in &self.worklist {
            live.extend(received_sets(&self.nodes[node.index()].inbox));
        }
        self.sets.sweep(live);
        self.set_holders = holders;
        let mut held = vec![false; self.sets.count()];
        let mut hold = |set: SetId| held[set.index()] = true;
        hold(SetId::EMPTY);
        hold(self.saturated_set);
        for entry in &self.nodes {
            hold(entry.done);
            hold(entry.fired);
            received_sets(&entry.inbox).into_iter().for_each(&mut hold);
            for (_, set) in entry.groups.iter().flat_map(|groups| groups.iter()) {
                hold(*set);
            }
        }
        for &(_, set) in &self.attach_deferred {
            hold(set);
        }
        for &set in &self.absorbed_sets {
            hold(set);
        }
        self.sets.compact(&held);
    }

    fn collapse_cycles(&mut self) {
        let starts = std::mem::take(&mut self.cycle_suspects);
        let (components, searched) = self.cycle_components(&starts);
        self.searched += searched;
        self.last_search_walked = searched;
        self.propagated_at_last_search = self.propagated_nodes_and_edges;
        for component in components {
            self.merge(component);
        }
    }

    fn successor_list(&mut self, node: NodeId) -> Vec<NodeId> {
        let listed: Vec<NodeId> = match &self.nodes[node.index()].successors {
            Successors::None => Vec::new(),
            Successors::One(only) => vec![*only],
            Successors::Many(map) => map.order.clone(),
        };
        listed.into_iter().map(|target| self.find(target)).collect()
    }

    fn cycle_components(&mut self, starts: &[NodeId]) -> (Vec<Vec<NodeId>>, u64) {
        let mut index: FxHashMap<NodeId, u64> = FxHashMap::default();
        let mut low: FxHashMap<NodeId, u64> = FxHashMap::default();
        let mut stack: Vec<NodeId> = Vec::new();
        let mut on_stack: FxHashSet<NodeId> = FxHashSet::default();
        let mut components = Vec::new();
        let mut edges: u64 = 0;
        for &start in starts {
            let start = self.find(start);
            if index.contains_key(&start) {
                continue;
            }
            let number = index.len() as u64;
            index.insert(start, number);
            low.insert(start, number);
            stack.push(start);
            on_stack.insert(start);
            let mut work = vec![(start, self.successor_list(start), 0usize)];
            while let Some(frame) = work.last_mut() {
                let node = frame.0;
                let mut next = None;
                while frame.2 < frame.1.len() {
                    let successor = frame.1[frame.2];
                    frame.2 += 1;
                    edges += 1;
                    if !index.contains_key(&successor) {
                        next = Some(successor);
                        break;
                    }
                    if on_stack.contains(&successor) && index[&successor] < low[&node] {
                        low.insert(node, index[&successor]);
                    }
                }
                if let Some(successor) = next {
                    let number = index.len() as u64;
                    index.insert(successor, number);
                    low.insert(successor, number);
                    stack.push(successor);
                    on_stack.insert(successor);
                    let successors = self.successor_list(successor);
                    work.push((successor, successors, 0));
                    continue;
                }
                work.pop();
                if let Some(parent) = work.last() {
                    let parent = parent.0;
                    if low[&node] < low[&parent] {
                        low.insert(parent, low[&node]);
                    }
                }
                if low[&node] == index[&node] {
                    let mut component = Vec::new();
                    loop {
                        let member = stack.pop().expect("the node is on the stack");
                        on_stack.remove(&member);
                        component.push(member);
                        if member == node {
                            break;
                        }
                    }
                    if component.len() > 1 {
                        component.reverse();
                        components.push(component);
                    }
                }
            }
        }
        (components, index.len() as u64 + edges)
    }

    fn merge(&mut self, members: Vec<NodeId>) {
        assert!(members.len() > 1);
        let representative = members[0];
        let mut distinct: Vec<SetId> = Vec::new();
        for &member in &members {
            let done = self.nodes[member.index()].done;
            if !distinct.contains(&done) {
                distinct.push(done);
            }
        }
        let mut done = if distinct.len() == 1 {
            distinct[0]
        } else {
            let numbers = self.sets.union_all(&distinct);
            let set = self.sets.intern(&numbers);
            self.sets.copied += self.sets.len(set) as u64;
            set
        };
        let saturated_number = self
            .sets
            .number_of(self.saturated)
            .expect("the saturated value is numbered");
        let over_cap = self
            .cap
            .is_some_and(|cap| self.sets.len(done) > cap as usize);
        if self.sets.contains(done, saturated_number) || over_cap {
            self.absorb(done);
            done = self.saturated_set;
        }
        let inside: FxHashSet<NodeId> = members.iter().copied().collect();
        let mut extras: Vec<(SetId, SetId)> = Vec::new();
        let mut catch_up: Vec<(Vec<NodeId>, SetId)> = Vec::new();
        for &member in &members {
            let member_done = self.nodes[member.index()].done;
            if member_done == done {
                continue;
            }
            let listed: Vec<NodeId> = successor_pairs(&self.nodes[member.index()].successors)
                .into_iter()
                .map(|(target, _)| target)
                .collect();
            let mut outside = Vec::new();
            for target in listed {
                if !inside.contains(&self.find(target)) {
                    outside.push(target);
                }
            }
            if outside.is_empty() {
                continue;
            }
            let extra = match extras.iter().find(|(key, _)| *key == member_done) {
                Some(&(_, extra)) => extra,
                None => {
                    let extra = if self.sets.is_empty(member_done) {
                        done
                    } else {
                        let right = self.sets.numbers(member_done);
                        let remaining: Vec<u32> = self
                            .sets
                            .numbers(done)
                            .iter()
                            .copied()
                            .filter(|number| right.binary_search(number).is_err())
                            .collect();
                        let set = self.sets.intern(&remaining);
                        self.sets.copied += self.sets.len(set) as u64;
                        set
                    };
                    extras.push((member_done, extra));
                    extra
                }
            };
            catch_up.push((outside, extra));
        }
        let mut inbox: Vec<SetId> = Vec::new();
        let mut groups: Vec<(Vec<C>, SetId)> = Vec::new();
        for &member in &members {
            let entry = &mut self.nodes[member.index()];
            inbox.extend(received_sets(&entry.inbox));
            if let Some(member_groups) = entry.groups.take() {
                groups.extend(*member_groups);
            } else if !entry.constraints.is_empty() {
                groups.push((std::mem::take(&mut entry.constraints), entry.fired));
            }
            if member != representative {
                entry.representative = Some(representative);
            }
        }
        let mut successors: OrderedMap<NodeId, bool> = OrderedMap::default();
        for &member in &members {
            let pairs = successor_pairs(&self.nodes[member.index()].successors);
            for (target, searched) in pairs {
                let target = self.find(target);
                if target != representative && !successors.contains_key(&target) {
                    successors.insert(target, searched);
                }
            }
            if member != representative {
                let entry = &mut self.nodes[member.index()];
                entry.done = SetId::EMPTY;
                entry.inbox = Inbox::Empty;
                entry.successors = Successors::None;
                entry.constraints = Vec::new();
                entry.groups = None;
                entry.fired = SetId::EMPTY;
            }
        }
        self.merged += members.len() as u64 - 1;
        self.set_done(representative, done);
        self.nodes[representative.index()].successors = Successors::None;
        for (target, searched) in successors {
            self.link(representative, target, searched);
        }
        let entry = &mut self.nodes[representative.index()];
        entry.constraints = Vec::new();
        entry.fired = SetId::EMPTY;
        entry.inbox = Inbox::Empty;
        if groups.is_empty() {
            entry.groups = None;
        } else {
            entry.groups = Some(Box::new(groups));
            self.firing_nodes.insert(representative);
        }
        for set in inbox {
            self.receive(representative, set);
        }
        for (outside, extra) in catch_up {
            for target in outside {
                let target = self.find(target);
                assert_ne!(target, representative, "a node is its own successor");
                self.receive(target, extra);
            }
        }
    }
}

fn received_sets(inbox: &Inbox) -> Vec<SetId> {
    match inbox {
        Inbox::Empty => Vec::new(),
        Inbox::One(set) => vec![*set],
        Inbox::Many(sets) => sets.to_vec(),
    }
}

fn successor_pairs(successors: &Successors) -> Vec<(NodeId, bool)> {
    match successors {
        Successors::None => Vec::new(),
        Successors::One(only) => vec![(*only, false)],
        Successors::Many(map) => map.pairs().collect(),
    }
}
