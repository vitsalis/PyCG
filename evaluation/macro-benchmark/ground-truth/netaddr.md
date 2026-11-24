# netaddr: judgements of the ground truth

The global-scope audit of 2026-11-15 removes 3 edges and adds 8. The global
README rules apply to this project without local exceptions. The current ledger
and counts below include these corrections.

See the audit record (audit record `2026-11-15/README.md`) for evidence.

The second complete audit found 22 false positives and 4 missed edges,
plus 12 corrections to source-site attribution or explanations. See
the pass-2 report (audit record `2026-11-15/pass-2/netaddr-review.json`).
The current ledger and statistics below include both audit passes.

The third complete source-first audit found no false-positive pairs and 16
missed pairs from supported zip resource loading, plus eight groups of
explanation corrections. See the pass-3 netaddr review and its pinned
CPython evidence. No target or dependency code was executed.

The fourth source-first audit adds two pairs for explicitly supported PyPy
dictionary equality, with no removals or node changes. Four independent
metadata groups clarify optimized modes, retained error witnesses, the full
site denominator, and PyPy bin/bulk-copy exclusions.

Release 1.3.0 (commit `85a7b25`). Analysed source: `netaddr/` without
`netaddr/tests/`: 20 modules, 362 functions (4 lambdas), 43 classes.
`pyproject.toml` sets `requires-python = ">=3.7"`, so the supported
versions are 3.7 and later. The release also explicitly supports PyPy
(`docs/source/reference/compatibility.rst:6-13`); CPython is not the sole
implementation in scope. The explicit pre-3.7 support drop applies to both.

The ledger is `netaddr.ledger`; the graph `netaddr.json` is generated from
it. Three trace pairs come from direct test calls of private APIs with
arguments excluded by B2/C; `netaddr.rejected.json` records them.

## Architecture, as the ledger uses it

- `IPAddress`, `IPNetwork` and `IPRange` (with its subclass `IPGlob`) derive
  from `BaseIP`; `IPNetwork` and `IPRange` also mix in `IPListMixin`. Each IP
  object keeps its strategy module in `_module` (`netaddr.strategy.ipv4` or
  `ipv6`); `EUI` keeps `eui48` or `eui64`. The attributes of a strategy
  module (`version`, `width`, `max_int`, ...) are ints and strs, so
  `self._module.version` runs no property.
- `self._module.f(...)` dispatches on that module: IP classes reach the
  `ipv4` and `ipv6` functions, `EUI` the `eui48` and `eui64` functions.
- `BaseIP` defines `__eq__` and `__hash__` through `key()`, and the order
  operators through `sort_key()`. `IPSet._cidrs`, `SubnetSplitter._subnets`
  and the dicts of `DictUpdater` (`IANA_INFO`) are keyed by IP objects, so
  their dict and set operations run `BaseIP.__hash__` and `BaseIP.__eq__`.
- Five attributes are `property(...)` calls, not decorated defs:
  `BaseIP.value` (getter `BaseIP.<lambda1>`, setter `_set_value`),
  `IPNetwork.prefixlen` (`IPNetwork.<lambda1>`, `_set_prefixlen`),
  `EUI.value` and `EUI.dialect` (`_get_*`, `_set_*`), and `IPGlob.glob`
  (`_get_glob`, `_set_glob`). The site finder of that time proposed no
  candidate at their loads and stores; it does now, and the ledger has these
  37 getattr and setattr entries with the accessor as a callee.
- The package exceptions (`AddrFormatError`, `AddrConversionError`,
  `NotRegisteredError`) define no `__init__`: a call names
  `<builtin>.Exception.__init__` (README: nearest base outside the
  package); the trace's canonical name is `<builtin>.BaseException.__init__`.

## Scope rules

**A. Edges are per function.** 50 functions never ran in the tests (the
CLI, `pprint_info`, `create_indices`, `IPListMixin.__contains__`, the
`IPGlob` pickling methods, several strategy wrappers, ...). They keep their
out-edges.

**B1. Receivers.**
- `BaseIP` is private and has no own package-created instance. Public
  `IPAddress`, `IPNetwork`, `IPRange` and `IPGlob` receivers override
  `key` and `sort_key`; the base operators reach those implementations.
