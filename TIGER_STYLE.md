# TigerStyle

How PyCG applies [TigerBeetle's
TigerStyle](https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/TIGER_STYLE.md),
so that bugs surface early, in a test, and performance follows from the
design. AGENTS.md wins where the two differ. A change that departs from a
rule says so in its commit message, with why and what bounds it.

## Safety

- Assert what the code relies on: arguments, results, and the invariants
  of each node, constraint and object. A broken invariant of our own
  crashes; it never becomes a value that flows on.
- Pair assertions across a boundary: check a property where it is written
  and again where it is read back, such as a constraint the builder emits
  and the solver applies, or a document written and parsed.
- Assert the positive and the negative space: what must hold, and what
  must not happen.
- Split compound assertions, so that a failure names the one condition
  that broke.
- Three kinds of failure, never mixed:
  1. our invariant broken: an assertion, which crashes;
  2. external input that is wrong (a file that does not parse, a path that
     does not exist, stub data that does not match its schema): a
     diagnostic that names what was wrong, and the analysis goes on where
     it can;
  3. a bound reached: the documented behaviour of that bound (a saturated
     set, a computed access that goes dynamic), which the output shows.

  Never assert on external input. The analysed program is external input:
  PyCG never crashes or hangs on any program that Python accepts.

## Limits

- Every set, queue, depth and loop has a bound. Its constant is named for
  what it bounds, with its unit last, and its value comes from Python, a
  measurement or the design; `docs/design.md` lists every bound.
- Reaching a bound is visible in the output, never a silent drop.
- Walk input-shaped data (syntax trees, stub data, nested annotations)
  iteratively, or with an explicit depth bound that gives a diagnostic.

## Memory and time

- Size and share structures from what the analysis knows: one record per
  class and site, not per object, where the result is the same.
- Back every performance or memory change with before and after
  measurements, run back to back, and the proof that the output is byte
  for byte the same.

## Control flow

- Model each lifecycle as one type whose variants carry only what that
  phase has.
- Push `if`s up and `for`s down: decide once, then run straight-line loops
  over the batch.
- Handle every error. Ignoring one is a decision with its reason in the
  commit message.
- One owner per piece of state; other code goes through its owner.
- Keep functions short enough to read at once, around 70 lines; split a
  longer one when you touch it.

## Determinism

- Iterate in an order that does not depend on a hash seed, an address or
  the order of the file system wherever the order reaches the output or a
  decision: sorted sequences, or insertion order of deterministic input.
- The analysis reads no clock, no randomness and no environment variable.
  Tests that choose orders take their seed as an argument and print it on
  failure.
- An error message carries no addresses, timestamps or other values that
  differ between two runs.

## Dependencies

- Every dependency is pinned to an exact version (`=x.y.z`), and
  `Cargo.lock` is committed. A pull request that adds a dependency states
  its cost and why the standard library does not do, and needs approval
  first.
- The tool depends on these crates:

  | Crate | Version | Used by |
  |---|---|---|
  | `ruff_python_parser` | 0.0.22 | `pycg-syntax` |
  | `ruff_python_ast`, `ruff_source_file`, `ruff_text_size` | 0.0.22 | `pycg-syntax`, `pycg-analysis` |
  | `indexmap` | 2.14.2 | `pycg-syntax`, `pycg-solver`, `pycg-analysis` |
  | `num-bigint` | 0.4.8 | `pycg-syntax`, `pycg-analysis`, `pycg-document`, `pycg` |
  | `rustc-hash` | 2.1.3 | `pycg-syntax`, `pycg-stubs`, `pycg-solver`, `pycg-analysis` |
  | `serde_json` | 1.0.154 | `pycg-stubs`, and the tests of `pycg-analysis` and `pycg` |
  | `libc` | 0.2.191 | `pycg-syntax`, on Unix only |

- The Python dependencies of the harness and the tools are locked in
  `uv.lock`.

## Naming

- Whole words, no abbreviations except established ones (`id`, `url`,
  `ast`, `mro`). Units and qualifiers last, so that related names line up:
  `objects_max`, `depth_max`.
- Name a constant for the bound or the Python fact it is; a bare number in
  code is a constant waiting for a name.
