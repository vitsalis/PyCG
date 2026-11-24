# pgvector: judgements of the ground truth

Release v0.5.1 (commit `5275164`). Analysed source: `pgvector/`, 40
modules, 211 functions (7 lambdas), 55 classes. `pyproject.toml` declares
`requires-python = ">= 3.10"` and no runtime dependency. Of the dependency
groups `numpy`, `scipy` and `dev` (asyncpg, Django, peewee, pg8000,
psycopg, psycopg2, SQLAlchemy, sqlmodel), only one entry names a version:
`SQLAlchemy[asyncio]>=2` (`pyproject.toml:31`), and `CHANGELOG.md:16`
(0.5.0) says "Dropped support for SQLAlchemy < 2". The other libraries
have no version bound in `pyproject.toml`. CI (`.github/workflows/build.yml`)
runs CPython 3.14 and 3.10 on Linux (`ubuntu-latest`, `build.yml:5`).

The ledger is `pgvector.ledger`; the graph `pgvector.json` is generated
from it. The trace covers only the four files of the types
(`tests/test_bit.py`, `test_half_vector.py`, `test_sparse_vector.py`,
`test_vector.py`; 63 items), so every edge of the integrations
(`pgvector.asyncpg`, `django`, `peewee`, `pg8000`, `psycopg`, `psycopg2`,
`sqlalchemy`) comes from reading only. No trace edge is rejected.

## Status (for a resumed session)

- Done: every site of the 40 modules is decided (two default rejections
  for `__eq__` and `__repr__`, below); `check.py --write pgvector` reports
  no error; every trace edge is in the graph.
- Scratch (not committed): the compact spec and its merge script are in
  `$TMPDIR/b7-gt-pgvector/` (`spec-core.txt`, `spec-int.txt`,
  `merge.py`); the ledger is the source of truth.
- Left: nothing. The blind audit (`pgvector.audit.md`) and the referee's
  ruling (`b7-ruling-pgvector.md` in the audit records) are
  applied: F1 (+18 outside edges, J10), Q1 (no edge, J13), W1 (J2), F2
  and F3 (the library pins in J4, J6, J7). J2, J4 and J11 are confirmed.

## Architecture, as the ledger uses it

- Four value classes: `Vector` (`vector.py`), `HalfVector` (`halfvec.py`),
  `Bit` (`bit.py`), `SparseVector` (`sparsevec.py`). None has a package
  subclass. They define `__init__`, `__repr__`, `__eq__` and plain
  methods; no `__iter__`, `__len__`, `__bool__`, `__hash__` or property,
  so the only implicit package calls are `__repr__` (formatting) and
  `__eq__` (comparison), and no site gives one a vector (the two default
  rejections). `from_binary` and `_from_parts` make instances with
  `cls.__new__(cls)` (`<builtin>.object.__new__`).
- The integration modules import a library that the test environment
  lacks. Their calls are named as missing modules by access path
  (micro-benchmark "Missing modules"): `asyncpg.Connection.set_type_codec`,
  `django.db.models.Field.__init__` (through `super()`, with
  `<builtin>.super`), `peewee.Field.to_value` (inherited from the stub
  base), `psycopg.types.TypeInfo.fetch`, `psycopg2.extensions.adapt`,
  `sqlalchemy.types.String._cached_literal_processor`, and so on. A
  missing module calls nothing back: the encoders, decoders, adapters,
  loaders, dumpers and casters that the package registers are not
  callees of the registration sites (the libraries call them later, from
  the client's queries). Their bodies keep their own edges (rule A).
- The parameters of the package functions that a library calls (dumpers,
  loaders, adapters, the lambdas of pg8000 and asyncpg) are judged by
  their annotations and by the registration: a dumper registered for
  `Bit` gets `Bit` values.

## Judgement calls

J1. **Missing modules.** asyncpg, Django, peewee, pg8000, psycopg,
psycopg2 and SQLAlchemy are not in the trace environment (the entry
installs no database client). Every call into them is named by access
path; the branches that a database answer or a library version decides
all run (README: "the rule fixes names only"): `pg8000/register.py:11`,
`23`, `27`; `psycopg2/register.py:18`, `23`, `26`;
`psycopg/register.py:18`, `22`; `asyncpg/register.py:30-32`.

J2. **numpy releases (confirmed by the referee, with audit W1).** The
package declares no numpy bound. The release's own statement admits numpy
1.x: `CHANGELOG.md:5` (0.5.1) "Fixed error with `Bit` constructor for
NumPy 1.24-1.26" (django-constance (f): an explicit support statement of
the release gives the admitted versions). The scipy branches agree: the
code branches for scipy before 1.12 and before 1.13 (`sparsevec.py:108`,
`121`, `129`), and scipy 1.11 runs on numpy 1.21 to 1.27. Before numpy
1.25, `np.any`, `np.packbits` and `np.unpackbits` are Python functions at
those public attributes; from 1.25 they are `_ArrayFunctionDispatcher`
objects. The three sites (`bit.py:43:53`, `51:37`, `70:29`) name both, as
itables names `numpy.where` (3 edges `numpy.any`, `numpy.packbits`,
`numpy.unpackbits` beside the traced
`numpy._ArrayFunctionDispatcher.__call__`). `np.frombuffer` and `np.zeros`
are C functions at `numpy.frombuffer` and `numpy.zeros` in every release.

