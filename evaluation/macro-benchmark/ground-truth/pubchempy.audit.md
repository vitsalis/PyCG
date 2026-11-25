**Status (2026-11-24):** closed. 146 of 146 sites agree; the lead admitted
F1 (3 outside edges), the writer applied it in `46e1959` (373 edges: 233
inside, 140 outside), and the re-check found nothing open (section
"Re-check" at the end).

# pubchempy: blind audit of the ground truth (batch 8)

Release v1.0.5, commit `9935a14e7fdb4a88d27a99fedce69ca99f004698` (batch 8,
no trace: the doubled audit, 140 sites and every value site, seed
20261124). Audited files: `pubchempy.ledger` (1565 lines, 497 entries, 3
default rejection lines with 9 candidates), `pubchempy.json` (135 nodes, 370
edges: 233 inside, 137 outside), `pubchempy.added.json` and `pubchempy.md`
(J1 to J7), at the writer's commit `5fadd1d` of `b8-gt-pubchempy`.
`check.py pubchempy` reports no errors; `check.py --origin pubchempy` gives
370 added edges (233 / 137) and no trace.

I judged the files by the rules A, B1 to B5 and C of
`macro-benchmark/README.md`, with the clarifications, the rulings for
batch 6 and the rulings for batch 7, and the naming rules of
`PyCG/micro-benchmark/README.md`. I read the package's source
(`pubchempy.py`, all of it), `pyproject.toml`, `.github/workflows/test.yml`,
`docs/` (`api.md`, `index.md`, `guide/advanced.md`, `compound.md`,
`pandas.md`, `install.md`), the tests where a name or a value role was in
question, and, from the dependency sources (read only), CPython 3.10.22 and
3.15.2 `Lib/enum.py`, `Lib/urllib/request.py`, `Lib/urllib/error.py`,
`Lib/urllib/response.py`, `Lib/tempfile.py`, `Lib/logging/__init__.py` and
`Lib/functools.py`, and 3.11.18 and 3.13.18 where the version mattered. I
did not run or import the package, and ran no analysis tool on it. I ran
`check.py` (skeleton in a scratch copy, the size report, `--report`,
`--report --default` for the three default lines, `--report
--without-candidates`, `--origin`) and scripts of my own on the text: the
draw (`selection/batch-8-proposal/audits/pubchempy/draw.py`), a comparison
of my answers with the ledger, and an `ast` binding check.

**Final state.** 146 of 146 sites re-derived blind agree with the ledger.
No edge of the graph cannot happen. One case adds edges (F1: 3 outside
edges, `Bond.__delitem__` with a client object passed as `self`); it is the
lead's to rule. Two remarks on the README (R1, R2). Every judgement call of
the writer is supported by the nearest rule. If the lead adopts F1, the
graph goes from 370 to 373 edges (233 inside, 140 outside); no inside edge
changes.

## Findings

