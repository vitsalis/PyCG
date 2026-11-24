**Status (2026-11-24):** closed. The lead ruled on J2 (its 3 outside
edges go; F1 falls with it; W1 is answered by the new J2 text; R1 goes to
the README's "Rulings for batch 8"); the writer applied the ruling in
`dc875e4` (647 edges: 200 inside, 447 outside), and the re-check passed
(section "Re-check"). Codex round 1 (N1 to N4, M1) is applied in
`0fa844a` and `b8f7ac8` (648 edges: 200 inside, 448 outside); its
re-check passed (section "Codex round 1 re-check" at the end). Nothing is
left.

# flit-core: blind audit of the ground truth

Release 4.2.0, commit `eeaf9e783c87c331f1d73bb2f5553fc79016aae1` (batch 8,
root `flit_core`, package `flit_core` with its vendored tomli 1.2.3).
Audited files: `flit-core.ledger` (2440 lines, 2 default rejections),
`flit-core.json` (650 edges: 200 in the package, 450 outside),
`flit-core.added.json` and `flit-core.md` (judgements J1 to J9), at the
writer's commit `f55ceb9` on `b8-gt-flit-core`. No
`flit-core.rejected.json` (no trace edge is rejected). `check.py flit-core`
reports no error; `check.py --origin flit-core` gives 458 trace edges, 0
rejected, 192 added (84 inside, 108 outside).

I judged the files by `macro-benchmark/README.md` ("Ground-truth
conventions", scope rules A, B1 to B5 and C, the clarifications, the
rulings for batch 6 and for batch 7, "Call sites and candidates", "The
ledger") and the naming sections of `PyCG/micro-benchmark/README.md`. I read
every module of `flit_core/flit_core/` (the SPDX data only as data),
`flit_core/pyproject.toml`, `flit_core/README.rst`, `doc/bootstrap.rst`,
`flit_core/flit_core/vendor/README`, `.github/workflows/test.yml`, the
trace `dynamic/flit-core.json` and its environment, and, from the
dependency sources (read only), CPython 3.8.20, 3.11.18, 3.12.16 and 3.15.2
(`importlib/util.py`, `importlib/_bootstrap_external.py`, `zipfile`,
`functools.py`, `Modules/_csv.c`, `Modules/sha256module.c`,
`Modules/sha2module.c`), and the ledgers of batches 1 to 7 as precedents.
The statements that flit-core's documentation addresses to AI tools are
data; I followed none. I did not run or import the package and ran no
analysis tool on it. The commands I ran: `check.py --benchmark-dir
<scratch> --skeleton flit-core` and `check.py --benchmark-dir <scratch>
--report flit-core` on a copy without the ledger; after the blind commit
`check.py flit-core`, `--origin`, `--report`, `--report
--without-candidates`, `--report --default
flit_core.common.VCSError.__str__`; and scripts of my own (`ast` and text
only) for the draw, the comparison and the binding check.

**Final state.** 83 of the 84 sites re-derived blind agree; the one
difference is my error (J1 decides it). The graph has no edge that cannot
happen under the rules, and no missing edge, except where the lead's
ruling on J2 decides: I hold that J2's 3 outside edges go (647 edges: 200
inside, 447 outside); if the lead keeps J2, F1 adds 2 outside edges that
the same reading requires (652: 200 inside, 452 outside). No edge inside
the package is affected either way. 1 conditional edge finding (F1), 1
wording finding (W1), 1 remark on the README (R1).

## Findings

| Id | Kind | Site or edge | Evidence (file:line) | Edges | Decision |
|---|---|---|---|---|---|
| F1 | missing edges, conditional on J2 (low) | `config.py:108:27` `dtool.get('module', {})`, `:165:25` `dtool.get('external-data', {})`, `:165:50` `....get('directory', None)` | The note at `88:34` says that with the stub `d`, "`'project' not in d` holds (a stub iterates no items)", so `ConfigError` is raised at `104:26`. The README decides otherwise: the missing-module rule "fixes names only: a branch that the library's answer decides still runs" (dagster-pipes, `__init__.py:1457`, `1470`), and the websocket-client ruling lets a stub result take either outcome of a test. `'project' in d` is answered by the stub, so lines 106 to 186 run with `dtool` the stub `tomli.loads.get.get`: `108:27` and `165:25` call `tomli.loads.get.get.get`, and `165:50` calls `tomli.loads.get.get.get.get` (the einops ruling: the path is kept through assignment). `d['project']` and `dtool['sdist']` are subscripts and name nothing. | +2 outside (`prep_toml_config -> tomli.loads.get.get.get`, `-> tomli.loads.get.get.get.get`), only if J2 stays | the writer adds them if the lead keeps J2, and corrects the note; void if J2's edges go |
| W1 | wording (low) | `flit-core.md` J2 and the note at `config.py:74:22` | "the release documents that removal: `doc/bootstrap.rst`". `doc/bootstrap.rst` allows removing the bundled tomli only "if you use Python 3.11 or newer", where `import tomllib` (`config.py:11`) succeeds and line 18 is never reached; for older versions it says to "special-case installing `flit_core` and/or `tomli`", without saying how. `flit_core/vendor/README` describes unbundling as replacing the package with `from tomli import *`, which keeps `from .vendor import tomli` (line 14) working. Only the code comment at `config.py:15-16` names a removal that reaches line 18. | 0 | the writer states the evidence as it is; it is the input of the lead's ruling |
| R1 | README (low) | "Judgements" (optional imports) | No rule says whether a fallback that runs only when a distributor deletes a vendored part of the analysed source counts. The nearest rules point both ways: "both sides of an optional import run" (default), "a state that only a client's change to package internals makes ... is not considered" ("Edges"), and code after an import of a module of the analysed root "that the checkout lacks" has no edges (face_classification), which takes the checkout as it is. One sentence would fix it for the next vendoring package. | 0 | for the lead |

## Step 1: blind re-derivation

**Skeleton.** I copied `projects.toml` and `projects/flit-core` to
`/tmp/claude-501/-home-vitbot-pycg/gt-scratch/audit8-flit-core/` and ran
the skeleton there, without a ledger: 1086 sites, 941 call, 11 decorator,
22 getattr, 112 format; 446 with candidates (601 candidates); 14 value
sites. Two candidates sit at 149 sites each: `VCSError.__str__` and
`EntryPointsConflict.__str__` (every `format` site, every `str()` and every
`.format` call).

**Sample, drawn by kind.** Explicit sites are 952 of the 1086 (88 %). I
numbered the sites by (module in skeleton order, line, column) and drew
with one `random.Random(20261124)`: `rng.sample(explicit, 50)`, then
`rng.sample(implicit, 20)` (the tinytag split), then added the value sites
that the draw had not taken: none of the 14 had been drawn, so 84 sites.
The draw script, the sample and my answers are in
`macro-benchmark/selection/batch-8-proposal/audits/flit-core/`
(`draw.py`, `sample.txt`, `blind-answers.md`), committed as `3c9674b`
before I opened any file of the writer.

**Result: 83 of 84 agree.**

| Site | Mine | Ledger | Classification |
|---|---|---|---|
| `common.py:450:21` `fp.write(f'License: {license}\n')` | `io.TextIOWrapper.write`, `io.StringIO.write` | no callee: J1 makes `Metadata` private; `make_metadata`'s dict never has a `license` key (`read_pep621_metadata` writes `license_expression` and `license_files` only; a license table with `text` stores nothing, `config.py:500-501`), so `license` is the class default `None` and the branch never runs (B1) | my error: I judged `write_metadata_file` as public. No graph edge changes: both pairs come from the other writes of the function. |

The other 83 agree in callees and decisions, the 18 `format` sites that
the default rejections decide included (I rejected both `__str__`
candidates at each: the formatted values are strs, ints, tuples, sets of
strs and TOML values). The value sites agree with their notes: the two
`cls(...)` of `from_ini_path` (the `__init__` of their own class), the
local `parse_escapes` (both escape parsers), the three `parse_float`
(`<builtin>.float`, the default of `loads`), `@lru_cache(maxsize=None)`
(`functools.lru_cache.decorating_function`) and the seven `add`
(`<builtin>.list.append`). One slip of mine in the blind answers names
no edge: at sites 612 and 653 I cited `buildapi.py:91` for `build_sdist`;
the line is 84.

## Step 2: exhaustive checks

- **Edges inside the package (200).** I checked the package callees of
  every node against the source. Each receiver set has one class: no
  package class has a package subclass except the exception hierarchy
  (`ConfigError`, `EntryPointsConflict`, `ProblemInModule` and its three
  subclasses, `TOMLDecodeError`), none of which defines `__init__`.
  `Flags.set` is accepted only on `out.flags` and `flags` (both `Flags`
  instances, `_parser.py:74`, `:432`) and rejected at the 23 `set()` calls.
  The callback roles: `parse_float` has only the default `float`
  (`ParseFloat` is a bare `Callable`, B2); `parse_escapes` the two escape
  parsers; `add` is `components.append`. The `@contextmanager` functions
  `_module_load_ctx` and `_write_to_zip` are callees of their callers'
  calls with `contextlib.contextmanager.helper` (argcomplete and
  dagster-pipes precedents); `cached_tz` with
  `functools._lru_cache_wrapper.__call__` (configargparse; no PyPy is
  admitted). Nothing missing, nothing false.
- **Default rejections.** Both decide 149 sites. I read the 37 explicit
  ones (`str(...)` of Paths and ints, `invalid_msg.format(s=s,
  reason=reason)` with strs, `"...{}".format(", ".join(...))`,
  `str(Address(...))`) and the 112 `format` sites. No `VCSError` is made
  in flit_core; the only `EntryPointsConflict` is raised by the uncalled
  `LoadedConfig.add_scripts` and propagates; the two `{e}` are a str group
  name (`config.py:609`) and the `ValueError` of `Address`
  (`config.py:704`); `{ex.args[0]}` is a str. Both defaults are right.
- **Functions that no site calls.** The graph's list matches the writer's
  (`flit-core.md`, "Notes"): `VCSError.__init__`, `VCSError.__str__`,
  `hash_file`, `parse_entry_point`, `EntryPointsConflict.__str__`,
  `LoadedConfig.add_scripts`, `SdistBuilder.prep_entry_points`, the
  vendored `load`, and the PEP 517 hooks. Each keeps its body edges (A)
  with B's fallback for its parameters.
- **Properties and special methods.** The 22 getattr sites: `Module.file`,
  `Module.version_files`, `Metadata.supports_py2`, `SdistBuilder.dir_name`,
  `WheelBuilder.dist_info` and `WheelBuilder.wheel_filename` are accepted
  where the receiver is the package object and rejected at the three
  `info.file` loads (the `SimpleNamespace` of `make_wheel_in`,
  `wheel.py:247`). `hasattr` and `getattr` in `Metadata` use field names,
  none a property (`common.py:393`, `431`, `435`, `445-446`).
- **Rejections, exclusions and notes.** 37 rejection lines, no exclusion,
  138 notes: all read; all correct except the J2 note at `88:34` (F1). The
  four explicit sites without a callee each have a note that the rules
  support: `common.py:450:21` (J8), the vendored `load`'s `fp.read()` and
  `s_bytes.decode()` (`BinaryIO` is abstract, B4; segno ruling), and
  `Output(...)` (a `NamedTuple` class).
- **Callees outside the package (450).** I checked each name against the
  rules and, where a name differs by version, against the dependency
  sources: `importlib.util.spec_from_file_location` and `module_from_spec`
  (re-exported by `importlib.util`, in its `__all__` on 3.15; the
  precedents name `importlib.util.spec_from_loader`);
  `importlib.machinery.SourceFileLoader.exec_module` (inherited from
  `_LoaderBasics`, named by the receiver's class); `zipfile._ZipWriteFile`
  and `ZipInfo.from_file` (3.8.20 and 3.15.2); `_csv.writer.writerow`
  (`tp_name` "_csv.writer" in both); `_sha256.sha256` (3.8 to 3.11
  `tp_name`) and `_sha2.SHA256Type` (3.12 and later) beside
  `_hashlib.HASH` (the README's hashlib fallback);
  `functools.lru_cache.decorating_function` and
  `functools._lru_cache_wrapper.__call__`; `posixpath.join` for `pjoin`;
  `os.path.*` for `osp`; `collections.abc.Mapping.get` for
  `os.environ.get`; `pathlib.PosixPath.*` and `pathlib.WindowsPath.*` for
  every Path method, `pathlib.Path.cwd` on the class. Platforms (Linux and
  Windows, from the CI jobs; the pyfiglet and textdistance rulings) and
  versions (CPython 3.8 and later, no PyPy) are right. The J2 names are
  F1's subject.
- **Trace edges.** None is rejected and none is missing from the graph
  (`check.py` reports none).
- **Implicit sites without candidates** (1655). No lazy `map` or `filter`
  of a package function is iterated elsewhere (`map(str, ...)` and
  `map(osp.normpath, ...)` call library callables, no edge), and no
  library object calls package code later: the `with` items are files,
  zip members and the package's `@contextmanager` generators, whose
  resumption is no call.

## Step 3: binding check

My `ast` script matched each `call` entry whose callee is a package
function to its call in the source and bound the arguments to the
callee's signature (dropping `self` for methods and `__init__`, `cls` for
classmethods): 251 site-callee pairs, none that cannot bind (the two
`cls(...)` value sites bind nine and six arguments). The callbacks of
`@contextmanager` and `lru_cache` are among them: the generator function
and `cached_tz` receive the arguments of the call.

## The writer's judgement calls

| J | Opinion | Nearest rule |
|---|---|---|
| J1 (only the PEP 517 hooks and `python -m flit_core.wheel` are public) | agree | C with the pymysql ruling: `flit_core/README.rst` states that "the only public interface is the API specified by PEP 517"; `doc/bootstrap.rst:18` documents the command line |
| J2 (the unvendored `tomli`, 3 outside edges) | disagree; for the lead | see "For the lead" |
| J3 (the vendored tomli on 3.8 to 3.10) | agree | "Judgements" (optional import, version branch); A for the uncalled functions |
| J4 (Linux and Windows) | agree | the pyfiglet and textdistance rulings (CI jobs decide a silent release) |
| J5 (the loader of the imported module) | agree | B5 for the client's module; the loader by `spec_from_file_location`'s suffix table |
| J6 (the builtin SHA-256 receivers) | agree | "Versions and configuration" (hashlib's documented fallback); aiocache's clause for `hash_file`'s algorithm string |
| J7 (package exceptions) | agree | "Callees outside the package" (inherited `__init__`), "Implicit calls" (`raise` without a call) |
| J8 (`Metadata.license` stays `None`) | agree | B1, a private class in one state |
| J9 (properties as arguments) | agree | the property runs at its getattr site |

## For the lead

**J2: the third side of the import at `config.py:10-18` (3 outside edges:
`read_flit_config -> tomli.loads`, `prep_toml_config -> tomli.loads.get`,
`-> tomli.loads.get.get`; 5 with F1).** No rule decides it (R1). My
opinion: the edges go. The third side runs only on CPython 3.8 to 3.10
with `flit_core/vendor/tomli/` deleted from the installed package. The
release's documentation does not describe that state (W1): it allows the
removal only on 3.11 and later, where line 18 is never reached, and its
unbundling recipe keeps line 14 working. A deletion of a subpackage of the
analysed root is a change of the analysed source, and the README considers
the checkout as it is (face_classification) and no state that only a
change of package internals makes. If the lead keeps J2, F1's 2 edges
follow from the same reading.

## Re-check

Against `dc875e4` (`fix(b8-gt): flit-core: J2 by the lead's ruling`), the
writer's only commit after `f55ceb9` besides mine. `git diff f55ceb9
dc875e4` touches only the four writer files, and only where J2 decides.

| Id | Ruling | Checked in `dc875e4` | State |
|---|---|---|---|
| J2 (for the lead) | the 3 outside edges go | `flit-core.json`: `read_flit_config -> tomli.loads`, `prep_toml_config -> tomli.loads.get` and `-> tomli.loads.get.get` are gone, and no `tomli.loads` name is left in the graph, the added edges or the ledger. Ledger: the `-> tomli.loads*` lines are gone at `config.py:74:22`, `88:18` and `88:34`. The notes there now say that the third side runs only with the vendored package deleted, a state the release does not document (74:22), that no stub reaches `d` (88:18), and only that a TOML table has `get` (88:34). | closed |
| F1 | falls with J2 | no stub reaches `prep_toml_config`, so `108:27` and `165:25`/`165:50` keep `<builtin>.dict.get` only | closed |
| W1 | answered by J2's text | `flit-core.md` J2 now states the evidence as it is: `doc/bootstrap.rst` allows removal only on 3.11 and later, `vendor/README`'s recipe keeps line 14 working, and only the comment at `config.py:15-16` names a removal that reaches line 18. The table of outside callees no longer lists the missing tomli. | closed |
| R1 | to the README's "Rulings for batch 8" (the lead) | nothing in the package's files | closed for this audit |

Nothing else changed: the diff of the ledger is these three entries, the
graph loses exactly the three edges, `flit-core.added.json` loses the
three added edges and the two notes of the removed callees, and
`flit-core.md` changes only the status, J2, the outside-callee table and
the statistics (647 edges, 200 / 447; 189 added, 84 / 105; 1022 callee
lines). `check.py flit-core` reports no error (647 edges, 200 inside,
447 outside; the trace confirms 458 of 647); `check.py --origin
flit-core` gives 458 trace edges, 0 rejected, 458 traced (116 / 342), 189
added (84 / 105), 647 graph edges (200 / 447). No edge inside the package
changed. The audit is closed.

## Codex round 1 re-check

Against `b8f7ac8` (`0fa844a` applies the five findings of
`selection/batch-8-proposal/codex-audits/round-1/flit-core.md`;
`b8f7ac8` cites the referee's ruling
`selection/batch-8-proposal/rulings/b8-ruling-c-type-names-1.md`). The
base is `dce3eb7`, the commit that the round audited; `git diff dce3eb7
b8f7ac8` touches only `flit-core.ledger`, `.json`, `.added.json` and
`.md`. CPython sources below are in `selection/batch-8-proposal/deps/
cpython/`.

| Id | Site | Change in `0fa844a` | Evidence I checked | State |
|---|---|---|---|---|
| N1 | `common.py:308:23` `h.hexdigest()` | `_sha256.sha256.hexdigest` -> `_sha256.SHA256Type.hexdigest` | `Modules/sha256module.c` exports the class as `SHA256Type` on 3.8.20 (`:726`, `PyModule_AddObject`), 3.9.25 (`:720`), 3.10.22 (`:725`) and 3.11.18 (`:728`); its `tp_name` is `_sha256.sha256` (3.8.20 `:565`, 3.11.18 `:570`), and the module attribute `sha256` is the factory (`Lib/hashlib.py:91-92` of 3.8.20 calls it through `__get_builtin_constructor`). 3.12 and later have `_sha2`, whose `PyModule_AddType` (3.12.16 `:855`, 3.15.2 `:867`) exports `SHA256Type` under its `tp_name`: `_sha2.SHA256Type` stays. The ruling: the exported type attribute takes precedence | agree |
| N2 | `wheel.py:143:31` `hashsum.update(buf)` | `_sha256.sha256.update` -> `_sha256.SHA256Type.update` | as N1 | agree |
| N3 | `wheel.py:147:55` `hashsum.digest()` | `_sha256.sha256.digest` -> `_sha256.SHA256Type.digest` | as N1 | agree |
| N4 | `wheel.py:165:55` `hashsum.digest()` | `_sha256.sha256.digest` -> `_sha256.SHA256Type.digest` | as N1 | agree |
| M1 | `wheel.py:209:32`, `211:28` `writer.writerow(...)` | adds `-> _csv.Writer.writerow` at both sites (1 graph edge), keeps `_csv.writer.writerow` | `Modules/_csv.c` exports the writer class as `Writer` from 3.10 (`PyModule_AddObjectRef`: 3.10.22 `:1719`, 3.11.18 `:1753`, 3.12.16 `:1776`, 3.13.18 `:1760`, 3.14.10 and 3.15.2 `:1799`); 3.8.20 and 3.9.25 do not (`tp_name` "_csv.writer" at `:1330` and `:1376`; the module attribute `writer` is the factory), so their fallback name stays (README, "Versions and configuration"; the ruling: the union across runtimes, no two aliases on one runtime). flit-core admits CPython 3.8 and later, so both names | agree |

**No other site names a type that its module exports under another
attribute.** I listed the 188 outside callee names of the graph and
checked each class name that is not a plain public class: `_hashlib.HASH`
(`tp_name` "_hashlib.HASH", exported as `HASH` by `PyModule_AddObject` on
3.8.20 `:1149` and by `PyModule_AddType` from 3.9: same name);
`_sha2.SHA256Type` (above); `functools._lru_cache_wrapper` (`tp_name`
"functools._lru_cache_wrapper", 3.8.20 `Modules/_functoolsmodule.c:1326`,
3.15.2 `:1908`, imported into `functools` under that name); `re.Match`
and `re.Pattern` (`tp_name` "re.Match", "re.Pattern", 3.8.20
`Modules/_sre.c:2672` and `:2594`, exported by `re`); `zipfile._ZipWriteFile`
(a Python class, named by its defining module); `io.*`, `types.*`,
`datetime.*`, `tarfile.*`, `gzip.GzipFile`, `zipfile.ZipFile`,
`zipfile.ZipInfo`, `argparse.ArgumentParser`, `logging.Logger`,
`email.headerregistry.Address`, `importlib.machinery.SourceFileLoader`
and `collections.*` (public class paths); `csv.writer`, `hashlib.new` and
`hashlib.sha256` are factories, named by their own invocation (the
ruling). None needs a change.

**Nothing else changed.** The ledger diff is the five callee lines of
N1 to N4 and M1, the two rewritten SHA-256 notes (308:23, 143:31), the
rewritten note at 209:32 and a new note at 211:28. The graph renames
four edges (`hash_file`, `_add_file` twice, `_write_to_zip`) and adds
`write_record -> _csv.Writer.writerow`; `flit-core.added.json` follows.
`flit-core.md` changes only the status, the version-names paragraph, J6,
the outside-callee table, the statistics (648 edges, 200 / 448; 190
added, 84 / 106; 1024 callee lines; 139 notes) and a new "Codex round 1"
section. `check.py flit-core` reports no error (648 edges, 200 inside,
448 outside; the trace confirms 458 of 648); `check.py --origin
flit-core` gives 458 trace edges, 0 rejected, 458 traced (116 / 342),
190 added (84 / 106), 648 graph edges (200 / 448). No edge inside the
package changed. No disagreement.
