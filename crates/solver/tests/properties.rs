use std::collections::{BTreeMap, BTreeSet};

use pycg_solver::{KindMask, NodeId, ObjId, Order, Rules, Solver, WatchId};

const NODES: usize = 8;
const OBJECTS: u32 = 6;
const KINDS: u32 = 3;
const FOLLOWERS: usize = 2;
const STEPS_MAX: usize = 40;
const TABLE_ENTRIES_MAX: usize = 12;
const ACTIONS_MAX: usize = 3;
const CYCLE_MIN: usize = 2;
const CYCLE_MAX: usize = 5;
const SATURATED: ObjId = ObjId(0);
const PLAIN: KindMask = 1;
const SMALL_CAP: u32 = 2;
const SYSTEMS: u64 = 3_000;
const SPLITMIX_INCREMENT: u64 = 0x9E37_79B9_7F4A_7C15;
const SPLITMIX_FIRST_MULTIPLIER: u64 = 0xBF58_476D_1CE4_E5B9;
const SPLITMIX_SECOND_MULTIPLIER: u64 = 0x94D0_49BB_1331_11EB;

struct Random(u64);

impl Random {
    fn below(&mut self, bound: usize) -> usize {
        self.0 = self.0.wrapping_add(SPLITMIX_INCREMENT);
        let mut mixed = self.0;
        mixed = (mixed ^ (mixed >> 30)).wrapping_mul(SPLITMIX_FIRST_MULTIPLIER);
        mixed = (mixed ^ (mixed >> 27)).wrapping_mul(SPLITMIX_SECOND_MULTIPLIER);
        mixed ^= mixed >> 31;
        usize::try_from(mixed % u64::try_from(bound).expect("a bound")).expect("an index")
    }

    fn node(&mut self) -> usize {
        self.below(NODES)
    }

    fn object(&mut self) -> u32 {
        u32::try_from(self.below(OBJECTS as usize)).expect("an object") + 1
    }

    fn kind(&mut self) -> u32 {
        u32::try_from(self.below(KINDS as usize)).expect("a kind")
    }

    fn slot(&mut self) -> usize {
        self.below(FOLLOWERS)
    }
}

#[derive(Clone, Debug)]
enum Action {
    Edge(usize, usize),
    Object(usize, u32),
    Attach(usize, u32),
    Follow(usize),
    Read(usize, u32),
}

#[derive(Clone, Debug)]
enum Step {
    Object(usize, u32),
    Edge(usize, usize),
    Cycle(Vec<usize>),
    Attach(usize, u32),
    Constant(u32, usize),
    ConstantRule(u32, u32),
    Follow(usize),
    Read(usize, u32),
    Solve,
}

#[derive(Clone, Debug)]
struct Spec {
    steps: Vec<Step>,
    table: BTreeMap<(u32, u32), Vec<Action>>,
}

fn action(random: &mut Random) -> Action {
    match random.below(5) {
        0 => Action::Edge(random.node(), random.node()),
        1 => Action::Object(random.node(), random.object()),
        2 => Action::Attach(random.node(), random.kind()),
        3 => Action::Follow(random.slot()),
        _ => Action::Read(random.slot(), random.kind()),
    }
}

fn step(random: &mut Random) -> Step {
    match random.below(9) {
        0 => Step::Object(random.node(), random.object()),
        1 => Step::Edge(random.node(), random.node()),
        2 => {
            let length = CYCLE_MIN + random.below(CYCLE_MAX - CYCLE_MIN + 1);
            Step::Cycle((0..length).map(|_| random.node()).collect())
        }
        3 => Step::Attach(random.node(), random.kind()),
        4 => Step::Constant(random.object(), random.node()),
        5 => Step::ConstantRule(random.object(), random.kind()),
        6 => Step::Follow(random.slot()),
        7 => Step::Read(random.slot(), random.kind()),
        _ => Step::Solve,
    }
}

fn spec(seed: u64) -> Spec {
    let mut random = Random(seed);
    let steps = (0..random.below(STEPS_MAX + 1))
        .map(|_| step(&mut random))
        .collect();
    let mut table = BTreeMap::new();
    for _ in 0..random.below(TABLE_ENTRIES_MAX + 1) {
        let key = (random.kind(), random.object());
        let actions = (0..random.below(ACTIONS_MAX + 1))
            .map(|_| action(&mut random))
            .collect();
        table.insert(key, actions);
    }
    Spec { steps, table }
}

