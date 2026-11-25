import argparse
import json
import random

DESCRIPTION = """Write a large synthetic call graph document for the viewer's size test.

    python tests/data/view/generate.py OUT.json [--definitions N] [--sites N]

The document has the shape of `docs/format.md` and no meaning: modules of
classes and functions that call each other, outside names of the three
kinds, implicit and unresolved sites, one failed and one extension module,
and one hub function that a few percent of the sites call. The same
arguments give the same bytes.
"""

PER_MODULE = 65
METHODS = 6
CLASSES = 5
OUTSIDE = 3000
IMPLICIT = ["iteration", "with", "decorator", "operator", "subscript", "attribute"]
UNRESOLVED = ["no value", "computed name"]


def generate(definitions=20000, sites=100000, seed=1):
    rng = random.Random(seed)
    modules = {}
    defs = {}
    functions = []
    module_count = max(1, definitions // PER_MODULE)
    for m in range(module_count):
        module = f"big.m{m:03}"
        modules[module] = {
            "file": f"big/m{m:03}.py",
            "kind": "source",
            "status": "analysed",
        }
        defs[module] = {"kind": "module", "module": module, "lines": [1, 1000]}
        line = 1
        for c in range(CLASSES):
            cls = f"{module}.C{c}"
            first = line
            methods = []
            for k in range(METHODS):
                name = f"{cls}.m{k}"
                defs[name] = {
                    "kind": "function",
                    "module": module,
                    "lines": [line + 1, line + 4],
                }
                methods.append(name)
                line += 5
            defs[cls] = {
                "kind": "class",
                "module": module,
                "lines": [first, line],
                "mro": [cls, "<builtin>.object"],
            }
            functions += methods
            line += 1
        f = 0
        while len(defs) < (m + 1) * definitions // module_count:
            name = f"{module}.f{f}"
            defs[name] = {
                "kind": "function",
                "module": module,
                "lines": [line, line + 6],
            }
            functions.append(name)
            f += 1
            line += 7
    hub = "big.m000.hub"
    defs[hub] = {"kind": "function", "module": "big.m000", "lines": [999, 1000]}
    functions.append(hub)
    modules["big.broken"] = {
        "file": "big/broken.py",
        "kind": "source",
        "status": "failed",
        "cause": "SyntaxError (line 1)",
    }
    modules["big._ext"] = {"file": "big/_ext.abi3.so", "kind": "extension"}

    outside_names = []
    for i in range(OUTSIDE):
        kind = ("stub", "name", "extension")[i % 3]
        if kind == "extension":
            name = f"big._ext.e{i}"
        else:
            name = f"lib{i % 40}.mod{i % 7}.func{i}"
        outside_names.append((name, kind))

    callers = [name for name in defs if defs[name]["kind"] != "class"]
    by_module = {}
    for name in functions:
        by_module.setdefault(defs[name]["module"], []).append(name)

    calls = {}
    used_outside = {}
    for i in range(sites):
        caller = callers[i % len(callers)]
        module = defs[caller]["module"]
        site = {"line": 0, "col": 0, "end": [0, 0], "callees": []}
        draw = rng.random()
        if draw < 0.04:
            site["unresolved"] = rng.choice(UNRESOLVED)
        elif draw < 0.08:
            site["callees"] = [hub]
        elif draw < 0.32:
            name, kind = rng.choice(outside_names)
            used_outside[name] = kind
            site["callees"] = [name]
        else:
            pool = by_module[module] if rng.random() < 0.6 else functions
            site["callees"] = sorted(
                {rng.choice(pool) for _ in range(rng.randint(1, 3))}
            )
        if "unresolved" not in site and rng.random() < 0.1:
            site["implicit"] = rng.choice(IMPLICIT)
        calls.setdefault(caller, []).append(site)
    for caller, caller_sites in calls.items():
        first = defs[caller]["lines"][0]
        for k, site in enumerate(caller_sites):
            site["line"] = first + k // 4
            site["col"] = 4 + 8 * (k % 4)
            site["end"] = [site["line"], site["col"] + 6]

    return {
        "format": "pycg/1",
        "tool": {"name": "pycg", "version": "1.0.0", "typeshed": "synthetic"},
        "package": {"name": "big", "version": "0.0.0"},
        "modules": modules,
        "definitions": defs,
        "exports": {"big.hub": [hub]},
        "outside": {name: {"known": kind} for name, kind in used_outside.items()},
        "calls": calls,
    }


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION.splitlines()[0])
    parser.add_argument("output")
    parser.add_argument("--definitions", type=int, default=20000)
    parser.add_argument("--sites", type=int, default=100000)
    args = parser.parse_args()
    document = generate(args.definitions, args.sites)
    with open(args.output, "w", encoding="utf-8") as file:
        json.dump(document, file, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    main()