- `XMLRecordParser` has only the four package-created concrete subclasses,
  each overriding `process_record`. `Publisher.notify` reaches only the
  registered `FileIndexer` and `DictUpdater` objects. `PrettyPrinter` has
  no package construction; its uncalled `update` body retains `pprint.pformat`
  but its hypothetical client `self.fh` is opaque.
- `IPListMixin.__contains__` has no nonrecursive package caller or admitted
  package receiver: `IPNetwork` and `IPRange` override it and do not call
  it explicitly. The A/B fallback preserves the uncalled body with opaque
  client `self`. Its version value can pass the check at 861, while
  `isinstance(other, BaseIP)` admits public IP objects in the `other` role.
  The call at 863 and `other.first`/`other.last` properties at 866 therefore
  count. The `in self` expression has no named package target.
- `self.__class__(...)` and `klass(...)` (37 value sites): the package
  defines no subclass of `OUI`, `IAB`, `EUI`, `IPAddress`, `IPNetwork` or
  `IPSet`, so the callee is that class's `__init__`.

**B2. Arguments and stored values.**
- `other` of the `BaseIP` comparisons is documented as an `IPAddress` or
  `IPNetwork`; the package (the sort in `cidr_merge`) and the tests
  (`test_ip_ranges.py:61, 216`) also pass `IPRange` objects. So
  `other.key()` and `other.sort_key()` reach the three subclass methods,
  not `BaseIP.key`.
- `num` of `IPAddress.__add__`, `__sub__`, `__iadd__`, `__isub__`: the tests
  pass `IPAddress` objects. `self._value + num` then runs
  `IPAddress.__radd__` (= `__add__`, `ip/__init__.py:465`) and
  `self._value - num` runs `IPAddress.__rsub__`; `int(...)` of the result
  runs `IPAddress.__int__`.
- `other` of `IPAddress.__or__`, `__and__`, `__xor__` is documented as an
  `IPAddress` or int-like object: `int(other)` reaches `IPAddress.__int__`.
  An `EUI` is not named, so `BaseIdentifier.__int__` is not a callee.
- `prefix` of `EUI.ipv6` ("ipv6 prefix"): the tests and
  `ipv6_link_local` pass ints, so `int(prefix)` has no package callee.
- The value assigned to `IPNetwork.netmask` is a str or an int in the tests
  and in `tutorial_01.rst:123`, so `str(value)` (`ip/__init__.py:1143`) has
  no package callee.
- `cidr_merge`, `spanning_cidr` and the `*_matching_cidr` functions take
  the client's container (a list or an iterator in the tests and the
  tutorials). An `IPNetwork` or `IPSet` passed as that iterable is not
  considered (B3), so these loops run no package `__iter__`.
- `create_index_from_registry(..., parser)`: the package passes
  `OUIIndexParser` and `IABIndexParser` (`ieee.py:265, 270`).
- `SaxRecordParser._callback`: the package passes the bound
  `XMLRecordParser.consume_record` (`iana.py:115`).

**B4. Concrete outside types.** Own regular package resource paths return
`io.BufferedReader` objects and concrete `pathlib.PosixPath` or
`pathlib.WindowsPath` resources. Zip-imported package resources return
`io.BytesIO` through `open_binary` on Python 3.7/3.8. On Python 3.9 and
later, `files` returns `zipfile.Path`; its binary `open` returns
`zipfile.ZipExtFile`. These documented interpreter resource configurations
are package-owned concrete values, not arbitrary client streams. The default of the uncalled `pprint_info`
body is `sys.stdout`, an `io.TextIOWrapper`. `PrettyPrinter.update` has no
admitted package-created receiver with known `fh`; its separate constructor
default does not establish such a receiver.

**B5. Client objects are opaque.** Abstract file-like inputs and hypothetical
client receivers have no concrete outside method name. Package-owned paths,
files and defaults retain their known classes. Optional IPython remains an
ordinary missing-module stub, and both calls use its imported access path.

