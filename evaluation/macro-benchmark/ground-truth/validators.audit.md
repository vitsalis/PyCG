# validators: independent audit of the ground truth

Release 0.36.0, commit `e2e49fb3bb4b9f1ce955638386aa167356d24055` (batch 6).
Audited files, as the writer left them (not committed):
`validators.ledger` (3 default rejections), `validators.json` (424 edges,
152 inside, 272 outside), `validators.added.json` (30 edges),
`validators.md` (judgements J1 to J11), the trace `dynamic/validators.json`
(394 edges). There is no `validators.rejected.json`. `check.py validators`
reports no errors: the trace confirms 394 of the 424 edges, and the tests
run 94 of the 96 functions.

I applied the rules of `macro-benchmark/README.md` (A, B1 to B5, C, the
clarifications of 2026-11-15 and the rulings for batch 6). I read the
package source, its tests, `docs/` and `pyproject.toml` as data, and the
pinned eth-hash 0.8.0 source under `deps/validators/` (the dependency sources of the audit records)
(read only). I ran no analysis tool on the package, read no analysis output,
and ran or imported nothing of the package or of its dependencies. The only
tool that I ran is the benchmark's own `check.py` (skeleton, reports, check).

**Result.** The blind re-derivation of 74 sites agrees with the ledger at
every site. The exhaustive checks found no missed edge and no edge that
cannot happen. The findings change no edge: three wording findings (W1 to
W3), one remark on the README and the site finder (R1), and one fact that I
could not check (V1). I agree with the lead's ruling on eth-hash (J3).

## Findings

| Id | Severity | Site or file | Evidence | Edges |
|---|---|---|---|---|
| W1 | wording (must fix: the judgements file is garbled) | `validators.md:63-64`, `96-98` | J2 stops in mid-sentence at line 63 ("The trace confirms") and the heading of J3 follows on the same line. Lines 96-98 are a fragment of an earlier draft ("he lead to rule on:** whether a backend that only a client installs is in scope ...") that repeats the `ImportError` sentence of lines 92-94. Finish the J2 sentence, put J3 on its own paragraph, and delete lines 96-98. | 0 |
| W2 | wording (note incomplete) | ledger, `utils.py:84:20` (and `91:24` by reference) | The note lists the decorated validators that can return a `ValidationError` (cards, hostname, es_doi, uri) but leaves out `url`. `url` returns the value of `(is_local_file or _validate_netloc(...))` when it is false (`url.py:248-265`), and `_validate_netloc` returns the hostname wrapper's result (`url.py:105`, `121`). The edge is already there; add `url.py:248-265 through _validate_netloc`. | 0 |
| W3 | wording (reason) | ledger line 13, default rejection of `AbsMax.__ge__` and `AbsMin.__le__` | The reason says "the package makes AbsMax and AbsMin only in between". J6 states, correctly, that both classes are public through `validators.between.AbsMax` and `.AbsMin` (rule C), so a client can make them too. The decision is still right at all 32 sites: their operands are ints and strs by the annotations (`cron.py:7`, `finance.py`, `fi.py:100-101`, `fr.py:28`; B4, and the clarification "a concrete annotation does not admit arbitrary out-of-contract types"), and `between` is the only function whose annotations admit the two classes. Reword the reason on these grounds. | 0 |
| R1 | remark (README and site finder; no change to the ground truth) | `url.py:248-265`; `hostname.py:130`, `137`; `es.py:168` | The table of sites says that a `truth` site is "the tested expression". The site finder also makes a truth site of the last operand of `and`/`or`, which Python does not test there, and it makes no site for a parenthesised `or` group that an outer `and` tests. The writer rejected the candidate at the three last operands and put the outer test of the `or` group at the site of its last operand (`url.py:252:16`). The README does not say where that edge goes. Smallest extension: the edge of a test of a nested `and`/`or` value is written at the site of the operand whose value is tested. The pair `url -> ValidationError.__bool__` is the same either way. | 0 |
| V1 | fact not checked | J3, `eth_address.py:24` | The extra admits `eth-hash[pycryptodome]>=0.7.0`, but only eth-hash 0.8.0 was available to read. The writer says so. If 0.7.x uses other module paths for `Keccak256` or `CryptodomePreimage`, the two names at `24:27` and `24:64` would need a second name each. Low risk: the names are in the trace of 0.8.0, and I know of no move of these classes. | 0 or +2 |

