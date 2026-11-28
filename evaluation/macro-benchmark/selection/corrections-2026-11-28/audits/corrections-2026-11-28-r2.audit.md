# Audit of the application of rulings N5a and N7a (2026-11-28)

PR #359, branch `vitsalis/gt-corrections-2026-11-28-r2` (c3371be6, one
commit), against `origin/main` (8e1db387). The record is
`selection/corrections-2026-11-28/rulings/n5a.md` and `n7a.md` of the PR.
I read the PR head and `origin/main` in detached worktrees. Sources:

- the packages from the inputs checkout (`projects/<name>/`; jsonpickle
  v4.1.4, path v17.1.1);
- CPython 3.9.25 to 3.15.2 and PyPy 3.9 v7.3.16, 3.10 v7.3.19, 3.11
  v7.3.23 from the batch-8 dependency sources (`deps/`);
- numpy sdists, fetched for this audit (below).

What I ran, all in containers:

- the numpy fetch, in `python:3.14-slim` (network, PyPI only; read-only
  root, no capabilities): the sdist of 1.17.3, 2.5.4 and the last release
  of each minor series 1.16 to 2.4, each checked against the SHA-256 that
  PyPI lists, and only the needed files extracted with tarfile's `data`
  filter (or zipfile, for the `.zip` sdists of 1.16 to 1.22);
- the numpy 2.5.4 wheel, downloaded with `pip download --require-hashes`
  against the two hashes of `test-environments/jsonpickle.txt:59-61`, in
  the trace image (`python:3.14-slim@sha256:9aaa4740...`,
  `Dockerfile.inputs:24`);
- the witness run, in the same image with `--network none`: that wheel
  installed from the local file, jsonpickle from the read-only inputs
  checkout, json backend;
- `check.py` and `check.py --origin`, in `pycg-eval-runner`
  (`--network none`, 6 GiB), with the inputs checkout mounted at
  `/inputs/macro-benchmark/projects`.

No PyCG output was read or run: not results, not the score table of the
PR body (shown by `gh pr view`, not used).

## 1. N5a: nested view bases (jsonpickle)

| Id | Check | Verdict |
|---|---|---|
| J1 | numpy keeps a view's base across a change of subclass, on every admitted release | agree |
| J2 | the witness: alternating `matrix`/`ndarray` views give base depth n | agree (own run) |
| J3 | each added site-callee runs at the stated depth | agree (own run) |
| J4 | members follow the open-path rule exactly | agree |
| J5 | the open-set declaration and the correction notes | agree; F1 required |
| J6 | releases read | record gap, closed here (R1) |

### J1. `PyArray_SetBaseObject` stops at a change of subclass

numpy, `numpy/(_)core/src/multiarray/arrayobject.c`, read as text. The body
of `PyArray_SetBaseObject` is the same, byte for byte once whitespace is
removed, in all 18 sdists read:

| Release | SHA-256 (PyPI, checked) | Function | Own data stops | Subclass stops | Base set |
|---|---|---|---|---|---|
| 1.16.6 | `e5cf3fdf...` | `:164` | `:201` | `:213` | `:231` |
| 1.17.3 | `a0678793...` | `:164` | `:201` | `:213` | `:231` |
| 1.17.5 | `16507ba6...` | `:164` | `:201` | `:213` | `:231` |
| 1.18.5 | `34e96e9d...` | `:164` | `:201` | `:213` | `:231` |
| 1.19.5 | `a76f5024...` | `:165` | `:202` | `:214` | `:232` |
| 1.20.3 | `e55185e5...` | `:167` | `:204` | `:216` | `:234` |
| 1.21.6 | `ecb55251...` | `:168` | `:205` | `:217` | `:235` |
| 1.22.4 | `425b390e...` | `:168` | `:205` | `:217` | `:235` |
| 1.23.5 | `1b1766d6...` | `:151` | `:188` | `:200` | `:218` |
| 1.24.4 | `80f5e3a4...` | `:151` | `:188` | `:200` | `:218` |
| 1.25.2 | `fd608e19...` | `:155` | `:192` | `:204` | `:222` |
| 1.26.4 | `2a02aba9...` | `:155` | `:192` | `:204` | `:222` |
| 2.0.2 | `883c987d...` | `:156` | `:193` | `:205` | `:223` |
| 2.1.3 | `aa08e04e...` | `:154` | `:191` | `:203` | `:221` |
| 2.2.6 | `e29554e2...` | `:154` | `:191` | `:203` | `:221` |
| 2.3.5 | `784db1dc...` | `:154` | `:191` | `:203` | `:221` |
| 2.4.6 | `f3a3570c...` | `:154` | `:191` | `:203` | `:221` |
| 2.5.4 | `9a94cf75...` | `:154` | `:191` | `:203` | `:221` |

