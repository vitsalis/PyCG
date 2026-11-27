use std::str::FromStr;

use num_bigint::BigInt;
use pycg_analysis::model::{
    Case, ConstValue, Pattern, Signature, constant_name, site_name, steps_past_root,
};

#[rustfmt::skip]
mod vectors {
    include!("vectors/model.rs");
}

fn texts(names: &[&str]) -> Vec<Box<str>> {
    names.iter().map(|name| Box::from(*name)).collect()
}

#[test]
fn the_name_of_a_str_constant_is_its_ascii() {
    for (code_points, expected) in vectors::STR_NAMES {
        let found = constant_name(&ConstValue::Str(code_points));
        assert_eq!(found, *expected, "{code_points:?}");
    }
}

#[test]
fn the_name_of_a_bytes_constant_is_its_ascii() {
    for (bytes, expected) in vectors::BYTES_NAMES {
        let found = constant_name(&ConstValue::Bytes(bytes));
        assert_eq!(found, *expected, "{bytes:?}");
    }
}

#[test]
fn an_int_constant_is_named_in_decimal_below_10_to_the_640_and_in_hexadecimal_from_it() {
    for (decimal, expected) in vectors::INT_NAMES {
        let value = BigInt::from_str(decimal).expect("a decimal integer");
        assert_eq!(
            constant_name(&ConstValue::Int(&value)),
            *expected,
            "{decimal}"
        );
    }
}

#[test]
fn a_dotted_module_name_is_identifiers_as_python_tests_them() {
    let mut alphabetic_wrong = 0;
    for (name, expected) in vectors::DOTTED_IDENTIFIERS {
        let found = pycg_analysis::builder::statements::is_dotted_identifier(name);
        assert_eq!(found, *expected, "{name:?}");
        let alphabetic = name.split('.').all(|part| {
            let mut characters = part.chars();
            characters
                .next()
                .is_some_and(|first| first == '_' || first.is_alphabetic())
                && characters.all(|character| character == '_' || character.is_alphanumeric())
        });
        if alphabetic != *expected {
            alphabetic_wrong += 1;
        }
    }
    assert!(alphabetic_wrong > 0);
}

#[test]
fn a_site_is_named_by_its_part_before_the_separator() {
    for (site, expected) in vectors::SITE_NAMES {
        assert_eq!(site_name(site), *expected);
    }
}

#[test]
fn the_steps_past_the_root_are_the_last_parts_of_the_name() {
    for (name, steps, expected) in vectors::STEPS_PAST_ROOT {
        assert_eq!(steps_past_root(name, *steps), *expected, "{name} {steps}");
    }
}

#[test]
fn a_signature_binds_names_and_accepts_keywords_as_python_does() {
    let candidates = ["a", "b", "c", "d", "e", "args", "kwargs", "z"];
    for (positional, only, keyword_only, vararg, kwarg, names, accepted, queries) in
        vectors::SIGNATURES
    {
        let signature = Signature::new(
            texts(positional),
            *only,
            texts(keyword_only),
            vararg.map(Box::from),
            kwarg.map(Box::from),
        );
        assert_eq!(signature.names(), *names);
        let found: Vec<&str> = candidates
            .into_iter()
            .filter(|name| signature.accepts_keyword(name))
            .collect();
        assert_eq!(found, *accepted);
        for (given, keywords, optional, expected) in *queries {
            let bound = signature.binds(*given, keywords, optional);
            assert_eq!(
                bound, *expected,
                "{signature:?} {given} {keywords:?} {optional:?}"
            );
        }
    }
}

fn case_of(name: &str) -> Case {
    match name {
        "lower" => Case::Lower,
        "upper" => Case::Upper,
        other => panic!("case {other}"),
    }
}

#[test]
fn a_pattern_is_named_and_matches_as_python_does() {
    for (prefix, suffix, case, name, matches) in vectors::PATTERNS {
        let pattern = Pattern {
            prefix: Box::from(*prefix),
            suffix: Box::from(*suffix),
            case: case.map(case_of),
        };
        assert_eq!(pattern.name(), *name);
        for (candidate, expected) in *matches {
            let found = pattern.matches(candidate);
            assert_eq!(found, *expected, "{pattern:?} {candidate}");
        }
    }
}