## Step 1: blind re-derivation

I made the skeleton without the ledger: a scratch benchmark directory with a
copy of `projects.toml` and a copy (`cp -R`) of `projects/validators`, and
`check.py --benchmark-dir <scratch> --skeleton validators`. It has all 721
sites (409 call, 66 decorator, 54 op, 183 truth, 9 format) and 4 value sites.
I numbered the sites module by module in (line, column) order.

**Draw by kind.** One candidate dominates: `ValidationError.__bool__` is a
candidate at 192 sites (183 truth sites and 9 calls), and 54 of the 66
decorators are the same `@validator`. So I drew by kind, in proportion to
the counts: `random.Random(20261122)`, then `rng.sample` of 40 calls, 6
decorators, 5 ops, 18 truth sites and 1 format site, and I added the 4 value
sites (none was drawn). That gives 74 sites. I wrote the callees of each
site from the source before I opened any file of the writer (the scratch
file `$TMPDIR/audit-validators/blind-answers.txt`, which also holds
the facts that I fixed for step 2).

| Module | Sites |
|---|---|
| `card` | 37:23 call, 84:69 call, 171:25 call |
| `country` | 266:2 decorator, 311:16 truth, 355:50 truth |
| `cron` | 24:24 op, 34:15 call, 65:12 truth |
| `crypto_addresses.btc_address` | 21:35 call |
| `crypto_addresses.trx_address` | 22:11 call, 30:11 call, 60:22 call, 62:11 truth |
| `domain` | 36:44 call, 76:12 truth, 107:27 call |
| `email` | 67:8 truth, 75:13 call |
| `finance` | 15:29 op, 36:12 truth, 49:26 call, 60:37 op, 65:2 decorator, 143:22 call, 145:36 call |
| `hashes` | 97:2 decorator, 143:70 truth |
| `hostname` | 29:22 call, 36:42 call, 37:31 call, 37:35 format, 42:42 call, 129:26 truth |
| `i18n.es` | 20:55 call, 138:8 truth |
| `i18n.fi` | 14:22 call, 97:26 call, 100:12 call, 101:14 truth, 101:54 op |
| `i18n.fr` | 27:2 decorator, 57:18 call, 64:35 op, 102:48 call, 108:11 call |
| `i18n.ind` | 27:20 call |
| `iban` | 22:2 decorator, 41:10 truth, 41:93 call, 42:12 truth |
| `length` | 41:25 call, 45:24 call |
| `uri` | 23:28 call, 50:34 truth, 64:8 truth, 69:31 call, 70:20 call, 99:25 call, 115:19 call, 126:8 truth, 134:8 truth |
| `url` | 71:74 call, 104:19 call, 120:36 call, 142:34 call, 164:2 decorator, 249:24 call (value), 251:13 truth |
| `utils` | 40:37 call, 73:6 decorator (value), 84:24 call (value), 87:42 call, 91:28 call (value) |

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Calls | 40 | 40 | 0 |
| Decorators | 6 | 6 | 0 |
| Ops | 5 | 5 | 0 |
| Truth | 18 | 18 | 0 |
| Format | 1 | 1 | 0 |
| Value sites (added) | 4 | 4 | 0 |
| **Total** | **74** | **74** | **0** |

Disagreements by class: the writer missed an edge, 0; the writer has an edge
that cannot happen, 0; naming only, 0; the auditor was wrong, 0. Sites that
test the decisions most: `email.py:75:13` (`bool(hostname(...))`: `bool` and
`ValidationError.__bool__`), the four decorated calls (`fr.py:102:48`,
`length.py:45:24`, `uri.py:70:20`, `115:19`: the wrapper, not the
undecorated function), `utils.py:84:24` and `91:28` (the same 54 decorated
functions as mine), `utils.py:73:6` (`functools.partial.__call__`, the
funcy precedent), `url.py:249:24` (only `_validate_scheme`), and
`url.py:251:13` (no callee: `is_local_file` is a bool; the writer puts the
outer test of the `or` group at `252:16`, see R1).

