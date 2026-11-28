# Audit of the application of the rulings of 2026-11-28

PR #358, branch `vitsalis/gt-corrections-2026-11-28` (f77ba960, one
commit), against `origin/main` (merge base 68bc2784). The record is
`selection/corrections-2026-11-28/rulings/q1.md` ... `q14.md` of the PR.
I read the PR head and `origin/main` in detached worktrees. Sources:

- the packages from the inputs checkout (`projects/<name>/`);
- CPython 3.7.17 to 3.15.2 and PyPy from the batch-8 dependency sources
  (`batch-8-proposal/deps/`).

What I ran, all in containers with `--network none`:

- the micro validator, in `pycg-eval-runner` (3.14.10) and
  `pycg-ci-uv-315` (3.15.2);
- identity checks and `common/lookup.py` on every `same_function.json`
  group, in `python:3.12-slim`, `python:3.13-slim`, `python:3.14.10` and
  `pycg-ci-uv-315`. That image is built `FROM` the official 3.15.2 image
  (`PYTHON_VERSION=3.15.2`, `PYTHON_SHA256` in its environment);
- for item 2, three helpers who worked blind on Q2/Q4/Q5, Q7/Q8/Q11 and
  Q12/Q13. They read only sections 1 and 3 of each ruling, derived the
  callees from the sources, and then opened the ledgers. I re-checked
  their two disagreements myself (N2a, N8a).

I did Q9, Q10 and the two named audit items myself. Nothing in the
packages ran. No PyCG output was read or run: not results, not
`known_failures.txt` as evidence, not the PR body's score table.

## 1. Application (`git diff origin/main...HEAD`)

The diff changes:

- `benchmark-rules.md`: the `dependencies` row, the new section, and the
  micro "Methods" sentence;
- `same_function.json`: six groups;
- two micro `callgraph.json`;
- two reason strings, in `tests/triage.py` and `tests/known_failures.txt`;
- and adds the 14 ruling files.

No ledger, graph, added or rejected file, trace, `projects.toml` or test
environment changes.

| Id | Check | Verdict |
|---|---|---|
| A1 | Q14 renames complete | agree |
| A2 | Q14 CPython facts | agree |
| A3 | Q14 validator | agree |
| A4 | Q14 reason strings | agree |
| A5 | Q6 groups | agree |
| A6 | Q3 wording | agree; R1 optional |
| A7 | New rules section | agree |

### A1. The renames are complete

`async/call_soon_callback` renames one edge and its node. Its rename is
`main.start -> asyncio.EventLoop.call_soon` =>
`asyncio.SelectorEventLoop.call_soon`.

`async/explicit_event_loop` renames two edges and their nodes:

- `main -> asyncio.EventLoop.run_until_complete` =>
  `asyncio.SelectorEventLoop.run_until_complete`;
- `main -> asyncio.EventLoop.close` => `asyncio.SelectorEventLoop.close`.

That is exactly q14.md's effect table.

At the PR head, a grep for a bare `EventLoop` identifier, preceded by no
letter or `_`, finds it in only three kinds of place:

- the new rules text itself;
- the traces (`dynamic/aiocache.json`, `structlog.json`, as aliases);
- `aiocache.audit.md:31`, the record of an earlier audit. "An
  `<name>.audit.md` records the audit against the ledger as it was then",
  so it correctly stays.

The search covered:

- every micro `callgraph.json` and README;
- every macro ledger, `.json`, `.added.json`, `.rejected.json` and `.md`;
- `benchmark-rules.md`;
- `tests/`, `crates/*/tests/`, `tools/`.

The macro ground truths name only Selector and Proactor (`grep -c`):

| Package | Edges |
|---|---|
| aiocache | 4 |
| bottle | 2 |
| structlog | 10 |

That is 16, as stated. No other micro case names an asyncio loop method;
the asyncio callees of the micro graphs are `run`, `sleep`, `gather`,
`create_task`, `get_running_loop`, `new_event_loop`, `TaskGroup` and
`TaskGroup.create_task`.

### A2. CPython: `EventLoop` is the Selector loop on Unix, the Proactor loop on Windows

From `Lib/asyncio/`:

| Version | `unix_events.py` | `windows_events.py` |
|---|---|---|
| 3.12.16 | `SelectorEventLoop = _UnixSelectorEventLoop` :1499; no `EventLoop` | `SelectorEventLoop = _WindowsSelectorEventLoop` :890; `DefaultEventLoopPolicy = WindowsProactorEventLoopPolicy` :901; no `EventLoop` |
| 3.13.18 | :1548; `EventLoop = SelectorEventLoop` :1550; in `__all__` :35 | `EventLoop = ProactorEventLoop` :906; in `__all__` :33 |
| 3.14.10 | :1029; `EventLoop = SelectorEventLoop` :1031 | `EventLoop = ProactorEventLoop` :906 |
| 3.15.2 | :1029; `EventLoop = SelectorEventLoop` :1031 | `EventLoop = ProactorEventLoop` :899 |

`asyncio/__init__.py` star-imports the platform module (3.13.18 :42-47).
The Unix `_loop_factory` is `_UnixSelectorEventLoop`, 3.14.10 :1026. The
Windows proactor policy's is `ProactorEventLoop`, :902.

`asyncio.Runner` makes the loop with `events.new_event_loop()`, 3.14.10
`runners.py:146-147`. Every citation of q14.md, of the rules text and of
the PR body is right.

The ruling's statement holds: on 3.13+ `EventLoop` is a public name bound
to another public name, and the class it names depends on the platform.
`SelectorEventLoop` and `ProactorEventLoop` exist on every admitted
version.

### A3. The validator passes both cases on 3.14.10 and 3.15.2

I ran
`python3 -I evaluation/micro-benchmark/validate.py` on the two cases, in
`pycg-eval-runner` (3.14.10) and in `pycg-ci-uv-315` (3.15.2). It gives
`async/call_soon_callback: ok` and `async/explicit_event_loop: ok`,
exit 0, on both.

### A4. The two reason strings

The reason strings in `tests/known_failures.txt` and `tests/triage.py`
are identical after the string concatenation. They only rename the class
that the reason names.

This is a consequence of A1, not a ground-truth decision. The ruling does
not name these files, but the reasons quote the renamed callee. I did not
run `triage.py`, since it needs PyCG's output.

### A5. The six groups name one object on every supported CPython

`array.ArrayType is array.array` holds, and so does `is` for each of
`buffer_info`, `byteswap`, `frombytes`, `tobytes` and `tolist`. The module
binds the type under exactly `['ArrayType', 'array']`.

Run on:

- 3.12.16 (`python:3.12-slim`);
- 3.13.18 (`python:3.13-slim`);
- 3.14.10 (`python:3.14.10`);
- 3.15.2 (`pycg-ci-uv-315`).

`lookup.resolve` gives one object per group for all 36 groups of the file
on the same four interpreters.

The `arraymodule.c` citations are right:

| Version | `.name` | `ArrayType` | `PyModule_AddType` |
|---|---|---|---|
| 3.12.16 | :2849 | :3081 | :3102 |
| 3.13.18 | :3053 | :3286 | :3304 |
| 3.14.10 | :3086 | :3320 | :3338 |
| 3.15.2 | :3294 | :3527 ("Older undocumented alias", :3526) | :3545 |

The method list is exact. A grep over every macro ledger and
`.json`/`.added.json`/`.rejected.json`, and every micro `callgraph.json`,
finds no `array.ArrayType` name, and finds these `array.array` names and
no others:

| Name | Occurrences |
|---|---|
| `array.array` | 56 |
| `.buffer_info` | 42 |
| `.byteswap` | 8 |
| `.frombytes` | 8 |
| `.tobytes` | 3 |
| `.tolist` | 4 |

A class-name group has a precedent (`copy.Error`/`copy.error`). The table
stays sorted, and each name is in one group.

### A6. The new `dependencies` wording is true of `trace.py`

`trace.py:126` is the only reader of the key besides `projects.py:181`.
It returns "client" for installed code under `site-packages` whose
top-level name is not in `dependencies`. No other code reads the key: I
grepped the repository. `test_requirements` is what the environment
installs (`projects.py:188`). "The key installs nothing" is true.

**R1 (optional).** "the libraries that the package imports" is narrower
than `projects.toml`. Several entries are transitive dependencies that the
package does not import itself:

| Package | Transitive entries |
|---|---|
| itables | `jedi`, `parso`, `pexpect`, `stack_data`, ... |
| structlog | `automat`, `constantly`, `hyperlink`, `incremental` |
| tablib | `et_xmlfile` |
| json-repair | `rpds` |
| whitenoise | `_brotli` |

