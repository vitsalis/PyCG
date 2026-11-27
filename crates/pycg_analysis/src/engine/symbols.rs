use rustc_hash::FxHashMap;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Sym(u32);

#[derive(Default)]
pub struct Symbols {
    by_text: FxHashMap<Box<str>, Sym>,
    texts: Vec<Box<str>>,
}

impl Symbols {
    pub fn intern(&mut self, text: &str) -> Sym {
        if let Some(&sym) = self.by_text.get(text) {
            return sym;
        }
        let sym = Sym(u32::try_from(self.texts.len()).expect("fewer than 2^32 symbols"));
        self.texts.push(text.into());
        self.by_text.insert(text.into(), sym);
        sym
    }

    pub fn text(&self, sym: Sym) -> &str {
        &self.texts[sym.0 as usize]
    }
}