| Id | Kind | Site or edge | Evidence (file:line) | Edges | Decision |
|---|---|---|---|---|---|
| F1 | missing edges (low; likely, needs a ruling) | `pubchempy.py:986:23` `hasattr(self.__wrapped, prop)`, `987:27` `KeyError(prop)`, `988:16` `delattr(self.__wrapped, prop)` in `Bond.__delitem__`: no callee in the ledger (J6) | J6 rules out the one witness it names, a client that stores `_Bond__wrapped` through `bond["_Bond__wrapped"] = obj` (django-constance (d): a public attribute hook admits no private name; I agree). It does not consider a second witness: B1's last sentence, "an object that the client passes explicitly as `self` to an unbound method of a public class (`Cls.method(obj, ...)`) is a client object and opaque (B5)". `Bond` is public and `__delitem__` is a dunder (rule C), so `pubchempy.Bond.__delitem__(obj, "k")` is a client call of the public `deprecated.deco.wrapped` (`816-823`), which calls the original function with `self = obj`. `self.__wrapped` is then `obj._Bond__wrapped`, an attribute of the client's own object (opaque, and its effect on control flow counts: clarification "Client control flow (B5)"), so `hasattr` runs, then `KeyError(prop)` or `delattr`. No private name of a package object is selected, which is what django-constance (d) excludes. The python-barcode audit (F1 there, `codex.py:57`) applied this sentence literally to a package instance; I found no precedent for a client object. No other method of the package gains an edge from a client `self` (I checked every public method: each other body makes the same builtin calls with a package `self`). | +3 outside (`Bond.__delitem__ -> <builtin>.hasattr`, `-> <builtin>.KeyError`, `-> <builtin>.delattr`); 370 to 373 | for the lead; I read B1 as admitting the witness and propose the 3 edges |
| R1 | README (low) | "Implicit calls", the sentence on a library decorator that wraps a method (fabric `@opens`) | The README has no sentence for a **package** decorator that replaces a method or property with a package wrapper. pubchempy has two: `deprecated(...)` returns `deco`, whose `wrapped` replaces nine functions (`879-983`, `1287`, `1298`), and `memoized_property` returns `property(fget_memoized)` for six (`1214-1240`, `1834-1866`). The writer and I, blind, applied the fabric sentence the same way: the wrapper is the callee where the method is reached, and the wrapper's value site (`806:42`, `823:24`) calls the decorated function. One sentence would fix it for the next writer. | 0 (decides the 15 value-site edges and 3 `to_dict` edges) | for the lead; no change proposed |
| R2 | README (low) | B1, last sentence | The sentence says that a client object passed as `self` is "a client object and opaque", but not whether the method's body then counts as run with that object. F1 depends on it. One clause ("the body runs with that object; its attributes are client values") or its negation would settle it. | 0 | for the lead |

## Step 1: blind re-derivation

**Skeleton.** I copied `projects.toml` and `projects/pubchempy` (`cp -R`)
to a scratch directory and ran `check.py --benchmark-dir <scratch>
--skeleton pubchempy` and the size report. 901 sites: 243 call, 86
decorator, 32 iter, 19 mapping, 89 op, 264 getitem, 5 setitem, 134 getattr,
1 setattr, 28 format; 691 with candidates (3398 candidates); 8 value sites.
Twelve candidates sit at 50 or more sites: `Atom.__getitem__` and
`Bond.__getitem__` (386 each), the five `__eq__` (362 each), the three
`record` properties (101 to 102), `Atom.__contains__` and
`Bond.__contains__` (59 each).

**Sample, drawn by kind.** Implicit sites are 572 of the 901, and 372 of
them are subscripts, comparisons and `**` of JSON dicts and builtin values
whose only candidates are the `__getitem__`, `__eq__` and `__contains__` of
the record classes; a plain draw of 140 would give about 51 explicit sites,
which carry every outside callee. I numbered the sites by (module, line,
column) and drew with one `random.Random(20261124)`:
`rng.sample(explicit, 90)`, then `rng.sample(implicit, 50)`. I added the 8
value sites; 2 were drawn (`803:6`, `1742:19`). 146 sites. The draw script,
the sample and my answers are in
`selection/batch-8-proposal/audits/pubchempy/` (`draw.py`, `sample.txt`,
`blind-answers.md`), committed as `3f7f674` before I opened any file of
the writer.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Explicit (62 call, 28 decorator) | 90 | 90 | 0 |
| Implicit (25 getitem, 11 getattr, 8 op, 3 iter, 2 format, 1 mapping) | 50 | 50 | 0 |
| Value sites not in the draw | 6 | 6 | 0 |
| **Total** | **146** | **146** | **0** |

Agreement: **146 of 146**. The writer missed no edge, has no edge that
cannot happen, and names every callee as I did; I made no error that the
comparison shows. My blind conventions (K1 to K11 of `blind-answers.md`)
are the writer's: the ftp redirect at every `.read()` of a response (J3),
`func_wrapper` alone for `e.read()`, `PubChemHTTPError.__str__` at `log.info(e)`
(J4), the two package wrappers (R1), the documented names at the `to_dict`
getattr (J2), JSON values as dicts (J1), no edge in `Bond.__delitem__` (J6;
see F1, which I found only in Step 2), and the two enum metaclass names
(J7). The only implicit sites of the draw with a package callee are
`1305:21` (`Compound.smiles`) and the eight `self.record` loads.

