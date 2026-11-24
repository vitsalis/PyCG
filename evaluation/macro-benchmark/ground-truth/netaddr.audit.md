# netaddr: independent audit of the ground truth

> Historical audit snapshot. The global-scope audit of 2026-11-15
> supersedes its current-state claims; see [netaddr.md](netaddr.md)
> and the audit record (audit record `2026-11-15/README.md`).

Release 1.3.0, commit `85a7b25304732785ddee31be3a644a77a243a978`. Audited
files (uncommitted, on branch `feat/heldout-2`): `netaddr.ledger` (1708
entries, 25 default lines that reject 71 candidates and decide 1820 sites,
309 rejection lines, 247 notes), `netaddr.json` (382 nodes, 1219 edges: 629
in the package, 590 outside), `netaddr.md`. There is no
`netaddr.rejected.json`. `check.py --benchmark-dir macro-benchmark-heldout-2
netaddr` reports no errors. The trace (`dynamic/netaddr.json`, CPython
3.14.10) has 960 edges; the graph has all of them, so 259 edges come from
reading only.

I judged the files by the README rules (A, B1 to B5, C), the conventions and
"Auditing a ground truth". I read the whole analysed source, and read the
tests, tutorials and `pyproject.toml` as data. I did not run or import the
package, and I used no static analysis tool. Plain Python facts (hashes of
ints and tuples) I checked in a Python process that imports nothing of the
package.

**Result.** The blind sample agrees on all 112 sites. The exhaustive checks
find no edge to add and no edge to remove. There are 0 findings against the
graph, 1 note to reword (W1), 3 remarks on the tools and the README (R1 to
R3), and rulings for the two judgement calls that the writer marked. None of
them changes an edge.

## Findings

| Id | Kind | Subject | Evidence | Edges | Severity |
|---|---|---|---|---|---|
| - | - | No edge that the writer missed, and no edge that cannot happen | Steps 1 to 6 below | 0 | - |
| R1 | tool gap (no graph change) | `name = property(...)` is not a property for `sites.py` | `BaseIP.value` (`ip/__init__.py:46`), `IPNetwork.prefixlen` (`:1083`), `EUI.value` (`eui/__init__.py:438`), `EUI.dialect` (`:463`), `IPGlob.glob` (`glob.py:301`). Their 37 loads and stores get no candidate, so the skeleton has no site for them (0 setattr sites; no getattr site for these names). A blind auditor cannot see them in the skeleton. The writer added all 37 entries, and the accessor of `hasattr(ip_range, 'value')` (`iana.py:413`). I found every access by an `ast` scan: 37 of 37 are in the ledger with the right accessor. Proposal: let `sites.py` propose the accessor functions of a class-body `name = property(f, g, ...)` at loads and stores of `name` | 0 | low |
| R2 | README gap (no graph change) | class-body aliases | `IPAddress.__radd__ = __add__` (`ip/__init__.py:465`); in `IPSet`, `__le__ = issubset`, `__ge__ = issuperset`, `__or__ = union`, `__and__ = intersection`, `__xor__ = symmetric_difference`, `__sub__ = difference`, `__str__ = __repr__` (`sets.py:466-699`). The README says that a module-level alias is not followed; a class-body alias is not followed either. Here it changes nothing: `__radd__` is the function `__add__`, which is a candidate, and no package site applies an `IPSet` operator. Proposal: say "a module-level or class-body alias is not followed" | 0 | low |
| W1 | note wording (no graph change) | `iana.py:404:31` `ipranges[iprange]`, note "the lookup finds it by identity, without `__eq__`" | CPython checks identity entry by entry along the probe sequence. A different key with the same hash earlier in that sequence would still be compared with `__eq__`. The result holds for another reason: the dict holds the IPv4 keys of the bundled data (judgement 7), and IPv4 values are below `2**61 - 1`, so the congruence of step 4 does not apply to them; I know of no public-API program that puts a colliding key before the first key. Proposal: "the keys are IPv4 networks, whose values are below 2**61 - 1, so the collisions of judgement 9 do not apply" | 0 | low |
| R3 | README gap (no graph change) | `__eq__` in dict and set operations | See "The hash-collision claim" below. Proposal: one sentence in "Implicit calls": a dict or set operation calls `__eq__` of the key when it finds a stored key with the same hash that is not the same object (an equal key, or a collision); `dict.update`, `set.union` and similar operations with a dict or set operand reuse the stored hashes and call no `__hash__` | 0 | low |