## Step 2: exhaustive checks

**`ValidationError.__bool__` (192 candidate sites).** A wrapper returns
`True` or a `ValidationError` (`utils.py:89-100`), so the candidate is a
callee exactly where the package truth-tests the result of a decorated
validator. I listed these sites from the source before I read the ledger:
the 8 `card_number(value) and ...` sites (`card.py:62` to `216`),
`hostname.py:128`, `129`, `135`, `136` (the `domain` result and the
conditional expressions of `ipv4`), `es.py:168` (`es_nie`, `es_nif`),
`fr.py:102` (`not fr_department(...)`), `url.py:121` (`hostname(...) and`),
the `or` group of `url.py:251-262`, and the two wrapper tests
(`utils.py:84`, `91`): 19 truth sites, and the `bool()` calls at
`email.py:75` and `length.py:45`. The ledger accepts the same 21 sites and
rejects the three last operands (`hostname.py:130:17`, `137:13`,
`es.py:168:46`), which are returned, not tested. I read all 168 sites of the
default (`--report --default`): each tests a str, bool, int, `None`, a
`re.Match`, an ipaddress or uuid object, a client value, or the result of a
private function that returns a bool, a match or a str. The documented
example `visa('bad_visa_number', r_ve=True)` (`docs/install_and_use.md:38`)
makes the card edges, which the trace lacks (the 8 card edges are added
edges).

**`AbsMax.__ge__`, `AbsMin.__le__`.** `total_ordering` makes `__gt__`,
`__lt__` and the missing one of `__le__`/`__ge__` in `functools`. At
`between.py:74` (`min_val > max_val`), `_gt_from_le` calls `AbsMin.__le__`
when `min_val` is the default `AbsMin`, and a client `min_val` gets
`NotImplemented` and the reflected `_lt_from_ge` calls `AbsMax.__ge__`. At
`79:20` only `AbsMin.__le__` runs, at `79:29` only the reflected
`AbsMax.__ge__`: `value` is never one of the two classes by its annotation.
The ledger has these sites as I derived them, with `74:20` added by hand.
The 32 sites of the default compare ints and strs (see W3).

**`ValidationError.__repr__`, `__str__` (38 sites of the default).** The
left operand of every `%` is an int; the formatted values are strs; the
`str()` arguments are ints and the caught `ValueError`, `TypeError` or
`UnicodeError`. The dict that `__repr__` formats (`utils.py:25`) holds the
arguments that the validator got: the package passes only strs, ints, bools
and `None` to its own validators, and `func` is left out. Only `repr(self)`
in `__str__` (`utils.py:30`) reaches `__repr__`; the ledger accepts it.

**Value sites and roles.** `func` at `utils.py:84` and `91`: the 54
functions that the package decorates, and no other package value (the
annotation is a bare `Callable`). `validate_scheme` (`url.py:249`): the
default only; neither the tests nor `docs/` pass another value.
`@wraps(func)` (`utils.py:73:6`): `functools.partial.__call__`, which calls
`functools.update_wrapper` (library code).

**Dispatch.** There is no class hierarchy in the package beyond
`ValidationError(Exception)` and the two `total_ordering` classes: no
package subclass, no property, no `__getattr__`. `_IanaTLD` is used only
through `_IanaTLD.check` and `cls._retrieve()` (`cls` is `_IanaTLD`).

**Sites that no candidate names.** I read the 542 implicit sites without
candidates (`--report --without-candidates`). Only `between.py:74:20` can run
package code, and the ledger has it. The iteration of the generator
`_retrieve` (`domain.py:34`, `36`) has its edge at the call.

**Functions that no site calls.** `ValidationError.__str__` only: a client's
`str()` calls it. Correct.

