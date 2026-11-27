# Cases

The end-to-end tests of the Rust `pycg` (docs/rust/PLAN.md, section 5,
"Cases"). A case is a program and the call graph that the Python engine,
the oracle, gives for it; `cargo test -p pycg --test cases` runs the Rust
`pycg` on every case and on every micro-benchmark case and prints the edges
that each gained or lost.

```
tests/cases/<family>/<case>/
├── main.py, ...      # the program
├── case.toml         # how it is analysed and what it is about
└── expected.json     # the oracle's edges and unresolved sites
```

| Key of `case.toml` | Meaning |
|---|---|
| `statement` | What the case shows, in one line |
| `design` | The heading of `docs/design.md` whose rule the case pins |
| `entry_points` | The entry points, relative to the case directory |
| `package` | `true`: the case directory is the package root; `false`: none is given |
| `cap` | The cap of the analysis, a number or `"none"`; absent: the default |
| `warnings` | The lines that the analysis writes to standard error, with the case directory left out of their paths |
| `present`, `absent` | The edges, `[caller, callee]`, that the case is about: in `expected.json`, or not |

`expected.json` holds `edges`, each node with its callees, as
`pycg.formats.edges` gives them, and `unresolved`, each caller with the
`line:col` of its unresolved sites and their causes. The Rust run must give
both exactly. A case may also hold `expected-document.json`, the oracle's
whole document, which the Rust run must then give as well.
`tests/test_cases.py` checks that every case still holds what the oracle
gives.

A micro-benchmark case runs against its `callgraph.json`; one listed in
`tests/known_failures.txt` must differ from it, and one whose
`requires-python` is newer than the grammar of the Rust parser is skipped,
and printed with that reason.

`pending.txt` lists the cases that the Rust `pycg` does not pass yet, each
with its cause, `<id>: <cause>`: it stops with "not ported" and the rule it
names, it fails, or its graph differs. The list is strict: a listed case
must not pass, and one that is not listed must pass. When it differs, the
harness prints the list for the build under test. A change removes the
lines of the cases that it makes pass; it adds a line only with the new case
that the line names.

`tools/parity/cases.py TEST_FILE FAMILY DESIGN` turns the tests of one
Python test file into the cases of one family. It writes every program that
a test analyses through `tests/programs.py`, with the edges that the test
asserts present or absent, and prints the assertions that it cannot read for
a conversion by hand.