The loop is `while (PyArray_Check(obj) && (PyObject *)arr != obj)` (2.5.4
`:181`, 1.17.3 `:191`). It replaces `obj` by `tmp = PyArray_BASE(obj)`
only while `obj` does not own its data, `tmp` is set, and
`Py_TYPE(tmp) == Py_TYPE(arr)`. So `a_k = a_{k-1}.view(t)` keeps
`a_k.base is a_{k-1}` when `a_{k-1}` owns nothing and
`type(a_{k-1}.base) != t`, as n5a.md §4 says.

The other citations hold: `PyArray_NewFromDescr_int` calls it
(`ctors.c:884-889` of 2.5.4), `PyArray_View` passes `self` as the base
(`convert.c:668-691`), numpy's test says "Create subclass so base will not
be collapsed" (`test_multiarray.py:133-135`), and `class matrix(N.ndarray)`
is `defmatrix.py:74`.

The sdist hashes of 1.17.3 and 2.5.4 match the ones the ruling cites. The
environment pins only the two 2.5.4 wheels, not the sdist, so the sdists
can be checked only against PyPI, as the ruling did.

### J2. The witness, by my own run

`scripts/views.py` (kept beside this audit), numpy 2.5.4 (`aarch64` wheel,
hash of `jsonpickle.txt`), CPython 3.14.10, `--network none`. Owner
`np.matrix(np.arange(4.0))`, then views of type `ndarray, ndarray, matrix,
matrix, ndarray, ...`:

| Views | numpy base depth | `base` depth written by `encode` | `View.restore` calls (with `base`) | Round trip equal |
|---|---|---|---|---|
| 1 | 1 | 1 | 2 (1) | yes |
| 2 | 2 | 2 | 3 (2) | yes |
| 3 | 3 | 3 | 4 (3) | yes |
| 4 | 4 | 4 | 5 (4) | yes |
| 5 | 5 | 5 | 6 (5) | yes |
| 6 | 6 | 6 | 7 (6) | yes |
| 7 | 7 | 7 | 8 (7) | yes |

`np.arange(4.0).view(Sub)[...]` keeps a `Sub` base whose base is an
`ndarray`. Every claim of n5a.md §4 on the run holds.

### J3. Depth at which each site runs

With `sys.settrace` on `ext/numpy.py`, the decoded dict at each nesting
depth identified by `id` (the unpickler hands the dict itself to the
handler, `unpickler.py:895`), three owners:

| Owner | Views | 96, 327 | 343-346 | By value |
|---|---|---|---|---|
| text (size 4) | 2 | 0, 1, 2 | 0, 1 | 112, 114 at 2 |
| text | 3 | 0 to 3 | 0, 1, 2 | 112, 114 at 3 |
| binary (size 40) | 2 | 0, 1, 2 | 0, 1 | 151, 224, 225 at 2 |
| binary | 3 | 0 to 3 | 0, 1, 2 | 151, 224, 225 at 3 |
| object dtype (size 40) | 2 | 0, 1, 2 | 0, 1 | 216, 217 at 2 |
| object dtype | 3 | 0 to 3 | 0, 1, 2 | 216, 217 at 3 |

