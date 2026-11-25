# pubchempy: judgements of the ground truth

Status: complete (2026-11-24). Every site is decided; `check.py --write
pubchempy` and `check.py pubchempy` report no error. The doubled blind
audit (`pubchempy.audit.md`: 146 of 146 sites agree, no false edge, one
finding F1) and the lead's rulings of 2026-11-24 are applied: J2 and J5
confirmed; J6 reversed by F1 (+3 outside edges). The Codex rounds are
still to come.

Counts: 135 nodes (1 module, 134 functions, of which 2 lambdas); 373 edges
(233 inside, 140 outside), all from reading; 497 ledger entries; 8 value
sites; 3 default rejection lines (9 candidates, 2675 candidate-site pairs);
12 exclusions.

Release v1.0.5 (commit `9935a14`, annotated tag object `1fcc2e5`).
Analysed source: `pubchempy.py` (root `.`), one module: 20 classes, 132
functions and 2 lambdas. `tests/`, `docs/`, `examples/` and `scripts/`
are not analysed.

pubchempy has **no trace** (the maintainer's decision, 2026-11-24: every
test calls the PubChem PUG REST service). Every edge comes from reading.
The ledger is `pubchempy.ledger`; `pubchempy.json` and
`pubchempy.added.json` are generated from it. There is no
`pubchempy.rejected.json` (nothing was traced).

Drafting: the writer listed the properties of each class with `ast` (to
generate the three `to_dict` getattr entries, J2) and filled three
mechanical kinds of entry with a script: each `@property` decorator
(`<builtin>.property`), each `self.record` or `other.record` load (the
`record` property of the enclosing class) and each `_parse_prop(...)` call.
Every other entry was written by hand, and every generated entry was
reviewed against the source.

## Supported versions, implementations and platforms

- `pyproject.toml`: `requires-python = ">=3.10"`, no dependency;
  classifiers Python 3, 3.10 to 3.13 and `Operating System :: OS
  Independent`; CI (`.github/workflows/test.yml`) runs 3.10 to 3.13 on
  ubuntu, macos and windows. `docs/guide/install.md` says 3.10+.
  `docs/index.md` still says "3.9+", but the module cannot import on 3.9
  (`QueryParam = str | int | ...` at line 94 is evaluated at import): the
  declared bound decides. The final classifier is no upper bound, so
  CPython 3.10 to 3.15 count (README, "Clarifications", versions).
- No implementation is declared; CPython only (a version declaration alone
  admits no other implementation).
- Platforms: every one ("OS Independent", and the CI jobs on Linux, macOS
  and Windows). The module has no platform branch; `os.path.isfile` keeps
  its imported name.
- Optional extras: `pandas` (`pandas>=0.16.2`) and `ssl`
  (`certifi>=2025.7.14`). The `import certifi` of lines 26-31 is an
  optional import: both sides run. `pandas` is imported inside the four
  functions that use it. Neither library is among the dependency sources,
  and no package definition goes through either (no base class, no
  decorator): their calls keep their access paths (`certifi.where`,
  `pandas.Series`, `pandas.DataFrame.from_records`), the same names under
  the missing-module convention.
- `from __future__ import annotations`: no annotation is evaluated.

## Architecture, as the ledger uses it

- `request` (`pubchempy.py:334`) builds the URL and calls `urlopen`; an
  `HTTPError` becomes the package's `PubChemHTTPError` subclass through
  `create_http_error`. `get` reads the response and follows the `Waiting`
  list key; `get_json` and `get_sdf` decode it and turn `NotFoundError`
  into `None` (with `log.info(e)`, J4). The search functions build
  `Compound`, `Substance` and `Assay` objects from the parsed JSON records.
- `Compound.__init__` assigns `self.record`, whose setter (`1106`) logs
  `f"Created {self}"` (so `Compound.__repr__`, then `Compound.cid`) and
  builds the `Atom` and `Bond` objects. Getter and setter of `record` are
  one node.