## Step 1: blind re-derivation

I made the skeleton without the ledger: a scratch benchmark directory with a
copy of `projects.toml` and a `projects` link, then `check.py
--benchmark-dir <scratch> --skeleton netaddr` (2990 sites: 1360 explicit,
1630 implicit; 43 value sites). I numbered the site lines from 0 in skeleton
order. Then `rng = random.Random(20261111)`, `rng.sample(explicit, 35)`,
`rng.sample(implicit, 35)`, and all 43 value sites (one, `ip/__init__.py
601:27`, was also in the explicit draw): 112 sites. I drew by kind because
calls and operators make 75% of the skeleton. I wrote the callees of each site
from the source alone and saved the file before I opened any writer file
(`$TMPDIR/heldout2-audit-netaddr/blind-answers.md`, SHA-256
`b39c380aa75f5830b2b0d90e04561528505c38f30995b6b9142dff38edf527d1`).

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random explicit | 35 | 35 | 0 |
| Random implicit | 35 | 35 | 0 |
| Value sites (other than the overlap) | 42 | 42 | 0 |
| **Total** | **112** | **112** | **0** |

Disagreements by class: the writer missed an edge 0; the writer has an edge
that cannot happen 0; naming only 0; the auditor was wrong 0. Outside names
agree too (`struct.unpack`, `socket.inet_aton`, `csv.writer`,
`IPython.terminal.embed.InteractiveShellEmbed.__call__`,
`<builtin>.Exception.__init__` for the package exceptions).

## Step 2: default rejections (1820 sites)

I listed the sites of all 71 candidates with `--report netaddr --default
<candidate>` and merged them by site. I then read each of the 1820 sites,
module by module, against the source, and asked for each one whether a
package object of the rejected class can be the operand. Result: no site
where a default-rejected method runs. The explicit acceptances are where
they must be. Examples that I checked one by one:

- `%` with a package operand: `IPAddress.__str__` at `ip/__init__.py:579,
  680, 1140, 1271, 1321, 1332, 1548, 1552`; `IPNetwork.__str__` at `:1140,
  1281, 1445`; `OUI`, `IAB`, `EUI` `__str__` at `eui/__init__.py:165, 314,
  741`. `%` takes an `IPNetwork` or `EUI` as a mapping (they have
  `__getitem__`), but `%s` without a key formats the whole operand.
- `int()` on package objects (`__int__`, not `__index__`): `ip/__init__.py:430,
  460, 631, 640, 649, 1184, 1205, 1478, 1519, 1524, 1850, 1851`,
  `rfc1924.py:56`, `eui/__init__.py:697:36`, `cli.py:91`. `hex()` at `cli.py:92`
  is the only `__index__`.
- `int + IPAddress` and `int - IPAddress` fall back to `__radd__` (=
  `__add__`) and `__rsub__` (`:430, 445, 460, 476`); in `__rsub__`, `num` is
  the int left operand, so `:490` has no package callee.
- The 15 `IPListMixin.__getitem__` subscripts (`sets.py`, `glob.py`), the 2
  `IPListMixin.__iter__` loops (`ip/__init__.py:1563`, `nmap.py:77`), the
  `in` tests on IP ranges and sets, `IPSet.__bool__` at `sets.py:365`,
  `BaseIP.__ne__` at `sets.py:712`, `__lt__` for `sorted()` and `<` of
  networks, `__gt__` only at `ip/__init__.py:1806`.
- The iterables of `cidr_merge`, `spanning_cidr` and the `*_matching_cidr`
  functions: the tests and tutorials pass lists (`test_cidr_v4.py:98-221`,
  `test_ip_v4.py:496`, `tutorial_01.rst:376`), so an `IPNetwork` or `IPSet`
  there is B3, as the writer says.

## Step 3: properties bound with `property(...)` (R1)

I scanned the source with `ast` for every load, store and augmented store of
`value`, `prefixlen`, `glob` and `dialect`, and every `getattr`/`hasattr`
with a constant name. Each of the 37 accesses has its entry and accessor:
`BaseIP.<lambda1>` and `BaseIP._set_value` (`ip/__init__.py:1396`, `1483`),
`IPNetwork.<lambda1>` and `IPNetwork._set_prefixlen` (20 sites in
`ip/__init__.py`, `sets.py:185, 186, 200`, `subnet_splitter.py:39`),
`EUI._get_value`, `_set_value`, `_get_dialect`, `_set_dialect` (8 sites),
`IPGlob._get_glob`, `_set_glob` (4 sites). `hasattr(ip_range, 'first')`
(`iana.py:410`) runs `IPNetwork.first` or `IPRange.first`, and
`hasattr(ip_range, 'value')` (`:413`) runs `BaseIP.<lambda1>`; both are in.
No other `hasattr`/`getattr` names a package property. The decorated
properties have candidates, and I checked their accept/reject lines with the
rejections (step 5).