A `data.get` on the dict at depth `d` is `G(d+1)`. So every one of the 13
sites runs at depth 2 (`G3`), and 343-346 at depth 1 (`G2`), as the table
of §4 says. No other call on the forwarded dict keeps the path:
`restore_dtype` makes no method call on `data`, `_restore_tags` and
`_restore_object` use `in`, `set(obj)` and a subscript
(`unpickler.py:971-1012`, `889`), and `unpickler.py` has no other `.get(`
on decoded data (`201`, `206`, `884`, `891`).

The 34 entries are exactly those sites: `X.get.get` and `X.get.get.get` at
343:69, 344:31, 345:32, 346:33 (16), `X.get.get.get` at 96:24, 112:67,
114:25, 151:29, 216:67, 217:33, 224:35, 225:35, 327:24 (18). A parse of the
PR ledger gives `G1`, `G2`, `G3` for both `X` at all 13 sites, beside
`<builtin>.dict.get`, and nothing longer.

`jsonpickle.json` gains exactly the 10 pairs `-> ujson.loads.get.get.get`
and `-> yaml.safe_load.get.get.get` of `NumpyNDArrayHandler.restore`,
`.restore_flags`, `NumpyNDArrayHandlerBinary.restore`,
`.restore_byteorder` and `NumpyNDArrayHandlerView.restore`; none removed.

### J4. The members follow the open-path rule

`ruling-fabric-1.md` records "one and two repetitions of the repeated
access-path segment beyond the originating path", and its table keeps the
originating `S1` and adds `S2`, `S3` at the stored-config sites. Here the
repeated segment is one `.get` per forwarding (327, 333), and the
originating path at every site is `G1` (the top-level dict, depth 0: a
view's own dict at 327 and 343-346, an owner without a base at the
by-value sites, every array at 96). So `G1`, `G2`, `G3` at each site: no
more, no less. No site first receives a path longer than `G1` (fabric's
`261` case does not arise).

The input is admissible: `encode` takes any object, `register_handlers`
installs the view handler for every `ndarray` subclass (`base=True`,
`ext/numpy.py:370`), and the handler's docstring names array views. The
recursion has no bound in jsonpickle or numpy; the recursion limit is a
runtime limit, as in fabric.

### J5. Declaration and notes

- `jsonpickle.md`, "Open path sets": the sites, the family `Gk, k >= 1`,
  why it is open, the members recorded, the lower bound, the rulings. It
  matches batch 7's "Open path sets" requirements. The Statistics row
  (1660 callee lines; 1320 edges, 383 / 937; 793 of 1320 = 60.1% confirmed;
  527 = 39 / 488 from reading) matches `check.py --origin`.
- The correction notes in jsonpickle's Corrections of 2026-11-25, its new
  Corrections of 2026-11-28 entry and `q5.md` §4 say what changed and leave
  Q5's ruling standing, which is right: Q5 asked about `Any` results.
- The ledger notes at 327:24, 343-346 and the shared note give the depth
  reading and point to "Open path sets".
- `jsonpickle.audit.md:306-307` still read a base dict as having no
  `base`; that file records an earlier audit and correctly stays.
- **F1 (required, formatting).** `jsonpickle.md:910` is a line holding the
  two characters `\n` (a literal backslash and `n`), between the N2a entry
  and the N5a entry of "Corrections of 2026-11-28". Delete it.

### J6. Releases read

**R1 (record gap, closed by this audit).** Batch 8, "Which releases of a
dependency are read", asks for the floor of the range and the last release
of each minor series up to the pin. n5a.md read 1.17.3 and 2.5.4 only. J1
reads the last of each series from 1.16 to 2.5 as well; the function is
unchanged in all of them, so the fact and the ruling stand. The floor was
taken as the first release with CPython 3.8 wheels, not by reading
whether an older sdist builds on 3.8. Since 1.16.6 has the same body, only
a floor at 1.15 or earlier could matter, and the function there would
have to differ. Optional: cite this coverage in n5a.md §4.

## 2. N7a: path's documented hash names