## Step 2: exhaustive checks

**Dispatch sets.**

| Site | Callees | Check |
|---|---|---|
| `self.record`, `other.record` (102 + 101 + 101 candidate sites) | the `record` of the enclosing class | no package subclass of `Compound`, `Substance`, `Assay`; `other` follows `isinstance(other, type(self))` |
| `i.to_dict()` `1155:26` | `Atom.to_dict`, `Bond.to_dict` | `i` is an item of `Compound.atoms` or `.bonds` |
| `c.to_dict(...)` `2025:19`, `s.to_dict(...)` `2043:19`, `self.to_dict(...)` `1181:38`, `1801:38` | the one class each | annotations `list[Compound] \| Compound`, `list[Substance] \| Substance` |
| `fget(self)` `806:42` | the six functions under `@memoized_property` | the package's six decorations; a client function is opaque |
| `func(*args, **kwargs)` `823:24` | the nine functions under `@deprecated(...)` | idem |
| `cls(record)` `1099:19`, `1742:19`, `1923:19` | the class's own `__init__` | classmethods of classes without package subclasses |
| `error_class(...)` `2112:23` | `PubChemHTTPError.__init__` | the seven `error_map` classes and the default define no `__init__` |
| `getattr(self, p)` `1155:45`, `1157:25`, `1784:27`, `1955:27` | 2, 41 + 2 wrappers, 5 + 1 wrapper, 9 getters | the default lists from `__dict__` minus the skip sets (counted with my own `ast` listing), the names of the docstrings and of `docs/guide/compound.md:19` and `pandas.md:29` (J2) |
| `getattr(self, prop)` `883:27`, `895:27` | `<builtin>.getattr`, `Atom.element` | J5 |

**Default rejections (2675 candidate-site pairs).** I listed every site of
each default with `--report pubchempy --default <candidate>`. Of the 386
`__getitem__` sites, 264 are subscripts of JSON records, `kwargs`,
`ELEMENTS`, `PROPERTY_MAP`, `error_map`, `_atoms` and `_bonds`; the others
are iterations (JSON lists, `dict_values`, `zip`, `zip_longest`, the
`*args` tuple of `wrapped`, `Compound.__dict__.items()`, lists of
`Compound` or `Substance`), 19 `**kwargs` and the `in` tests. None iterates
or subscripts an `Atom` or a `Bond`. The 357 `__eq__` sites compare strs,
ints, floats, `None`, IntEnum members with JSON ints, and JSON dicts; the
`in` tests look up strs in str literals, lists, sets and JSON dicts. The 59
`__contains__` sites test containers that are JSON dicts, displays and
`dict_items`. A client value at `prop in {...}` (`882:17`, `894:17`) is
hashed; an `Atom` there is unhashable (it defines `__eq__` without
`__hash__`), so no `__eq__` runs. The 12 explicit sites that the
`__getitem__` default reaches keep their own entries. Every default is
right at every site.

**Functions that no site calls (28).** The public functions and
classmethods (`get_compounds` to `download`, `Substance.from_sid`,
`Assay.from_aid`, `Assay.to_dict`, the two `to_series`); the special
methods that no package code invokes (the five `__eq__`, `Atom`, `Bond`,
`Substance`, `Assay` and `PubChemHTTPError` `__repr__`);
`Atom.coordinate_type` (no package load); `Substance.deposited_compound`
(J2). Each is consistent with the source.

**Special methods and properties.** `Compound.__repr__` is called only by
the `{self}` of the record setter (`1109:29`); `PubChemHTTPError.__str__`
only by the two `log.info(e)` (J4); every property's callers are its
attribute loads, the `to_dict` getattr and, for `Atom.element`, the two
`getattr(self, prop)`. The `record` setter is reached from
`Compound.__init__` (`1031:14`), and getter and setter are one node.

