use std::collections::BTreeMap;

use pycg_stubs::mro::{exhaustive_order, linearizations, linearize};
use serde_json::Value;

fn cases(name: &str) -> Vec<Value> {
    let path = format!("{}/tests/vectors/{name}", env!("CARGO_MANIFEST_DIR"));
    let text = std::fs::read_to_string(&path).expect("read the vectors");
    serde_json::from_str(&text).expect("parse the vectors")
}

fn text(value: &Value) -> String {
    value.as_str().expect("a string").to_owned()
}

fn texts(value: &Value) -> Vec<String> {
    value.as_array().expect("a list").iter().map(text).collect()
}

fn slots(value: &Value) -> Vec<Vec<Option<String>>> {
    value
        .as_array()
        .expect("slots")
        .iter()
        .map(|slot| {
            slot.as_array()
                .expect("a slot")
                .iter()
                .map(|candidate| candidate.as_str().map(str::to_owned))
                .collect()
        })
        .collect()
}

fn mro_lists(value: &Value) -> BTreeMap<String, Vec<Vec<String>>> {
    value
        .as_object()
        .expect("mros")
        .iter()
        .map(|(name, mros)| {
            let mros = mros
                .as_array()
                .expect("a list of mros")
                .iter()
                .map(texts)
                .collect();
            (name.clone(), mros)
        })
        .collect()
}

fn mros_of(
    table: &BTreeMap<String, Vec<Vec<String>>>,
) -> impl Fn(Option<&String>) -> Vec<Vec<String>> {
    move |candidate| match candidate {
        None => vec![Vec::new()],
        Some(name) => table[name].clone(),
    }
}

#[test]
fn linearize_gives_what_python_gives() {
    for case in cases("linearize.json") {
        let table: BTreeMap<String, Vec<String>> = case["mros"]
            .as_object()
            .expect("mros")
            .iter()
            .map(|(name, mro)| (name.clone(), texts(mro)))
            .collect();
        let found = linearize(&text(&case["class"]), &texts(&case["bases"]), |base| {
            &table[base][..]
        });
        assert_eq!(found, texts(&case["expected"]), "{case}");
    }
}

#[test]
fn linearizations_give_what_python_gives() {
    for case in cases("linearizations.json") {
        let table = mro_lists(&case["mros"]);
        let limit = case["limit"].as_u64().expect("a limit");
        let found = linearizations(
            &text(&case["class"]),
            &slots(&case["slots"]),
            mros_of(&table),
            limit,
        );
        let expected = case["expected"]
            .as_array()
            .map(|mros| mros.iter().map(texts).collect::<Vec<_>>());
        assert_eq!(found, expected, "{case}");
    }
}

#[test]
fn exhaustive_order_gives_what_python_gives() {
    for case in cases("exhaustive_order.json") {
        let table = mro_lists(&case["mros"]);
        let found = exhaustive_order(
            &text(&case["class"]),
            &slots(&case["slots"]),
            mros_of(&table),
        );
        assert_eq!(found, texts(&case["expected"]), "{case}");
    }
}

#[test]
fn class_names_give_what_python_gives() {
    for case in cases("class_names.json") {
        let reduced = pycg_stubs::Type::from_json(&case["type"]).expect("a stub type");
        let found: Vec<String> = pycg_stubs::class_names(&reduced)
            .into_iter()
            .map(str::to_owned)
            .collect();
        assert_eq!(found, texts(&case["expected"]), "{case}");
    }
}
