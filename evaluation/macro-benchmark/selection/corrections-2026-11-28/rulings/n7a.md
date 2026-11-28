# N7a. path: does `read_hash`'s docstring admit every hashlib name?

Adopted by the lead in place of a referee, maintainer's instruction of
2026-11-28. Raised by the audit of the corrections of 2026-11-28
(`../audits/corrections-2026-11-28.audit.md`, N7a). Read at `8e1db387`.
Paths are relative to `evaluation/macro-benchmark/`; a package's files are
cited from its root under `projects/<name>/`, its ground truth is under
`ground-truth/`, and `C9` to `C15`, `P9`, `P10`, `P11` are the batch-8
dependency sources `deps/cpython/3.9.25/` to `3.15.2/` and
`deps/pypy/pypy3.9-v7.3.16/`, `pypy3.10-v7.3.19/`, `pypy3.11-v7.3.23/`.

**1. The question.** path v17.1.1, `path/__init__.py`:

| Site | Caller | Call | Callees at `8e1db387` (`path.ledger:993-1024`) |
|---|---|---|---|
| 979:21 | `path.Path._hash` | `m.update(chunk)`, `m = hashlib.new(hash_name)` (977) | `_hashlib.HASH`, `_md5.MD5Type`, `_md5.md5`, `hashlib.md5`, `_sha1.SHA1Type`, `_sha1.sha` (`.update`) |
| 990:44 | `path.Path.read_hash` | `self._hash(hash_name).digest()` | the same six (`.digest`) |
| 1000:47 | `path.Path.read_hexhash` | `self._hash(hash_name).hexdigest()` | the same six (`.hexdigest`) |

Judgement J6 (`path.md`) read: "The hash names in scope are `md5`
(`read_md5`, the tests) and `sha1` (the docstring of `_hash`)." The public
methods document their parameter otherwise:

- `read_hash` (982-990) and `read_hexhash` (992-1000): "List of supported
  hashes can be obtained from :mod:`hashlib` package." (985, 995).
  `docs/api.rst` renders both with `automodule:: path` and `:members:`.
- `_hash` (971-980, private): "`hash_name` should be a hash algo name (such
  as ``'md5'`` or ``'sha1'``) that's available in the :mod:`hashlib`
  module." (974-975).
- `read_md5` passes `'md5'` (969); the one test passes `'md5'`
  (`tests/test_path.py:256`).

Does B2 make every name of hashlib's list a value of `hash_name`; which
list; what callees does each site gain on each admitted runtime; must J6
yield?

**2. The ruling.** **A public method's docstring that refers its string
parameter to the list of hash names that hashlib supports names every such
name as a value of that role (B2, the avro J5 precedent); the role is the
names that `hashlib.new` accepts on an admitted build, of which only the
guaranteed names change a callee.** path's `read_hash` and `read_hexhash`
admit them, and `_hash` takes them through its package callers; judgement
J6 yields. This does not admit names that a client string selects where no
document, test or package call states them (the aiocache rule stands), and
adds no edge where a call cannot bind (SHAKE `digest()` and
`hexdigest()`).

Effect, path only, all outside, none removed:

| Site | Callees added |
|---|---|
| 979:21 `.update` | the 26 receivers below, and `_hashlib.HASHXOF`, `hashlib.shake_128`, `hashlib.shake_256`, `_sha3.shake_128`, `_sha3.shake_256` |
| 990:44 `.digest` | the 26 receivers |
| 1000:47 `.hexdigest` | the 26 receivers |

The 26 receivers: `_sha256.SHA224Type`, `_sha256.SHA256Type`,
`_sha512.SHA384Type`, `_sha512.SHA512Type`, `_sha512.sha384`,
`_sha2.SHA224Type`, `_sha2.SHA256Type`, `_sha2.SHA384Type`,
`_sha2.SHA512Type`, `hashlib.sha224`, `hashlib.sha256`, `hashlib.sha384`,
`hashlib.sha512`, `_sha256.sha224`, `_sha256.sha256`, `_sha512.sha512`,
`hashlib.blake2b`, `hashlib.blake2s`, `hashlib.sha3_224`,
`hashlib.sha3_256`, `hashlib.sha3_384`, `hashlib.sha3_512`,
`_sha3.sha3_224`, `_sha3.sha3_256`, `_sha3.sha3_384`, `_sha3.sha3_512`
(`_sha512.sha384` is CPython 3.10 and 3.11's type name and PyPy's class,
one string).

- 83 site-callee entries and 83 graph edges (31 for `Path._hash`, 26 each
  for `read_hash` and `read_hexhash`; none was in `path.json`): 680 to 763
  edges, 422 inside, 341 outside.
- J6 is rewritten and says that the earlier reading yields; the ledger
  note at 979:21 gives the names per runtime, and the notes at 990:44 and
  1000:47 say why no SHAKE class is there; `path.md`, "Corrections of
  2026-11-28", records it.
