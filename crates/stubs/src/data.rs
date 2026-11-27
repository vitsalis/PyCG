include!(concat!(env!("OUT_DIR"), "/stub_files.rs"));

pub fn package_bytes(top: &str) -> Option<&'static [u8]> {
    [STANDARD_LIBRARY, THIRD_PARTY]
        .into_iter()
        .find_map(|table| {
            table
                .binary_search_by(|(name, _)| (*name).cmp(top))
                .ok()
                .map(|index| table[index].1)
        })
}

pub fn package_names() -> impl Iterator<Item = &'static str> {
    STANDARD_LIBRARY
        .iter()
        .chain(THIRD_PARTY)
        .map(|(name, _)| *name)
}
