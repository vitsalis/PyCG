use pycg_solver::{ATTACH_NESTING_MAX, KindMask, NodeId, ObjId, Rules, Solver, WatchId};

const SATURATED: ObjId = ObjId(0);
const PLAIN: KindMask = 1;
const SPECIAL: KindMask = 2;

#[derive(Default)]
struct Recorded {
    applied: Vec<(u32, Vec<ObjId>)>,
    saturated: Vec<u32>,
    woken: Vec<WatchId>,
    results: Vec<(u32, NodeId)>,
    kinds: Vec<(u32, KindMask)>,
    nest: Vec<(u32, NodeId)>,
    between: u32,
}

impl Rules<u32> for Recorded {
    fn apply(&mut self, solver: &mut Solver<u32>, constraint: u32, objects: &[ObjId]) {
        self.applied.push((constraint, objects.to_vec()));
        if let Some(&(_, node)) = self.nest.iter().find(|(c, _)| *c == constraint) {
            solver.attach(self, node, constraint + 1);
        }
    }

    fn saturate(&mut self, solver: &mut Solver<u32>, constraint: u32) {
        self.saturated.push(constraint);
        if let Some(&(_, node)) = self.results.iter().find(|(c, _)| *c == constraint) {
            let saturated = solver.saturated();
            solver.add_object(self, node, saturated);
        }
    }

    fn kinds(&self, constraint: u32) -> Option<KindMask> {
        self.kinds
            .iter()
            .find(|(c, _)| *c == constraint)
            .map(|&(_, kinds)| kinds)
    }

    fn captures_opaque(&self, _solver: &Solver<u32>, _constraint: u32) -> bool {
        false
    }

    fn opaque(&self, _object: ObjId) -> bool {
        false
    }

    fn between_rounds(&mut self, _solver: &mut Solver<u32>) -> bool {
        self.between += 1;
        false
    }

    fn wake(&mut self, _solver: &mut Solver<u32>, watch: WatchId) {
        self.woken.push(watch);
    }
}

fn solver(cap: Option<u32>) -> Solver<u32> {
    Solver::new(SATURATED, PLAIN, cap)
}

fn objects(solver: &mut Solver<u32>, numbers: &[u32]) -> Vec<ObjId> {
    numbers
        .iter()
        .map(|&number| {
            solver.declare(ObjId(number), PLAIN);
            ObjId(number)
        })
        .collect()
}

#[test]
fn objects_flow_along_edges_to_a_fixpoint() {
    let mut rules = Recorded::default();
    let mut solver = solver(None);
    let [a, b, c] = [solver.node(), solver.node(), solver.node()];
    let found = objects(&mut solver, &[1, 2]);
    solver.add_edge(&mut rules, a, b);
    solver.add_edge(&mut rules, b, c);
    solver.add_object(&mut rules, a, found[0]);
    solver.add_object(&mut rules, a, found[1]);
    solver.solve(&mut rules);
    assert_eq!(solver.objects(c), found);
    assert_eq!(solver.work().edges, 2);
    assert_eq!(rules.between, 1);
}

#[test]
fn a_constraint_sees_each_object_once_in_rounds() {
    let mut rules = Recorded::default();
    let mut solver = solver(None);
    let node = solver.node();
    let found = objects(&mut solver, &[1, 2]);
    solver.attach(&mut rules, node, 7);
    solver.add_object(&mut rules, node, found[0]);
    solver.solve(&mut rules);
    solver.add_object(&mut rules, node, found[1]);
    solver.solve(&mut rules);
    assert_eq!(rules.applied, [(7, vec![found[0]]), (7, vec![found[1]])]);
}

#[test]
fn a_constraint_attached_later_sees_what_the_node_holds_at_once() {
    let mut rules = Recorded::default();
    let mut solver = solver(None);
    let node = solver.node();
    let found = objects(&mut solver, &[1, 2]);
    solver.add_object(&mut rules, node, found[0]);
    solver.attach(&mut rules, node, 1);
    solver.solve(&mut rules);
    solver.attach(&mut rules, node, 2);
    solver.add_object(&mut rules, node, found[1]);
    solver.solve(&mut rules);
    assert_eq!(
        rules.applied,
        [
            (1, vec![found[0]]),
            (2, vec![found[0]]),
            (1, vec![found[1]]),
            (2, vec![found[1]]),
        ]
    );
}