- `benchmark-rules.md`: one bullet in "Rulings for the corrections of
  2026-11-28"; no convention text changes.

**3. What the rules say.**

- Scope rule B2: "The values of a parameter, and of what is fed from it,
  are client objects, the values that the package defines for that
  parameter's role, and the package's defaults. A package value is in
  scope for a role when ... the documentation names it for that role ...
  or when the package's own code, tests or documented examples pass it
  there." And: "A string of the client that selects a method of an outside
  object that the package made names the methods that the package, its
  tests and its documented examples pass (aiocache: the command of `raw`,
  `memory.py:92`)."
- Rule B, private functions: "For a private function or method, which
  clients do not call, they are what the package's own calls of it pass."
- Clarification "Concrete types (B4)": "argument binding failure before
  entry gives no edge."
- Scope rules preamble: "A project judgement records how its ledger
  applies the global rules and cannot override them."
- Precedent, avro J5 (`avro.md`, "J5. Hash objects"):
  `Schema.fingerprint`'s docstring ("any algorithm supported by hashlib
  (as can be referenced with `hashlib.algorithms_guaranteed`) can be
  specified") admits every name of `hashlib.algorithms_guaranteed` at
  `hashlib.new` (`schema.py:337`).
- Names: batch 8, "A C type exported under a module attribute other than
  its type name" (`b8-ruling-c-type-names-1.md`); corrections of
  2026-11-25, "Public class aliases by configuration"
  (`../../corrections-2026-11-25/rulings/ruling-names-2.md`, H1 BLAKE2,
  H2 PyPy's MD5 and SHA-2, H3 SHA-3) and the lead's decision there to keep
  the private names beside the aliases at `hashlib.new(name)`;
  clarification "Versions and configuration" (hashlib's documented
  fallback counts). These rulings name the classes; they do not say which
  names reach `hashlib.new`.

The rules decide it, through B2's documentation clause. The public
docstrings of `read_hash` and `read_hexhash`, rendered in the API
documentation, name the role's values by reference to one closed,
documented list, the hashes that hashlib supports, as avro's docstring
did; avro J5 read such a sentence as admitting every name of that list.
The aiocache sentence is not in play: it governs "a string of the client
that selects a method of an outside object that the package made", and
`hash_name` selects no method; it is the argument of a library factory,
`hashlib.new`, which selects the class of the object it makes. The ruling
rests on B2's documentation clause alone; B5 is not part of it.

`_hash` is private: its `hash_name` is what `read_md5`, `read_hash` and
`read_hexhash` pass (`'md5'` and the two public parameters), so the set
reaches 979:21 too. J6 rested on the code, the test and `_hash`'s examples
("such as"), which are the minimum, not the role; it yields.

**4. The evidence.**

- path admits CPython 3.9 and later and PyPy 3.9 and later (`path.md`,
  "Supported versions and platforms", "PyPy").
- Which list. hashlib's own documentation: the named constructors md5 to
  shake_256 "are guaranteed to exist. See the algorithms_guaranteed and
  algorithms_available attributes to find out what algorithm names can be
  passed to new()" (`C9/Lib/hashlib.py:14-19`). `algorithms_guaranteed` is
  the 14 names of `__always_supported`; `algorithms_available` adds
  `_hashlib.openssl_md_meth_names` on an OpenSSL build (`C9:173-174`,
  `C15:193-194`). A name outside the guaranteed set goes only to
  `_hashlib.new` (`C9:160`, `C15:180`), which makes `_hashlib.HASH`, or on
  CPython `_hashlib.HASHXOF` for an XOF digest
  (`C9/Modules/_hashopenssl.c:891-897`); PyPy's `_hashlib.new` makes
  `HASH`, or with non-empty data on 3.11 a `_OneShotHash`
  (`P11/lib_pypy/_hashlib/__init__.py:38-53`), and path passes no data
  (977). Both classes are reached by guaranteed names too, so the two
  lists give the same callees.
- What each guaranteed name makes. `hashlib.new(name)` on an OpenSSL
  build calls `_hashlib.new` and, on `ValueError`, the builtin constructor
  (`P11/lib-python/3/hashlib.py:152-166`, the same in CPython); without
  `_hashlib` it is `__py_new`. BLAKE2 never comes from OpenSSL
  (`__block_openssl_constructor`). The builtin classes, each checked in
  the sources:

  | Hash | CPython 3.9 | CPython 3.10, 3.11 | CPython 3.12 to 3.15 | PyPy 3.9 to 3.11 |
  |---|---|---|---|---|
  | sha224, sha256 | exported as `_sha256.SHA224Type`, `SHA256Type` (`sha256module.c:718`, `:720`; type names `_sha256.sha224`, `sha256`, `:522`, `:556`) | the same (`:720`, `:725` of 3.10.22; `:723`, `:728` of 3.11.18) | `_sha2.SHA224Type`, `SHA256Type` (`sha2module.c` `.name` `:539`, `:547`, `PyModule_AddType` `:852`, `:855` of 3.12.16; `:864`, `:867` of 3.15.2) | classes `_sha256.sha224`, `sha256` (`lib_pypy/_sha256.py:230`, `:206` of P9; `:242`, `:218` of P10, P11), bound as `hashlib.sha224`, `sha256` by the fallback (H2) |
  | sha384, sha512 | `_sha512.SHA384Type`, `SHA512Type` (`sha512module.c:776`, `:778`) | SHA-384 by its type name `_sha512.sha384`; SHA-512 `_sha512.SHA384Type` (the export is overwritten, `:782`, `:788` of 3.10.22; `:785`, `:791` of 3.11.18) | `_sha2.SHA384Type`, `SHA512Type` (`:555`, `:563`, `:858`, `:861` of 3.12.16; `:870`, `:873` of 3.15.2) | classes `_sha512.sha384`, `sha512` (`_sha512.py:258`, `:234` of P9; `:269`, `:245` of P10, P11), bound as `hashlib.sha384`, `sha512` |
  | blake2b, blake2s | always bound as `hashlib.blake2b`, `blake2s` (H1) | same | same | same |
  | sha3_224 to sha3_512 | types `_sha3.sha3_*` (`_sha3/sha3module.c:559-562`, exported `:731-734`), bound as `hashlib.sha3_*` by the fallback (H3) | same (`PyModule_AddType`, `:770` of 3.10.22, `:617` of 3.11.18) | same (`sha3module.c:580-588` of 3.12.16, `:666-674` of 3.15.2) | classes `_sha3.sha3_*` (`_sha3/__init__.py:88-100` of P9, `:100-115` of P10, `:103-118` of P11), bound as `hashlib.sha3_*` |
  | shake_128, shake_256 | types `_sha3.shake_*` (`:692-693`, exported `:741-742`), bound as `hashlib.shake_*`; OpenSSL: `_hashlib.HASHXOF` (`_hashopenssl.c:860`, `PyModule_AddType` `:2208`) | same; `HASHXOF` `:2165` of 3.10.22, `:2166` of 3.11.18 | same; `HASHXOF` `:931`, `:2280` of 3.12.16, `:2809` of 3.15.2 | classes `_sha3.shake_*` (`:104`, `:108` of P9; `:120`, `:125` of P10; `:123`, `:128` of P11); OpenSSL: `_hashlib.HASH` |

  Where the fallback binds a builtin class to the public hashlib
  attribute, the alias names it (`ruling-names-2.md`); at
  `hashlib.new(name)` the private name stays beside it (the lead's
  decision at avro `schema.py:337`). CPython's SHA-2 attributes hold
  factories, so the exported-type names stay. These are avro's names at
  `schema.py:338:24` (`avro.ledger`), plus `_sha512.SHA512Type` for
  CPython 3.9, which avro does not admit.
- SHAKE digests. `digest` and `hexdigest` of every SHAKE class take a
  required `length`: `_sha3.shake_128.digest` (`METH_O`,
  `C9/Modules/_sha3/clinic/sha3module.c.h:121`;
  `C15/Modules/clinic/sha3module.c.h:183`), `_hashlib.HASHXOF.digest`
  (`C9/Modules/_hashopenssl.c:720`, `C15:1111-1119`), PyPy
  `_shake.digest(self, length)` (`P9/lib_pypy/_sha3/__init__.py:66`,
  `:84`; `P11:81`, `:99`). path calls them without arguments (990:44,
  1000:47): the binding fails before entry, so no edge, as in avro J5.
  `update` binds for every class.
- The trace (`dynamic/path.json`, CPython 3.14.10 with OpenSSL) runs
  `read_md5` and `read_hexhash('md5')` only (`tests/test_path.py:251`,
  `256`) and records `_hash -> _hashlib.HASH.update`,
  `read_hash -> _hashlib.HASH.digest` and
  `read_hexhash -> _hashlib.HASH.hexdigest`, all in the graph before and
  after. It records none of the 83 added edges, as the tests' one hash
  name gives, and no edge at these callers that the ground truth lacks; no
  trace edge is rejected or changes. path has no other trace.

**5. Against.** The aiocache sentence lists three sources for a client
string (package code, tests, documented examples), and a reference to
another module's list is none of them; "List of supported hashes can be
obtained from hashlib" tells the reader where to look, not which values
path supports, and `_hash` gives only md5 and sha1. Against that: the
aiocache sentence covers a client string that selects a method of an
outside object that the package made, and `hash_name` selects no method:
it is the argument of a library factory, `hashlib.new`, so B2's general
documentation clause decides, and avro J5 already read the same kind of
sentence as naming the whole list.
A second argument: `_hash` is annotated `-> hashlib._Hash`, which names
the OpenSSL class only. The ground truth already names the builtin MD5 and
SHA-1 classes at these sites under the 2026-11-15 "Versions and
configuration" clarification, and Q5 adopted that an annotation does not
decide what a library returns.