## Step 4: the hash-collision claim (R3)

The writer puts `BaseIP.__eq__` on the dict and set operations whose keys are
IP objects, also where the keys are distinct, because of hash collisions.

**The claim holds.** Evidence:

- CPython reduces an int modulo `2**61 - 1` before it hashes it
  (`sys.hash_info.modulus`, width 64), and the hash of a tuple depends only on
  the hashes of its items. In a plain Python process:
  `hash((6, 2**100, 2**100)) == hash((6, 2**100 + 2**61 - 1, 2**100 + 2**61 - 1))`,
  while the tuples differ. The writer's example also checks out:
  `2**64 % (2**61 - 1) == 8` and `(2**65 - 1) % (2**61 - 1) == 15`, so
  `0:0:0:1::/64` and `::8/125` (keys `(6, 2**64, 2**65 - 1)` and
  `(6, 8, 15)`) have the same hash. Neither network contains the other, so
  `IPSet(['0:0:0:1::/64', '::8/125'])` keeps both, and the second insertion
  calls `BaseIP.__eq__`. The partitions of `cidr_exclude` give such pairs as
  well: in an IPv6 partition, the pieces at prefix lengths `k` and `k + 61`
  have congruent first and last values (`2**61` is 1 modulo `2**61 - 1`).
- Equal keys that are not the same object reach `__eq__` without any
  collision: `SubnetSplitter.remove_subnet(IPNetwork(...))`,
  `potential_supernet in self._cidrs` (`sets.py:151`), and a second call of
  the public `netaddr.ip.iana.load_info()`, which stores again into
  `IANA_INFO` every key that the import stored.
- The trace confirms it: `IPSet.__init__ -> BaseIP.__eq__` and five other
  `IPSet` methods call `__eq__` while the tests run.
- The writer has also put `__hash__` only where Python calls it.
  `dict.update` and `set.union` with a dict or set operand reuse the stored
  hashes (`sets.py:277, 370`, `subnet_splitter.py:33:48`: `__eq__` only).
  A set made from a one-element list compares nothing
  (`subnet_splitter.py:24`: `__hash__` only). The lookup in `pprint_info`
  (`iana.py:404`) sees only the IPv4 keys (judgement 7), so it has
  `__hash__` only.

**The rule that decides** is the edge rule of "Ground-truth conventions,
Edges": an edge `A -> B` exists if the code of `A` can call `B` when `A`
runs. If the call depends on what the container already holds, the
fresh-process clause applies: some program that uses only the public API
makes it. The site table names `__hash__` and `__eq__` of the key for these
sites ("a dict or set looks it up as a key"). B3 does not remove them: the
keys are networks that the package itself makes and keeps in its own
containers. The README does not describe the mechanism; R3 proposes one
sentence.

## Step 5: dispatch, rejections, notes, outside callees, uncalled functions

- **Dispatch (B1, B2).** `self.key()`/`self.sort_key()` in the `BaseIP`
  operators reach `BaseIP` (a plain public class; its docstring calls it
  abstract, but `abc` does not make it so), `IPAddress`, `IPNetwork`,
  `IPRange` (`IPGlob` inherits). `other.key()` leaves out `BaseIP.key`
  (documented `IPAddress` or `IPNetwork`; the package and tests add
  `IPRange`). `self._module.f(...)` reaches `ipv4`/`ipv6` from IP classes and
  `eui48`/`eui64` from `EUI`. `self.process_record` reaches all five
  parsers; `subscriber.update` the four `Subscriber` classes;
  `parser(registry_fh)` the two index parsers; `self._callback` the bound
  `consume_record`. `IPListMixin.__contains__` has only a plain
  `IPListMixin` as `self` (both users override it), so `:863-866` never run.
  All correct.
- **Rejections.** I read all 187 named rejection lines and grouped the 122
  `reject *` lines by reason. Every reason holds.