**Rejections, exclusions and notes.** I read all 497 entries. Every
`reject *` and named rejection gives the receiver or the operand type that
the source fixes; the 12 exclusions (6 at `1157:25`, 5 at `1784:27`, 1 at
`1955:27`) name nodes that are not candidates there and say why. The notes
of the value sites and of J3 and J4 cite the right lines. Wording:
`reject *: the receiver is self a Compound` (and "a Assay"), written by the
writer's script at the `record` loads, lacks a comma; it misleads no one.

**Callees outside the package (62 names).** Checked against the source and
CPython 3.10 and 3.15: `HTTPError` defines no `read` and inherits
`addinfourl` (`Lib/urllib/error.py:35-47`), and `_TemporaryFileWrapper`
returns its local `func_wrapper` from `__getattr__` (`Lib/tempfile.py:498`
on 3.10, `573` on 3.15); `HTTPRedirectHandler` admits ftp
(`Lib/urllib/request.py:707` on 3.10, `678` on 3.15), `build_opener` keeps
`FTPHandler` when `urlopen` gets a context, and `ftp_open` returns
`addinfourl`; `LogRecord.getMessage` calls `str(self.msg)`
(`Lib/logging/__init__.py:366`, `395`); `functools.wraps` returns a
`partial` on 3.10 and 3.15; `EnumMeta` is the class on 3.10 and an alias
of `EnumType` from 3.11 (`Lib/enum.py:161`; 3.11 `:479`, `:1052`).
`types.MappingProxyType.items`, `io.BufferedWriter.write`,
`<builtin>.property.setter`, `itertools.zip_longest` (imported name) and
the missing-module names `certifi.where`, `pandas.Series` and
`pandas.DataFrame.from_records` (no source in the dependency set; extras
only) follow the naming rules. Supported runtimes: CPython 3.10 to 3.15
(`requires-python = ">=3.10"`; CI 3.10 to 3.13 on Linux, macOS and
Windows), no other implementation, every platform.

