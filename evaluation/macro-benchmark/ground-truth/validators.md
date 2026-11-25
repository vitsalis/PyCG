# validators: judgements of the ground truth

Release 0.36.0 (commit `e2e49fb`). Analysed source: `validators/` under the
root `src` (32 modules, 96 functions, no lambdas, 4 classes).
`src/__init__.py` lies outside the package. `pyproject.toml:35` sets
`requires-python = ">=3.11"`; the classifiers name CPython only and
"Operating System :: OS Independent". So the supported runtimes are CPython
3.11 and later, on every platform. The package has no `assert` and no
`__debug__` code, so `-O` and `-OO` change no edge.

The ledger is `validators.ledger`; the graph `validators.json` is generated
from it. The graph has 422 edges (152 inside, 270 outside; 424, 152 and 272 before Codex audit round 1). The trace has
394 edges, and the graph has all of them but the nine `lru_cache` wrapper
spellings that `validators.rejected.json` rejects as naming artefacts
(Corrections of 2026-11-25). 37 edges come from reading only, 11 inside
and 26 outside (`validators.added.json`). The tests run 94 of the 96 functions; the two
others are `uri._file_url` and `uri._ipfs_url`.

The writer read every function of the package, the tests (for the values
that the tests pass) and `docs/` (for documented roles). No analysis tool
ran on the package, and nothing of it was run or imported. The lead then
gave read-only sources of the pinned test dependencies (eth-hash 0.8.0 and
pycryptodome 3.24.0, unpacked from the hash-checked wheels); the writer read
eth-hash there and ran nothing of it (see "Outside names verified in the
dependency sources").

## Default rejections

| Candidate | Sites decided | Reason (short) | Accepted explicitly at |
|---|---|---|---|
| `ValidationError.__bool__` | 168 | the tested value is a str, bool, int, None, container, `re.Match`, an ipaddress or uuid object, or a client value | the 19 truth sites that test a result of a wrapped validator, and `bool(...)` at `email.py:75` and `length.py:45` (J2) |
| `AbsMax.__ge__`, `AbsMin.__le__` | 32 each | the comparisons compare ints and strs | `between.py:74` (added by hand) and `79` (J6) |
| `ValidationError.__repr__`, `__str__` | 38 each | `%` is a modulo of ints; formatted values and `str()` arguments are ints, strs and the caught `ValueError`, `TypeError` or `UnicodeError` | `repr(self)` in `ValidationError.__str__` (`utils.py:30`) |

## Judgements

**J1. The `@validator` wrapper.** `validator` (`utils.py:45-102`) returns the
closure `wrapper`, so each of the 54 decorated functions is a module name
bound to a `wrapper`. A call by that name (`card_number(value)`,
`card.py:62`; `hostname(...)`, `email.py:76`; 25 sites in all) has the callee
`validators.utils.validator.wrapper`. The candidate of the same name (the
undecorated function) is rejected there. The wrapper calls the function at
its value sites `func(*args, **kwargs)` (`utils.py:84`, `91`). `func` is
annotated `Callable[..., Any]`, a bare callable (B2). The package applies
`@validator` to exactly 54 functions, so both sites have these 54 callees. A
client may decorate its own function (the docstring example,
`utils.py:52-58`); that function is client code. The trace has all 54 edges
and `visa -> wrapper` and the like.

**J2. Where `ValidationError.__bool__` runs.** The wrapper returns `True` or
a `ValidationError` (`utils.py:89-100`), and `ValidationError.__bool__`
returns `False`. So a truth test of a wrapped call's result calls
`__bool__`. The site finder marks every operand of `and` and `or` as a truth
site, also the last one. In `return a or b` Python tests `a` only; `b` is
returned untested. So the last operand gets no edge where it is a wrapped
call: `hostname.py:130:17`, `137:13` (the `ipv6` arm) and `es.py:168:46`
(`es_cif`). The returned value reaches the wrapper of the enclosing
validator, which tests it at `utils.py:84` and `91` (both accepted). One
site stands for an outer test: in `url.py:248-265`,
`validate_scheme(...) and (is_local_file or _validate_netloc(...)) and ...`,
the outer `and` tests the value of the parenthesised `or`, which is the
result of `_validate_netloc` when `is_local_file` is false. That result can
be a `ValidationError` (`url.py:105`, `121`). The site finder names this test
at the inner operand (`url.py:252:16`), and the edge is written there. The
general case: where the site finder names a truth test at an operand of the
tested expression, not at the expression itself, the edge is written at the
site of the operand whose value is tested. The trace confirms
`url -> __bool__`. The eight card validators test `card_number(value)` first
(`card.py:62` and the like); the tests pass only numbers that pass the Luhn
check, so these eight edges come from reading only.

**J3. eth-hash names (`eth_address.py:12`, `24`).** `keccak` is the object
that `eth_hash.auto` exports: `Keccak256(AutoBackend())` (`eth_hash/auto.py:8`).
The extra `crypto-eth-addresses` installs `eth-hash[pycryptodome]>=0.7.0`
(`pyproject.toml`). `keccak.new(...)` is `eth_hash.main.Keccak256.new`
(`eth_hash/main.py:48`). It returns `self.preimage(...)` (`main.py:54`): the
`preimage` of the backend that `AutoBackend` chooses at its first use
(`eth_hash/backends/auto.py:11-24`, `eth_hash/utils.py:13-19`). Without the
variable `ETH_HASH_BACKEND`, eth-hash tries `pycryptodome` first and then
`pysha3` (`eth_hash/backends/__init__.py:11-14`, `utils.py:63-74`). The
pycryptodome backend returns a `CryptodomePreimage`
(`eth_hash/backends/pycryptodome.py:39-40`), so `.digest()` is
`eth_hash.backends.pycryptodome.CryptodomePreimage.digest` (`pycryptodome.py:27`).
`digest` returns the bytes of pycryptodome's keccak object, so `.hex()` is
`<builtin>.bytes.hex`. The trace has the same three names.

The pysha3 backend's `Pysha3Preimage.digest` (`eth_hash/backends/pysha3.py:18`)
is not in the graph. That backend imports `sha3` (safe-pysha3), which neither
the package nor its extra installs. eth-hash chooses it only when a client
installs `sha3` and either has no pycryptodome or sets
`ETH_HASH_BACKEND=pysha3`; with the extra, pycryptodome is always there. So
this is a library configured by a client to use a library that only the
client installs (B5: a client's choice of configured class is client code).
**Ruling of the lead (2026-11-22):** only the pycryptodome backend is in
scope. The package's own extra names it (`crypto-eth-addresses =
["eth-hash[pycryptodome]>=0.7.0"]`, `pyproject.toml:50`), and the versions and
the configuration that the package's own requirements admit decide which
concrete names a call has. A pysha3 backend that only a client installs is not
admitted by the package. No edge changes.

eth-hash 0.7.1 (read after Codex audit round 1) differs from 0.8.0 only in
annotations (`Union[bytearray, bytes]` for `bytearray | bytes`): the same
modules, classes and methods, so the names hold for it. eth-hash 0.7.0
(read later, on disk from the lead) has the same `eth_hash` package as 0.7.1,
file for file (`Keccak256.new` at `main.py:52`, returning `self.preimage(...)`
at `main.py:58`; `CryptodomePreimage.digest` at
`backends/pycryptodome.py:28`), so the names hold for every admitted
release from 0.7.0 to 0.8.0. The other side of
the optional import runs too: `eth_address -> <builtin>.ImportError`
(`eth_address.py:55`, reading only).

**J4. SHA-256 receivers (`btc_address.py:23`, `trx_address.py:33`).** The
factory is `hashlib.sha256` (the trace's `_hashlib.openssl_sha256` has that
alias). Its result has `.digest()` on `_hashlib.HASH`, and, by hashlib's
documented fallback without OpenSSL's SHA-256, on `_sha256.SHA256Type`
(CPython 3.11) or `_sha2.SHA256Type` (3.12 and later; see "Corrections of
2026-11-25"). This is the precedent of
markdown2 (`markdown2.py:150`) applied to 3.11 and later. 4 edges from
reading only. The candidate `validators.hashes.sha256` is rejected at the
four factory calls: there the name is hashlib's.

**J5. The `except TypeError` branch of `_validate_optionals`
(`url.py:151-154`; corrected in Codex audit round 1).** The package's
comment says the branch is for Python before 3.9.2, whose `parse_qs` has no
`separator` argument. With an exact `str` it does not run on 3.11 and later.
But `value` is annotated `str`, and an admitted `str` subclass can override
its methods (B5, "Client control flow"). `urlsplit` keeps such a subclass
through `lstrip`, `replace`, slicing and `split` (CPython 3.12
`urllib/parse.py:494-520`). `parse_qsl` calls `qs.split(separator)` on the
query (`parse.py:819`), and the subclass can make that raise `TypeError`
(for example with `file:///tmp?x=1`, whose empty netloc skips the netloc
check). The branch then runs, and `parse_qs` at `url.py:153:30` is a callee.
The pair `_validate_optionals -> urllib.parse.parse_qs` was already in the
graph through `url.py:147-148`, so no edge changes.

**J6. `between`'s comparisons (`between.py:74`, `79`).** `AbsMax` and
`AbsMin` have `@functools.total_ordering`. Each defines one comparison
(`__ge__`, `__le__`), and `total_ordering` adds the others as generated
functions of `functools`. `min_val > max_val` (`between.py:74:20`) has no
candidate by name, because the package defines no `__gt__` or `__lt__`; the
entry was added by hand. `AbsMin() > x` runs `_gt_from_le`, which calls
`AbsMin.__le__`. `x > AbsMax()` with a client `x` gets `NotImplemented` from
`x` and runs the reflected `AbsMax.__lt__` (`_lt_from_ge`), which calls
`AbsMax.__ge__`. The `functools` frames are library code between two
package frames, so both are callees of the site (the trace has both). At
`79:20` (`min_val <= value`) only `AbsMin.__le__` runs; at `79:29`
(`value <= max_val`) only the reflected `AbsMax.__ge__`. `value` is annotated
`PossibleValueTypes` (int, float, str, datetime, None), so it is never an
`AbsMin` or `AbsMax`; `min_val` admits `AbsMin` and `max_val` admits `AbsMax`
by their annotations. Both classes are reachable on the public path
`validators.between.AbsMax`; the annotations admit them either way.
`AbsMax()` and `AbsMin()` (`between.py:69`, `71`) run `object.__init__`: no
edge.

**J7. Path flavours (`domain.py:23`).** `Path(__file__)` is `pathlib.Path`
(the factory keeps its name). It makes a `PosixPath` or a `WindowsPath`
("OS Independent"), so `joinpath` and `open` have both class names (the
precedent of netaddr and itables). The two `WindowsPath` edges come from
reading only.

**J8. `urlsplit` (`uri.py:54`, `url.py:240`).** From Python 3.11 on,
`urllib.parse.urlsplit` is an `lru_cache` wrapper, so the callee is
`_functools._lru_cache_wrapper.__call__` only (the precedent of
fastjsonschema; validators has no 3.10).

**J9. `validate_scheme` (`url.py:249`).** The parameter's default is
`_validate_scheme` (`url.py:178`). Its annotation `Callable[[str], bool]` is a
bare callable, and neither the documentation nor the tests pass another
package function. So the one package callee is `_validate_scheme`; every
other value is a client callback (B2, B5). Its result is not a
`ValidationError`, so the truth site `249:9` keeps the default rejection.

**J10. Environment variables (corrected in Codex audit round 1).** Both
variables set package-owned values, so the tinytag ruling decides them: such
a variable counts as configuration when the package's documentation or its
own test setup sets it. `RAISE_VALIDATION_ERROR` (`utils.py:79`) is
documented (`docs/install_and_use.md:23-26`, `.rst:29-34`), so both branches
run. Under it an inner wrapper raises a `ValidationError`, which subclasses
`Exception` only, so no `except` of the package catches it; no edge depends
on it (the `r_ve` keyword reaches the same branches). `PYVLD_CACHE_TLD`
(`domain.py:33`) appears nowhere but in the source: not in `docs/`, the
README, `CHANGES.md`, the CI files under `.github/` or the tests (a search of
the whole tree). So the cache branch `domain.py:34` is not admitted: its
`set(...)` and `cls._retrieve()` have no edge (-1 outside edge,
`_IanaTLD.check -> <builtin>.set`; `check -> _retrieve` stays through
`domain.py:36`). The path ruling ("Environment data read through
libraries") does not apply: the package reads the variable itself, through
`os.environ`, not through a library that documents it.

**J11. `validators.uri`.** `validators/__init__.py` does not import the
module, but its path has no underscore component, so `uri` is public (rule C).
`uri -> wrapper` (`url`, `email`), `-> _file_url`, `-> _ipfs_url` and
`-> <builtin>.len` come from reading only.

## Outside names verified in the dependency sources

Read in `deps/validators/eth_hash-0.8.0/` (the dependency sources of the audit records) (read only,
nothing run or imported):

- `eth_hash.main.Keccak256.new` (`eth_hash/main.py:48`), at `eth_address.py:24:27`.
- `eth_hash.backends.pycryptodome.CryptodomePreimage.digest`
  (`eth_hash/backends/pycryptodome.py:27`; the class is returned by
  `CryptodomeBackend.preimage`, `pycryptodome.py:39-40`), at `eth_address.py:24:64`.
- `<builtin>.bytes.hex` at `eth_address.py:24:70`: `digest` returns the bytes
  of the pycryptodome hash object (`pycryptodome.py:28`).
- The choice of backend (`eth_hash/utils.py:13-74`), for J3.

The package calls nothing of pycryptodome directly, so its sources were not
needed. Every other outside name is of the standard library or a builtin.

## Notes on the tools

- The site finder marks the last operand of an `and` or `or` as a truth
  site, although Python does not test it there (J2). The ledger rejects the
  candidate at the three sites where the operand can be a
  `ValidationError`; elsewhere the default rejection decides it.
- The site finder proposes no candidate for a comparison whose method
  `functools.total_ordering` generates (J6); `--report --without-candidates`
  lists the site (`between.py:74:20`).

## Codex audit round 1

- False edge `uuid.uuid -> re.match` (`uuid.py:39:39`): applied (-1 outside
  edge). `UUID(value)` returns an exact `uuid.UUID`, which has no `__bool__`
  or `__len__` (checked in the CPython 3.12, 3.13 and 3.14 sources on disk;
  the 3.11 source is not on disk and was not read), so the second operand
  of `or` never runs.
- False edge `_IanaTLD.check -> <builtin>.set` (`domain.py:34:38`): applied
  (-1 outside edge). `PYVLD_CACHE_TLD` is in no document, CI file or test
  (J10).
- Unsure, eth-hash 0.7.x: decided. 0.7.1 and, later, 0.7.0 have the same
  names as 0.8.0 (J3); no edge change.
- Metadata, J5 (`url.py:153:30`): applied. The site gets
  `urllib.parse.parse_qs` through an admitted `str` subclass; no edge change.
- Metadata, the note at `utils.py:40:52`: applied. `func` can also be a
  client callable instance; still no package callee.

## Corrections of 2026-11-25

**The builtin SHA-256 object (J4).** At `btc_address.py:23:52` and
`23:62` (`_validate_old_btc_address`) and `trx_address.py:33:67` and
`33:77` (`_validate_trx_checksum_address`), `_sha256.sha256.digest` is
renamed `_sha256.SHA256Type.digest` (2 edges renamed; 422 edges, 152
inside, 270 outside, unchanged in number). Batch 8's ruling "A C type
exported under a module attribute other than its type name"
(`selection/batch-8-proposal/rulings/b8-ruling-c-type-names-1.md`) names
an outside C type by the attribute under which its module exports it, and
by its type name only where no attribute is exported. A public class alias
would come first ("Public class aliases by configuration",
`ruling-names-2.md`), but validators admits CPython only, where
`hashlib.sha256` is a factory.

| Runtime | Builtin fallback | Type name | Exported as | Name |
|---|---|---|---|---|
| CPython 3.11 | `_sha256.sha256` (`Lib/hashlib.py:95-97` of 3.11.18) | `_sha256.sha256` (`Modules/sha256module.c:570`) | `SHA256Type` (`PyModule_AddObject`, `:728`) | `_sha256.SHA256Type` |
| CPython 3.12 to 3.15 | `_sha2.sha256` | `_sha2.SHA256Type` (`Modules/sha2module.c:547` of 3.12.16, `:540` of 3.15.2) | `SHA256Type` (`PyModule_AddType`, `:855`, `:867`) | `_sha2.SHA256Type` |

`_hashlib.HASH.digest` (OpenSSL) and `_sha2.SHA256Type.digest` stay.

## Corrections of 2026-11-25: the lru_cache wrapper

The referee's `ruling-lru-3.md` (adopted by the lead; README, "Rulings for
the corrections of 2026-11-25") names a call of an `lru_cache` wrapper on
CPython through the type that `_functools` exports: `functools` imports
`_lru_cache_wrapper` from `_functools` without listing it in `__all__`
(CPython 3.10.22 `Lib/functools.py:12`, `:642`; 3.12.16 `:645`; 3.15.2
`:738`), a private re-export that establishes no public class path, and
`_functools` exports the type under that attribute
(`Modules/_functoolsmodule.c`, 3.10.22 `:1462`, type name
`functools._lru_cache_wrapper` at `:1419`; 3.15.2 `:1969`, `:1908`).
`functools._lru_cache_wrapper.__call__` becomes
`_functools._lru_cache_wrapper.__call__` here (outside; edge count
unchanged):

| Caller | Site |
|---|---|
| `validators.hostname._port_validator` | `src/validators/hostname.py:37:23, 43:23` |
| `validators.hostname.hostname._matches_simple_hostname` | `src/validators/hostname.py:123:38` |
| `validators.i18n.fi.fi_business_id` | `src/validators/i18n/fi.py:57:41` |
| `validators.i18n.fi.fi_ssn` | `src/validators/i18n/fi.py:95:44` |
| `validators.i18n.fr.fr_ssn` | `src/validators/i18n/fr.py:96:36` |
| `validators.uri._telnet_url` | `src/validators/uri.py:54:57` |
| `validators.url._validate_auth_segment` | `src/validators/url.py:81:31, 83:31, 85:27` |
| `validators.url._validate_optionals` | `src/validators/url.py:142:46` |
| `validators.url.url` | `src/validators/url.py:240:57` |

The trace names the type by its facade qualname, so its 9 pairs `caller ->
functools._lru_cache_wrapper.__call__` are rejected as naming artefacts in
`validators.rejected.json` (rule A).