J3. **numpy arrays (B4).** The constructors annotate the array as
`np.ndarray[...]` (the alias `_utils.ndarray` under `TYPE_CHECKING`, read
as a string annotation) and check it with `isinstance(value,
numpy.ndarray)`. Method calls on it are named `numpy.ndarray.astype`,
`.tobytes`, `.tolist`. ndarray subclasses that a client can pass
(`numpy.matrix`, `numpy.memmap`, masked arrays) are not named: the
annotation names the concrete class (B4), and the docs show only
`np.array(...)`.

J4. **SciPy sparse receivers (`sparsevec.py:106:50`; confirmed by the referee).**
`_from_sparse(arr)` receives what `SparseVector.__init__` admits after
`is_sparse_array`: an instance of `scipy.sparse.sparray` or `spmatrix`
(annotation and `isinstance`). These two are base classes without
instances; the concrete classes are the seven formats as array and as
matrix (bsr, coo, csc, csr, dia, dok, lil). By the jsonpickle ruling (e)
("one name per admitted concrete receiver class"), `arr.tocoo(copy=False)`
names all fourteen `scipy.sparse.<format>_<array|matrix>.tocoo`. The
trace confirms five (coo_array, coo_matrix, csr_array, csr_matrix,
dok_array: the tests pass them). The README documents `coo_array` only
(`README.md:778`). The narrower reading (only the documented `coo_array`
and the tested formats, the other trace edges rejected as the tests' own
values) would remove 9 edges. `tocoo` returns a `coo_array` or a
`coo_matrix`, so `.copy()` and `.sum_duplicates()` (110:31, 111:33) name
those two. The referee confirmed J4. The set was first written from my
knowledge of scipy 1.11 to 1.16. The auditor then checked it against the
pinned scipy 1.18.1 (`deps/pgvector/scipy-1.18.1/`, sdist
`scipy-1.18.1.tar.gz`, SHA-256 `52c4b742...2747307`, as
`deps/pgvector/README.md` records): no other class derives from `sparray`
or `spmatrix`, and every format's `tocoo` returns a `coo_array` or
`coo_matrix` (`pgvector.audit.md`, "Scipy formats").

J5. **Byte order.** `sys.byteorder == 'big'` (`vector.py:55`, `79`;
`halfvec.py:57`, `81`): the release's own test job establishes Linux
(`runs-on: ubuntu-latest`, `.github/workflows/build.yml:5`), as the
batch-7 rulings require for a platform. The release declares no PyPy
support, so the admitted implementation is CPython. On CPython on
little-endian Linux the little-endian side runs, with its calls (`array`,
`byteswap`); the trace has them. The big-endian side makes no call
(`value = self._value`; no `byteswap` in `from_binary`), so whether a
big-endian platform is admitted changes no edge.

J6. **Library bases (README, "the exception").** Package classes derive
from Django's `Field`, `Func`, `PostgresIndex`, `CreateExtension`,
`forms.CharField`, `forms.TextInput`; from peewee's `Field`; from
psycopg's `Dumper` and `Loader`; from SQLAlchemy's `UserDefinedType`,
`TypeDecorator` and their `Comparator`; and from SQLAlchemy's
`ReturnTypeFromArgs` (`avg`). The package calls these definitions only
through `super()` (`__init__`, `deconstruct`, `formfield`, `to_python`,
`format_value`) and through the inherited `value_from_object` and
`to_value`. None of the library code that these calls reach calls a
method that the package overrides; `Field.formfield` instantiates the
package form class, whose first `__init__` is Django's. So no package
callee is added, and the calls keep their stub names.

Library code read, never installed, imported or run:

- Django 4.2.30 and 6.1.2, text sources of the wheels in
  `deps/django-constance/django-4.2.30/` and `django-6.1.2/`. The Django
  6.1.2 wheel is the pin of `requirements/django-constance.txt`, SHA-256
  `141efee6ec64d1db6db90683bf734c550102450f444fb099063b0be1bd27d991`. The
  Django 4.2.30 tree is the content of `django-4.2.30-py3-none-any.whl`,
  SHA-256
  `4d07aaf1c62f9984842b67c2874ebbf7056a17be253860299b93ae1881faad65`
  (verified against PyPI on 2026-11-23, every file on disk identical:
  `deps/django-constance/README.md`). I read `Field.__init__`, `deconstruct`, `formfield`,
  `value_from_object`, `forms.Field.__init__`, `CharField.__init__`,
  `to_python`, `Widget.__init__`, `format_value`, `Input.__init__`,
  `Func.__init__`, `_parse_expressions`, `BaseExpression.__init__`,
  `Value.__init__`, `Index.__init__`, `deconstruct` and
  `CreateExtension.__init__`.
- After I finished, the lead put the other libraries on disk under
  `deps/pgvector/` (each the newest release uploaded before pgvector
  0.5.1; sdists checked against PyPI's JSON; versions and SHA-256 from
  `deps/pgvector/README.md`): SQLAlchemy 2.1.4
  (`7bd7ad604487daa7eab8716471c29a7185f17b5287ce73bb7bc79fea050d8cfd`),
  peewee 4.5.3
  (`434576afaf806428a01f84af74c42fde59372c4f6a6eba26d9b5372113344a8a`),
  psycopg 3.3.6
  (`c081f2250df751a943036e42db6df4571c66cd0aabe8291a7a506512b12007d2`),
  psycopg2 2.9.13
  (`d36784fc2dae69523ba4b79c7d1d1b4d6e83e87836874f111262f4db940b16a6`),
  asyncpg 0.32.0
  (`45e64e56714d888330b884aad1dfb363d0bf43fb343e3d1a8968525f3bade478`),
  pg8000 1.31.5
  (`46ebb03be52b7a77c03c725c79da2ca281d6e8f59577ca66b17c9009618cae78`).
  The auditor checked every one of the 47 package classes with a library
  base against them (Django, peewee, psycopg, SQLAlchemy) and found no
  call-back at a package site and no class-creation hook that calls
  package code (`pgvector.audit.md`, "Library bases"). asyncpg, pg8000
  and psycopg2 give the package no base class.

J7. **psycopg's `Buffer` (`psycopg/vector.py:37:44`, `halfvec.py:30:48`,
`sparsevec.py:30:50`).** A loader gets `data: Buffer`; psycopg documents
`Buffer` as bytes, bytearray or memoryview: `Buffer: TypeAlias =
Union[bytes, bytearray, memoryview]` in psycopg 3.3.6 (`psycopg/abc.py:27`;
`deps/pgvector/psycopg-3.3.6/`, SHA-256 in J6), which the auditor
confirmed. A memoryview is converted with `tobytes()` first, so
`data.decode` names `<builtin>.bytes.decode` and
`<builtin>.bytearray.decode`.

J8. **Django releases (`django/extensions.py:8`).** No version is
declared; the `else` branch exists for Django before 6, so both run.

J9. **Lambdas of pg8000 and asyncpg.** pg8000 calls an out adapter with
values of the class that it was registered for, so `lambda v:
v.to_text()` registered for `Vector` calls `Vector.to_text`
(`pg8000/register.py:14:58`; also `24:66`, `28:68`). The lambda for
`np.ndarray` makes a `Vector` (`19:63`). The asyncpg encoders convert any
value that is not already of the class (`asyncpg/register.py:9`, `18`,
`26`).

J10. **Missing-module access paths of parameters (the referee's ruling
on audit F1, adopted by the lead).** The rule: "Preserve each
missing-module access path carried by an admitted package argument flow,
alongside annotation-derived paths where rule B independently admits
them. An annotation constrains admitted types; it does not rename an
admitted stub value when package code forwards it." So a site keeps both:

- the annotation's path, because the four `register_*_info` functions of
  `pgvector.psycopg` are public (C) and a client can pass any value of the
  annotation: `context: BaseConnection[Any]` gives
  `psycopg.BaseConnection.adapters.register_dumper` and
  `register_loader`; `info: TypeInfo` gives
  `psycopg.types.TypeInfo.register`;
