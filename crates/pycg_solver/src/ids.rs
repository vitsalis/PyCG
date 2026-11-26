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
