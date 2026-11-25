# b8-ruling-toolz-1: the signature registry (toolz J4)

Referee: Codex (gpt-6-astra, xhigh), read-only, 2026-11-24, on writer commit d9a80bb (with 9ae1884) and audit bfa7a47. Adopted by the lead, 2026-11-24.

J4 asks whether registry dispatch admits all 193 surviving lambdas, only
the 61 selected by the narrow reading, or 187 after excluding six toolz
keys, and whether that decision changes any other call site.

**I retain all 193 lambda edges at `_signatures.py:684:13`. J4 adds and
removes no edges from the writer’s ledger.**

An admitted public input may select a handler that the package installs
in its own dispatch table: client opacity does not erase the provenance
of that package-defined handler. Each target still needs a witness on an
admitted runtime that reaches the call and binds its arguments, accounting
for overwritten entries and short-circuiting. Registry membership does
not independently admit package objects excluded by B2/B3. Admission
extends between parameters through actual forwarding or documentation
establishing a common input role; similar implementation alone is
insufficient.

Here, the public contract expressly supports standard-library builtins
([functoolz.py:1109](macro-benchmark/projects/toolz/toolz/functoolz.py:1109)).
The package constructs the registry at `_signatures.py:664–671`, retrieves
its own entry at `:694`, and invokes its stored lambda at `:684`.
The client’s callable selects the implementation; this invocation does
not call that client callable.

The six disputed package keys also qualify. `is_valid_args` and
`is_partial_args` document complementary questions about the same
callable and arguments, with identical support notes
(`functoolz.py:1088–1138`). Their paired tests reuse the same callable
cases (`test_inspect_args.py:204–205`, `354–355`), and the module sweep
passes the six keys to `is_partial_args`
([test_inspect_args.py:387](macro-benchmark/projects/toolz/toolz/tests/test_inspect_args.py:387),
especially `:416` and `:422–425`). Together, this establishes one
callable-introspection input role for the disputed admission. I therefore
accept the auditor’s withdrawal of A3.

This is admission across a documented role, **not a forwarding claim**:
`is_partial_args` and `num_required_args` do not themselves call these
lambda bodies. The admitted values reach `check_valid` through
`is_valid_args`’s own dispatch path.

| Package key | Retained target | Definition in `_signatures.py` |
|---|---|---|
| `curry` | `<lambda284>` | 581 |
| `flip` | `<lambda286>` | 585 |
| `juxt` | `<lambda287>` | 587 |
| `memoize` | `<lambda288>` | 589 |
| `Compose` | `<lambda289>` | 594 |
| `InstanceProperty` | `<lambda290>` | 596 |

These definitions are in the package’s
[toolz registry entries](macro-benchmark/projects/toolz/toolz/_signatures.py:579).
`excepts`, `<lambda285>` at `:583`, also retains its independent package
flow through `toolz.curried.excepts` and `curry._should_curry`.

For runtime reachability, admitted PyPy sends every registered key
through the registry
([functoolz.py:942](macro-benchmark/projects/toolz/toolz/functoolz.py:942)).
The CPython-only `frozendict` entries have a separate witness: CPython
3.15 provides no text signature for that native constructor
([dictobject.c:8537](macro-benchmark/selection/batch-8-proposal/deps/cpython/3.15.2/Objects/dictobject.c:8537));
`inspect.signature` raises `ValueError`
([inspect.py:2612](macro-benchmark/selection/batch-8-proposal/deps/cpython/3.15.2/Lib/inspect.py:2612)),
which reaches toolz’s registry fallback at `functoolz.py:923–924`.
Each surviving overload has arguments that bind while earlier overloads
fail, so `any(...)` at `_signatures.py:695` excludes no further lambda.

The complete disposition is:

| Site | Caller | Retained callees | Count | J4 change |
|---|---|---|---:|---:|
| `_signatures.py:684:13` | `toolz._signatures.check_valid` | `toolz._signatures.<lambdaN>`, with `N` below | 193 | 0 |

Ranges below are inclusive and specify every retained edge:

```text
2–5, 9–11, 15–20, 23–33, 38–56, 58–65, 68–80,
86–103, 107–108, 112–145, 149–151, 154–162,
215, 217–224, 227–230, 232–235, 237–247, 249–251,
256–274, 276, 278, 280–290
```

This retains **132 more inside edges than the proposed 61-edge
alternative**, including the six disputed package-key edges. No other
site gains lambda callees. The calls at `_signatures.py:708`, `723`,
`740`, `759`, and `776` pass the lambdas to introspection functions;
they inspect signatures without invoking the lambda bodies. The separate
F1 disposition at `functoolz.py:933:31` remains unchanged.

One exclusion explanation needs correction, without changing its target
set: the 97 excluded lambdas divide into **51 unavailable names and
46 overwritten entries**, rather than 44 and 53. Seven Python-2-only
dunders currently grouped as overwritten are absent:
`__delslice__`, `__div__`, `__getslice__`, `__idiv__`, `__irepeat__`,
`__repeat__`, and `__setslice__` (`_signatures.py:348–433`). The actual
overwrites comprise 45 surviving dunder aliases and `builtins.abs`.

This ruling follows B5’s
[client-control-flow clarification](macro-benchmark/README.md:2258)
and the provenance distinction adopted in
[b8-ruling-avro-1.md](macro-benchmark/selection/batch-8-proposal/rulings/b8-ruling-avro-1.md).
It applies pymysql’s requirement for
[documentation joining roles](macro-benchmark/README.md:2738).
It does not extend aiocache’s restriction on client-selected outside
method names to package-defined dispatch handlers. That restriction,
B3’s attribute-name restriction, client-callback opacity, and the
prohibition on modifying package internals remain in force.