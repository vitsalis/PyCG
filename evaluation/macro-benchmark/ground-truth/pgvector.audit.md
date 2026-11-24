Status: done. The audit, the referee's ruling and my re-check of commit `a9a5b9e` are complete. The ledger and the graph are clean; one record item is left for the lead (R3, the SHA-256 of Django 4.2.30).

# Blind audit of pgvector (batch 7)

Audit of `pgvector.ledger` at commit `72e5c21` (482 edges: 121 inside, 361
outside). The checker reports no error on it.

## Summary

| Id | Severity | Where | Finding | Edges | Proposal |
|---|---|---|---|---|---|
| F1 | ruling needed (writer's J10); medium if adopted | `psycopg/vector.py:50`, `57-62`; `psycopg/halfvec.py:41`, `48-51`; `psycopg/sparsevec.py:41`, `48-51`; `psycopg/bit.py:26`, `33-34` | The ledger names `context.adapters.register_*` and `info.register` only through the annotations (`BaseConnection`, `TypeInfo`). The package's own callers pass other stub values: `context` from `register_vector` (`psycopg/register.py:10`, annotated `Connection[Any]`) and from `register_vector_async` (`:26`, `AsyncConnection[Any]`), and `info` from `TypeInfo.fetch(...)` (`:11`, `14`, `17`, `21`). B makes the values of a public parameter "what a client or the package can pass". The missing-module rule keeps imported paths ("This does not resolve aliases inside missing libraries: those calls retain their imported paths"), and django-constance ruling (c) names a factory's returned value by the factory's path "beside `redis.Redis.*` where another admitted branch makes that receiver". The writer applies the same union in `psycopg2/register.py:11-16` (two access paths for `conn`, J10). | +18, all outside: +14 `psycopg.Connection.adapters.register_dumper` / `.register_loader` and `psycopg.AsyncConnection.adapters.register_dumper` / `.register_loader` (4 for each of `register_vector_info`, `register_halfvec_info`, `register_sparsevec_info`; 2 for `register_bit_info`); +4 `psycopg.types.TypeInfo.fetch.register` (one per `register_*_info`) | my opinion: add; for the lead (a naming policy for every missing-module parameter that the package also feeds) |
| F2 | low (records) | `pgvector.md` J6 | The README's exception says library code read for a base class is "pinned by SHA-256 in the judgements file". J6 names Django 4.2.30 and 6.1.2 but gives no SHA-256. | 0 | add the pins (from `deps/django-constance/`) |
| F3 | low (records) | `pgvector.md` J4, J6, J7 | They say that scipy 1.18.1, peewee, psycopg and SQLAlchemy were not on disk. They are now (`deps/pgvector/`, releases on or before the upload of pgvector 0.5.1). I read the parts that the judgements depend on; each judgement holds (see "Judgement calls"). | 0 | update the three paragraphs, with the releases and SHA-256 of `deps/pgvector/README.md` |
| Q1 | question (not a finding) | `django/sparsevec.py:61:33` | With a disabled form field, Django cleans the initial value: `_clean_fields` calls `field.clean(bf.initial)`, so `SparseVectorFormField.to_python` can get the `SparseVector` that `SparseVectorField.from_db_value` made for a `ModelForm(instance=...)` (tested: `tests/test_django.py:434-438`). Then `CharField.to_python` (Django 6.1.2 `forms/fields.py`) runs `value not in self.empty_values` (reflected `SparseVector.__eq__`) and `str(value)` (`SparseVector.__repr__`). | 0, or +2 inside (`SparseVectorFormField.to_python -> SparseVector.__eq__`, `-> SparseVector.__repr__`) | my opinion: no change. Django calls `to_python` as a client (B5, "a server or framework that calls the package is a client"). The witness needs a disabled field, which neither the package's documentation nor its tests set. |
| W1 | wording | `pgvector.md` J2 | The conclusion holds, but the evidence is indirect: admitted scipy 1.11 needs numpy 1.x. The README decides admitted versions by the package's own declarations. The release has one: `CHANGELOG.md:5` (0.5.1) "Fixed error with `Bit` constructor for NumPy 1.24-1.26". numpy 1.24 is before 1.25, so `np.any`, `np.packbits` and `np.unpackbits` are Python functions there. | 0 | cite `CHANGELOG.md:5` |
| W2 | wording | `pgvector.md` J10 | "the ledger does not add those access paths" states the decision of F1 but not its reason. The paragraph also keeps two paths for psycopg2's `conn`, so it reads as inconsistent. | 0 | follows F1 |
| R1 | README / brief (low) | "Auditing a ground truth", step 1; "Rulings for batch 6" | The README gives the seed `20261111` and 60 to 80 sites. The brief of batch 7 gives `20261123` and 140 sites for the four packages with partial or absent traces. Neither says how to split 140 sites by kind. I doubled the tinytag split (100 explicit, 40 implicit). | 0 | state the split for a doubled audit |
| R2 | README (low) | ground-truth conventions, missing modules | The micro-benchmark says what calling a stub returns, and in a `with` statement, but not what `await` of a stub instance gives (`info = await TypeInfo.fetch(...)`, `psycopg/register.py:27`). F1 does not depend on it: the synchronous path alone gives each of its edges. | 0 | add one sentence (my reading: the awaited value is the stub instance itself, as in `with`) |

The edges inside the package do not change unless the lead rules Q1 the other way. If F1 is adopted, the ground truth has 500 edges (121 inside, 379 outside).

## Step 1: blind re-derivation

**Skeleton.** I copied `projects.toml` and `projects/pgvector` (`cp -R`) to
`$TMPDIR/b7-audit-pgvector/` and ran `check.py --benchmark-dir <scratch>
--skeleton pgvector`. It has 697 sites: 536 call, 19 decorator, 44 op, 67
getitem, 12 setitem, 19 format. 311 have candidates, and 23 are value sites.
The four `__eq__` of the value classes are candidates at 122 sites each.

**Sample, drawn by kind.** Explicit sites (call and decorator) are 555 of
the 697. The brief asks for 140 sites for pgvector, so I doubled the
tinytag split (50 explicit, 20 implicit). I split the sites into explicit
(555) and implicit (142) and sorted each by (module, line, column). Then I
drew with one `random.Random(20261123)`: `rng.sample(explicit, 100)`, then
`rng.sample(implicit, 40)`. I added the 23 value sites; 2 were in the
explicit draw. That gives 161 sites. I read the whole package and wrote my
callees for each site in `$TMPDIR/b7-audit-pgvector/answers.txt` (the draw
is in `sample.tsv`) before I opened any file of the writer or the trace.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Explicit (call, decorator) | 100 | 95 | 5 |
| Implicit (op, getitem, setitem, format) | 40 | 40 | 0 |
| Value sites not in the draw | 21 | 21 | 0 |
| **Total** | **161** | **156** | **5 (3.1 %)** |

The 5 disagreements are one question, F1 (a ruling on naming). At
`psycopg/bit.py:33:29`, `psycopg/halfvec.py:48:29` and
`psycopg/vector.py:58:29`, `60:29` and `61:29`, I named the
`register_dumper` / `register_loader` of `psycopg.Connection` and
`psycopg.AsyncConnection` beside the writer's `psycopg.BaseConnection`. No
disagreement is an auditor error that I could find. The writer and I agree
on every implicit site (all without a package callee), on all 23 value
sites, and on every name outside the package in the sample.

## Step 2 and 3: exhaustive checks

**Dispatch sets.** No value class (`Vector`, `HalfVector`, `Bit`,
`SparseVector`) has a package subclass. The package subclasses
(`VectorBinaryDumper(VectorDumper)` and the like) override `dump` or `load`
and call no method on `self`. So every `self.`, `cls.` and receiver call
has one package class, as the ledger says. The four `_distance` and the
two `get_prep_value` calls on `self` are right (a client subclass that
overrides them is client code).

**Default rejections (2, on 8 candidates).** I read all 122 `__eq__` sites
and all 28 `__repr__` sites (`--report --default`). No operand, key or
formatted value is a package vector. The explicit sites are `set(value)`
on a str (`bit.py:29:25`), `str(e)` on an exception, `format(v, '08b')` on
an int, `str(value)` on a str by annotation, and `str(v)` / `str(float(v))`
on floats. The closest case is `v != 0` in `_from_dict`
(`sparsevec.py:98:55`): a vector as a dict value would call `__eq__`, but
the annotation `dict[int, float]` excludes it (B2).

**Value sites (23).** All agree: the `cls(...)` of the classmethods reach
the class's own `__init__`, and the 17 SQLAlchemy sites call stub values
(J11).

**Binding.** I checked every call of a package function against its
signature, including the positional-only `/` parameters of `_to_db`,
`_from_db`, `_from_text`, `_from_parts`, `_distance` and the
`register_*_info` functions. Every call binds.

**Nodes that no site calls (203, modules included) and empty bodies (54 nodes).**
These are the public API and the methods that the frameworks call. Each
keeps its body edges (rule A). The bodies without out-edges are right:
`db_type`, `get_modifiers`, `get_col_spec`, the `bind_processor` and
`result_processor` that only return a closure, the two psycopg2 adapter
`__init__`, `SparseVector.dimensions` / `indices` / `values`, and the
modules that only define classes.

**Special methods and properties.** The package has no property, no
`__set_name__`, no `__init_subclass__` and no metaclass. `Sentinel()` has
no edge (`sparsevec.py:15:39`, first `__init__` is `object.__init__`). The
`type('', (XDumper,), {...})` sites run no package code: psycopg's
`Dumper` is a `Protocol` with `ABC` (`psycopg-3.3.6/psycopg/adapt.py:27`,
`abc.py:101`), and its metaclass hooks are outside implicit calls.

**Callees outside the package (113 names).** I checked all of them. The
builtin, `struct`, `array`, `typing` and numpy names match the trace by
alias (`_struct.pack`, `numpy._core._multiarray_umath.frombuffer`). The
fourteen scipy `tocoo` receivers are exactly the subclasses of `sparray`
and `spmatrix` in scipy 1.18.1 (`_bsr.py:659`, `778`; `_coo.py:1694`,
`1811`; `_csc.py:188`, `292`; `_csr.py:333`, `465`; `_dia.py:516`, `621`;
`_dok.py:674`, `733`; `_lil.py:526`, `598`). The names of the missing
modules follow the access path, with the exception of F1.

**Library bases (the README's exception), with the libraries that arrived
after the writer finished.** The writer had none of the seven integration
libraries and not scipy 1.18.1 (`deps/pgvector/README.md`). I checked every
package class that derives from a library class (47 classes, the nested
SQLAlchemy `Comparator` classes included). For each class I asked two
questions. First, does a library method that the package calls (through
`super()` or by inheritance) call a package override back? Second, does a
class-creation hook of the library call package code? The answer is no in
every case, so the ledger needs no change.

| Package classes | Library base | Library code that the package reaches | Package overrides | Call-back? |
|---|---|---|---|---|
| `django.{vector,halfvec,sparsevec,bit}` `*Field` | `django.db.models.Field` | `__init__`, `deconstruct`, `formfield` (with `has_default`, `get_default`, `_get_default`, `get_choices`), `value_from_object`; read in Django 4.2.30 (`fields/__init__.py:179`, `515`, `960-990`, `1086`) and 6.1.2 (`:219`, `605`, `1053-1191`) | `__init__`, `deconstruct`, `db_type`, `from_db_value`, `to_python`, `get_prep_value`, `value_to_string`, `formfield` | none. `formfield` stores `self.to_python` as `coerce` (it does not call it) and instantiates the package form class, whose first `__init__` is Django's. |
| `*FormField` (4) | `django.forms.CharField` | `CharField.to_python` (calls `str` and `strip`); `forms.Field.__init__` calls `self.widget_attrs`, which the package does not override | `to_python` | none (see Q1 for a value that only a disabled field passes) |
| `SparseVectorWidget` | `django.forms.TextInput` | `Widget.format_value` (4.2.30 and 6.1.2: `value == ""`, `formats.localize_input`, `str`); the package converts a `SparseVector` before the call | `format_value` | none |
| `DistanceBase`, `BitDistanceBase` and their 6 subclasses | `django.db.models.Func` | `Func.__init__` (`self._parse_expressions`, `BaseExpression.__init__`), the same in 4.2.30 and 6.1.2 | `__init__` | none |
| `IvfflatIndex`, `HnswIndex` | `django.contrib.postgres.indexes.PostgresIndex` (`Index`) | `Index.__init__`, `Index.deconstruct` (4.2.30 and 6.1.2): attribute stores and reads only | `__init__`, `deconstruct`, `get_with_params` | none. Only `PostgresIndex.create_sql` calls `get_with_params`, and the package never calls it (Django's schema editor does). |
| `VectorExtension` | `django.contrib.postgres.operations.CreateExtension` | `__init__(self, name, hints=None)` in 6.1.2, but `__init__(self, name)` in 4.2.30. This is why the package has the `VERSION[0] >= 6` branch (J8): both sides bind. | `__init__` | none |
| `peewee.*Field` (4) | `peewee.Field` | `Field.__init__` (`peewee.py:5661`); `to_value` (`:5724`) builds `Value(value, self.db_value, unpack=False)` (`:1514`): with `unpack=False` it stores `db_value` and does not call it | `__init__`, `db_value`, `python_value`, `get_modifiers` | none |
| psycopg `*Dumper`, `*Loader` (12) | `psycopg.adapt.Dumper`, `Loader` (`adapt.py:27`, `120`; `Protocol` with `ABC`) | no inherited method is called by the package. The `class` statements and `type('', (XDumper,), {...})` run only `ABCMeta` and `Protocol`'s hooks; psycopg defines no `__init_subclass__`. `AdaptersMap.register_dumper` / `register_loader` (`_adapters_map.py:114`, `165`) read `dumper.format` and store. | `dump`, `load` | none |
| `VECTOR`, `HALFVEC`, `SPARSEVEC` | `sqlalchemy.types.UserDefinedType` (`type_api.py:1383`) | `super().__init__()`: no `__init__` in the MRO, so CPython runs `object.__init__` (the ledger keeps the stub name, as the missing-module rule asks). Class hooks: `Visitable.__init_subclass__` (`visitors.py:91`, only with `__visit_name__` in the class), `EnsureKWArg.__init_subclass__` (`langhelpers.py:2210`: it inspects `get_col_spec`, which already takes `**kw`, and calls nothing) | `__init__`, `get_col_spec`, `bind_processor`, `literal_processor`, `result_processor` | none |
| `BIT` | `sqlalchemy.types.TypeDecorator` | no inherited method is called by the package | `process_bind_param` | none at a package site (SQLAlchemy calls it when it binds) |
| `*.Comparator` (4) | `TypeEngine.Comparator`, `TypeDecorator.Comparator` (`type_api.py:172`, `1799`) | `Operators.op` (`operators.py:271`) and the operator that it returns, then `operate` and the default comparator. On the type of the column they call only `coerce_compared_value` (`type_api.py:1455`, which the package does not override; it returns `self`) and read `coerce_to_is_types` | the distance methods | none |
| `avg` | `sqlalchemy.sql.functions.ReturnTypeFromArgs` | `GenericFunction.__init_subclass__` (`functions.py:1610`) registers the class by name | none | none |

asyncpg, pg8000 and psycopg2 give the package no base class, and the
package does not import sqlmodel. The call-backs that these libraries make
later (codecs, adapters, casters) run from the client's queries, as the
ledger says. Two library facts confirm judgements:

- psycopg 3.3.6: `Buffer = Union[bytes, bytearray, memoryview]`
  (`abc.py:27`), which confirms J7.
- pg8000 1.31.5: `make_param` (`converters.py:751-764`) looks the adapter
  up by `type(value)`, then by `isinstance`. This confirms J9.

**Scipy formats at `arr.tocoo(copy=False)` (J4) against scipy 1.18.1.**
The fourteen subclasses of `sparray` and `spmatrix` are listed above. No
other class in scipy derives from either. Every format's `tocoo` returns
`self._coo_container` (a `coo_array` or `coo_matrix`):

- `_bsr.py:394-422`
- `_compressed.py:995-1005` (csc and csr)
- `_csr.py:63`
- `_dok.py:568-578`
- `_coo.py:441-445` (returns `self` or `self.copy()`)
- `_base.py:1343-1357` (dia and lil, through `tocsr`)

So the `copy` and `sum_duplicates` receivers at `110:31` and `111:33`
(`coo_array`, `coo_matrix`) are complete too. The writer's set is
confirmed: 0 edges change.

**Trace.** There are 151 trace edges and no rejected edge. Every trace
edge is in the graph, and the checker confirms the identity. No trace edge
comes from a test-only value that the rules exclude: the five traced scipy
formats are admitted under J4.

## Judgement calls

| Call | Nearest rule | Opinion |
|---|---|---|
| J1 missing modules; branches that the database or the library decides all run | "Callees outside the package": "the rule fixes names only: a branch that the library's answer decides still runs" (dagster-pipes) | supported |
| J2 numpy 1.x admitted: `numpy.any`, `numpy.packbits`, `numpy.unpackbits` beside the dispatcher (3 edges) | "a callee that is a plain function on one supported version and a wrapper object on another" (fastjsonschema); django-constance (f) for undeclared dependency versions | supported; cite `CHANGELOG.md:5` (W1) |
| J3 ndarray subclasses not named | B4 and the clarification "A concrete annotation does not admit arbitrary out-of-contract types"; the `isinstance` check fixes `numpy.ndarray` | supported |
| J4 fourteen scipy formats at `tocoo` (9 untraced) | jsonpickle (e), one name per admitted concrete receiver class; the annotation `sparray \| spmatrix` and `is_sparse_array` admit every format, and neither base has instances of its own | supported; the narrower reading has no rule behind it. I confirmed the set in scipy 1.18.1 (F3). |
| J5 both byte orders | the supported-platform rule (netaddr) | supported |
| J6 library bases call nothing back | "the exception" (itables, fabric) | supported; I re-checked it on peewee, SQLAlchemy and psycopg (F3); add the SHA-256 pins (F2) |
| J7 `Buffer` gives `bytes.decode` and `bytearray.decode` | B4 (documented concrete types) | supported; confirmed at `psycopg/abc.py:27` |
| J8 both sides of `VERSION[0] >= 6` | version branch of a dependency; django-constance (f). `CHANGELOG.md` 0.4.2 adds Django 6, and the CI job on Python 3.10 installs Django 5.2 | supported |
| J9 pg8000 and asyncpg lambdas | B2, the role that the registration fixes | supported; confirmed in pg8000 1.31.5 |
| J10 annotated missing-module parameters | prometheus-client (annotation path); pyrate-limiter (two annotation paths) | **ruling needed (F1)**. The README does not decide whether a public parameter's stub name also comes from the package's own callers. The smaller extension of the existing rules is django-constance (c) together with B: the union of the stub paths of all admitted flows. The writer's psycopg2 entries already do this. |
| J11 subscripted stub bases resolve to the base | the site finder's rule (`class String(Field[str])` is `Field`); Python's `__mro_entries__` | supported. The README's "the subscript of a missing-module value is not named" is about values, not bases; a sentence would make that explicit. |
| J12 value sites | B1 (classmethod `cls`); B (private `_to_db` called only on its class) | supported |

## Notes on method

- I ran only `check.py` (skeleton, size report, `--report`,
  `--default`) and scripts of my own that draw the sample and compare the
  answers with the ledger. I ran no analysis tool and read no analysis
  output.
- Once, a search command with an empty path variable fell back to the
  working directory. It printed some `def __init__` lines of tool and test
  sources, `pycg-evaluation/PyCG/` among them. These were source lines,
  not output of an analysis, and none of them is about pgvector. I opened
  no file there.

## Re-check (commit `a9a5b9e`, 500 edges: 121 inside, 379 outside)

I diffed the four pgvector files from `72e5c21` (the ledger that I
audited) to `a9a5b9e`. Then I ran `check.py` on the committed files in my
scratch directory.

**Verdict: clean.** Only a record item is left (R3 below); no edge
depends on it.

- **The ruling's adapter sites.** Each of the 16 sites has the two added
  callees and keeps the annotation's callee
  (`psycopg.BaseConnection.adapters.register_dumper` or
  `.register_loader`):
  - `psycopg/vector.py:57:29` to `62:29`
  - `psycopg/halfvec.py:48:29` to `51:29`
  - `psycopg/sparsevec.py:48:29` to `51:29`
  - `psycopg/bit.py:33:29`, `34:29`

  The added callees are `psycopg.Connection.adapters.register_*` and
  `psycopg.AsyncConnection.adapters.register_*`, with `register_dumper`
  at the dumper sites and `register_loader` at the loader sites, exactly
  as the ruling's first table lists them.
- **The ruling's `info.register(context)` sites.** Each of the 4 sites
  (`vector.py:50:18`, `halfvec.py:41:18`, `sparsevec.py:41:18`,
  `bit.py:26:18`) has `psycopg.types.TypeInfo.fetch.register` and keeps
  `psycopg.types.TypeInfo.register`, as the ruling's second table lists
  them.
- **The graph.** It gains exactly 18 outside edges: 5 each for
  `register_vector_info`, `register_halfvec_info` and
  `register_sparsevec_info`, and 3 for `register_bit_info`. The graph
  loses no edge, and no edge inside the package changes.
- **Nothing else changed.** The ledger diff has only these 20 sites, with
  their notes, and one new note at `django/sparsevec.py:61:33` (Q1). That
  site keeps `django.forms.CharField.to_python` and has no package
  callee, as the ruling says.
- **The checker.** `check.py --benchmark-dir <scratch> pgvector` reports
  no errors: 500 edges (121 inside, 379 outside). The trace confirms 155
  of them, and no trace edge is rejected. The checker also checks
  `pgvector.added.json` against the ledger and the trace.
- **`pgvector.md`.**
  - **J10** quotes the ruling's rule. It lists the 14 adapter edges at
    their 16 sites and the 4 `fetch.register` edges, and it explains the
    psycopg2 case with the same rule.
  - **J13** records Q1 and the ruling's text.
  - **J2** cites `CHANGELOG.md:5` under django-constance (f).
  - **J4** records the referee's confirmation and my check of scipy
    1.18.1, with its SHA-256.
  - **J7** cites psycopg 3.3.6 `abc.py:27`.
  - **J6** lists the library code that the writer read.

  I compared each SHA-256 in J6 with `deps/pgvector/README.md`
  (SQLAlchemy, peewee, psycopg, psycopg2, asyncpg, pg8000) and with
  `requirements/django-constance.txt` (Django 6.1.2). All seven match.
  The README's "Rulings for batch 7" states the same three rules (forwarded
  stub paths, a call-back needs an admitted input, a changelog as a
  support statement).
- **R3 (low, records, for the lead).** J6 says that Django 4.2.30 has no
  SHA-256 on disk; its directory in `deps/django-constance/` has no
  README, and only the wheel's `RECORD` is there. The README's base-class
  exception asks for the pin, and the writer cannot supply it. No edge
  rests on Django 4.2.30 alone:
  - 6.1.2, which is pinned, gives the same "no call-back" result.
  - The difference that matters, `CreateExtension.__init__(name)`
    without `hints`, only explains why both sides of `VERSION[0] >= 6`
    exist (J8).

  Proposal: the lead adds the SHA-256 of the 4.2.30 wheel to J6, or to a
  README in that directory.
