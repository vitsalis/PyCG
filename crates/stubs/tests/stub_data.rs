use pycg_stubs::{
    DefinitionKind, Entry, EntryId, LiteralValue, Stubs, TYPESHED_COMMIT, Type, package_names,
};
use serde_json::json;

#[test]
fn every_embedded_package_decodes_and_holds_its_top_level_module() {
    let mut stubs = Stubs::new();
    let names: Vec<&str> = package_names().collect();
    assert!(!names.is_empty());
    for top in names {
        assert!(stubs.module(top).is_some(), "{top}");
    }
}

#[test]
fn the_typeshed_commit_is_a_full_hash() {
    assert_eq!(TYPESHED_COMMIT.len(), 40);
}

#[test]
fn a_missing_package_has_no_module() {
    let mut stubs = Stubs::new();
    assert!(stubs.module("not_a_stub_package").is_none());
    assert!(stubs.find("not_a_stub_package.name").is_empty());
}

#[test]
fn a_literal_type_keeps_its_class_and_values() {
    let reduced = Type::from_json(&json!(["*lit", "builtins.int", [-1, 1]])).expect("a literal");
    let values = [LiteralValue::Int(-1), LiteralValue::Int(1)];
    assert_eq!(reduced, Type::Literal("builtins.int".into(), values.into()));
    let reduced = Type::from_json(&json!(["*lit", "builtins.int", [u64::MAX]])).expect("a literal");
    let values = [LiteralValue::Int(u64::MAX.into())];
    assert_eq!(reduced, Type::Literal("builtins.int".into(), values.into()));
    let reduced = Type::from_json(&json!(["*lit", "builtins.str", ["rb"]])).expect("a literal");
    let values = [LiteralValue::Str("rb".into())];
    assert_eq!(reduced, Type::Literal("builtins.str".into(), values.into()));
    for malformed in [
        json!(["*lit", "builtins.int"]),
        json!(["*lit", "builtins.int", 1]),
        json!(["*lit", "builtins.float", [1.5]]),
        json!(["*lit", "builtins.bool", [true]]),
    ] {
        assert!(Type::from_json(&malformed).is_err(), "{malformed}");
    }
}

#[test]
fn a_builtin_class_is_found_with_its_mro() {
    let mut stubs = Stubs::new();
    let found = stubs.find("builtins.bool");
    assert_eq!(found.len(), 1);
    assert_eq!(found[0].kind, DefinitionKind::Class);
    let mro = stubs.mro("builtins.bool");
    let mro: Vec<&str> = mro.iter().map(|name| &**name).collect();
    assert_eq!(mro, ["builtins.bool", "builtins.int", "builtins.object"]);
}

fn class_paths(reduced: &Type, paths: &mut Vec<String>) {
    let mut pending = vec![reduced];
    while let Some(current) = pending.pop() {
        match current {
            Type::Class(path) | Type::Literal(path, _) => paths.push(path.to_string()),
            Type::Generic(path, arguments) => {
                paths.push(path.to_string());
                pending.extend(arguments.iter());
            }
            Type::Union(arms) => pending.extend(arms.iter()),
            Type::TypeOf(argument) => pending.push(argument),
            Type::Callable { result, parameters } => {
                pending.push(result);
                pending.extend(parameters.iter().flatten());
            }
            Type::Variable { bound, .. } => pending.extend(bound.as_deref()),
            Type::Unknown | Type::None | Type::SelfType | Type::Ellipsis => {}
        }
    }
}

#[test]
fn every_class_that_the_stub_data_names_is_a_class_or_nothing() {
    let mut stubs = Stubs::new();
    let mut paths = Vec::new();
    for top in package_names().collect::<Vec<_>>() {
        for (_, module) in stubs.package_modules(top) {
            let mut pending: Vec<EntryId> =
                stubs.module_data(module).names.values().copied().collect();
            while let Some(id) = pending.pop() {
                match stubs.entry(id) {
                    Entry::Class(class) => {
                        for base in &class.bases {
                            class_paths(base, &mut paths);
                        }
                        if let Some(metaclass) = &class.metaclass {
                            class_paths(metaclass, &mut paths);
                        }
                        pending.extend(class.members.values().copied());
                    }
                    Entry::Function(function) => {
                        for signature in &function.signatures {
                            class_paths(&signature.result, &mut paths);
                            for parameter in &signature.parameters {
                                class_paths(&parameter.annotation, &mut paths);
                            }
                        }
                    }
                    Entry::Property(property) => class_paths(&property.annotation, &mut paths),
                    Entry::Variable(variable) => class_paths(&variable.annotation, &mut paths),
                    Entry::Reference(_) => {}
                }
            }
        }
    }
    paths.sort();
    paths.dedup();
    assert!(paths.len() > 8000, "{}", paths.len());
    for path in paths {
        if let Some(found) = stubs.definition(&path) {
            assert_eq!(found.kind, DefinitionKind::Class, "{path}");
        }
    }
}