**C. "Public" is judged on the access path and explicit documentation.**
`docs/source/api.rst:5-12` marks submodule-only definitions private.
Documented root exports and their inherited methods remain public;
`CHANGELOG.rst:336` documents the root-exported `SubnetSplitter`. Private
classes and functions use package-owned construction and call arguments.
An uncalled private body retains its edges under A and uses the fallback
parameter rules of B; this does not create an otherwise unconstructible
private receiver. In particular, clients cannot call `DictUpdater.update`
or `load_info` to insert arbitrary IANA records.

## Judgement calls

The earlier independent audit (`netaddr.audit.md`) agreed on all 112
sampled sites and found no edge to add or remove. Its rulings are historical.
The current judgments below incorporate the full pass-2 source audit,
including the explicit privacy contract and fixed bundled-data witnesses.

1. **Version branch `__init__.py:15`.** Only Python older than 3.7 takes
   it, so `RuntimeError` (16:23) is never called: a note, no edge.
2. **Version branch `compat.py:10`.** `_open_binary` is the package
   function on 3.9 and later (`importlib.resources.files` exists), and
   `importlib.resources.open_binary` on 3.7 and 3.8. Each of the 8
   `_open_binary(...)` sites has both callees.
3. **Platform branch `strategy/ipv4.py:14`.** The README decides version
   branches and optional imports, not platform branches. By the nearest
   rule (a branch counts if a supported version takes it), both sides
   count: `_inet_pton` is `socket.inet_pton` and, on win32 and cygwin,
   `netaddr.fbsocket.inet_pton` (`ipv4.py:128`). **Lead's ruling: kept.** A
   platform branch is judged like a version branch: it runs if a platform
   that the package supports takes it (the package declares itself OS
   independent).
4. **Optional import `strategy/ipv6.py:14-26`.** Both sides: `_socket.inet_pton`
   and `_socket.inet_ntop` (named by the module that the code imports) and
   the `fbsocket` fallbacks; `Exception('IPv6 disabled')` (19:24) is an
   edge.
5. **Optional import `cli.py:60-71`.** The two local `shell` functions are
   one node (`netaddr.cli.shell.shell`) with both bodies: the IPython
   shell (both calls use the missing-module path
   `IPython.terminal.embed.InteractiveShellEmbed`) and `code.interact`.
   A called stub instance keeps its access path; no concrete runtime
   class is inferred.
6. **Dead `except NameError` branch `strategy/__init__.py:242-251`.**
   Python 3.7 and later have `bin`. Admitted integer inputs, including
   subclasses passed through public setters, take `_PyNumber_Index`'s
   `PyLong_Check` fast path before `nb_index`. An overridden `__index__`
   cannot raise `NameError` there. The four handler calls remain excluded;
   the documented integer role does not admit arbitrary non-int callbacks.
7. **`pprint_info` and fixed bundled records** (`iana.py:404-405`).
   The first sorted category is IPv4, whose first sorted key `000/8` was
   also inserted first. Its lookup finds that identical key at the initial
   slot, including after ordered resizes, so it invokes no equality method.
   Percent-r invokes `IPNetwork.__repr__`. Adding the ordinary record dict
   to the resulting string then raises before `write` at 405 or a later
   record. The earlier writes at 399-401 remain. Private `DictUpdater`
   cannot supply client `IPAddress` or `IPRange` formatting witnesses.
8. **`_within_bounds` never raises** (`iana.py:417`): it is private and
   `query` passes only keys of `IANA_INFO`, which all have `first` or
   `value`. The `Exception(...)` call has a note, no edge. `hasattr(...,
   'first')` and `hasattr(..., 'value')` run the properties (410:15,
   413:17).
9. **Hash collisions of package keys.** Public `IPSet` and `SubnetSplitter`
   operations admit arbitrary supported networks, including documented
   collisions. `dict.update` and `set.union` with dict or set operands reuse
   stored hashes, so they add equality callbacks without new hash calls.
   Private `DictUpdater` receives fixed bundled data. Equality still runs
   on supported CPython 3.7: the old 32-bit tuple hash collides for IPv4
   `000/8` and `016/8`, and for IPv6 `0000::/8` and `0100::/8`. Both old
   32-bit and 64-bit hashes collide for IPv6-unicast `2400::/12` and
   `2600::/12`. Thus the stores at 346, 349 and 352 retain `BaseIP.__eq__`.
   The 547 multicast keys have no duplicates or full collisions under the
   verified old/new 32-bit and 64-bit formulas, so the store at 364 has
   only the hash callback. `pprint_info`'s first lookup uses identity (J7).
   The pass-2 evidence retains the three pinned `tupleobject.c` sources,
   the integer fast-path source and the bundled-key hash analysis.
