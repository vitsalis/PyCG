#![allow(clippy::type_complexity)]

use pycg_analysis::models::{self, DefaultConstant, Model};

#[rustfmt::skip]
mod vectors {
    include!("vectors/models.rs");
}

type ModelTuple = (&'static str, &'static str, Vec<&'static str>);

fn model_tuple(model: &Model) -> ModelTuple {
    (model.signature, model.rule.name(), model.arguments.to_vec())
}

fn python_model(model: &(&'static str, &'static str, &'static [&'static str])) -> ModelTuple {
    (model.0, model.1, model.2.to_vec())
}

fn keyed_models(table: &[(&'static str, Model)]) -> Vec<(&'static str, ModelTuple)> {
    table
        .iter()
        .map(|(key, model)| (*key, model_tuple(model)))
        .collect()
}

fn python_keyed_models(
    table: &[(
        &'static str,
        (&'static str, &'static str, &'static [&'static str]),
    )],
) -> Vec<(&'static str, ModelTuple)> {
    table
        .iter()
        .map(|(key, model)| (*key, python_model(model)))
        .collect()
}

#[test]
fn the_function_models_are_the_python_tables() {
    assert_eq!(
        keyed_models(models::FUNCTIONS),
        python_keyed_models(vectors::FUNCTIONS)
    );
    assert_eq!(
        keyed_models(models::SPECIAL_METHOD_CALLS),
        python_keyed_models(vectors::SPECIAL_METHOD_CALLS)
    );
    assert_eq!(
        keyed_models(models::REFLECTION_CALLS),
        python_keyed_models(vectors::REFLECTION_CALLS)
    );
}

#[test]
fn the_method_models_are_the_python_table_with_the_lazy_iterators() {
    let mut found: Vec<(&str, &str, ModelTuple)> = models::METHODS
        .iter()
        .map(|((kind, method), model)| (*kind, *method, model_tuple(model)))
        .collect();
    found.sort();
    let expected: Vec<(&str, &str, ModelTuple)> = vectors::METHODS
        .iter()
        .map(|(kind, method, model)| (*kind, *method, python_model(model)))
        .collect();
    assert_eq!(found, expected);
}

#[test]
fn the_container_classes_are_the_python_table() {
    let found: Vec<(&str, &str, ModelTuple)> = models::CONTAINER_CLASSES
        .iter()
        .map(|(key, (kind, model))| (*key, *kind, model_tuple(model)))
        .collect();
    let expected: Vec<(&str, &str, ModelTuple)> = vectors::CONTAINER_CLASSES
        .iter()
        .map(|(key, kind, model)| (*key, *kind, python_model(model)))
        .collect();
    assert_eq!(found, expected);
}

#[test]
fn the_library_operations_are_the_python_table() {
    let found: Vec<(&str, &str, &[&str], &str, Option<&str>)> = models::LIBRARY_ITERATION
        .iter()
        .map(|(key, operation)| {
            (
                *key,
                operation.mode.name(),
                operation.roles,
                operation.shape.name(),
                operation.kind,
            )
        })
        .collect();
    assert_eq!(found, vectors::LIBRARY_ITERATION);
    let lazy: Vec<bool> = models::LIBRARY_ITERATION
        .iter()
        .map(|(_, operation)| operation.mode.is_lazy())
        .collect();
    let expected: Vec<bool> = vectors::LIBRARY_ITERATION
        .iter()
        .map(|(_, mode, _, _, _)| {
            [
                "lazy",
                "tee",
                "starmap",
                "groupby",
                "lazy all",
                "lazy outer",
                "merge",
            ]
            .contains(mode)
        })
        .collect();
    assert_eq!(lazy, expected);
}

#[test]
fn the_name_tables_are_the_python_tables() {
    let maps: [(&[(&str, &str)], &[(&str, &str)]); 12] = [
        (models::KEY_WRAPPERS, vectors::KEY_WRAPPERS),
        (models::LIBRARY_VALUES, vectors::LIBRARY_VALUES),
        (models::REPEATS, vectors::REPEATS),
        (models::DEFINES_MARKERS, vectors::DEFINES_MARKERS),
        (models::CALLS_BACK, vectors::CALLS_BACK),
        (models::VARIABLE_TYPES, vectors::VARIABLE_TYPES),
        (models::PROPERTY_ACCESSORS, vectors::PROPERTY_ACCESSORS),
        (models::CLOSURES, vectors::CLOSURES),
        (models::VARIABLE_FUNCTIONS, vectors::VARIABLE_FUNCTIONS),
        (models::CONCRETE_CLASSES, vectors::CONCRETE_CLASSES),
        (models::STUB_RESULTS, vectors::STUB_RESULTS),
        (models::CACHED_FUNCTIONS, vectors::CACHED_FUNCTIONS),
    ];
    for (found, expected) in maps {
        assert_eq!(found, expected);
    }
    let sets: [(&[&str], &[&str]); 5] = [
        (models::KEYED_OPERATIONS, vectors::KEYED_OPERATIONS),
        (models::READS_TUPLES, vectors::READS_TUPLES),
        (models::NOT_CONSUMING, vectors::NOT_CONSUMING),
        (models::OPENERS, vectors::OPENERS),
        (models::DECORATING_CLOSURES, vectors::DECORATING_CLOSURES),
    ];
    for (found, expected) in sets {
        let mut found = found.to_vec();
        found.sort();
        assert_eq!(found, expected);
    }
    assert_eq!(models::KEYED_SEQUENCES, vectors::KEYED_SEQUENCES);
    assert_eq!(
        models::WRAPPED_ATTRIBUTES_BY_TYPE,
        vectors::WRAPPED_ATTRIBUTES_BY_TYPE
    );
    assert_eq!(models::GROUPER, vectors::GROUPER);
    assert_eq!(models::BUFFER_EXPORTER, vectors::BUFFER_EXPORTER);
    assert_eq!(models::TUPLE_STORAGE, vectors::TUPLE_STORAGE);
    assert_eq!(models::ITERABLE, vectors::ITERABLE);
    assert_eq!(models::REVERSIBLE, vectors::REVERSIBLE);
    assert_eq!(models::DYNAMIC_NAMES_MAX, vectors::DYNAMIC_NAMES_MAX);
    assert_eq!(
        models::RETURNED_DECORATOR_SIGNATURE,
        vectors::RETURNED_DECORATOR_SIGNATURE
    );
}

#[test]
fn the_length_hints_and_hashed_arguments_are_the_python_tables() {
    let found: Vec<(&str, &str, models::LengthPlan, &str)> = models::LENGTH_HINTS
        .iter()
        .map(|(key, (parameter, plan, source))| (*key, *parameter, *plan, source.name()))
        .collect();
    assert_eq!(found, vectors::LENGTH_HINTS);
    let found: Vec<(&str, &str, bool)> = models::HASHED_ARGUMENTS
        .iter()
        .map(|(key, (parameter, hashed))| (*key, *parameter, *hashed))
        .collect();
    assert_eq!(found, vectors::HASHED_ARGUMENTS);
    let found: Vec<(&str, &str, Option<&str>, Option<&str>)> = models::RETURNS_ARGUMENT
        .iter()
        .map(|(key, entry)| (*key, entry.signature, entry.argument, entry.wrapper))
        .collect();
    assert_eq!(found, vectors::RETURNS_ARGUMENT);
}

#[test]
fn an_opened_file_has_the_class_that_python_gives_for_its_mode() {
    for (mode, unbuffered, expected) in vectors::OPENED_CLASSES {
        assert_eq!(
            models::opened_class(mode, *unbuffered),
            *expected,
            "{mode:?} {unbuffered}"
        );
    }
}

#[test]
fn a_method_model_is_found_through_the_builtin_kind_as_in_python() {
    for (kind, expected) in vectors::BUILTIN_KINDS {
        assert_eq!(models::builtin_kind(kind), *expected);
    }
    for (kind, method, expected) in vectors::METHOD_MODELS {
        let found = models::method_model(kind, method).map(model_tuple);
        assert_eq!(
            found,
            expected.as_ref().map(python_model),
            "{kind} {method}"
        );
    }
}

fn names(names: &[Box<str>]) -> Vec<&str> {
    names.iter().map(|name| &**name).collect()
}

#[test]
fn a_model_signature_parses_as_python_parses_it() {
    for (text, positional, only, keyword_only, vararg, kwarg, constants) in vectors::SIGNATURES {
        let parsed = models::parse_signature(text);
        assert_eq!(names(&parsed.signature.positional), *positional, "{text}");
        assert_eq!(parsed.signature.positional_only_count, *only, "{text}");
        assert_eq!(
            names(&parsed.signature.keyword_only),
            *keyword_only,
            "{text}"
        );
        assert_eq!(parsed.signature.vararg.as_deref(), *vararg, "{text}");
        assert_eq!(parsed.signature.kwarg.as_deref(), *kwarg, "{text}");
        assert_eq!(parsed.constants.len(), constants.len(), "{text}");
        for ((name, found), (expected_name, expected)) in parsed.constants.iter().zip(*constants) {
            assert_eq!(&**name, *expected_name, "{text}");
            let same = match (found, expected) {
                (DefaultConstant::Str(found), vectors::Constant::Str(expected)) => {
                    **found == **expected
                }
                (DefaultConstant::Int(found), vectors::Constant::Int(expected)) => {
                    found == expected
                }
                _ => false,
            };
            assert!(same, "{text} {name}");
        }
    }
}