- Two package decorators wrap functions (value sites):
  - `memoized_property` returns `property(fget_memoized)`. A load of
    `Compound.synonyms`, `.sids`, `.aids`, `Substance.standardized_compound`,
    `.cids` or `.aids` runs `memoized_property.fget_memoized`, which calls
    the decorated function through `fget(self)` (`806:42`; 6 edges).
  - `deprecated(message)` returns `deco`, which returns `wrapped`. The
    dict-style methods of `Atom` and `Bond` and the properties
    `Compound.canonical_smiles` and `.isomeric_smiles` are `wrapped`
    functions; `wrapped` warns and calls the original through
    `func(*args, **kwargs)` (`823:24`; 9 edges). The package never
    subscripts an `Atom` or a `Bond` and never loads the two deprecated
    properties itself; `wrapped` is a callee only at the `to_dict` getattr
    (J2).
- Both decorators copy attributes with `@functools.wraps(...)`: the call
  is `functools.wraps`, the decorator `functools.partial.__call__` (the
  aiocache precedent).
- Receivers: the package has no subclass of `Atom`, `Bond`, `Compound`,
  `Substance` or `Assay`; a client subclass is client code. `self.record`
  in a method of class `X` is `X.record`; `other.record` in the `__eq__`
  methods is an instance of `type(self)` after the `isinstance` test.
  `Atom.aid` and `Atom.charge` are plain attributes, so the candidates
  `Assay.aid` and `Compound.charge` at those loads are rejected.
- The records are dicts from `json.loads` (annotation `dict[str, Any]`), so
  `.get`, `.items` and `.keys` on them are `<builtin>.dict.*`.
- `create_http_error` calls the class that `error_map.get(code,
  PubChemHTTPError)` gives (`2112:23`); the seven subclasses define no
  `__init__`, so each call runs `PubChemHTTPError.__init__`.
  `ResponseParseError(...)` runs `<builtin>.Exception.__init__` (no
  package `__init__` in its MRO).

## Default rejections

Three default lines (first lines of the ledger), all decided at every
site:

| Candidates | Sites | Reason |
|---|---|---|
| `Atom.__getitem__`, `Bond.__getitem__` | 386 each | no subscripted value is an Atom or a Bond (records, package dicts, strs) |
| `__eq__` of `Atom`, `Bond`, `Compound`, `Substance`, `Assay` | 357 each | no operand, `in` element or dict/set key is one of these objects |
| `Atom.__contains__`, `Bond.__contains__` | 59 each | no `in` container is an Atom or a Bond |

The remaining 5 sites of each `__eq__` and the explicit sites of the
defaults (`zip`, `frozenset`, `sorted`, `set`, `filter`, `all`, `list`)
keep their own entries.

## Judgements

J1. **Records hold JSON values only.** `Compound`, `Substance` and `Assay` are
public and take `record: dict[str, Any]`. The package's own flows pass the
dicts of `json.loads`; their nested values are JSON values. No package
object is a value in a record (B3: a value that the package never produces
for that role). This decides the defaults and the `<builtin>.dict.*`
names; no alternative changes an edge.