#[test]
fn a_large_set_hands_each_constraint_the_objects_of_its_kinds() {
    let mut rules = Recorded::default();
    rules.kinds.push((3, SPECIAL));
    let mut solver = solver(None);
    let node = solver.node();
    let mut special = Vec::new();
    for number in 1..=40 {
        let kinds = if number % 10 == 0 { SPECIAL } else { PLAIN };
        solver.declare(ObjId(number), kinds);
        if kinds == SPECIAL {
            special.push(ObjId(number));
        }
        solver.add_object(&mut rules, node, ObjId(number));
    }
    solver.solve(&mut rules);
    solver.attach(&mut rules, node, 3);
    solver.attach(&mut rules, node, 4);
    assert_eq!(rules.applied[0], (3, special));
    assert_eq!(rules.applied[1].1.len(), 40);
}

#[test]
fn a_node_past_the_cap_holds_the_saturated_value_only() {
    let mut rules = Recorded::default();
    let mut solver = solver(Some(2));
    let [node, next] = [solver.node(), solver.node()];
    let result = solver.node();
    rules.results.push((5, result));
    let found = objects(&mut solver, &[1, 2, 3]);
    solver.add_edge(&mut rules, node, next);
    solver.attach(&mut rules, next, 5);
    for &object in &found {
        solver.add_object(&mut rules, node, object);
    }
    solver.solve(&mut rules);
    assert!(solver.is_saturated(node));
    assert!(solver.is_saturated(next));
    assert!(solver.is_saturated(result));
    assert_eq!(solver.objects(next), [SATURATED]);
    assert_eq!(solver.absorbed(), found);
    assert_eq!(rules.saturated, [5]);
    assert!(rules.applied.is_empty());
}

#[test]
fn a_cycle_of_edges_becomes_one_node() {
    let mut rules = Recorded::default();
    let mut solver = solver(None);
    let [a, b, c] = [solver.node(), solver.node(), solver.node()];
    let found = objects(&mut solver, &[1]);
    solver.add_object(&mut rules, a, found[0]);
    solver.add_edge(&mut rules, a, b);
    solver.add_edge(&mut rules, b, a);
    solver.solve(&mut rules);
    solver.add_edge(&mut rules, b, c);
    solver.solve(&mut rules);
    assert_eq!(solver.work().merged, 1);
    assert_eq!(solver.objects(c), found);
    assert_eq!(solver.objects(b), found);
}

#[test]
fn a_constant_node_gives_its_object_to_every_target() {
    let mut rules = Recorded::default();
    let mut solver = solver(None);
    let found = objects(&mut solver, &[1]);
    let constant = solver.constant(found[0]);
    let target = solver.node();
    solver.add_edge(&mut rules, constant, target);
    solver.solve(&mut rules);
    assert_eq!(solver.objects(target), found);
    assert_eq!(solver.work().edges, 0);
}

#[test]
#[should_panic(expected = "a constant node receives no other object")]
fn a_constant_node_receives_no_other_object() {
    let mut rules = Recorded::default();
    let mut solver = solver(None);
    let found = objects(&mut solver, &[1, 2]);
    let constant = solver.constant(found[0]);
    solver.add_object(&mut rules, constant, found[1]);
}

#[test]
fn applications_nested_past_the_bound_wait_for_the_solve() {
    let mut rules = Recorded::default();
    let mut solver = solver(None);
    let node = solver.node();
    let found = objects(&mut solver, &[1]);
    solver.add_object(&mut rules, node, found[0]);
    solver.solve(&mut rules);
    let chain = ATTACH_NESTING_MAX + 5;
    for constraint in 0..chain {
        rules.nest.push((constraint, node));
    }
    solver.attach(&mut rules, node, 0);
    assert_eq!(rules.applied.len(), ATTACH_NESTING_MAX as usize);
    solver.solve(&mut rules);
    assert_eq!(rules.applied.len(), chain as usize + 1);
}

#[test]
fn a_witness_wakes_its_watch_once() {
    let mut rules = Recorded::default();
    let mut solver = solver(None);
    let watch = solver.watch();
    let witness = solver.witness(watch);
    let found = objects(&mut solver, &[1, 2]);
    solver.add_object(&mut rules, witness, found[0]);
    solver.add_object(&mut rules, witness, found[1]);
    let source = solver.node();
    solver.add_edge(&mut rules, source, witness);
    assert_eq!(rules.woken, [watch]);
    assert!(!solver.is_waiting(watch));
}

#[test]
fn a_follower_made_in_a_later_round_holds_its_source_at_once() {
    let mut rules = Recorded::default();
    let mut solver = solver(None);
    let source = solver.node();
    let found = objects(&mut solver, &[1]);
    solver.add_object(&mut rules, source, found[0]);
    solver.solve(&mut rules);
    let since = solver.phase - 1;
    let follower = solver.follower(&mut rules, source, since);
    assert_eq!(solver.objects(follower), found);
    let late = solver.follower(&mut rules, source, solver.phase);
    assert!(solver.holds(late, found[0]));
    assert_eq!(solver.work().edges, 2);
    solver.solve(&mut rules);
    assert_eq!(solver.objects(late), found);
}