| Id | Check | Verdict |
|---|---|---|
| H1 | B2 admits hashlib's list from these docstrings | agree; R2 on the reasoning |
| H2 | the 26 / 31 receivers are what `hashlib.new` makes on each admitted runtime | agree |
| H3 | the class names follow `ruling-names-2.md` and the batch-8 ruling | agree |
| H4 | SHAKE `digest` / `hexdigest` excluded | agree |
| H5 | J6, path.md, ledger notes, statistics, trace | agree; S1 |

### H1. B2's documentation route

`read_hash` and `read_hexhash` are public, rendered by `docs/api.rst`
(`automodule:: path`, `:members:`), and say "List of supported hashes can
be obtained from :mod:`hashlib` package." (`__init__.py:985`, `995`).
That is documentation that states the values of `hash_name` by reference
to one closed, documented list. B2 admits a value "when the documentation
names it for that role"; avro J5 read the same kind of sentence
("any algorithm supported by hashlib ...") as admitting the whole list.
`_hash` is private (rule B), so it takes what its three callers pass.

The counter-argument of n7a.md §5 does not hold, for a simpler reason than
the ruling gives. The aiocache sentence governs "a string of the client
that selects a method of an outside object that the package made" (B2,
`benchmark-rules.md:2073-2076`). `hash_name` selects no method: it is the
argument of a library factory, `hashlib.new`. So that sentence is not in
play, and B2's general documentation clause decides. J6's reading rested
on `_hash`'s "such as" examples and the test, which give the minimum, not
the role. J6 yields, as the preamble requires.