**Trace.** None (no test runs; maintainer's decision). No rejected trace
edges.

**Implicit sites without candidates.** `--report --without-candidates`
lists 11 non-attribute sites: the five `|` of the `QueryParam` alias, two
set unions, an augmented str `+=`, a comparison of ints, a unary minus and
the `with open(...)`. No lazy `map` or `filter` is iterated (the one
`filter(None, ...)` has no function), and no library calls back into the
package beyond the `sorted` keys, the logging formatter (J4) and the
`getattr` getters, all in the ledger.

## Step 3: binding check

An `ast` script matched every call whose callee may be a package function
(by name, as the site finder does) against that function's signature with
`inspect.Signature.bind`. Every call whose callee the ledger accepts binds:
the 54 calls of `request`, `get`, `get_json`, `_parse_prop`,
`create_http_error` and the frame functions (the `**kwargs` of the public
functions cannot repeat a named parameter of the callee in `get` and
`request`), the constructors (`Atom`, `Bond`, `Compound`, `Substance`,
`Assay`), `set_coordinates`, `_setup_atoms`, `_setup_bonds`,
`Compound.from_cid`, the `to_dict` calls and the nine decorator calls. The
script's failures are all candidates that the ledger rejects
(`Atom.to_dict` and `Bond.to_dict` with one argument, the `__init__` of
`Atom`, `Bond`, `PubChemHTTPError` at `super().__init__(msg)`). The value
sites bind by hand: `cls(record)`, `error_class(code, msg, details)`,
`fget(self)`, and `func(*args, **kwargs)` for each of the nine wrapped
signatures under the calls that reach them (subscript, item assignment,
deletion, `in`, property load). No call fails to bind, so no code is cut
off after one.

## The writer's judgement calls

| Id | Opinion |
|---|---|
| J1 records hold JSON values | B3 ("a value that the package never produces for that role") with B4 for the `dict` annotation; decides the defaults and the `<builtin>.dict.*` names. Agree. |
| J2 property names at `to_dict` | The admitted docstring names (3 inside edges: `Compound.to_dict -> memoized_property.fget_memoized`, `-> deprecated.deco.wrapped`, `Substance.to_dict -> memoized_property.fget_memoized`) rest on B2 ("when the documentation names it for that role"): the docstrings say these names are included when specified. The exclusions (4 inside edges: `record` of the three classes, `Substance.deposited_compound`) follow B3's text ("unless the tests or the documented examples use the name"); `docs/api.md`'s autodoc of every property documents the attributes, not a value of `properties`. Agree with both halves; the lead confirms, as the writer asks. |
| J3 ftp redirect | The asciinema ruling ("a branch that a server's answer decides runs") and the fastjsonschema name; sources checked above. Agree. |
| J4 `log.info(e)` | B5's call-back rule under the documented logging setup (`docs/guide/advanced.md:28-46`; pyrate-limiter and structlog). Agree. |
| J5 `Atom.__contains__ -> Atom.element` | The package's own name set fixes `prop` to five names, one of them a property: explicit handling, the reason the clarification "Explicit handling of another type still counts" gives for types. The sibling `__getitem__` has the test evidence. Agree. |
| J6 `Bond.__delitem__` | Agree that the `__setitem__` route is excluded (django-constance (d)); see F1 for the unbound-call route. |
| J7 `ProjectCategory(...)` | The einops metaclass ruling, with "retain an older fallback name" and "do not add two aliases for one class on the same runtime". Agree. |

## For the lead

- F1 needs a ruling on B1's last sentence: does a client object passed
  explicitly as `self` to a public method run the body with that object?
  If yes, 3 outside edges (`Bond.__delitem__ -> <builtin>.hasattr`,
  `<builtin>.KeyError`, `<builtin>.delattr`); no inside edge. R2 is the
  README sentence that would record the answer.
- J2, as the writer asks: the 3 inside edges of the docstring names (I
  agree they stay) and the 4 inside edges of the excluded names (I agree
  they stay out).
- R1: a sentence on package decorators that wrap methods; no edge changes.
- README and tools: no error found. The skeleton, `--report`,
  `--default`, `--without-candidates` and `--origin` worked as documented.

## Re-check (2026-11-24, against `46e1959`)

The lead's rulings of 2026-11-24: F1 admitted (B1's last sentence: a
client's unbound call runs the body with an opaque `self`; the
stored-attribute route stays no witness); J2 and J5 confirmed; R1 and R2
go into the README's "Rulings for batch 8". The writer applied them in
`46e1959`.

| Finding | What changed | Check |
|---|---|---|
| F1 | `pubchempy.ledger`: `986:23 -> <builtin>.hasattr`, `987:27 -> <builtin>.KeyError`, `988:16 -> <builtin>.delattr`, each with a note (the client `self` of B1's last sentence; `KeyError` when `hasattr` is false, `delattr` when true); `pubchempy.json`: `Bond.__delitem__` has the three callees; `pubchempy.added.json` has the three edges | correct; the notes keep the `__setitem__` route as no witness, as ruled |
| J6 | rewritten in `pubchempy.md` with the ruling and both routes | correct |
| J2, J5 | "Confirmed by the lead" added; no edge changed | correct |
| Counts | `pubchempy.md` status, counts and statistics: 373 edges (233 inside, 140 outside) | match `check.py` |

Nothing else changed: the diff from `5fadd1d` to `46e1959` touches only
the three entries of `Bond.__delitem__` in the ledger, the generated
graph and added-edges files, and the status, J2, J5, J6, notes and
statistics of `pubchempy.md`. `check.py pubchempy` reports no errors;
`check.py --origin pubchempy` gives 373 added edges (233 / 140), the
graph's 373. Of my 146 blind sites only `987:27` changes, by the ruling
(my blind answer had no callee, as the first ledger did).

Nothing is open: the audit is closed.
