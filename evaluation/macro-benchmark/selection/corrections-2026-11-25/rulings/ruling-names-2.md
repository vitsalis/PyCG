The question is whether an outside class’s canonical method name follows
a public alias that is stable, exists only in some configurations, or
appears in later versions—and how those distinctions change avro,
Sublist3r and the other supplied hash-related ground truths.

**A direct public class alias takes precedence in each admitted
implementation, version and configuration where that attribute actually
holds the receiver’s class.** This applies equally to stable,
configuration-dependent and version-dependent aliases; a factory
returning instances is not a class alias. Without a public class alias,
use the defining extension’s exported type attribute, then the existing
type-name fallback where that attribute is unavailable. Choose one name
per class in each configuration, and take the union across admitted
configurations. An alias in one configuration does not rename receivers
in another configuration where that attribute holds a factory.

This settles the naming rule. It does **not** establish every proposed
deletion at avro’s generic `hashlib.new()` site: the supplied sources
leave a configuration question described below.

For the dependency citations below, `C10` means
`deps/cpython/3.10.22/` and `P10` means
`deps/pypy/pypy3.10-v7.3.19/`, under the supplied dependency directory.

At **avro `schema.py:338:24`**, every edge below has caller
`avro.schema.Schema.fingerprint`. The source constructs the receiver
through `hashlib.new` at
[schema.py:337](evaluation/macro-benchmark/projects/avro/avro/schema.py:337);
the current targets appear at
[avro.ledger:4163](evaluation/macro-benchmark/ground-truth/avro.ledger:4163).

| Add target | Existing target | Disposition of existing target | Evidence |
|---|---|---|---|
| `hashlib.blake2b.digest` | `_blake2.blake2b.digest` | Remove | H1 |
| `hashlib.blake2s.digest` | `_blake2.blake2s.digest` | Remove | H1 |
| `hashlib.md5.digest` | `_md5.md5.digest` | Full-union deletion unresolved | H2 |
| `hashlib.sha224.digest` | `_sha256.sha224.digest` | Full-union deletion unresolved | H2 |
| `hashlib.sha256.digest` | `_sha256.sha256.digest` | Full-union deletion unresolved | H2 |
| `hashlib.sha384.digest` | `_sha512.sha384.digest` | Retain for CPython 3.10–3.11 | H2, earlier C-type ruling |
| `hashlib.sha512.digest` | `_sha512.sha512.digest` | Full-union deletion unresolved | H2 |
| `hashlib.sha3_224.digest` | `_sha3.sha3_224.digest` | Full-union deletion unresolved | H3 |
| `hashlib.sha3_256.digest` | `_sha3.sha3_256.digest` | Full-union deletion unresolved | H3 |
| `hashlib.sha3_384.digest` | `_sha3.sha3_384.digest` | Full-union deletion unresolved | H3 |
| `hashlib.sha3_512.digest` | `_sha3.sha3_512.digest` | Full-union deletion unresolved | H3 |

The evidence for those decisions is:

- **H1:** `C10/Lib/hashlib.py:78–80,102–105,126–129,257–261`
  excludes BLAKE2 from OpenSSL selection and binds the builtin classes
  publicly. `C10/Modules/_blake2/blake2module.c:85,107` exports the
  actual types. PyPy follows the same selection
  (`P10/lib-python/3/hashlib.py:79–81,103–106,127–130`);
  its classes are established at
  `P10/lib_pypy/_blake2/__init__.py:157–166`.
  Thus the two private BLAKE2 names disappear.
- **H2:** PyPy’s
  [hashlib.py:92](deps/pypy/pypy3.10-v7.3.19/lib-python/3/hashlib.py:92)
  selects the builtin MD5 and SHA2 constructors in fallback
  configurations. These are classes:
  `P10/pypy/module/_md5/moduledef.py:22`,
  `P10/lib_pypy/_sha256.py:218,242`, and
  `P10/lib_pypy/_sha512.py:245,269`.
  CPython’s corresponding public attributes remain factories, so its
  exported-type names remain independently necessary.
- **H3:** `C10/Lib/hashlib.py:106–111,126–141,257–261`
  binds the builtin SHA3 constructors publicly when selected;
  [sha3module.c:763](deps/cpython/3.10.22/Modules/_sha3/sha3module.c:763)
  creates and exports the four types at lines 775–778. PyPy defines
  the corresponding classes at
  `P10/lib_pypy/_sha3/__init__.py:100,105,110,115`.
  They remain classes throughout the supplied admitted versions.

**Why the conditional deletions remain unresolved:** CPython chooses a
named OpenSSL constructor by probing with `usedforsecurity=False`, but
avro calls `hashlib.new()` with the security-default setting. That call
can catch `ValueError` and construct a builtin without rebinding the
named public attribute.
See [hashlib.py:126](deps/cpython/3.10.22/Lib/hashlib.py:126)
and `:152–166`. The two settings use different OpenSSL property lookups,
at [_hashopenssl.c:331](deps/cpython/3.10.22/Modules/_hashopenssl.c:331).
Therefore, a builtin result does not itself prove that the corresponding
`hashlib` attribute holds its class.

