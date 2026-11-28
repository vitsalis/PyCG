use std::collections::{BTreeMap, BTreeSet};

use serde_json::{Value, json};

const PER_MODULE: usize = 65;
const METHODS: usize = 6;
const CLASSES: usize = 5;
const OUTSIDE: usize = 3000;
const IMPLICIT: [&str; 6] = [
    "iteration",
    "with",
    "decorator",
    "operator",
    "subscript",
    "attribute",
];
const UNRESOLVED: [&str; 2] = ["no value", "computed name"];
const SPLITMIX_INCREMENT: u64 = 0x9E37_79B9_7F4A_7C15;
const SPLITMIX_FIRST_MULTIPLIER: u64 = 0xBF58_476D_1CE4_E5B9;
const SPLITMIX_SECOND_MULTIPLIER: u64 = 0x94D0_49BB_1331_11EB;
const FRACTION_BITS: u32 = 53;

struct Random(u64);

impl Random {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(SPLITMIX_INCREMENT);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(SPLITMIX_FIRST_MULTIPLIER);
        z = (z ^ (z >> 27)).wrapping_mul(SPLITMIX_SECOND_MULTIPLIER);
        z ^ (z >> 31)
    }

    fn fraction(&mut self) -> f64 {
        (self.next() >> (64 - FRACTION_BITS)) as f64 / (1u64 << FRACTION_BITS) as f64
    }

    fn below(&mut self, count: usize) -> usize {
        usize::try_from(self.next() % count as u64).expect("an index fits usize")
    }

    fn choice<'a, T>(&mut self, items: &'a [T]) -> &'a T {
        &items[self.below(items.len())]
    }
}

pub fn generate(definitions: usize, sites: usize, seed: u64) -> Value {
    let mut random = Random(seed);
    let mut modules = BTreeMap::new();
    let mut defs: BTreeMap<String, Value> = BTreeMap::new();
    let mut order: Vec<String> = Vec::new();
    let mut functions: Vec<String> = Vec::new();
    let module_count = (definitions / PER_MODULE).max(1);
    for m in 0..module_count {
        let module = format!("big.m{m:03}");
        modules.insert(
            module.clone(),
            json!({"file": format!("big/m{m:03}.py"), "kind": "source", "status": "analysed"}),
        );
        defs.insert(
            module.clone(),
            json!({"kind": "module", "module": module, "lines": [1, 1000]}),
        );
        order.push(module.clone());
        let mut line = 1;
        for c in 0..CLASSES {
            let class = format!("{module}.C{c}");
            let first = line;
            for k in 0..METHODS {
                let name = format!("{class}.m{k}");
                defs.insert(
                    name.clone(),
                    json!({"kind": "function", "module": module, "lines": [line + 1, line + 4]}),
                );
                order.push(name.clone());
                functions.push(name);
                line += 5;
            }
            defs.insert(
                class.clone(),
                json!({"kind": "class", "module": module, "lines": [first, line], "mro": [class, "<builtin>.object"]}),
            );
            order.push(class);
            line += 1;
        }
        let mut f = 0;
        while defs.len() < (m + 1) * definitions / module_count {
            let name = format!("{module}.f{f}");
            defs.insert(
                name.clone(),
                json!({"kind": "function", "module": module, "lines": [line, line + 6]}),
            );
            order.push(name.clone());
            functions.push(name);
            f += 1;
            line += 7;
        }
    }
    let hub = "big.m000.hub".to_owned();
    defs.insert(
        hub.clone(),
        json!({"kind": "function", "module": "big.m000", "lines": [999, 1000]}),
    );
    order.push(hub.clone());
    functions.push(hub.clone());
    modules.insert(
        "big.broken".to_owned(),
        json!({"file": "big/broken.py", "kind": "source", "status": "failed", "cause": "SyntaxError (line 1)"}),
    );
    modules.insert(
        "big._ext".to_owned(),
        json!({"file": "big/_ext.abi3.so", "kind": "extension"}),
    );
    let outside_names: Vec<(String, &str)> = (0..OUTSIDE)
        .map(|i| match ["stub", "name", "extension"][i % 3] {
            "extension" => (format!("big._ext.e{i}"), "extension"),
            kind => (format!("lib{}.mod{}.func{i}", i % 40, i % 7), kind),
        })
        .collect();
    let callers: Vec<&String> = order
        .iter()
        .filter(|name| defs[*name]["kind"] != "class")
        .collect();
    let mut by_module: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for name in &functions {
        let module = defs[name]["module"].as_str().expect("a module name");
        by_module
            .entry(module.to_owned())
            .or_default()
            .push(name.clone());
    }
    let mut calls: BTreeMap<String, Vec<Value>> = BTreeMap::new();
    let mut used_outside: BTreeMap<String, &str> = BTreeMap::new();
    for i in 0..sites {
        let caller = callers[i % callers.len()];
        let module = defs[caller]["module"].as_str().expect("a module name");
        let mut site = json!({"line": 0, "col": 0, "end": [0, 0], "callees": []});
        let draw = random.fraction();
        if draw < 0.04 {
            site["unresolved"] = json!(random.choice(&UNRESOLVED));
        } else if draw < 0.08 {
            site["callees"] = json!([hub]);
        } else if draw < 0.32 {
            let (name, kind) = random.choice(&outside_names);
            used_outside.insert(name.clone(), kind);
            site["callees"] = json!([name]);
        } else {
            let pool = if random.fraction() < 0.6 {
                &by_module[module]
            } else {
                &functions
            };
            let count = 1 + random.below(3);
            let chosen: BTreeSet<&String> = (0..count).map(|_| random.choice(pool)).collect();
            site["callees"] = json!(chosen);
        }
        if site.get("unresolved").is_none() && random.fraction() < 0.1 {
            site["implicit"] = json!(random.choice(&IMPLICIT));
        }
        calls.entry(caller.clone()).or_default().push(site);
    }
    for (caller, caller_sites) in &mut calls {
        let first = defs[caller]["lines"][0].as_u64().expect("a first line");
        for (k, site) in caller_sites.iter_mut().enumerate() {
            let line = first + k as u64 / 4;
            let col = 4 + 8 * (k as u64 % 4);
            site["line"] = json!(line);
            site["col"] = json!(col);
            site["end"] = json!([line, col + 6]);
        }
    }
    let outside: BTreeMap<String, Value> = used_outside
        .into_iter()
        .map(|(name, kind)| (name, json!({"known": kind})))
        .collect();
    json!({
        "format": "pycg/1",
        "tool": {"name": "pycg", "version": "1.0.0", "typeshed": "synthetic"},
        "package": {"name": "big", "version": "0.0.0"},
        "modules": modules,
        "definitions": defs,
        "exports": {"big.hub": [hub]},
        "outside": outside,
        "calls": calls,
    })
}