struct Rule {
    kind: u32,
    path: String,
    applied: Vec<u32>,
}

enum Effect {
    Edge(usize, usize),
    Object(usize, u32),
    Attach(usize, usize),
    Follow(usize),
    Read(usize, usize),
}

#[derive(Default)]
struct Book {
    table: BTreeMap<(u32, u32), Vec<Action>>,
    rules: Vec<Rule>,
    attached: Vec<(usize, usize)>,
    constant_rules: Vec<(u32, usize)>,
    read_slots: BTreeSet<usize>,
    waiting: BTreeMap<usize, Vec<usize>>,
}

impl Book {
    fn rule(&mut self, kind: u32, path: String) -> usize {
        self.rules.push(Rule {
            kind,
            path,
            applied: Vec::new(),
        });
        self.rules.len() - 1
    }

    fn effects(&mut self, rule: usize, object: u32) -> Vec<Effect> {
        self.rules[rule].applied.push(object);
        let (kind, path) = (self.rules[rule].kind, self.rules[rule].path.clone());
        let actions = self.table.get(&(kind, object)).cloned().unwrap_or_default();
        let mut effects = Vec::new();
        for (number, action) in actions.into_iter().enumerate() {
            let nested = format!("{path}/{object}.{number}");
            match action {
                Action::Edge(source, target) => effects.push(Effect::Edge(source, target)),
                Action::Object(node, object) => effects.push(Effect::Object(node, object)),
                Action::Attach(node, nested_kind) if nested_kind > kind => {
                    let nested = self.rule(nested_kind, nested);
                    self.attached.push((node, nested));
                    effects.push(Effect::Attach(node, nested));
                }
                Action::Follow(slot) => effects.push(Effect::Follow(slot)),
                Action::Read(slot, nested_kind) if nested_kind > kind => {
                    let nested = self.rule(nested_kind, nested);
                    effects.push(Effect::Read(slot, nested));
                }
                Action::Attach(..) | Action::Read(..) => {}
            }
        }
        effects
    }
}

enum Follower<N> {
    Absent,
    Since(N, u32),
    Node(N),
}

struct Real {
    book: Book,
    nodes: Vec<NodeId>,
    followers: Vec<Follower<NodeId>>,
}

impl Rules<usize> for Real {
    fn apply(&mut self, solver: &mut Solver<usize>, constraint: usize, objects: &[ObjId]) {
        for object in objects {
            let effects = self.book.effects(constraint, object.0);
            self.run(solver, effects);
        }
    }

    fn saturate(&mut self, _solver: &mut Solver<usize>, _constraint: usize) {}

    fn kinds(&self, _constraint: usize) -> Option<KindMask> {
        None
    }

    fn captures_opaque(&self, _solver: &Solver<usize>, _constraint: usize) -> bool {
        false
    }

    fn opaque(&self, _object: ObjId) -> bool {
        false
    }

    fn between_rounds(&mut self, _solver: &mut Solver<usize>) -> bool {
        false
    }

    fn wake(&mut self, _solver: &mut Solver<usize>, _watch: WatchId) {}

    fn firing(&mut self, _solver: &mut Solver<usize>) {}
}

impl Real {
    fn run(&mut self, solver: &mut Solver<usize>, effects: Vec<Effect>) {
        for effect in effects {
            match effect {
                Effect::Edge(source, target) => {
                    let (source, target) = (self.nodes[source], self.nodes[target]);
                    solver.add_edge(self, source, target);
                }
                Effect::Object(node, object) => {
                    let node = self.nodes[node];
                    solver.add_object(self, node, ObjId(object));
                }
                Effect::Attach(node, rule) => {
                    let node = self.nodes[node];
                    solver.attach(self, node, rule);
                }
                Effect::Follow(slot) => self.follow(solver, slot),
                Effect::Read(slot, rule) => self.read(solver, slot, rule),
            }
        }
    }

    fn follow(&mut self, solver: &mut Solver<usize>, slot: usize) {
        if !matches!(self.followers[slot], Follower::Absent) {
            return;
        }
        self.followers[slot] = Follower::Since(self.nodes[slot + 1], solver.phase);
        for rule in self.book.waiting.remove(&slot).unwrap_or_default() {
            self.read(solver, slot, rule);
        }
    }