**R2 (record precision, optional).** n7a.md §3 route 2, and §5 ("B5 admits
the client string's effect on hashlib's control flow in any case"), go
further than needed: if B5 alone admitted every value a client string can
take, the aiocache sentence, which limits a client string to the names
that code, tests and documented examples pass, would have no effect. The
ruling does not need route 2, and the rules bullet does not carry it.
Drop it, or say that it is not part of the ruling, so it is not cited as a
precedent.

### H2. What `hashlib.new(name)` makes, per admitted runtime

path admits CPython 3.9 and later and PyPy 3.9 and later (`path.md`,
"Supported versions and platforms", "PyPy"; `requires-python = ">=3.9"`).

`Lib/hashlib.py` has the same structure in 3.9.25 to 3.15.2:
`__always_supported` is the 14 guaranteed names (`:58`);
`algorithms_available` adds `_hashlib.openssl_md_meth_names` (3.9 `:173-
174`, 3.15 `:193-194`); `__hash_new` sends BLAKE2 to the builtin
constructor (`__block_openssl_constructor`, `:78`), else tries
`_hashlib.new` (3.9 `:160`, 3.15 `:180`) and on `ValueError` the builtin
constructor (`:166`, `:186`); without `_hashlib`, `new = __py_new`. PyPy
3.9 and 3.11 `lib-python/3/hashlib.py` are the same (3.11 `:152-166`).

A name outside the guaranteed set reaches only `_hashlib.new`. On CPython
that makes `HASH`, or `HASHXOF` for an XOF digest (3.9.25
`_hashopenssl.c:888-897`). On PyPy it makes `HASH`, or on 3.11 with
non-empty data a `_OneShotHash` (`lib_pypy/_hashlib/__init__.py:40-55`).
path passes no data (977). PyPy defines a class `HASHXOF(HASH)` (3.9
`:134`, 3.10 `:167`, 3.11 `:228`), but no code of `_hashlib` makes one. So
the non-guaranteed names add no callee.

The builtin constructors (`__get_builtin_constructor`) and the classes
they give, checked in every admitted CPython, not only the two ends of
each range:

| Hash | CPython 3.9 | 3.10, 3.11 | 3.12 to 3.15 | PyPy 3.9 to 3.11 |
|---|---|---|---|---|
| sha224/256 | factories `_sha256.sha224/sha256`; types exported `SHA224Type` `:718`, `SHA256Type` `:720` | same (`:720`, `:725`; `:723`, `:728`) | factories `_sha2.sha224/256`; types `.name = "_sha2.SHA224Type"` etc., `PyModule_AddType` (3.12 `:852-861`, 3.13 `:875-884`, 3.14 `:911-920`, 3.15 `:864-873`) | classes `_sha256.sha224(sha256)`, `sha256` (P9 `:230`, `:206`; P10, P11 `:242`, `:218`) |
| sha384/512 | exported `SHA384Type` `:776`, `SHA512Type` `:778` | SHA-384 export overwritten by SHA-512 (`:782`, `:788`; `:785`, `:791`) | as above | classes `_sha512.sha384(sha512)`, `sha512` (P9 `:258`, `:234`; P10, P11 `:269`, `:245`) |
| blake2 | builtin, bound as `hashlib.blake2b/s` | same | same | same |
| sha3 | types `_sha3.sha3_*` (`:559-562`), exported under their short names (`:731-734`) | `SHA3_TYPE_SPEC` `"_sha3." type_name`, `PyModule_AddType` | same, in all four | classes `_sha3.sha3_*` |
| shake | types `_sha3.shake_*` (`:692-693`, `:741-742`) | same | same | classes `_sha3.shake_*` |

So the guaranteed names give exactly: the SHA-2 classes above, BLAKE2,
SHA-3, SHAKE, and (already in the graph) MD5 and SHA-1, OpenSSL's `HASH`
and, on CPython, `HASHXOF` for SHAKE.

### H3. The names

By `ruling-names-2.md` (public class alias where that attribute holds the
class in that configuration, else the exported type attribute, else the
type name) and the batch-8 ruling, with the lead's avro decision keeping
the private names beside the aliases at `hashlib.new(name)`:

- CPython SHA-2: the public attributes and `_sha256.sha224` ... `_sha2.*`
  are factories, so the exported types: `_sha256.SHA224Type`,
  `SHA256Type` (3.9-3.11), `_sha512.SHA384Type`, `SHA512Type` (3.9),
  `_sha512.sha384` by type name and `_sha512.SHA384Type` for SHA-512
  (3.10, 3.11), `_sha2.SHA224Type` ... `SHA512Type` (3.12-3.15).
- PyPy SHA-2: `hashlib.sha224` ... `sha512` where the fallback binds the
  class (H2 of `ruling-names-2.md`), and `_sha256.sha224`, `sha256`,
  `_sha512.sha384`, `sha512` beside them. The methods of `sha224` and
  `sha384` are inherited from `sha256`, `sha512`; "a method of an outside
  object is named by the class of the receiver, also when that class
  inherits it" (`benchmark-rules.md:1877-1881`), so the receiver's name
  is right.
- BLAKE2: `hashlib.blake2b`, `blake2s` only (H1).
- SHA-3: `hashlib.sha3_*` and `_sha3.sha3_*` (H3 and the avro decision).
- SHAKE, at 979:21 only: `hashlib.shake_*`, `_sha3.shake_*`, and
  `_hashlib.HASHXOF` (CPython; private class inheriting `update` from the
  private `HASH`, so named by the receiver).

That is 26 receivers (25 of avro's `schema.py:338:24`, without the MD5,
SHA-1, `HASH` and `_OneShotHash` names, plus `_sha512.SHA512Type` for
CPython 3.9, which avro does not admit) and 5 SHAKE receivers. `path.json`
gains exactly these 83 pairs (31 / 26 / 26) and loses none; the ledger has
37 callees at 979:21 and 32 at 990:44 and 1000:47.

### H4. SHAKE `digest()` and `hexdigest()` cannot bind

Every SHAKE class takes a required `length`:

| Class | Runtimes | Evidence |
|---|---|---|
| `_sha3.shake_128` | CPython 3.9-3.12 | `METH_O`, "digest($self, length, /)" (clinic `sha3module.c.h:121`, `:148` of 3.9; `:150`, `:177` of 3.12) |
| `_sha3.shake_128` | CPython 3.13-3.15 | "digest($self, /, length)", `minpos 1` (3.15 `:177-183`) |
| `_hashlib.HASHXOF` | CPython 3.9-3.15 | "digest($self, /, length)", `_PyArg_UnpackKeywords(..., 1, 1, 0, ...)` / `minpos 1`, no default (3.9 `:71-77`, 3.15 `:92-98`, `_hashopenssl.c:1110-1119`) |
| `_shake` | PyPy 3.9-3.11 | `def digest(self, length)`, `hexdigest(self, length)` (P9 `:66`, `:84`; P10 `:78`, `:96`; P11 `:81`, `:99`) |

path calls both without arguments (990:44, 1000:47), so the binding fails
before entry (B4), as at avro 338:24. `update` binds for every class. The
exclusion is right, and the aliases `hashlib.shake_*` are correctly left
out there too.

### H5. Records

- J6's rewrite and `path.md`, "Corrections of 2026-11-28", say what the
  ruling says; their table matches H2 and H3.
- Statistics: 763 edges (422 / 341), 487 traced (63.8%), 276 from reading,
  83 of them on J6's hash names; `check.py --origin` gives the same.
- Trace: `dynamic/path.json` (CPython 3.14.10) has
  `_hash -> _hashlib.HASH.update`, `read_hash -> _hashlib.HASH.digest`,
  `read_hexhash -> _hashlib.HASH.hexdigest` at these callers and nothing
  else of these sites; none of the 83 is traced, and no trace edge changes.
- **S1 (slip, optional).** The ledger note at 979:21 says "PyPy's
  _hashlib.new always makes _hashlib.HASH"; PyPy 3.11 makes a
  `_OneShotHash` when data is passed. path passes none, so "makes
  _hashlib.HASH without data" (as `path.md` says) is the exact statement.

## 3. Application (`git diff origin/main...HEAD`)

| Id | Check | Verdict |
|---|---|---|
| A1 | the diff is what the rulings say | agree |
| A2 | `check.py`, `check.py --origin` | pass |

### A1. Scope

The diff changes 12 files:

- `benchmark-rules.md`: the section's preamble (naming `n5a.md`, `n7a.md`)
  and one bullet per ruling;
- jsonpickle: `.ledger`, `.json`, `.added.json`, `.md`;
- path: `.ledger`, `.json`, `.added.json`, `.md`;
- `q5.md` §4: the correction note;
- and adds `n5a.md`, `n7a.md`.

That is exactly the effect sections of the two rulings. No trace,
rejected file, `projects.toml`, test environment or other package
changes. The two bullets state the rulings and their scope limits (no
hand-written JSON, no subscripts; no client string without a stating
document, no SHAKE digest). The commit message carries no attribution
lines.

### A2. Checks

In `pycg-eval-runner` with the inputs' sources: `check.py` reports "no
errors" for all 60 projects (exit 0); `check.py --origin` exits 0, with
jsonpickle 1320 (383 / 937; 793 traced, 527 added, 34 rejected) and path
763 (422 / 341; 487 traced, 276 added, 12 rejected).

## 4. Independence

| Id | Finding | Verdict |
|---|---|---|
| I1 | No change rests on PyCG's output. N5a rests on numpy's and jsonpickle's sources and a run of the package; N7a on path's docstrings, B2, avro J5 and the CPython and PyPy sources. Neither ruling cites a tool result; n5a.md mentions the outside score without open-set packages only to say jsonpickle is already outside it. The PR body's score table and its remark on one path edge are information only, and I did not use them. | agree |

## Findings

| Id | Severity | Where | Fix |
|---|---|---|---|
| F1 | required (formatting) | `jsonpickle.md:910` | delete the line holding a literal `\n` |
| R1 | record gap, closed by this audit | n5a.md §4 | optional: cite the 18 releases of J1 (the batch-8 "releases read" rule) |
| R2 | record precision | n7a.md §3 route 2, §5 | optional: drop the B5 route, or say it is not part of the ruling; the aiocache sentence is out of play because `hash_name` selects no method |
| S1 | slip | `path.ledger` note at 979:21 | optional: "without data" instead of "always" |

**Verdict.** The PR applies the rulings correctly; required change:
delete the stray `\n` line at `jsonpickle.md:910` (F1).
