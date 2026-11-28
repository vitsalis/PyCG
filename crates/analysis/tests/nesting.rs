use pycg_analysis::builder::bindings::{NESTING_MAX, nesting};
use pycg_syntax::parse::with_parsed;

#[rustfmt::skip]
mod vectors {
    include!("vectors/nesting.rs");
}

#[test]
fn the_nesting_bound_is_the_oracles() {
    assert_eq!(NESTING_MAX, vectors::NESTING_MAX);
}

#[test]
fn a_statement_nests_as_the_oracle_counts_it() {
    for (source, expected) in vectors::NESTING {
        let found: Vec<usize> = with_parsed(source, |parsed| {
            let parsed = parsed.expect("a vector parses");
            parsed.syntax().body.iter().map(nesting).collect()
        });
        assert_eq!(found, *expected, "{source}");
    }
}