J2. **`to_dict(properties)` and client property names** (`1157:25`,
`1784:27`, `1955:27`; rules B2, B3). `getattr(self, p)` runs the getter of
each property name `p`. With `properties` unset, the package lists every
`property` of the class's `__dict__` except a skip set: these names are
package values and give 41 + 5 + 9 getter edges. A client list is a list
of client-supplied attribute names (B3: "not taken to name a package
property, unless the tests or the documented examples use the name"). The
ledger admits the names that the documentation gives for the role: the
docstrings of `Compound.to_dict` (`1126-1132`: synonyms, aids and sids "are
not included unless explicitly specified"; canonical_smiles and
isomeric_smiles are not included by default) and `Substance.to_dict`
(`1762-1763`: cids and aids), and the documented examples
(`docs/guide/compound.md`: atoms, bonds, inchi; `docs/guide/pandas.md`:
smiles, xlogp, rotatable_bond_count, through `compounds_to_frame`). So
`Compound.to_dict -> memoized_property.fget_memoized`,
`Compound.to_dict -> deprecated.deco.wrapped` and
`Substance.to_dict -> memoized_property.fget_memoized` are edges (3
inside). Not admitted, recorded as exclusions: `Compound.record`,
`Substance.record`, `Substance.deposited_compound` (and
`Substance.standardized_compound`, which would add no edge) and
`Assay.record`: the skip set leaves them out by default, and no test,
example or docstring names them for `properties` (4 inside edges).
Alternative: `docs/guide/compound.md` calls `record` a property of
`Compound`, and `docs/api.md` documents every property of each class; a
reading that every documented property is a documented value of
"List of desired properties" would add the 4 edges. The writer follows
B3's text (tests or documented examples). Confirmed by the lead
(2026-11-24, after the auditor's opinion).

J3. **A redirect to an ftp URL** (`399:15`, `408:23`, `419:23`,
`423:15`, `1098:56`, `1740:67`, `1921:78`). `request` returns what
`urlopen` returns: an `http.client.HTTPResponse` for the https URL of
`API_BASE`, or a `urllib.response.addinfourl` when the server redirects to
an ftp URL (`HTTPRedirectHandler.http_error_302` allows http, https and
ftp: `Lib/urllib/request.py:707` on 3.10, `678` on 3.15;
`FTPHandler.ftp_open` returns `addinfourl`; `urlopen` with a `context`
builds an opener with the default handlers). `addinfourl` defines no
`read`; its base `tempfile._TemporaryFileWrapper` returns its local
`func_wrapper` from `__getattr__` (`Lib/tempfile.py:498` on 3.10, `573`
on 3.15). So each `.read()` has `http.client.HTTPResponse.read` and
`tempfile._TemporaryFileWrapper.__getattr__.func_wrapper`: 4 outside
edges for the redirect (`get`, `Compound.from_cid`, `Substance.from_sid`,
`Assay.from_aid`). Precedents: asciinema judgement 11 (the lead's ruling:
a branch that the server's answer decides runs) and fastjsonschema
`__init__.py:73:50`. `e.read()` in `create_http_error` (`2094:34`) is the
read of an `HTTPError`, an `addinfourl` in every case (with `fp` None,
`HTTPError.__init__` wraps an `io.BytesIO`, `Lib/urllib/error.py:45-47`):
`func_wrapper` only.

J4. **`log.info(e)` under the documented logging setup** (`446:17`,
`467:17`; B5, callback rule). `docs/guide/advanced.md` ("Logging")
documents `logging.basicConfig(level=logging.DEBUG)` and a `StreamHandler`
on the `pubchempy` logger at DEBUG. Under either, the handler formats the
INFO record, and `LogRecord.getMessage` calls `str(self.msg)`
(`Lib/logging/__init__.py:366` on 3.10, `395` on 3.15) on the
`NotFoundError`, which runs `PubChemHTTPError.__str__`. Two inside edges:
`get_json` and `get_sdf` to `PubChemHTTPError.__str__` (pyrate-limiter
`limiter.py:182` and structlog `_base.py:224` are the precedents). The site
finder proposes no candidate here; the callee is added by hand. The other
log calls pass already formatted strs.

J5. **`Atom.__contains__` and the name `element`** (`895:27`; B3). `prop`
is client-supplied, but the package runs `getattr(self, prop)` only for
the five names of its own membership test (`894`), and `element` is the
property `Atom.element`; the sibling `__getitem__` with the same set is
tested with `"element"` (`tests/test_compound.py:43`). The ledger takes
the package's explicit handling as naming the property: 1 inside edge
(`Atom.__contains__ -> Atom.element`). Alternative: B3 read strictly (the
tests use only `"z" in atom`) removes it. Confirmed by the lead
(2026-11-24, after the auditor's opinion).

J6. **`Bond.__delitem__` runs only with a client object as `self`**
(`986:23`, `987:27`, `988:16`; ruling of the lead, 2026-11-24, on the
audit's finding F1). `self.__wrapped` is the mangled
`self._Bond__wrapped`; no Bond has it (`__init__` sets `aid1`, `aid2`,
`order`, `style`; no `__getattr__`), so on a Bond the load raises
`AttributeError` before `hasattr` runs. A client that first stores the
private attribute with the deprecated `bond["_Bond__wrapped"] = obj` is no
witness: an assignment of a private attribute, a change of package
internals that is not considered (README, "Edges"; django-constance ruling
(d) on private names through attribute hooks). The witness is B1's last
sentence: a client calls the public `Bond.__delitem__(obj, key)` (the
`deprecated` wrapper, which calls this function with `self = obj`) with
its own object as `self`; that object is opaque (B5), so the load of
`_Bond__wrapped` can succeed, `hasattr` runs, and then `KeyError(prop)` or
`delattr`. Three outside edges: `Bond.__delitem__` to `<builtin>.hasattr`,
`<builtin>.KeyError` and `<builtin>.delattr`. The first draft had none
(370 to 373 edges). On a Bond the method always fails: a bug of the
release (it was probably copied from a wrapper class).

J7. **Calling an IntEnum class** (`1980:35`). `ProjectCategory(value)`
goes through the metaclass's `__call__`, which looks up the member and
runs no `__init__`. By the einops metaclass ruling the call has an
outside edge to that method, named through the concrete metaclass:
`enum.EnumMeta.__call__` on 3.10 (the class is `EnumMeta`) and
`enum.EnumType.__call__` from 3.11 (`EnumMeta = EnumType` is an alias
there, so one name per runtime). 2 outside edges.

## Callees outside the package

| Callee | Where | Why this name |
|---|---|---|
| `http.client.HTTPResponse.read`, `tempfile._TemporaryFileWrapper.__getattr__.func_wrapper` | reads of `request(...)` | J3 |
| `<builtin>.bytes.decode` | after each read | `read` returns bytes |
| `logging.Logger.debug`, `.info`, `.addHandler` | `log` | `logging.getLogger("pubchempy")` returns a `Logger` |
| `io.BufferedWriter.write` | `download`, `792:16` | `open(path, "wb")` with default buffering |
| `types.MappingProxyType.items` | the three `to_dict` | the `__dict__` of a class |
| `<builtin>.Exception.__init__` | `ResponseParseError(...)`, `super().__init__(msg)` | first `__init__` in the MRO |
| `functools.wraps`, `functools.partial.__call__` | the two `@functools.wraps` | `wraps` returns a `partial` (3.10 to 3.15) |
| `enum.EnumMeta.__call__`, `enum.EnumType.__call__` | `1980:35` | J7 |
| `certifi.where`, `pandas.Series`, `pandas.DataFrame.from_records` | optional dependencies | access paths |
| `os.path.isfile` | `789:40` | the imported name, also on Windows |

## Open path sets

None.

## Rejected trace edges

None: there is no trace.

## Notes for the auditor

- Bugs of the release: `Bond.__delitem__` fails on every Bond (J6; its
  edges come from a client `self`);
  `create_http_error` catches `ValueError`, `IndexError` and `KeyError`,
  but a `Fault` that is not a dict makes `fault.get` raise an uncaught
  `AttributeError`; `get_cids`, `get_sids` and `get_aids` return `None`
  when the answer has neither list; `docs/index.md` claims Python 3.9.
- Surprising non-edges: the package never calls `Atom.__getitem__` and the
  other dict-style methods; `Atom.__setitem__` and `Bond.__setitem__` run
  no package code (`Atom.element` and `Atom.coordinate_type` have no
  setter); `Bond.order` is the JSON int of the record for package-built
  bonds, so `Bond.__repr__` formats no package object; the `aid` and
  `charge` of `Atom` are plain attributes, not the properties
  `Assay.aid` and `Compound.charge`; `property(fget_memoized)` (`809:20`)
  does not call the getter.
- `warnings.warn` instantiates and formats `PubChemPyDeprecationWarning`
  through `Warning`: implicit outside calls, no edge.
- `pandas` receives only dicts and lists of JSON values (J2 keeps
  `deposited_compound` out of `Substance.to_dict`).

## Statistics

`check.py pubchempy`: 1 module, 134 functions (2 lambdas), 20 classes, 243
calls; 901 sites (243 call, 86 decorator, 32 iter, 19 mapping, 89 op, 264
getitem, 5 setitem, 134 getattr, 1 setattr, 28 format), 691 with
candidates (3398 candidates), 8 value sites; ground truth 373 edges (233
internal, 140 outside); no trace; no errors.

`check.py --origin pubchempy`:

| Project | Trace edges | Rejected | Traced edges in the graph (inside / outside) | Added (inside / outside) | Graph edges (inside / outside) |
| --- | --- | --- | --- | --- | --- |
| pubchempy | no trace | - | - | 373 (233 / 140) | 373 (233 / 140) |
