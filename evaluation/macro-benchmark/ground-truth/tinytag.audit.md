# tinytag: independent audit of the ground truth

Release 2.3.2, commit `c123836e950a897bd4bbee04d3700bec8762ca27` (batch 6).
Audited files: `tinytag.ledger` (737 entries, 37 notes, 1
default rejection), `tinytag.json` (437 edges: 134 in the package, 303
outside), `tinytag.added.json` (46 edges), `tinytag.rejected.json` (9 trace
edges) and `tinytag.md` (judgements J1 to J9). `check.py tinytag` reports no
errors; the trace confirms 391 of the 437 edges.

I judged the files by the scope rules A, B1 to B5 and C of
`macro-benchmark/README.md`, with its clarifications and rulings. I read
the package's source, `README.md`, `pyproject.toml`,
`.github/workflows/tests.yml`, and the referenced lines of
`tinytag/tests/test_all.py`, as data. I did not run or import the package,
and I ran no analysis tool on it. The only tools I ran were `check.py`
(skeleton, size report, `--report`, `--default`) and scripts of my own on
their text output.

**Final state.** No edge that is missing, and no edge that cannot happen.
1 wording finding (W1), 1 judgement call that needs a ruling (J1: my
opinion is to keep its 10 edges), 2 remarks (R1 on the README, R2 on
interpreters). No finding changes the graph: 437 edges.

## Findings

| Id | Kind | Site or edge | Evidence | Edges | Decision |
|---|---|---|---|---|---|
| J1 | ruling needed (judgement call of the writer) | the 10 `if _DEBUG:` blocks: `tinytag.py:317`, `328`, `439`, `446`, `672`, `692`, `1129`, `1317-1318`, `1855`, `1863` | `_DEBUG = bool(environ.get('TINYTAG_DEBUG'))` at import (`tinytag.py:59`). The package README does not name the variable. The code comment (`:58`) says "some of the parsers can print debug info". Upstream's test job sets `TINYTAG_DEBUG: true` (`.github/workflows/tests.yml:58-61`) and requires 100% coverage (`MIN_COVERAGE_PERCENTAGE: 100`, `:8`, checked at `:131`), so the package's own test setup runs these branches. See "Judgement calls" below. | 10 at stake (all outside, all from reading only): 8 `-> <builtin>.print`, `_ID3._parse_frame -> io.BufferedReader.tell`, `-> io.BytesIO.tell` | my opinion: keep (no change) |
| W1 | wording (low) | `tinytag.md`, "Scope rules", A | The list of functions whose bodies make no call names `TinyTag._parse`, `_ID3._unsynchsafe`, `_MP4._build_audio_data_tree` and `_MP4._data_parser`. The graph also has no out-edges for `_MP4._nums_parser` (`:753-762`: it only defines and returns a closure) and `Image.__init__` (`:462-472`: only attribute stores). Both are right in the graph; only the list is incomplete. | 0 | the writer completes the list |
| R1 | README (low) | "Auditing a ground truth", step 1 | It still names the seed `random.Random(20261111)` and "60 to 80 sites"; the batch-6 brief uses `20261122` and 70 sites plus every value site. It says to draw by kind where one kind dominates, but not how to split. State the batch-6 seed and the split rule (here: 50 explicit, 20 implicit). | 0 | for the lead |
| R2 | remark | `tinytag.md` opening paragraph; J7 | The CI matrix runs PyPy 3.8 to 3.11, but `pyproject.toml` declares no implementation classifier. By the clarification "Versions and configuration", a CI job alone is not explicit support. No edge depends on it: the package has no branch on the implementation, and I know of no outside name in the graph that differs on PyPy. The writer checked `_csv.writer` only on CPython 3.12 to 3.15. CPython 3.7 to 3.11 also name the C type `_csv.writer` (my reading, not checked by a run). | 0 | no change |

## Step 1: blind re-derivation

**Skeleton.** I copied `projects.toml` and `projects/tinytag` (`cp -R`) to
`$TMPDIR/audit-tinytag/` and ran `check.py --benchmark-dir <scratch>
--skeleton tinytag`. It has 780 sites: 704 call, 31 decorator, 6 op, 2
getattr, 37 format. 272 have candidates, and 3 are value sites. One
candidate, `Image.__repr__`, sits at 61 sites.