    fn read(&mut self, solver: &mut Solver<usize>, slot: usize, rule: usize) {
        let node = match self.followers[slot] {
            Follower::Absent => {
                self.book.waiting.entry(slot).or_default().push(rule);
                return;
            }
            Follower::Since(source, since) => {
                let node = solver.follower(self, source, since);
                self.followers[slot] = Follower::Node(node);
                node
            }
            Follower::Node(node) => node,
        };
        self.book.read_slots.insert(slot);
        self.book.attached.push((NODES + slot, rule));
        solver.attach(self, node, rule);
        let target = self.nodes[slot];
        solver.add_edge(self, node, target);
    }
}

#[derive(Default)]
struct Reference {
    cap: Option<u32>,
    pts: Vec<BTreeSet<u32>>,
    edges: Vec<(usize, usize)>,
    constraints: Vec<(usize, usize, BTreeSet<u32>)>,
    added: Vec<(usize, u32)>,
    nodes: Vec<usize>,
    followers: Vec<Follower<usize>>,
}

impl Reference {
    fn node(&mut self) -> usize {
        self.pts.push(BTreeSet::new());
        self.pts.len() - 1
    }

    fn capped(&self, objects: BTreeSet<u32>) -> BTreeSet<u32> {
        let over = self
            .cap
            .is_some_and(|cap| objects.len() > usize::try_from(cap).expect("a cap"));
        if objects.contains(&SATURATED.0) || over {
            return BTreeSet::from([SATURATED.0]);
        }
        objects
    }

    fn apply(&mut self, book: &mut Book, rule: usize, objects: BTreeSet<u32>) {
        for object in objects {
            if object != SATURATED.0 {
                let effects = book.effects(rule, object);
                self.run(book, effects);
            }
        }
    }

    fn attach(&mut self, book: &mut Book, node: usize, rule: usize) {
        let seen = self.pts[node].clone();
        self.constraints.push((node, rule, seen.clone()));
        self.apply(book, rule, seen);
    }

    fn run(&mut self, book: &mut Book, effects: Vec<Effect>) {
        for effect in effects {
            match effect {
                Effect::Edge(source, target) => {
                    self.edges.push((self.nodes[source], self.nodes[target]));
                }
                Effect::Object(node, object) => self.added.push((self.nodes[node], object)),
                Effect::Attach(node, rule) => self.attach(book, self.nodes[node], rule),
                Effect::Follow(slot) => self.follow(book, slot),
                Effect::Read(slot, rule) => self.read(book, slot, rule),
            }
        }
    }

    fn follow(&mut self, book: &mut Book, slot: usize) {
        if !matches!(self.followers[slot], Follower::Absent) {
            return;
        }
        let follower = self.node();
        self.edges.push((self.nodes[slot + 1], follower));
        self.followers[slot] = Follower::Node(follower);
        for rule in book.waiting.remove(&slot).unwrap_or_default() {
            self.read(book, slot, rule);
        }
    }

    fn read(&mut self, book: &mut Book, slot: usize, rule: usize) {
        let Follower::Node(follower) = self.followers[slot] else {
            book.waiting.entry(slot).or_default().push(rule);
            return;
        };
        book.read_slots.insert(slot);
        book.attached.push((NODES + slot, rule));
        self.attach(book, follower, rule);
        self.edges.push((follower, self.nodes[slot]));
    }

    fn solve(&mut self, book: &mut Book) {
        loop {
            for (node, object) in std::mem::take(&mut self.added) {
                let mut objects = self.pts[node].clone();
                objects.insert(object);
                self.pts[node] = self.capped(objects);
            }
            let mut changed = true;
            while changed {
                changed = false;
                for (source, target) in self.edges.clone() {
                    let joined: BTreeSet<u32> =
                        self.pts[target].union(&self.pts[source]).copied().collect();
                    let joined = self.capped(joined);
                    if joined != self.pts[target] {
                        self.pts[target] = joined;
                        changed = true;
                    }
                }
            }
            let mut fired = false;
            for index in 0..self.constraints.len() {
                let (node, rule, _) = self.constraints[index];
                let new: BTreeSet<u32> = self.pts[node]
                    .difference(&self.constraints[index].2)
                    .copied()
                    .collect();
                self.constraints[index].2.extend(new.iter().copied());
                fired |= new.iter().any(|&object| object != SATURATED.0);
                self.apply(book, rule, new);
            }
            if !fired && self.added.is_empty() {
                return;
            }
        }
    }
}