- the paths of what the package's own callers pass (B: what the package's
  calls pass counts in full): `register_vector` passes a
  `psycopg.Connection` and `register_vector_async` a
  `psycopg.AsyncConnection` (`psycopg/register.py:10`, `26`), so the
  adapter sites add `psycopg.Connection.adapters.register_dumper`,
  `register_loader` and `psycopg.AsyncConnection.adapters.register_dumper`,
  `register_loader` (14 edges at 16 sites: `vector.py:57` to `62`,
  `halfvec.py:48` to `51`, `sparsevec.py:48` to `51`, `bit.py:33`, `34`);
  both pass the result of `TypeInfo.fetch`, an instance of the stub
  `psycopg.types.TypeInfo.fetch`, so `info.register(context)` adds
  `psycopg.types.TypeInfo.fetch.register` (4 edges: `vector.py:50:18`,
  `halfvec.py:41:18`, `sparsevec.py:41:18`, `bit.py:26:18`).

The ruling added these 18 outside edges (482 to 500). Reading psycopg's
implementation does not replace these paths with `AdaptersMap`. The same
rule gives psycopg2's `register_vector` (`psycopg2/register.py:10-16`)
two paths: `conn` is the argument (annotated `connection`) or the
attribute `connection` of a cursor argument, so `conn.cursor`,
`cur.execute` and `cur.fetchall` name
`psycopg2.extensions.connection.cursor...` and
`psycopg2.extensions.cursor.connection.cursor...`. Other annotated
parameters have no package caller that passes another stub value:
`conn: Connection` gives `asyncpg.Connection.set_type_codec` and
`pg8000.native.Connection.run`.

J11. **Subscripted stub bases (`sqlalchemy/*.py`).** `class
VECTOR(UserDefinedType[Any])` and `class
Comparator(TypeEngine.Comparator[Any])` subscript a stub class. The README
gives the subscript of a missing-module value no stub path, but a
subscripted generic class in a class's bases resolves to the class
(`__mro_entries__`; the README's site rule reads `class String(Field[str])`
as the base `Field`). So `super().__init__()` names
`sqlalchemy.types.UserDefinedType.__init__`, and `self.op(...)` names
`sqlalchemy.types.TypeEngine.Comparator.op` (`TypeDecorator.Comparator.op`
in `bit.py`). The call of what `op` returns, `self.op(...)(other)`, is a
call of an instance of a stub and has the same name (pyrate-limiter
ruling 13). In `psycopg`, `BaseConnection[Any]` in an annotation is read
the same way (J10). The referee confirmed J11: a parameterized generic
used as a base keeps its origin's stub path for inheritance; ordinary
subscript results get no path.

J12. **Value sites (23).** `cls(...)` in `from_text` (`bit.py:81`,
`halfvec.py:66`, `vector.py:64`): the class or a client subclass, so the
class's own `__init__`. `cls(value)` in the private `_to_db`
(`halfvec.py:102`, `sparsevec.py:182`, `vector.py:100`): the package calls
it only on the class itself. The 17 SQLAlchemy sites call stub values
(J11).

J13. **A disabled Django form field (`django/sparsevec.py:61:33`; audit
Q1, the referee's ruling, adopted by the lead).** With `disabled=True`,
Django's form cleaning takes the field's initial value (Django 6.1.2
`forms/fields.py:271`; 4.2.30 `_clean_fields`), and
`SparseVectorFormField.to_python` passes it to `CharField.to_python`,
which tests it against `empty_values` and calls `str(value)`. An initial
`SparseVector` (as `tests/test_django.py:434` renders it) would so call
`SparseVector.__eq__` and `__repr__`. The ruling: "The base-class
exception exposes callbacks made by the reached library implementation,
including implicit calls on admitted arguments, but does not widen the
definition's input roles. A package value established for rendering is
not thereby admitted for cleaning through otherwise opaque
client-framework dispatch." The tests give the SparseVector only for
rendering; cleaning gets strs. So the site has no edge to
`SparseVector.__eq__` or `SparseVector.__repr__` (the defaults decide
both), and keeps `django.forms.CharField.to_python`. No change.

## Default rejections

- `Bit.__eq__`, `HalfVector.__eq__`, `SparseVector.__eq__`,
  `Vector.__eq__`: 122 sites each. No compared, searched or subscripted
  value is a package vector; the explicit site under the default is
  `set(value)` (`bit.py:29:25`), on a str.
- `Bit.__repr__`, `HalfVector.__repr__`, `SparseVector.__repr__`,
  `Vector.__repr__`: 28 sites each (f-strings, `str()`, `format()`, `%`):
  ints, floats, strs, lists, dicts and an exception.