They are listed so that their code counts as library code.

"... that the package imports, directly or through other libraries" would
match the file. No edge depends on it.

### A7. The new rules section matches the rulings

The section states:

- the Q14 rule with its scope limits (`ruling-names-2.md` order and the
  batch-8 C-type ruling untouched; written names and factories excluded);
- the Q6 groups and their condition;
- the Q3 rule;
- for each no-change question, the rule that decides it.

These are the rules that q2.md to q13.md cite.

The micro "Methods" sentence is q14.md's one sentence.

Q1 is not in the section. Its reporting change is PR #356, as q1.md says
("applied in its own change").

## 2. The no-change rulings, re-derived on cited sites

For each question, at least three of the sites the ruling cites were
re-derived from the sources before the ledger was opened.

| Id | Question | Sites re-derived | Verdict |
|---|---|---|---|
| N2 | Q2 jsonpickle fan-out | `ext/numpy.py` 100:50, 52:50, 153:47; `ext/pandas.py:348:32`; `pickler.py:610:48` | agree, except N2a |
| N4 | Q4 numpy names | face_classification `data_augmentation.py:214:51`, `preprocessor.py:6:17`; pgvector `bit.py:45:37`; uncertainties `unumpy/core.py:81:24` | agree |
| N5 | Q5 `Any` results | jsonpickle `ext/numpy.py:96:24`, 327:24-333 | agree on the question; N5a |
| N7 | Q7 hashlib, `_sre` | avro `schema.py:338:24`; pymysql `_auth.py` 33-38, 87, 93, 103, 200-202; path 979:21, 990:44, 1000:47; validators `btc_address.py:23`; Sublist3r 554:127; `_sre` in funcy, pypinyin, Sublist3r | agree; N7a open point |
| N8 | Q8 `raise C` | marshmallow `fields.py` 102, 105; structlog `dev.py` 776, 781, `stdlib.py:840`, `testing.py:63`; tablib `core.py` 278, 566, 644, 669, 887; flit-core `config.py:236:23` | agree on the ground truth; N8a |
| N9 | Q9 B2 roles | more-itertools `split_into` 1772:14, 1774:17, 1776:23; `running_mean` 1458:20; funcy `lcat` 178:16, `_lfilter` 32:16, `first` 63:16, `group_values` 331:23 | agree |
| N10 | Q10 B5 | fabric `group.py` 148:24, 150:24, 248:31, 250:32; tinydb `utils.py` 91:31, 94:35; structlog `tracebacks.py:173:32` | agree; see B2 |
| N11 | Q11 path call-backs | `Path.normcase` 274:53, `normpath` 278:53, `dirname` 294:52, `basename` 298:53, `absolute` 270:52, `copymode` 1506, `copystat` 1509, `realpath` 282:53 | agree; N11a |
| N12 | Q12 django-constance | `base.py` 41:19, 122:22 (`__rmod__`), 125-128; `database.py` 53:27, 77:36, 159:28, and the other 8 cache sites | agree |
| N13 | Q13 toolz | `_signatures.py:684:13`: all 290 lambdas against CPython 3.12-3.15 (run), 3.9-3.11 and PyPy (read) | agree |

Notes per question:

- **N2.**
  - The dtype set at 100:50 is 27 `numpy.dtypes` classes plus
    `numpy.dtype`, from numpy's own list (`_add_newdocs.py:7028-7054`)
    plus `StringDType`.
  - 52:50 correctly drops `ObjectDType` and `StringDType`.
  - The `Index` classes at 348:32 are exactly the eight concrete ones.
  - Every per-class entry lies at a declared open receiver site.
  - Slip in q2.md §1: a class-name count gives 90 numpy-scalar entries,
    not 87, all at declared sites.
  - Could not check: the C and Cython claims behind 610:48 (numpy
    `descriptor.c`, pandas `offsets.pyx`). No numpy C or pandas `.pyx`
    is on the VM.