10. **Equal-key witnesses.** The former public `DictUpdater.update` and
    second-client-`load_info` witnesses are excluded by explicit upstream
    privacy documentation. The updater's equality edge remains supported
    by the actual bundled-data collisions in J9.
11. **`ranges.sort()` in `cidr_merge`** (`ip/__init__.py:1679`).
    The tuples cache `(version, last, first, net)`. The documented
    `network.value` setter admits an int subclass whose operations change after
    caching. Equal cached tuple prefixes can therefore reach both
    `BaseIP.__eq__` and `BaseIP.__lt__` on the package networks. Client side
    effects do not turn those stored networks into client values.
12. **`%` with an IP operand.** `IPNetwork` and `EUI` define `__getitem__`,
    so `%` takes them as a mapping; `%s` and `%r` without a key still format
    the whole operand (`'...%s...' % self` runs `IPNetwork.__str__`,
    `ip/__init__.py:1281`).
13. **f-strings and `hex()` in `cli.info`.** `{IPAddress(...)}` and
    `{value}` run `IPAddress.__str__` through `object.__format__`;
    `hex(network.network)` runs `IPAddress.__index__`.
14. **`IPSet.__iter__`** returns `itertools.chain(*sorted(...))`. The chain
    iterates the networks only when the caller consumes it, so the site has
    no `IPListMixin.__iter__` callee.
15. **Callee names.** `pathlib.PosixPath.joinpath/open` and
    `pathlib.WindowsPath.joinpath/open` for
    `importlib.resources.files(pkg)` of a package directory, and
    `zipfile.Path.joinpath/open` for a zip-imported package. Both paths have
    primary-source witnesses in CPython 3.9.25 `importlib/_common.py:17-25`
    and `zipfile.py:2337-2350,2391-2393`. CPython 3.7.17
    `importlib/resources.py:279-285` and 3.8.20 `zipimport.py:736-743`
    return `io.BytesIO` for zip resources. Package seek/read/close calls
    therefore include `io.BytesIO` and `zipfile.ZipExtFile` alongside
    `io.BufferedReader`. CPython 3.12.0 retains the public `zipfile.Path`
    alias when its implementation moves into `_path`; no duplicate alias
    is added. `_csv.writer.writerow` (the type of the csv writer has
    no public path; the trace uses this name); `argparse._SubParsersAction.add_parser`;
    `xml.sax.expatreader.ExpatParser.setContentHandler` and `.parse` for
    `make_parser()`; `struct.pack` and `struct.unpack` for the `fbsocket`
    imports `from struct import pack as _pack`.

16. **Private calls and fixed branch inputs.** `cli.main` creates only
    `shell`/`info` subcommands and defaults to `shell`; its unknown-command
    print and exit sites cannot run. Private `Publisher.attach` receives
    only the own `FileIndexer` and `DictUpdater` subscribers, so its
    interface-error constructor cannot run. Private `fbsocket.inet_ntoa`
    receives packed bytes and raises `TypeError` before its length check
    and unpack call. `inet_ntop` receives only AF_INET6 with 16-byte input;
    `inet_pton` receives only AF_INET or AF_INET6. Their rejected family and
    length branches cannot run. Fixed regex formats in `eui48.str_to_int`
    and `eui64.str_to_int` exclude the unexpected-word-count constructors;
    each caller's exception pair remains supported at an earlier site.