struct Outcome {
    sets: Vec<BTreeSet<u32>>,
    applied: BTreeMap<String, Vec<u32>>,
}

fn sorted(objects: &[u32]) -> Vec<u32> {
    let mut objects = objects.to_vec();
    objects.sort_unstable();
    objects
}

fn outcome(book: &Book, sets: Vec<BTreeSet<u32>>) -> Outcome {
    let applied = book
        .rules
        .iter()
        .map(|rule| (rule.path.clone(), sorted(&rule.applied)))
        .collect();
    Outcome { sets, applied }
}

fn real(spec: &Spec, cap: Option<u32>, order: Order) -> (Outcome, Book) {
    let mut solver = Solver::new(SATURATED, PLAIN, cap, order);
    for object in 1..=OBJECTS {
        solver.declare(ObjId(object), PLAIN);
    }
    let nodes = (0..NODES).map(|_| solver.node()).collect();
    let mut system = Real {
        book: Book {
            table: spec.table.clone(),
            ..Book::default()
        },
        nodes,
        followers: (0..FOLLOWERS).map(|_| Follower::Absent).collect(),
    };
    for (position, step) in spec.steps.iter().enumerate() {
        let root = format!("root{position}");
        match step {
            Step::Object(node, object) => {
                system.run(&mut solver, vec![Effect::Object(*node, *object)]);
            }
            Step::Edge(source, target) => {
                system.run(&mut solver, vec![Effect::Edge(*source, *target)]);
            }
            Step::Cycle(ring) => {
                let effects = ring
                    .iter()
                    .zip(ring.iter().cycle().skip(1))
                    .map(|(&source, &target)| Effect::Edge(source, target))
                    .collect();
                system.run(&mut solver, effects);
            }
            Step::Attach(node, kind) => {
                let rule = system.book.rule(*kind, root);
                system.book.attached.push((*node, rule));
                system.run(&mut solver, vec![Effect::Attach(*node, rule)]);
            }
            Step::Constant(object, target) => {
                let constant = solver.constant(ObjId(*object));
                let target = system.nodes[*target];
                solver.add_edge(&mut system, constant, target);
            }
            Step::ConstantRule(object, kind) => {
                let constant = solver.constant(ObjId(*object));
                let rule = system.book.rule(*kind, root);
                system.book.constant_rules.push((*object, rule));
                solver.attach(&mut system, constant, rule);
            }
            Step::Follow(slot) => system.run(&mut solver, vec![Effect::Follow(*slot)]),
            Step::Read(slot, kind) => {
                let rule = system.book.rule(*kind, root);
                system.run(&mut solver, vec![Effect::Read(*slot, rule)]);
            }
            Step::Solve => solver.solve(&mut system),
        }
    }
    solver.solve(&mut system);
    let mut nodes = system.nodes.clone();
    for slot in 0..FOLLOWERS {
        match system.followers[slot] {
            Follower::Node(node) if system.book.read_slots.contains(&slot) => nodes.push(node),
            _ => nodes.push(solver.node()),
        }
    }
    let sets = nodes
        .into_iter()
        .map(|node| {
            solver
                .objects(node)
                .into_iter()
                .map(|object| object.0)
                .collect()
        })
        .collect();
    let found = outcome(&system.book, sets);
    (found, system.book)
}