For PyPy’s MD5/SHA2 names, the ordinary fallback witnesses use the public
aliases. A separate potential path is successful empty construction at
import followed by a data-processing `ValueError`; PyPy explicitly raises
one on failed `EVP_DigestUpdate`
(`P10/lib_pypy/_hashlib/__init__.py:124–125`).
The inputs establish neither an admitted witness for these mismatches
nor their impossibility. OpenSSL provider/configuration evidence,
including the relevant initialization and update behaviour, would decide
the remaining deletions. The unresolved entries above are **not findings
that the private targets have a verified retention witness**.

At **Sublist3r**, add these two edges and remove none from the
cross-version union:

| Site | Caller | Add | Retain for earlier versions |
|---|---|---|---|
| `sublist3r.py:611:26` | `sublist3r.DNSdumpster.check_host` | `threading.Lock.acquire` | `_thread.LockType.acquire` |
| `sublist3r.py:621:26` | `sublist3r.DNSdumpster.check_host` | `threading.Lock.release` | `_thread.LockType.release` |

The receiver is the default lock constructed at
[sublist3r.py:260](evaluation/macro-benchmark/projects/Sublist3r/sublist3r.py:260),
stored at `:264`, through the initializer called at `:604`.
CPython 3.13 exports `Lock` publicly, binds
`_LockType = _thread.LockType`, and assigns `Lock = _LockType`
([threading.py:28](deps/cpython/3.13.18/Lib/threading.py:28),
`:38`, `:120`); 3.14 and 3.15 preserve that alias.
CPython 3.12 instead assigns the `allocate_lock` factory
(`cpython/3.12.16/Lib/threading.py:37,122`).
Thus 3.13+ uses only the public method names, while older admitted
versions justify the `_thread.LockType` names.

The **direct named-constructor sites** have these further definite
changes. Unlike `hashlib.new()`, their OpenSSL constructors do not perform
the independent builtin fallback discussed above.

| Caller | Site or sites | Remove | Add |
|---|---|---|---|
| `avro.protocol.Protocol.__init__` | `protocol.py:108:59` | `_md5.md5.digest` | `hashlib.md5.digest` |
| `pymysql._auth.ed25519_password` | `_auth.py:87:40`, `93:49`, `103:48` | `_sha512.sha512.digest` | `hashlib.sha512.digest` |
| `pymysql._auth.scramble_caching_sha2` | `_auth.py:200:41`, `201:35`, `202:43` | `_sha256.sha256.digest` | `hashlib.sha256.digest` |
| `markdown2._hash_text` | `lib/markdown2.py:150:70` | `_sha256.sha256.hexdigest` | `hashlib.sha256.hexdigest` |

These calls are visible at
[protocol.py:108](evaluation/macro-benchmark/projects/avro/avro/protocol.py:108),
[_auth.py:87](evaluation/macro-benchmark/projects/pymysql/pymysql/_auth.py:87),
[_auth.py:200](evaluation/macro-benchmark/projects/pymysql/pymysql/_auth.py:200),
and [markdown2.py:150](evaluation/macro-benchmark/projects/markdown2/lib/markdown2.py:150).
H2 establishes their PyPy class aliases. Both pymysql and markdown2 admit
PyPy (`pymysql.md:5–7`; `markdown2.md:354,378–380`).
CPython receiver contributions still require the exported-type names
under the earlier ruling; some current pymysql and markdown2 entries
already omit those names, an existing conformity issue.

Pymysql’s SHA1 calls at `_auth.py:33–38` acquire no `hashlib.sha1` method
names: PyPy’s `sha1` is a factory for class `_sha1.sha`
(`P10/lib_pypy/_sha1.py:129,359`), and CPython likewise uses a factory.
The sweep found no BLAKE2 or SHA3 method targets outside avro. The other
hash-bearing ground truths—flit-core, bottle, Sublist3r and
websocket-client—use CPython SHA1/SHA256 receivers and gain no public
class-alias names from this ruling. Constructor-call names such as
`hashlib.sha256` are unchanged.

This ruling **follows and clarifies**
[b8-ruling-c-type-names-1.md:5](evaluation/macro-benchmark/selection/batch-8-proposal/rulings/b8-ruling-c-type-names-1.md:5):
its public-alias precedence applies to actual bindings in configurations,
not merely to stable aliases. Its table’s blanket retention of private
hash names cannot override that precedence where a public class alias
exists. The
[version-and-configuration clarification](evaluation/macro-benchmark/README.md:2114)
already requires the union that adds Sublist3r’s newer names;
[Sublist3r judgement 9](evaluation/macro-benchmark/ground-truth/Sublist3r.md:182)
correctly identifies one class but incorrectly suppresses its later
canonical spelling.

The
[pyfiglet/path/structlog ruling](evaluation/macro-benchmark/README.md:2749)
still governs private classes **without** a public path. This decision
changes names of already-admitted explicit calls; it admits no new
receivers, implicit outside edges or missing-library alias resolution.
No files were edited, packages run or imported, or analysis-tool outputs
consulted.