17. **PyPy dictionary equality** (round 4; `sets.py:426,438`).
    The release explicitly supports PyPy, with Python >=3.7. In pinned
    PyPy 3.11 v7.3.20, `dictmultiobject.py:655-669` implements equality by
    calling `w_other.getitem(w_key)`. `ObjectDictStrategy` stores a dict
    whose hash callback is `space.hash_w` (`:1210-1211`); `getitem`
    (`:1097-1101`) uses its `get`. The translated `rdict.py:735-736`
    performs `dict.keyhash(key)`. Thus both `IPSet.__eq__` and `__ne__`
    call `BaseIP.__hash__`. Construct two distinct
    `IPSet(['10.0.0.0/24'])` objects and compare them with `==` or `!=`.
    Both dicts are package-owned; no callback injection or mutation is
    required. `descr_ne = negate(descr_eq)` is at `dictmultiobject.py:149`.
    These are two original-baseline omissions, not proposal corrections.
    CPython's stored-hash path still explains its existing behavior.

18. **Optimized execution union** (round 4 working assumption).
    Include normal, `-O` and `-OO` modes. The sole assertion
    (`sets.py:171`) is followed immediately by return; removing it cannot
    reach the subsequent merge loop. `cli.py:57` formats `__doc__` with
    `%s`; `None` under `-OO` changes only the banner. No pairs change.
    This is the supplied working assumption, not a user-approved choice.

19. **Retained integer-subclass error witnesses** (round 4).
    `tutorial_01.rst:106-116` explicitly permits `IPNetwork.value` and
    `prefixlen` assignment. These setters admit int subclasses and store
    them unchanged. At `ip/__init__.py:403`, a value subclass can make is_netmask
    true and perform 33 zero-bit shifts before yielding plain 1, producing
    mask length -1. Use the documented network value setter, then the
    accepted BaseIP copy input to IPAddress. At `ip/__init__.py:1374`, a prefix
    subclass can pass setter comparison then fail the subnet comparison.
    At `glob.py:227`, a network value subclass with underlying 0, `&`
    returning 0 and `|` returning 258 makes the two indexed endpoints
    0.0.0.0 and 0.0.1.2: multiple globs are required. The retained ledger
    notes give the exact paths. No private state assignment, failed-object
    reuse, or package target inferred from client return values is needed.

20. **PyPy exclusions and bulk copies** (round 4).
    In PyPy v7.3.20, builtin `bin` maps to `app_operation.bin`, which uses
    `_operator.index` then `int.__format__`. `descroperation._index:599-601`
    returns int instances/subclasses without consulting their override;
    `index:622-627` normalizes the result. It supplies no NameError witness
    for the dead handler at `strategy/__init__.py:242`. Translated
    `rdict.ll_copy:751-772` copies stored hashes, and `ll_update:785-801`
    uses cached `entries.hash(i)`. The two equality edges do not imply
    extra hash calls from dict/set bulk copies. Source files and SHA-256
    hashes are retained in the round-4 netaddr primary evidence and
    `post-freeze-inputs.json`.

## Rejected trace edges

Three trace pairs come from direct test calls of private APIs with excluded
arguments: `Publisher.attach -> TypeError` (`test_pubsub.py:35-36`) and
`fbsocket.inet_ntoa -> len/ValueError` (`test_socket_module_fallback.py:34-35`).
They are recorded in `netaddr.rejected.json`. A still retains each function
body; B2 and C constrain the arguments used to judge that body.

## Default rejections

25 default lines reject 71 candidates. Together they decide 1820 sites.
Each line names the sites where its candidates are accepted explicitly.

