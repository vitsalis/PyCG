use pycg_solver::{ObjId, SetId, Sets};

const FUNCTION: u64 = 1;
const INSTANCE: u64 = 2;

fn set_of(sets: &mut Sets, objects: &[u32]) -> SetId {
    let numbers = objects
        .iter()
        .map(|&object| sets.number(ObjId(object), FUNCTION))
        .collect();
    sets.intern_unsorted(numbers)
}

#[test]
fn objects_are_numbered_in_order_of_first_arrival() {
    let mut sets = Sets::new();
    let first = sets.number(ObjId(7), FUNCTION);
    let second = sets.number(ObjId(3), INSTANCE);
    assert_eq!((first, second), (0, 1));
    assert_eq!(sets.number(ObjId(7), INSTANCE), 0);
    assert_eq!(sets.kinds(0), FUNCTION);
    let set = set_of(&mut sets, &[3, 7]);
    assert_eq!(sets.ordered(set).collect::<Vec<_>>(), [ObjId(7), ObjId(3)]);
}

#[test]
fn equal_content_is_one_set() {
    let mut sets = Sets::new();
    let a = set_of(&mut sets, &[1, 2]);
    let b = set_of(&mut sets, &[2, 1]);
    assert_eq!(a, b);
    assert_eq!(sets.intern(&[]), SetId::EMPTY);
    assert_eq!(sets.new_sets_object_count, 2);
}

#[test]
fn a_singleton_counts_one_copy_each_time() {
    let mut sets = Sets::new();
    let first = sets.singleton(ObjId(5), FUNCTION);
    let again = sets.singleton(ObjId(5), FUNCTION);
    assert_eq!(first, again);
    assert_eq!(sets.copied, 2);
    assert_eq!(sets.numbers(first), [0]);
}

#[test]
fn union_and_difference_are_remembered_and_count_their_copies_once() {
    let mut sets = Sets::new();
    let a = set_of(&mut sets, &[1, 2]);
    let b = set_of(&mut sets, &[2, 3]);
    let union = sets.union(a, b);
    assert_eq!(sets.numbers(union), [0, 1, 2]);
    assert_eq!(sets.copied, 3);
    assert_eq!(sets.union(a, b), union);
    assert_eq!(sets.copied, 3);
    assert_eq!(sets.union(SetId::EMPTY, b), b);
    assert_eq!(sets.union(a, a), a);
    let difference = sets.difference(union, a);
    assert_eq!(sets.numbers(difference), [2]);
    assert_eq!(sets.copied, 4);
    assert_eq!(sets.difference(a, SetId::EMPTY), a);
    let none = sets.difference(a, union);
    assert_eq!(none, SetId::EMPTY);
}

#[test]
fn a_sweep_keeps_the_live_sets_and_forgets_the_others() {
    let mut sets = Sets::new();
    let live = set_of(&mut sets, &[1, 2]);
    let dead = set_of(&mut sets, &[3]);
    let union = sets.union(live, dead);
    sets.sweep([live]);
    assert_eq!(set_of(&mut sets, &[1, 2]), live);
    let again = set_of(&mut sets, &[3]);
    assert_ne!(again, dead);
    assert_ne!(sets.union(live, again), union);
    assert_eq!(sets.new_sets_object_count, 4);
    assert_eq!(
        sets.sweep_at_new_objects,
        pycg_solver::SWEEP_NEW_OBJECTS_MIN
    );
    assert!(!sets.sweep_due());
}

#[test]
fn a_singleton_of_a_swept_set_is_made_again() {
    let mut sets = Sets::new();
    let first = sets.singleton(ObjId(9), FUNCTION);
    sets.sweep([]);
    let again = sets.singleton(ObjId(9), FUNCTION);
    assert_ne!(first, again);
    assert_eq!(sets.numbers(again), [0]);
}

#[test]
fn the_objects_of_given_kinds_keep_their_order() {
    let mut sets = Sets::new();
    sets.number(ObjId(1), FUNCTION);
    sets.number(ObjId(2), INSTANCE);
    sets.number(ObjId(3), FUNCTION | INSTANCE);
    let all = sets.intern(&[0, 1, 2]);
    assert_eq!(sets.of_kinds(all, INSTANCE), [ObjId(2), ObjId(3)]);
    assert_eq!(sets.of_kinds(all, FUNCTION), [ObjId(1), ObjId(3)]);
}