fn reference(spec: &Spec, cap: Option<u32>) -> Outcome {
    let mut graph = Reference {
        cap,
        ..Reference::default()
    };
    graph.nodes = (0..NODES).map(|_| graph.node()).collect();
    graph.followers = (0..FOLLOWERS).map(|_| Follower::Absent).collect();
    let mut book = Book {
        table: spec.table.clone(),
        ..Book::default()
    };
    for (position, step) in spec.steps.iter().enumerate() {
        let root = format!("root{position}");
        match step {
            Step::Object(node, object) => {
                graph.run(&mut book, vec![Effect::Object(*node, *object)])
            }
            Step::Edge(source, target) => {
                graph.run(&mut book, vec![Effect::Edge(*source, *target)])
            }
            Step::Cycle(ring) => {
                let effects = ring
                    .iter()
                    .zip(ring.iter().cycle().skip(1))
                    .map(|(&source, &target)| Effect::Edge(source, target))
                    .collect();
                graph.run(&mut book, effects);
            }
            Step::Attach(node, kind) => {
                let rule = book.rule(*kind, root);
                book.attached.push((*node, rule));
                graph.run(&mut book, vec![Effect::Attach(*node, rule)]);
            }
            Step::Constant(object, target) => {
                let constant = graph.node();
                graph.pts[constant].insert(*object);
                graph.edges.push((constant, graph.nodes[*target]));
            }
            Step::ConstantRule(object, kind) => {
                let constant = graph.node();
                graph.pts[constant].insert(*object);
                let rule = book.rule(*kind, root);
                book.constant_rules.push((*object, rule));
                graph.attach(&mut book, constant, rule);
            }
            Step::Follow(slot) => graph.run(&mut book, vec![Effect::Follow(*slot)]),
            Step::Read(slot, kind) => {
                let rule = book.rule(*kind, root);
                graph.run(&mut book, vec![Effect::Read(*slot, rule)]);
            }
            Step::Solve => graph.solve(&mut book),
        }
    }
    graph.solve(&mut book);
    let mut sets: Vec<BTreeSet<u32>> = graph
        .nodes
        .iter()
        .map(|&node| graph.pts[node].clone())
        .collect();
    for slot in 0..FOLLOWERS {
        sets.push(match graph.followers[slot] {
            Follower::Node(node) if book.read_slots.contains(&slot) => graph.pts[node].clone(),
            _ => BTreeSet::new(),
        });
    }
    outcome(&book, sets)
}

fn agrees(seed: u64, cap: Option<u32>, order: Order) {
    let spec = spec(seed);
    let (found, book) = real(&spec, cap, order);
    let expected = reference(&spec, cap);
    assert_eq!(
        found.sets, expected.sets,
        "seed {seed}, {order:?}, cap {cap:?}: {spec:?}"
    );
    assert_eq!(
        found.applied, expected.applied,
        "seed {seed}, {order:?}, cap {cap:?}: {spec:?}"
    );
    for &(node, rule) in &book.attached {
        let seen = sorted(&book.rules[rule].applied);
        let unique: BTreeSet<u32> = seen.iter().copied().collect();
        assert_eq!(
            seen.len(),
            unique.len(),
            "seed {seed}: a rule sees an object twice"
        );
        if found.sets[node] != BTreeSet::from([SATURATED.0]) {
            let held: Vec<u32> = found.sets[node].iter().copied().collect();
            assert_eq!(seen, held, "seed {seed}: a rule sees what its node holds");
        }
    }
    for &(object, rule) in &book.constant_rules {
        assert_eq!(
            book.rules[rule].applied,
            [object],
            "seed {seed}: a constant rule"
        );
    }
}

fn orders(seed: u64) -> [Order; 4] {
    [
        Order::Canonical,
        Order::LastInFirstOut,
        Order::Reversed,
        Order::shuffled(seed),
    ]
}

#[test]
fn the_solver_agrees_with_the_naive_reference_in_every_order() {
    for seed in 0..SYSTEMS {
        for order in orders(seed) {
            agrees(seed, None, order);
        }
    }
}

#[test]
fn the_solver_agrees_with_the_naive_reference_at_a_small_cap() {
    for seed in 0..SYSTEMS {
        for order in orders(seed) {
            agrees(seed, Some(SMALL_CAP), order);
        }
    }
}

#[test]
fn the_solver_gives_the_same_objects_and_rule_order_twice() {
    for seed in 0..SYSTEMS {
        let spec = spec(seed);
        let run = || {
            let (found, book) = real(&spec, None, Order::Canonical);
            let log: Vec<(String, Vec<u32>)> = book
                .rules
                .iter()
                .map(|rule| (rule.path.clone(), rule.applied.clone()))
                .collect();
            (found.sets, log)
        };
        assert_eq!(run(), run(), "seed {seed}");
    }
}