**Binding check.** I checked every call of a package function against the
callee's signature: the 25 calls of decorated validators (each keyword that
`email.py:76`, `url.py:105`, `121`, `hostname.py:128-137` and `uri.py:70`
pass exists in the callee), `_validate_netloc` (9 arguments for 9
parameters), `_validate_optionals`, `_check_private_ip`, the
`lru_cache` functions (`_ssn_pattern(ssn_check_marks)` in `fi`, no argument
elsewhere), `_func_args_as_dict` and `ValidationError(...)`. All bind. The
wrapper's `func(*args, **kwargs)` binds for the package's own calls and
depends on the client's arguments otherwise.

**Callees outside the package.** I checked each of the 91 outside names of
the graph. Points that needed a source or a precedent:
`functools._lru_cache_wrapper.__call__` (and the package function on a
miss) for the 7 `@lru_cache` functions; `urlsplit` is an `lru_cache`
wrapper on every supported version (I read `urllib/parse.py` of CPython
3.12, 3.13 and 3.14; 3.11 by the fastjsonschema record), so it has only
the wrapper's name; `parse_qs` and `unquote` are plain functions;
`hashlib.sha256(...).digest()` has `_hashlib.HASH.digest`,
`_sha256.sha256.digest` (3.11) and `_sha2.SHA256Type.digest` (3.12 and
later), the markdown2 precedent; `pathlib.Path` with the `PosixPath` and
`WindowsPath` methods (OS independent; the netaddr precedent; a zip import
does not change the class, because the package builds a `Path` from
`__file__`); `collections.abc.Mapping.get` for `os.environ.get` (anytree);
`eth_hash.main.Keccak256.new`,
`eth_hash.backends.pycryptodome.CryptodomePreimage.digest` and
`<builtin>.bytes.hex` (`eth_hash/main.py:48-54`, `backends/auto.py:11-24`,
`utils.py:13-74`, `backends/pycryptodome.py:15-45`). `TypeVar`,
`total_ordering`, `classmethod`, `wraps`, `ipaddress`, `uuid.UUID`, `re`,
`inspect` and `itertools` names follow the micro-benchmark rules.

**Rejected trace edges.** None; every trace edge is in the graph.

## The writer's judgements

| Judgement | Opinion | Nearest rule |
|---|---|---|
| J1 `@validator` wrapper | agree | micro-benchmark: a call of a decorated name calls the wrapper; B2 (bare `Callable`) for `func` |
| J2 where `__bool__` runs | agree on every edge; placement at `url.py:252:16` needs the extension of R1 | "Implicit calls"; the truth row of "Call sites and candidates" |
| J3 eth-hash names, lead's ruling | agree with the ruling (below) | declared requirements ("Judgements"); library configuration (B5, whitenoise ruling 4) |
| J4 SHA-256 receivers | agree | markdown2 `markdown2.py:150`; "Versions and configuration" (hashlib fallback) |
| J5 `except TypeError` at `url.py:151-154` | agree: on 3.11 and later `parse_qs` takes `separator`, and `query` and the separators are strs | netaddr `except NameError`, `strategy/__init__.py:242` |
| J6 `between`'s comparisons | agree; `AbsMax` and `AbsMin` are public through `validators.between` (rule C), which changes no edge | callback rule (B5), micro-benchmark "Callbacks" |
| J7 path flavours | agree | netaddr, json-repair |
| J8 `urlsplit` | agree | fastjsonschema ruling 4 (only the wrapper, because 3.10 is not supported) |
| J9 `validate_scheme` | agree | B2 (bare `Callable`), B5 |
| J10 environment variables | agree: both branches run, and no `except` of the package catches a `ValidationError` | "Judgements" (both sides run); B5 control flow |
| J11 `validators.uri` is public | agree | C |