- **N2a (disagree, a ground-truth error outside the rulings).**
  `ext/numpy.py:153:47` `arr.dtype.newbyteorder(byteorder)` in
  `restore_byteorder` lists `numpy.dtypes.ObjectDType.newbyteorder`, and
  it cannot run:
  - The only caller is `:227`, in the `else` of `if dtype == object:`
    (`:214`).
  - `flatten_byteorder` (`:145-148`) never writes `byteorder` for `'|'`,
    the byteorder of an object dtype.
  - A client's direct call would make `arr` an opaque client value (B5).
  - The ledger's own note ("rebuilt from the dtype strings that
    flatten_dtype writes") excludes it.
  - Fix: remove the callee. The pair `restore_byteorder ->
    numpy.dtypes.ObjectDType.newbyteorder` has no other site, so it
    leaves `jsonpickle.json`.
  - At `343:60` the name is right: a by-reference view of an object array
    writes `'object'`.
- **N4.** Each package's names follow whether numpy is installed. The
  sweep claim holds: 134 numpy callees in face_classification, all access
  paths or module functions, and only class names in the six packages that
  have numpy. The cited ledger lines are right.
- **N5.**
  - The five callees at 96:24 and the `.get.get` at 327:24 follow the rules
    as the ledger reads them. Slip: one of the "16 further `data.get`
    sites" is `handlers.py:271:20`, not in `ext/`.
  - **N5a (question for the lead).** q5.md §4 says "one forwarding, no
    loop: a finite path", and the ledger has `.get.get` at 327:24 but only
    `.get` at 343:69, 344:31, 345:32 and 346:33. That is, a level-1
    restore never takes the base branch.
  - `NumpyNDArrayHandlerView.flatten` (`:281-283`) writes a nested `base`
    whenever `obj.base.base` is a contiguous ndarray. numpy stops
    collapsing a view's base at a change of subclass:
    `test_multiarray.py:133-135`, "Create subclass so base will not be
    collapsed". So `w = arr.view(np.matrix)[...]` gives `w.base is m`
    with `m.base is arr`.
  - jsonpickle itself then writes a base inside a base, and alternating
    subclasses make the depth unbounded.
  - Under the ledger's own reading, deeper stub paths are missing:
    - `.get.get` at 343-346;
    - `.get.get.get` at 96:24, 327:24 and the by-value restore sites.
  - The sites are not in the declared open sets. A cut or an open set
    needs a ruling.
  - Could not run: no image has numpy and no numpy C is on the VM. The
    collapse rule rests on numpy's test comment and on the code as I recall
    it (`PyArray_SetBaseObject`).
- **N7.**
  - The fallback and alias names match the admitted runtimes. A container
    check confirmed `_sha512.SHA384Type` on 3.10 and `_sha2.*Type` on
    3.12. The cited lines are right.
  - Could not check Sublist3r on 3.0-3.3: no sources or images. q7.md
    says so.