- **Notes.** I read all 247 notes. They are correct, also on the `%`
  mapping rule, the `cidr_merge` sort (`__eq__`, never `__lt__`, on the
  fourth items), `pprint_info` (`str + dict` raises at `iana.py:405`), and the
  `chain(*sorted(...))` of `IPSet.__iter__`. One note gives a wrong reason
  for a right result (W1).
- **Outside callees.** 113 names. Each is named by the micro-benchmark rules
  or is a trace name: `_socket.inet_pton`/`inet_ntop` (the code imports from
  `_socket`), `socket.inet_pton`/`inet_aton`, `io.BufferedReader.*` for
  `_open_binary` and `open(..., 'rb')`, `io.TextIOWrapper.write` for the
  default `sys.stdout`, `pathlib.Path.joinpath`/`open`,
  `xml.sax.expatreader.ExpatParser.*`, `argparse._SubParsersAction.add_parser`,
  `re.Pattern.findall`, `_csv.writer.writerow`. Client file objects, client
  subscribers and client callbacks have no outside callee (B5).
- **Uncalled functions.** 161 nodes have no caller (20 modules and the
  client-only API). I checked that each keeps the out-edges of its body
  (rule A); only the 8 explicit sites without callees have none, each with a
  correct "never runs" note.
- **Untraced edges.** I classified all 259: each is possible by the source
  and the rules. They are the CLI, the never-tested API, the error branches,
  the both-sides branches (judgements 2 to 5), the B1 receivers above, and
  the `__eq__` edges of step 4.

## Step 6: the writer's judgement calls

| # | Subject | Ruling that the nearest README rule supports | Edges |
|---|---|---|---|
| 3 | Platform branch `strategy/ipv4.py:14` (`_inet_pton` is `netaddr.fbsocket.inet_pton` on win32 and cygwin, `socket.inet_pton` elsewhere) | **Keep both callees.** Rule: "Judgements", default "both sides of an optional import run": this is an import whose source depends on the environment, as an optional import's does. It agrees with the edge rule, and Windows is a supported platform (`Operating System :: OS Independent`, `pyproject.toml`). | 0 (if ruled otherwise: -1, `strategy.ipv4.str_to_int -> netaddr.fbsocket.inet_pton`) |
| 6 | `except NameError` branch `strategy/__init__.py:242-251` | **No edges (the writer's choice).** Rule: "Judgements", default "a version branch runs if a supported version takes it": the handler exists for Python older than 2.6, which has no `bin()`, and no supported version (3.7 and later) takes it. A client int whose `__index__` raises `NameError` is not a value of the role ("An unsigned integer"; B3). | 0 (if ruled otherwise: +4, `strategy.int_to_bin -> <builtin>.list.append`, `<builtin>.list.reverse`, `re.sub`, `<builtin>.str.join`) |
| 1, 2, 4, 5, 7 to 15 | Version branches, optional imports, `pprint_info`, `_within_bounds`, equal keys, sort, `%`, f-strings, `chain`, names | I agree with each one. Judgement 9 is step 4. | 0 |

## Steps

1. Blind sample: 112 sites (35 explicit, 35 implicit, 42 more value sites).
   112 agree.
2. Default rejections: all 1820 sites read. No site where a rejected method
   runs.
3. `property(...)` accesses: 37 of 37 in the ledger, plus `hasattr` at
   `iana.py:413`.
4. Hash-collision claim: holds by the edge rule; checked by plain Python and
   by the trace.
5. Dispatch, rejections, notes, outside callees, uncalled functions,
   untraced edges: no error.
6. Judgement calls: rulings for 3 and 6; no edge change.

## Judgement

The ground truth is complete and precise as far as I can test it: 112 of 112
sites agree, and no exhaustive check finds an edge to add or remove. The
graph keeps 1219 edges (629 in the package, 590 outside). The remarks R1 to
R3 concern the tools and the README, not this ledger.


## Round 4 source-first audit (2026-11-16)

Adds IPSet.__eq__ and IPSet.__ne__ calls to BaseIP.__hash__ for supported PyPy dictionary equality. No removed pairs or node changes: 382 nodes, 1224 pairs. Full coverage: 1222 baseline pairs, 4383 inventory sites, 382 bodies, 71 default candidates, zero exclusions. Four independent metadata groups cover optimized modes, retained error witnesses, the complete site denominator, and PyPy bin/copy exclusions. Current judgements 17-20 and the retained round-4 evidence give witnesses and pinned interpreter sources. No target/dependency code or test gates were executed by the primary auditor.