**The lead's ruling on eth-hash (J3).** I agree. The nearest rules support
it directly. (1) The versions and libraries that a package admits are
decided by its own declared requirements ("Judgements", itables ruling 7):
the extra is `eth-hash[pycryptodome]>=0.7.0` (`pyproject.toml:50`), and it
installs no `sha3`. (2) When library code picks an object from the client's
configuration, the library's defaults and the configurations that the
package documents are in scope, and any other configured class is client
code (B5, whitenoise ruling 4). eth-hash's default order with the extra
installed picks pycryptodome (`eth_hash/utils.py:63-66`,
`backends/__init__.py:11-14`); `ETH_HASH_BACKEND=pysha3` with a `sha3`
that only the client installs is another configured class. The ruling is
the smaller extension of these two rules, and it changes no edge. A related
case that also changes no edge: with eth-hash installed without any backend,
`keccak.new` raises `ImportError` at its first use; the call
`eth_hash.main.Keccak256.new` still runs.

## Cases for the lead

None that changes an edge. R1 asks for one sentence in the README (where the
edge of a test of a nested `and`/`or` value is written). V1 can be closed
only by reading eth-hash 0.7.0.

## README and tools

- The README's truth row ("the tested expression") and the site finder
  differ for the last operand of `and`/`or` and for a nested `and`/`or`
  operand (R1). Harmless here: the candidates are rejected or the pair has
  another site.
- The site finder proposes no candidate for a comparison whose method
  `functools.total_ordering` generates (`between.py:74:20`); the README's
  "Limits of the site finder" does not name this case. The writer found it
  with `--without-candidates`, as the README says to do for other cases.
- The tools worked as the brief says. `check.py --skeleton` on the scratch
  copy, `--report --default`, `--report --without-candidates` and the plain
  check gave consistent counts (721 sites, 4 value sites; defaults 168, 32,
  32, 38, 38 sites).

## Audit of the corrections of 2026-11-25

Branch `vitsalis/gt-validators-sha256` (cf42fd1, PR #108) against `main`
(14798e4): two outside edges renamed in `validators.json`,
`validators.added.json`, `validators.ledger` and `validators.md`;
`evaluation/metrics.json` is not recorded yet. I read `src/validators/`
and `pyproject.toml` from the inputs image and CPython 3.11.18 to 3.15.2
from the dependency sources, as text. Nothing ran; no PyCG output was read.

| Site | Change | Verdict | Evidence |
|---|---|---|---|
| `crypto_addresses/btc_address.py:23:52`, `23:62` (`_validate_old_btc_address`) | `_sha256.sha256.digest` renamed `_sha256.SHA256Type.digest` | agree | `sha256` is `hashlib.sha256` (`from hashlib import sha256`, `:4`). validators admits CPython 3.11 and later only (`pyproject.toml:32`, `:35`). On 3.11 hashlib's fallback is the factory `_sha256.sha256` (`Lib/hashlib.py:94-97` of 3.11.18), whose objects have `.name = "_sha256.sha256"` (`sha256module.c:570`) and whose type `_sha256` exports as `SHA256Type` (`PyModule_AddObject`, `:728`); `hashlib.sha256` is a factory, so no public class alias applies (ruling-names-2) |
| `crypto_addresses/trx_address.py:33:67`, `33:77` (`_validate_trx_checksum_address`) | the same | agree | `hashlib.sha256` (`import hashlib`, `:4`) |
| the four sites | `_hashlib.HASH.digest`, `_sha2.SHA256Type.digest` kept | agree | `_hashlib` exports `HASH` (`PyModule_AddType`); from 3.12 the fallback is `_sha2.sha256`, type `.name = "_sha2.SHA256Type"` added by `PyModule_AddType` (`sha2module.c:547`, `855` of 3.12.16; `:540`, `867` of 3.15.2) |

Nothing missed: these two lines are the package's only hash objects
(`hashes.py` defines validators, not hash calls; `eth_address.py:24` uses
the installed `eth_hash`, outside both rulings), and no other outside
callee of `validators.json` falls under them (`re.Pattern`, `re.Match`,
`functools.partial`, the `ipaddress` and `pathlib` classes are public;
`functools._lru_cache_wrapper` is the micro-benchmark's own example).

Counts. 422 edges (152 inside, 270 outside), unchanged in number; 394
traced, 28 from reading only: as `check.py validators` reports, which
passes with the source in place, as do `--origin` and `--report`. The
`make eval` numbers come from PyCG's output, which I did not read.

**Verdict.** Closed: the two renames stand, and nothing is missed. No
finding.