- **N7a (open point, outside Q7's question).** path's J6 limits
  `hash_name` to md5 and sha1, so 979:21, 990:44 and 1000:47 name only
  those. But `read_hash`/`read_hexhash` document `hash_name` with "List of
  supported hashes can be obtained from :mod:`hashlib`". If that names the
  role's values (B2), these sites lack:
  - the sha2, blake2 and sha3 names that avro has;
  - at 979:21, `_hashlib.HASHXOF.update` and the shake names.
- **N8.** No package class at these sites defines an `__init__`, and no
  macro graph has the outside `__init__` edge.
  `tablib insert_col -> <builtin>.AttributeError.__init__` comes from the
  explicit `raise HeadersNeeded()`, not from line 566.
- **N8a (disagree with the record, no edge effect).** In q8.md §1, the
  flit-core site `config.py:236:23` is in `LoadedConfig.add_scripts`
  (`config.py:233-236`), not `prep_toml_config`. The ledger's
  default-reject note says the same (`flit-core.ledger:17`).
  `flit_core.config.LoadedConfig.add_scripts` has no edges in
  `flit-core.json`, so the micro-style `<builtin>.ValueError.__init__` is
  not "already in the graph" for that caller. The count in §1, §2 and §5
  is 14 pairs, not 13.
- **N9.** All sampled sites agree:
  - (a) `_concurrent_tee.__iter__`/`__next__` at the ordinary iterable
    inputs of `split_into` (1772:14, 1776:23), as the batch-6 ruling
    says.
  - (b) `numeric_range` only at the numeric inputs (`sizes` 1774:17,
    `running_mean` 1458:20).
  - (c) the funcy consumers carry their factory's mapper role at the
    consumer that a document names:
    - `_lfilter`: `docs/seqs.rst:298-301`;
    - `first`: `:312-314`;
    - `group_values`: `:434`;
    - `lcat`: B1.
- **N10.**
  - fabric's `Group` is a `list` (`group.py:12`, `:70`), so `Group('h',
    'h')` gives two equal, distinct Connections. The second `results[cxn]`
    compares them (`connection.py:425-442`).
  - tinydb's `get` and `move_to_end` look the probe query up against an
    equal stored query (`tests/test_tinydb.py:408-411`).
  - Note: reading `-W error` as "documented interpreter configuration" is
    a stretch of "changes a package-owned default or value". q10.md
    addresses it with the nodeenv ruling, and I accept it.
- **N11.**
  - Every call-back matches CPython 3.9-3.12 or PyPy 3.10/3.11 `ntpath`
    and `shutil` on Windows.
  - Citation drift: the PyPy 3.11 line numbers in the path notes are 44
    lines off against `pypy3.11-v7.3.23` of the dependency sources. For
    example, `return prefix + sep.join(comps)` is :492, not :536. The
    notes read v7.3.20, as the ruling says, and the behaviour is the same.
  - PyPy 3.9 is admitted too (`>=3.9`) and adds no edge.
- **N12.**
  - The 29 self-edges and 65 proxy-to-proxy pairs were recounted from
    `django-constance.json`.
  - Could not check from source: that Django removed `MemcachedCache`.
    There is no Django source on the VM; J9 records it.
  - Slip: `caches[...]` is `backends/database.py:34`, not :33.
- **N13.**
  - 51 lambdas are unavailable and 46 overwritten, exactly the two
    `exclude` lines. 193 are stored on some admitted runtime (191 on
    3.12-3.14; 193 on 3.15 with `frozendict`), exactly the 193 callees.
  - Most stored keys reach `check_valid` only on PyPy, which is admitted.
  - Slips:
    - `check_valid` ends at :687, not :686;
    - the PyPy path ends at `functoolz.py:947`, not :946;
    - "3.8" is not an admitted version.

## 3. The two audit items

### B1. Q9: funcy `docs/seqs.rst:331` does not hand the lazy object to `lcat`

`docs/seqs.rst:327-336` is the entry `mapcat(f, *seqs)` / `lmapcat(f,
*seqs)`. Line 331 reads "essentially a shortcut for `cat(map(f,
*seqs))`".

It hands `map`'s lazy object to `cat`. That is `chain.from_iterable`
(`seqs.py:179`), a library function, so the iteration it starts runs in
the caller, not in `lcat`. Line 331 is therefore not a document that
hands the lazy object to the consumer at `seqs.py:178:16` (`list(cat(seqs))`
in `lcat`), and on its own it would not admit that site.

The admission at 178:16 stands on two other witnesses:

- `README.rst:70`, `lcat(map(range, range(4)))`, a documented example
  that hands `map`'s output to `lcat`;
- the package's own call `lmapcat`: `seqs.py:197`,
  `return lcat(map(f, *seqs))`, with `lmapcat`'s public `f` (B2: "the
  package's own code ... pass[es] it there").

**Verdict:** the edges at 178:16 stand; no edge changes. The citation of
`docs/seqs.rst:331` is weaker than presented:

- in q9.md's §4 table;
- in the ledger notes at `funcy.ledger:2315-2323`, "docs/seqs.rst331
  also gives cat(map(f,*seqs))".

Recommended for the record: q9.md should say that 331 hands the object to
`cat`, and that the lcat site rests on `README.rst:70` and `seqs.py:197`.

### B2. Q10: structlog `to_repr -> ReprWrapper.__repr__` stands under B2

`twisted.JSONRenderer` is admitted as the last processor of a
`ProcessorFormatter`:

1. **The role.**
   - `ProcessorFormatter.__init__` takes `processors:
     Sequence[Processor]` (`stdlib.py:1100`), documented as "A chain of
     *structlog* processors" (`stdlib.py:1028-1031`).
   - `Processor` is `Callable[[WrappedLogger, str, EventDict],
     ProcessorReturnValue]`.
   - `ProcessorReturnValue` includes `tuple[Any, ...]`
     (`typing.py:65-74`).
   - `twisted.JSONRenderer.__call__` has that signature and returns a
     tuple (`twisted.py:173-197`).
   - It is a member of the documented processor set P (`structlog.ledger`
     header; `docs/twisted.md:53`, `:100`).
2. **The last position.**
   - The docstring narrows the last processor: "The last one must render
     to a `str`".
   - But `format` handles the other type explicitly:
     `if not isinstance(ed, str): warnings.warn(...)`, then it goes on
     (`stdlib.py:1204-1212`).
   - The 2026-11-15 clarification "Concrete types (B4)": "Explicit
     handling of another type still counts".
   - The same admission already gives the existing edge
     `ProcessorFormatter.format -> ReprWrapper.__repr__` at 1216:30.
3. **The frame.**
   - With `processors=[ProcessorFormatter.remove_processors_meta,
     twisted.JSONRenderer()]`, `ed` is `((ReprWrapper(...),),
     {"_structlog": True})` when the warning is issued.
   - Under `-W error::RuntimeWarning` it is raised with
     `ProcessorFormatter.format`'s frame in the traceback.
   - `ExceptionDictTransformer(show_locals=True)` (`tracebacks.py:430`)
     passes each frame local to `to_repr`. `suppress` is empty by default;
     `ed` is no dunder.
   - On the side without rich (rich is a missing optional import, both
     sides run), `repr(obj)` at 173:32 formats the tuple. The tuple's
     repr calls `ReprWrapper.__repr__`, a builtin call-back of that site.

**Verdict:** agree, the edge stands. Its admission rests on the B4
explicit-handling clause together with the documented processor role, not
on the documentation alone.

`structlog.md:325` still says "Out: `ReprWrapper.__repr__`" from an
earlier round. The later summary (`structlog.md:28-29`, "two paths that
format `ReprWrapper`") supersedes it, and the ledger is authoritative.

## 4. Independence

| Id | Finding | Verdict |
|---|---|---|
| I1 | No change of the PR rests on PyCG's output. The study only selects the questions (§1 of each ruling). The evidence is the rules, the CPython, PyPy and package sources, the traces and the test environments. The Q14 names come from `unix_events.py`/`windows_events.py`; PyCG gives neither the old nor the new name. The Q6 method list comes from the ground truths' names, not the tool's; the groups state an identity that holds on every runtime. q3.md cites PyCG's bundled paramiko stubs only to say that they are tool knowledge the ground truth must not use. The score table of the PR body is information only. | agree |

## Findings

| Id | Severity | Where | Fix |
|---|---|---|---|
| N8a | record error | q8.md §1 table, §2, §5 | flit-core's caller is `LoadedConfig.add_scripts`, which has no `ValueError.__init__` edge; 14 pairs, not 13 |
| N2a | ground-truth error (outside the rulings) | `jsonpickle.ledger`, `ext/numpy.py:153:47`; `jsonpickle.json` | remove `numpy.dtypes.ObjectDType.newbyteorder` at 153:47 and its pair from `restore_byteorder` |
| N5a | question for the lead | jsonpickle view restore, `ext/numpy.py:327-346` | nested views make `yaml.safe_load`/`ujson.loads` paths deeper than one forwarding; rule a cut or declare an open set; q5.md's "finite path" is not shown |
| N7a | question for the lead | path J6, `__init__.py` 979:21, 990:44, 1000:47 | decide whether the `read_hash` docstring admits every hashlib name |
| B1 | record precision | q9.md §4 table; `funcy.ledger:2315-2323` notes | 331 hands the object to `cat`; the lcat site rests on `README.rst:70` and `seqs.py:197` |
| R1 | wording, optional | `benchmark-rules.md:102` | "directly or through other libraries" |
| S1 | slips | q2.md §1 (87 -> 90); q5.md §1 (`handlers.py:271` among the 16); q12.md §1 (`database.py:34`); q13.md §1 (:687, `functoolz.py:947`), §4 ("3.8"); path notes' PyPy 3.11 lines (v7.3.20 against v7.3.23) | optional |

**Verdict.** The PR applies the rulings correctly: every change is the
one the rulings make, and nothing else. Required change: correct q8.md
(N8a). N2a is a ground-truth error that the audit found outside the
rulings, for a correction here or in a follow-up. N5a and N7a are for the
lead to rule on.
