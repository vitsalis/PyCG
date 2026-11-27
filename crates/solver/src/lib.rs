pub mod ids;
pub mod sets;
pub mod solver;

pub use ids::{NodeId, ObjId, SetId, WatchId};
pub use sets::{KIND_SELECTION_OBJECTS_MIN, KindMask, SWEEP_NEW_OBJECTS_MIN, Sets};
pub use solver::{ATTACH_NESTING_MAX, OBJECTS_PER_NODE_DEFAULT, Rules, Solver, Work};