| Candidates | Sites decided | Accepted explicitly at |
|---|---|---|
| `DictDotLookup.__getitem__`, `__iter__` | 484, 296 | nowhere |
| `DictDotLookup.__repr__` | 145 | `core.py:185` (`pformat` of nested lookups) |
| `EUI.__getitem__` | 482 | `EUI.ei` (`self[3:6]`, `self[3:8]`) |
| `IPListMixin.__getitem__` | 469 | 15 subscripts of IP ranges (`sets.py`, `glob.py`) |
| `__eq__` of `EUI`, `IAB`, `OUI`, `IPSet` | 457 each | nowhere |
| `BaseIP.__eq__` | 422 | dict and set operations, `==` of IP objects, `cidr_merge` sort |
| `__index__` of `BaseIdentifier`, `IPAddress` | 350 each | `cli.py:92` |
| `__hash__` of `EUI`, `OUI`, `IPSet` | 309 each | nowhere |
| `BaseIP.__hash__` | 280 | IPNetwork-keyed dict and set operations |
| `IPListMixin.__iter__`, `IPSet.__iter__` | 294, 296 | `ip/__init__.py:1563`, `nmap.py:77` |
| `IPListMixin.__len__`, `IPSet.__len__` | 170 each | nowhere |
| order operators of `EUI` and `IPSet` | 82 to 159 | nowhere |
| `BaseIP.__ge__`, `__gt__`, `__le__`, `__lt__` | 159, 81, 159, 64 | `sorted()` of networks, `spanning_cidr`, the `IPSet` merges |
| `__repr__` of the 8 classes | 144 to 145 | `iana.py:405` (`IPNetwork.__repr__`) |
| `EUI.version`, `BaseIP.version` | 113 each | loads on EUI and IP objects |
| `BaseIP.__init__` | 126 | the two `super().__init__()` calls |
| `IPAddress.__add__` | 99 | 430:37, 460:37, `sets.py:714` |
| `__int__` of `BaseIdentifier`, `IPAddress` | 109, 93 | `int()` of package objects |
| `__str__` of the 7 classes | 78 to 94 | `str()`, `%s` and f-strings of package objects |
| `IPAddress.__rsub__`, `__sub__` | 89, 91 | 445:37, 476:37 |
| `__bool__` of `IPAddress`, `IPListMixin`, `IPSet` | 87, 87, 86 | `sets.py:365` |
| `__contains__` of the 4 classes | 52 to 78 | the `in` tests on IP ranges and sets |
| bit operators of `IPAddress` | 12 to 41 | nowhere |
| `__ne__` of the 5 classes | 42 to 43 | `sets.py:712` (`BaseIP.__ne__`) |
| `EUI.__setitem__` | 37 | nowhere |

The report lists the explicit sites of each default; they are builtins
(`len`, `sorted`, `set`, `str`, `int`, `hex`, ...) applied to ints, strs,
lists and dicts, except the ones the ledger accepts. The sites where a
`.version` value is passed as an argument (`IPAddress(x, self._module.version)`)
propose the `version` properties as callbacks; the callee does not call
them.

## Value sites

43 value sites: 37 `self.__class__(...)` and `klass(...)` (B1), 2
`self.compact()` (the name `compact` is also a class attribute of the IPv6
dialects; `self` is an `IPSet`), `self._callback(...)`
(`XMLRecordParser.consume_record`), `parser(registry_fh)` (the two index
parsers), `_csv.writer(...)` (the module function `csv.writer`; the name
clashes with the attribute `FileIndexer.writer`), and
`InteractiveShellEmbed(...)()` (the same missing-module access path
`IPython.terminal.embed.InteractiveShellEmbed`).

## Statistics

| | Count |
|---|---|
| Sites requiring decisions (all inventory sites: 4383) | 3027 (1329 call, 31 decorator, 157 iter, 929 op, 180 getitem, 37 setitem, 7 delitem, 255 getattr, 10 setattr, 81 truth, 11 format) |
| Ledger entries | 1708 (1329 call, 31 decorator, 174 getattr, 10 setattr, 116 op, 18 getitem, 16 setitem, 6 delitem, 5 format, 2 iter, 1 truth) |
| Callee lines / rejection lines (`reject *`) / exclusion lines / notes | 1833 / 333 (122) / 0 / 272 |
| Default rejections | 71 candidates in 25 lines, deciding 1820 sites |
| Exclusions | 0 |
| Nodes | 382 |
| Edges | 1224: 625 in the package, 599 outside |
| Graph edges with a trace name or alias | 957 of 1224 (78.2%) |
| Edges only from reading | 267 |
| Trace edges rejected | 3 |
| Functions that the tests run | 312 of 362 |

The source also hashes the key of `{iterable.cidr: True}` in
`IPSet.__init__` (`sets.py:103`). Its edge to `BaseIP.__hash__` already
exists at other sites. The site inventory has no dict-literal hash site,
so this additional source location is recorded here.

Both the constructor call at `cli.py:64:34` and the outer call at
`64:94` retain the same missing-library stub path. Sharing a graph pair
does not remove either call site from the ledger.
