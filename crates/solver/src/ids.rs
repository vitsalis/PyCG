use std::num::NonZeroU32;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct ObjId(pub u32);

impl ObjId {
    pub fn index(self) -> usize {
        self.0 as usize
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct SetId(u32);

impl SetId {
    pub const EMPTY: SetId = SetId(0);

    pub fn new(index: usize) -> SetId {
        SetId(u32::try_from(index).expect("sets fit u32"))
    }

    pub fn index(self) -> usize {
        self.0 as usize
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct NodeId(NonZeroU32);

impl NodeId {
    pub fn new(index: usize) -> NodeId {
        let index = u32::try_from(index).expect("nodes fit u32");
        NodeId(NonZeroU32::new(index + 1).expect("fewer than u32::MAX nodes"))
    }

    pub fn index(self) -> usize {
        (self.0.get() - 1) as usize
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct WatchId(u32);

impl WatchId {
    pub fn new(index: usize) -> WatchId {
        WatchId(u32::try_from(index).expect("watches fit u32"))
    }

    pub fn index(self) -> usize {
        self.0 as usize
    }
}
