use pycg_solver::ObjId;
use rustc_hash::FxHashMap;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Chain(pub(crate) u32);

impl Chain {
    pub const EMPTY: Chain = Chain(0);
}

#[derive(Default)]
pub struct Chains {
    pub(crate) links: Vec<(Chain, ObjId)>,
    pub(crate) extensions: FxHashMap<(Chain, ObjId), Chain>,
}

impl Chains {
    pub fn push(&mut self, chain: Chain, object: ObjId) -> Chain {
        assert!(chain.0 as usize <= self.links.len(), "a chain that exists");
        if let Some(&extended) = self.extensions.get(&(chain, object)) {
            return extended;
        }
        self.links.push((chain, object));
        let extended = Chain(u32::try_from(self.links.len()).expect("fewer than 2^32 links"));
        self.extensions.insert((chain, object), extended);
        extended
    }

    pub fn objects(&self, chain: Chain) -> Vec<ObjId> {
        let mut objects = Vec::new();
        let mut at = chain;
        while at != Chain::EMPTY {
            let (parent, object) = self.links[at.0 as usize - 1];
            assert!(parent.0 < at.0, "a chain extends an older chain");
            objects.push(object);
            at = parent;
        }
        objects.reverse();
        objects
    }
}