**Sample, drawn by kind.** Explicit sites (call and decorator) are 735 of
the 780, so a plain draw of 70 would hold about 4 implicit sites. I split
the sites into explicit (735) and implicit (45), sorted each by (module,
line, column), and drew with one `random.Random(20261122)`:
`rng.sample(explicit, 50)`, then `rng.sample(implicit, 20)`. I added the 3
value sites; `690:53` was already in the draw. 72 sites. I wrote my callees
for each site in `$TMPDIR/audit-tinytag/blind.md` before I opened
any file of the writer.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Explicit (call, decorator) | 50 | 50 | 0 |
| Implicit (19 format and op, 1 getattr) | 20 | 20 | 0 |
| Value sites not in the draw (`163:31`, `800:37`) | 2 | 2 | 0 |
| **Total** | **72** | **72** | **0** |

The 19 format and op sites of the implicit sample have no callee in my
answers. The writer's default rejection of `Image.__repr__` decides all 19
and leaves them without an entry. The value sites agree to the callee:
`parser_class()` has `TinyTag.__init__`, `_ID3.__init__`, `_MPEG.__init__`
and `_Ogg.__init__`; `sub_path(data)` has the nine leaves of the atom
trees; `parser(data_atom)` has `_MP4._data_parser._parse_data_atom`. The
file-object receivers that I derived before reading (`blind.md`, "Facts
used") are the writer's table in `tinytag.md`, row by row.

## Step 2: exhaustive checks

I read all 737 entries of the ledger against the source.

**Dispatch over the class hierarchy (B1).** `TinyTag` has eight private
subclasses. `_ID3`, `_MPEG` and `_Ogg` define `__init__`; the other five
inherit `TinyTag.__init__`. `Images`, `Image`, `OtherFields` and
`OtherImages` have no package subclasses.

| Site | Receivers | Callees (ledger = mine) |
|---|---|---|
| `self._parse(...)` `:299` | instances made at `:163`, `1089`, `1106`, `1771`, `2053`, `2514`: the eight parsers, never a bare `TinyTag` | the eight `_parse` overrides; `TinyTag._parse` rejected |
| `self._set_field`, `self._set_other_field` in `TinyTag` and the parsers (51 sites) | parser instances | `TinyTag._set_field`, `TinyTag._set_other_field` |
| the same calls in `Images` (`:432`, `436`, `454`, `457`) | `Images` | the `Images` methods |
| `self.images._set_field` / `._update` (`:345`, `696`, `1419`, `1884`, `2154`) | the `Images` of `TinyTag.__init__` | `Images._set_field`, `Images._update` |
| `self._update(child)` (`:1096`, `1113`, `1778`, `2059`, `2520`) | parser instances | `TinyTag._update` |
| `self._parse_image` `:1417` / `:2150`; `_Flac._parse_image` `:1857` | `_ID3` / `_Flac` / the class `_Flac` | `_ID3._parse_image` / `_Flac._parse_image` |
| `super().__init__()` `:1067`, `1524`, `1714` | `_ID3`, `_MPEG`, `_Ogg` | `TinyTag.__init__` |
| `_MPEG()`, `_ID3()` / `_Flac()` | | own `__init__` / `TinyTag.__init__` |
| `OtherFields()`, `OtherImages()` `:114`, `395` | dict subclasses (`TYPE_CHECKING` is `False`, `:39`, `56`) | `<builtin>.dict.__init__` |

**Callback and strategy roles.** The only role is the leaf of an atom tree
(`:690`). I listed every leaf of `_build_audio_data_tree` (`:560-568`),
`_build_meta_data_tree` (`:574-610`), their union (`:616-622`) and the
one-leaf tree of `:721`: the nine callees of the ledger. `parser` at `:800`
comes only from `_data_parser` (`:799`).

**File objects (B2, B4, B5).** A client's `file_obj` is opaque: annotated
`BinaryIO` (abstract), and an outside value that the client passes stays a
client value "whatever the documentation shows" (B2). The README's "e.g.
BytesIO" (`README.md:473`) is an example. This is python-barcode J4. The
package's own objects are the `io.BufferedReader` of `open(filename, 'rb')`
(`:146`) and its 13 `BytesIO` objects. I traced each handler to its
creators. `_ID3._parse` sees a `BytesIO` only up to `:1081` (the handlers of
`_Wave` and `_Aiff` set `_only_id3`). `_ID3._parse_id3v1` and `_MPEG._parse`
see only the opened file. `_Flac._parse` and `_Flac._parse_image` see both.
`_ASF._parse_value` sees only `BytesIO`. Every `fh.read`, `seek` and `tell`
of the ledger has these receivers.

**Default rejection.** `check.py --report tinytag --default
tinytag.tinytag.Image.__repr__` lists 61 sites: 18 explicit (`print`,
`str`), 37 format, 6 op. I checked each operand: strs, ints, floats, bools,
bytes, lists of str, dicts of those, and in `__main__` `{exc}`, an `OSError`
or a `TinyTagException`, whose arguments hold no `Image`. No package code
formats an `Image`. The default is right at all 61.

**Functions that no site calls.** The graph gives `Image.__repr__`,
`Images.as_dict`, `TinyTag._parse`, `audio_offset`, `extra`, `get_image`
and the three modules. Each is public API that only clients call, or (for
`_parse`) has no package caller. Rule A keeps their out-edges.

**Special methods and properties.** The three properties (`audio_offset`,
`extra`, `any`) are loaded only at `__main__.py:102` and `tinytag.py:364`
(`any`). No package code loads `audio_offset` or `extra`. No package class
defines `__eq__`, `__hash__`, `__iter__`, `__len__`, `__bool__`,
`__getattr__` or `__format__`. The skeleton has no class, with, iter, truth
or getitem site with candidates. `--without-candidates` lists the others,
and each has a builtin or library operand.

**Rejections, exclusions and notes.** All 76 rejection lines, 3 exclusion
lines and 37 notes are consistent with the source. The writer marks the 14
debug sites with judgement J1. The `ValueError` of `_load` (`:295`) has no
callee: every package caller sets `_filehandler` first (B1, a check that
cannot fail; python-barcode J7).

**Callees outside the package.** These names are right by the
micro-benchmark rules and their precedents: `os.fsdecode` (the public
attribute of a wrapper), `collections.abc.Mapping.get` for `environ.get`
(anytree), `<builtin>.Exception.__init__` for the package exceptions,
`<builtin>.dict.__init__` for `OtherFields()`, `<builtin>.bytearray.*` for
the Ogg packets, `<builtin>.int.from_bytes`, `struct.*`,
`binascii.a2b_base64`, `warnings.warn`, `json.dumps`, `csv.writer` and
`_csv.writer.writerow`/`.writerows` (netaddr), `io.StringIO.getvalue`,
`io.BufferedWriter.write`, `io.TextIOWrapper.write` for `sys.stderr`, and
`os.path.isfile` and `os.path.splitext`. The package has no third-party
dependency.

**Rejected trace edges.** All 9 are right. 7 are the test's own `BytesIO`
as `file_obj` (`test_all.py:3403`), at functions that no package `BytesIO`
reaches. 2 are a client subclass's direct call of the private `_load`
(`test_all.py:3533-3548`; rule A).

**Binding check.** I checked every call of a package function against the
callee's signature: the 8 `__init__` paths, `_load` (4 call shapes),
`_traverse_atoms` (keyword calls), the nine leaves (one argument each,
bound classmethods or closures), `Image(...)` (3 and 4 positional
arguments), `_create_tag_image`, `_find_string_end_pos`, `_decode_string`,
`_parse_vorbis_comment`, `_parse_value`, and the 11 calls of `__main__`.
All bind.

## Judgement calls

| Call | Nearest rule | Opinion |
|---|---|---|
| J1 debug output | Not decided by the README (below) | keep the 10 edges |
| J2 file objects | B2 (last sentence), B4 (an abstract annotation decides), B5; python-barcode J4 | supported |
| J3 `cls != TinyTag` | B1 (a private class is used only where the package uses it); rule A (direct test calls of private API) | supported, no edge |
| J4 `None` check of `_load` | B1 (a check that cannot fail under the package's own values; ruling 11 of batch 5); rule A | supported |
| J5 default rejection | checked at all 61 sites | supported |
| J6 exceptions | "Callees outside the package" (inherited `__init__`) | supported |
| J7 outside names | precedents named above | supported (R2) |
| J8 value sites | B2 (the package's own values for the role) | supported |
| J9 command line | rule A (`__main__` block keeps its edges) | supported |

**J1, the ruling.** The README does not decide it. Three rules are near:

- "Edges": a fresh process that uses only the public API. An environment
  variable that is set before the import is no change to package internals.
  But it is not public API either.
- The clarification "Versions and configuration": *documented*
  configuration counts when it changes a package-owned value. `_DEBUG` is
  package-owned, but the package does not document the variable.
- Ruling 2 of batch 5 (B2): a client's assignment counts where the
  package's *documentation or tests* make it.

The smaller extension joins the last two: **an environment variable that
the package reads to set a package-owned value counts when the package's
documentation or its own test setup sets it.** Upstream's test job sets
`TINYTAG_DEBUG` and requires full coverage under it, so the 10 edges stay.
This is not the argcomplete case (B1, the private `shlex` with `debug` 0):
there the package fixes the state itself, and here the process environment
sets it. The ruling decides 10 edges of 437. By "Rulings for batch 6",
the lead decides whether that is many enough to need the independent
referee.

## Audit of the corrections of 2026-11-25

Branch `vitsalis/gt-tinytag-csv` (7ffe863, PR #102) against `main`
(2130a69): two outside edges added, at three sites, in `tinytag.json`,
`tinytag.added.json`, `tinytag.ledger` and `tinytag.md`, and
`evaluation/metrics.json` re-based; no other file changed. I read
`tinytag/__main__.py` and `pyproject.toml` from the inputs image,
`Modules/_csv.c` and `Lib/csv.py` of CPython 3.7.17 to 3.15.2 and
`pypy/module/_csv/` and `lib-python/3/csv.py` of PyPy 3.8 v7.3.11 to 3.11
v7.3.23 from the dependency sources, and `pypy/module/_csv/moduledef.py`
and `interp_writer.py` of PyPy 3.7 v7.3.9, fetched in a container at the
commit of the tag `release-pypy3.7-v7.3.9` of the PyPy repository
(`3a614a6737a119273a601c86eae9ee822a60d607`), read as text. Nothing ran;
no PyCG output was read.

| Site (`tinytag/__main__.py`) | Edge | Verdict | Evidence |
|---|---|---|---|
| `68:28` `writer.writerow(data.keys())` | `_print_tag -> _csv.Writer.writerow` | agree | `writer` is `csv.writer(csv_file, ...)` (`:65`), an object of the type `_csv.writer`; `_csv` exports it as `Writer` on CPython 3.10.22 `_csv.c:1719`, 3.11.18 `:1753`, 3.12.16 `:1776`, 3.13.18 `:1760`, 3.14.10 and 3.15.2 `:1799` (all checked); `csv` re-exports only the factory (`Lib/csv.py:7` in 3.10.22, `:67` in 3.15.2; no `Writer` in any `csv.py` read), so there is no public alias |
| `70:24` `writer.writerow(data.values())` | the same edge | agree | the same writer |
| `73:25` `writer.writerows(data.items())` | `_print_tag -> _csv.Writer.writerows` | agree | the same writer |
| the three sites | `_csv.writer.writerow`, `.writerows` kept | agree | CPython 3.7.17, 3.8.20 and 3.9.25 add only `__version__`, `_dialects`, constants, `Dialect` and `Error` in the module init (`_csv.c:1635-1668`, `1645-1678`, `1688-1720`); PyPy 3.7 to 3.11 export the factory `writer` only (`moduledef.py:86`) with the TypeDef `'_csv.writer'` and its `writerow` and `writerows` (`interp_writer.py:166-170` in 3.7 v7.3.9; `:167` in 3.8 and 3.9, `:173` in 3.10, `:186` in 3.11) |

The two names belong to different runtimes, as the ruling requires.
Nothing missed: `csv` is used only in `_print_tag`; `csv.writer` at
`65:24` is the factory's own call; no other outside callee of
`tinytag.json` falls under the ruling (`io.*` are public aliases,
`binascii.a2b_base64`, `struct.unpack` and `struct.unpack_from` are
functions).

Counts. Callee lines 793 to 796, notes 37 to 39 (the new notes at
`70:24` and `73:25`), 439 edges (134 inside, 305 outside), 391 of 439
traced (89.1%), 48 from reading only (39 outside): as `check.py tinytag`
reports, which passes with the source in place, as do `--origin` and
`--report`. `gate.benchmark_digest()` on the branch gives
`37823be3545aab56524294b149d928718a582cab3865cdb96edc29679d4060a0`, the
recorded digest. The `make eval` numbers and the macro outside P come
from PyCG's output, which I did not read.

| Id | Finding | Where | Fix |
|---|---|---|---|
| A1 | `pypy/module/_csv/moduledef.py:85` is a blank line in PyPy 3.8 to 3.11; the factory `'writer'` is at `:86` | the note at `68:28` (`tinytag.ledger`, `tinytag.added.json`) and the commit message | cite `:86` |
| A2 | PyPy 3.7 is "assumed to be that of 3.8"; its source gives the same answer: `moduledef.py:86` exports the factory only, `interp_writer.py:166-167` names the type `'_csv.writer'` (v7.3.9, `3a614a6737a119273a601c86eae9ee822a60d607`) | `tinytag.md`, "Corrections of 2026-11-25" | replace the assumption with this evidence |

**Verdict.** The two edges stand and nothing is missed. A1 and A2 correct
the evidence; no edge depends on them.

A1 and A2 were applied before the merge (the note cites `moduledef.py:86`;
`tinytag.md` gives the PyPy 3.7 v7.3.9 evidence instead of the
assumption). The audit is closed.
