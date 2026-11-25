**Status (2026-11-24):** closed. The writer applied F1 and R2 in
`d407603`; the re-check (last section) finds nothing open. R1 goes to the
README's "Rulings for batch 8" (the lead).

# pyusb: blind audit of the ground truth (batch 8, doubled audit)

Release v1.3.1, commit `89ea84d6c9e4cb81bc6e40d7df849d0cbd7dfd47` (root
`.`, analysed source `usb/`, 14 modules, 301 functions). Audited files, at
the writer's commit `c7f0e59` of `b8-gt-pyusb`: `pyusb.ledger` (3418
lines, 6 default-rejection lines with 22 candidates), `pyusb.json` (315
nodes, 923 edges: 549 inside, 374 outside), `pyusb.added.json` (828 added
edges), `pyusb.rejected.json` (2 trace edges) and `pyusb.md` (J1 to J11).
The trace (16 tests through the tests' fake backends) confirms 95 of the
923 edges; 39 of 301 functions ran. `check.py pyusb` reports no errors.

I read the package source (all 14 modules), `setup.py`, `tox.ini`,
`.github/workflows/run_tox.yml` (as data), `docs/tutorial.rst`,
`docs/faq.rst`, the tests (`tests/*.py`, as data), the README's rules and
rulings, `PyCG/micro-benchmark/README.md` (names), the precedents of
batches 1 to 7 (`mss`, `pymysql`, `bottle`, `tenacity`, `asyncstdlib`,
`funcy`, `configargparse`, `pyrate-limiter`, `structlog` ledgers for
ctypes, `functools.wraps`, `weakref`, `object.__init__`, `_thread.RLock`
and logging names), and in the dependency sources (read only): CPython
3.9.25, 3.12.16, 3.13.18 and 3.14.10 `Lib/ctypes/__init__.py`,
`Lib/weakref.py`, `Lib/threading.py` and `Modules/_ctypes/_ctypes.c`;
PyPy 3.9 to 3.11 `lib-python/3/ctypes/__init__.py`,
`lib-python/3/threading.py` and `lib_pypy/_ctypes/{array,basics}.py`. I ran
nothing of the package and no analysis tool. Commands: `check.py
--benchmark-dir <scratch> --skeleton pyusb` and the size report (blind);
then `check.py pyusb`, `--origin`, `--report`, `--report
--without-candidates`, `--report --default <candidate>` for the defaults;
scripts of my own on the text (`draw.py`; an `ast` binding script; graph
counts with `json`).

## Final state

- **Agreement: 167 of 168** sites re-derived blind. The one difference is
  a name (F1), in which I think the writer is wrong.
- **Edges missing: 0. Edges that cannot happen: 0.**
- **Changes asked:** F1 renames 4 outside edges
  (`ctypes.memset` to `ctypes.CFUNCTYPE.CFunctionType.__call__`); the edge
  count stays 923 (549 / 374). No edge inside the package changes.
- The writer's three large judgements (J1 tracing, J2 `synchronized`, J3
  `IBackend` as a receiver) are the ones I wrote blind, before reading the
  writer's files (`blind-answers.md`, "Conventions").

## Findings

| Id | Kind | Site or edge | Evidence (file:line) | Edges | Decision |
|---|---|---|---|---|---|
| F1 | naming (low) | `memset(byref(request), 0, sizeof(request))` at `openusb.py` 653:15, 663:15, 673:15, 683:15: `-> ctypes.memset` | `ctypes.memset` is no function: it is an instance of the class that `CFUNCTYPE(c_void_p, c_void_p, c_int, c_size_t)` returns (CPython 3.9 `ctypes/__init__.py:499`, 3.13 `:533`, 3.14 `:606`; PyPy 3.10 `lib-python/3/ctypes/__init__.py:498`, 3.11 `:502`), the class `CFunctionType` defined inside `CFUNCTYPE` (PyPy 3.11 `:103-108`). The micro-benchmark names a call of an instance of an outside class `<class path>.__call__` ("Calls of instances"), and the 2026-11-15 clarification says "a callable wrapper object uses its concrete class's `__call__`"; the mss rulings name the same kind of object, a foreign function pointer, `ctypes.CDLL.__init__._FuncPtr.__call__`, and its class `ctypes.CFUNCTYPE.CFunctionType`. | 4 renamed (`_OpenUSB.bulk_write`, `bulk_read`, `intr_write`, `intr_read -> ctypes.CFUNCTYPE.CFunctionType.__call__`) | the writer renames; `pyusb.md` J8 names it |
| R1 | README (low) | ctypes helpers that are function-pointer objects | `ctypes.memset` and `ctypes.memmove` are `CFUNCTYPE(...)` instances, while `cast`, `string_at` and `wstring_at` are Python functions. The ctypes ruling of batch 7 covers foreign functions of a `CDLL`, not these module-level objects; one clause would fix the name for the next writer. | 0 | for the lead |
| R2 | dependency sources (low) | `self.lock.acquire()`, `.release()` at `core.py` 112:30, 115:30 | `threading.RLock()` returns `_thread.RLock` when `_thread` has it (CPython 3.13 `threading.py:53`, `:137-139`; PyPy 3.9 to 3.11 `threading.py:46`, `:91-93` or `:99-101`, the same code); otherwise the Python `threading._RLock`. CPython's `_thread.RLock` is in the trace. PyPy's `_thread` is interpreter-level code (`pypy/module/thread`), which the dependency sources do not hold (only `lib-python` and `lib_pypy`), so the writer's "from memory" for PyPy cannot be checked there. I take `_thread.RLock` as the writer does; if PyPy lacked it, `threading._RLock.acquire` and `.release` would be added (2 outside edges). | 0 (2 at most) | for the lead: accept, or add PyPy's interpreter modules to the dependency sources |

## Step 1: blind re-derivation

**Skeleton.** From a scratch copy of `projects.toml` and `projects/pyusb`
(no ledger): 2564 sites: 975 call, 88 decorator, 1267 getattr, 101 op, 62
getitem, 57 iter, 11 mapping, 3 setitem; 29 value sites. The two
`__getattr__` of libusb1 are candidates at 1300 sites each.

**Draw, by kind.** Explicit sites (call, decorator) are 1063 of 2564; the
1501 implicit sites are dominated by attribute loads (1267) whose only
candidates are the two `__getattr__`. I numbered the sites by (module in
skeleton order, line, column) and drew with one `random.Random(20261124)`:
`rng.sample(explicit, 100)` then `rng.sample(implicit, 40)` (the mss split
of batch 7 for a doubled audit), then added the 28 value sites the draw did
not take (one, `libusb1.py:776:49`, was drawn as explicit): 168 sites.
`draw.py`, `sample.txt` and `blind-answers.md` are in
`macro-benchmark/selection/batch-8-proposal/audits/pyusb/`, committed as
`8386c11` before I opened any file of the writer.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Explicit (call, decorator) | 100 | 99 | 1 (F1) |
| Implicit (32 getattr, 4 getitem, 3 op, 1 iter) | 40 | 40 | 0 |
| Value sites not in the draw | 28 | 28 | 0 |
| **Total** | **168** | **167** | **1** |

The one difference, classified: **naming only, the writer's** (F1,
`openusb.py:663:15`, drawn as #1435; the other three `memset` sites follow).
No difference of the kinds "the writer missed an edge", "the writer has an
edge that cannot happen" or "I was wrong".

Of the 40 implicit sites, 39 have no ledger entry: the defaults decide them,
and my blind rejections are the defaults' decisions. The 40th
(`core.py:259:46`, `self.backend` on a `_ResourceManager`) rejects
`Device.backend` in both. The 29 value sites all agree, among them the
two dispatch sites of `Device.write` and `Device.read` (10 callees each,
with `IBackend.iso_write`/`iso_read` through openusb and without
`IBackend`'s other methods), the 70 callees of `do_trace`'s `f(...)` and
the 11 of `wrapper`'s `f(...)`.

## Step 2: exhaustive checks

**Dispatch over the backend (J1, J3).** I listed every call of a backend
method in `core.py` (21 sites) and in the backends (`self.X(...)` at
libusb0 480, 492, 519; libusb1 787, 799; openusb 735; `_LibUSB(_lib)` at
libusb1 967; `self._finalize_object()` at `_objfinalizer.py:71`). Each has
`do_trace` (29 callers, the writer's count) beside the methods. The
receivers at the core sites after a `Device` exists are the three
`get_backend` backends; `IBackend`'s methods appear only where libusb0 or
openusb inherit them (`get_parent`, `iso_write`, `iso_read`,
`is_kernel_driver_active`, `detach_kernel_driver`,
`attach_kernel_driver`), and `IBackend` itself only at the two first calls
(`find.device_iter` `enumerate_devices`, `Device.__init__`
`get_device_descriptor`). I count the 17 `IBackend` methods that J3 leaves
out and find the same 17. `do_trace -> f` has the 70 decorated methods
(an `ast` listing of `@methodtrace` gives 70: 23 libusb0, 28 libusb1, 19
openusb).

**`synchronized` (J2).** Every call of the 11 methods (24 callers, in
`core.py` and `util.py`) has `usb.core.synchronized.wrapper` and rejects the
method; `wrapper -> f` has the 11. `wrapper` also calls
`_thread.RLock.acquire` and `.release` (R2).

**`_finalize_object`.** `_do_finalize_object` (`_objfinalizer.py:71`)
reaches the 10 overrides (5 libusb1, 3 openusb, `core.Device`,
`legacy.DeviceHandle`), the base method (inherited by `IBackend`, libusb0
`_LibUSB`, openusb `_OpenUSB`) and `do_trace` (two libusb1 overrides are
decorated). `__del__ -> AutoFinalizedObject.finalize` only.

**Default rejections (22 candidates).** I listed the sites of each with
`--report --default`:

- `_ConfigDescriptor.__getattr__` (1295 sites) and
  `_WrapDescriptor.__getattr__` (1297): the two classes reach attribute
  loads only through libusb1's descriptor methods (`libusb1.py:780`, `795`,
  `804`) and `core._set_attr` (`core.py:67`). The accepted sites
  (`libusb1.py` 782:29, 782:48, 788:24, 790:17, 800:19, 802:21, and
  `getattr(input, f)` at `core.py:67`) are all of them; `desc`,
  `_finalizer` and `_finalize_called` are instance attributes, and
  `hasattr(self, 'desc')` (`libusb1.py:632`) never falls back because
  `__init__` sets `desc` first.
- `__getitem__` of `Device`, `Configuration`, `Interface` (129 sites): the
  package subscripts a Device at `core.py:144`, `265` and a Configuration at
  `187`, `206` (accepted); the other 129 subscript ctypes pointers and
  arrays, dicts, tuples, `array.array` buffers, lists and a match.
- `Device.__eq__` (116) and `Device.__hash__` (68): no comparison, `in` test
  or dict/set key of the package meets a Device (`val ==
  _try_getattr(d, key)` and `val == getattr(d, key)` compare client values
  with descriptor fields; `_claimed_intf`, `_intf_setting`, `_ep_info` hold
  ints; `groupby` in `legacy.busses` compares `d.bus` ints).
- The nine `__str__`/`__repr__` (72 sites): the descriptor objects are
  formatted only at `core.py` 517, 640, 773, 1345 (accepted); every other
  `%`, `str()` and log argument is an int, str, None, bytes, a backend
  argument (`_trace_function_call`, `_debug.py:48`, `49`) or a CDLL.
- The six `__iter__` (63 to 66 sites): the accepted iterations (`util.py:179`;
  `legacy.py` 120, 134, 339; `core.py` 243, 516, 522, 639, 645, 772, 784,
  1304; `openusb.py` 558, 559) are all that iterate a package iterable; the
  rest iterate tuples, sets, lists, `buffer_info()` results, generators and
  ctypes arrays.

**Implicit sites without candidates** (`--report --without-candidates`):
truth tests of ints, bools, strs, ctypes values and a `Device` (no
`__bool__` or `__len__`); arithmetic on ints and ctypes classes (library
metaclass code). The one library iteration that calls the package back is
`legacy.py:353:44` (a `groupby` group, `busses.<lambda2>`), which the
writer added (J10). The lazy `map` of `util.py:281` is consumed in its own
function.

**Functions that no site calls (87 nodes, modules included).** I checked
each: the `functiontrace` closures (no package use), `__del__` (garbage
collection only), `_AutoFinalizedObjectBase.finalize` (overridden),
`NullHandler.emit` (J7), the 17 `IBackend` methods of J3, the client API of
`usb.control` (but `get_descriptor`), `core` (`show_devices`, the
`__repr__`s, `__eq__`, `__hash__`, `Device.manufacturer`, `parent`,
`product`, `serial_number`, the `default_timeout` accessors,
`Interface.__getitem__`, `Endpoint.read`/`write`/`clear_halt`,
`Configuration.set`/`interfaces`, `Interface.endpoints`/`set_altsetting`,
`Device.configurations`, `is_kernel_driver_active`,
`attach_kernel_driver`), `legacy` (`busses`, `Device.open`, the
`DeviceHandle` methods) and `util.endpoint_address`. None has a package
caller that the ledger misses.

**Special methods and properties.** Properties loaded by the package:
`Device.langids` (`util.py:307`) and `Device.backend` (`core.py:758`, `759`,
`764`), both accepted; every other load of `backend` is the plain attribute
of `_ResourceManager` or the module `usb.backend`, rejected. No field name of
`_set_attr` is a property. `default_timeout` is never loaded or stored by the
package. No package class defines `__bool__`, `__len__`, `__call__`,
`__init_subclass__`, `__set_name__` or a metaclass. Constructors: every
construction of an `AutoFinalizedObject` subclass (Device, the libusb1 and
openusb helpers, the three backends, `DeviceHandle`) has
`AutoFinalizedObject.__new__` and rejects the base `__new__`; the classes
without `__init__` (libusb0 `_LibUSB`, `_OpenUSB`, `IBackend`) get no
`__init__` edge; `NullHandler()` is `logging.Handler.__init__`;
`NoBackendError` and the libloader exceptions are named through
`ValueError.__init__` and `OSError.__init__`; `_DescriptorInfo(strings)` has
none (the tabulate ruling).

**Rejections, exclusions and notes.** I read all 281 rejection lines and
127 notes (no exclusion). Each reason holds against the source; the notes
of the value sites name the right flows. J6's bytes comparison
(`libusb0.py:440`) is false on every runtime (the restype `c_char_p` is set
unconditionally at `:357`; a `_lib` left behind by a failed
`_setup_prototypes` is excluded by B3).

**Callees outside the package (101 names).** I checked each against the
naming rules and the dependency sources: the ctypes names (J8:
`ctypes.CDLL.__init__._FuncPtr.__call__` 70 edges, also for libusb1's
`WinDLL`, which inherits `CDLL.__init__`; `ctypes.Structure.__init__` for
the ten package structures without `__init__`;
`ctypes.c_void_p.__pointer_type__` and `ctypes.c_uint64.__pointer_type__`
on CPython 3.14, `Lib/ctypes/__init__.py:271-295`;
`_ctypes.PyCArrayType.from_address`, type name in `_ctypes.c` of 3.9 to
3.14, and PyPy's `_ctypes.array.ArrayMeta.from_address`,
`lib_pypy/_ctypes/array.py:76`), `weakref.finalize.__call__` calling
`_do_finalize_object_ref` (`weakref.py:586-591`), `weakref.ref.__call__`,
`functools.partial.__call__` at `@functools.wraps(f)`, the logging names by
receiver class (`logging.FileHandler.setFormatter`,
`logging.StreamHandler.setFormatter`), `<builtin>.IOError.__init__` (the name
the code uses; the trace's alias list maps it to `OSError.__init__`),
`re.Match.groups`, `array.array.*`, `<builtin>.bytes.decode`/`lower`. All
hold but `ctypes.memset` (F1) and the PyPy half of `_thread.RLock` (R2).

**Rejected trace edges.** `find -> _AutoFinalizedObjectBase.__del__` and
`find.device_iter -> _AutoFinalizedObjectBase.__del__`: `__del__` that runs
when a function drops the last reference is no edge (README, "Implicit
calls"). Correct.

**Trace edges that the graph lacks:** none (`check.py pyusb`, and
`--report`: 0 trace edges that no site accounts for).

## Step 3: binding check

An `ast` script matched every call site of the ledger with a callee in the
package against the callee's signature (positional count with the bound
receiver for method calls and constructors, keyword names, required
parameters). It flagged only its own blind spots, which I checked by hand:
calls through `wrapper(self, *args, **kwargs)` and `do_trace(*args,
**named_args)` (always bind), the bound methods of `fn_map`
(`core.py:1003`, `1043`: five arguments and `self` for six parameters), the
callback `_do_finalize_object_ref(obj_ref)` (called by `weakref.finalize`
with its one registered argument) and the five lambdas (one argument for
the `sorted` and `groupby` keys, two for the `map` of `util.py:281`). The
starred calls bind too (`_trace_function_call(logger, fn, *args[1:],
**named_args)`, `device_iter(**args)`, `desc_iter(**args)`,
`find(**kwargs)`, the `super().__new__(cls, *args, **kwargs)` chain). No
call fails to bind, so no edge and no following code is removed.

## The writer's judgement calls

| J | Opinion | Nearest rule |
|---|---|---|
| J1 `PYUSB_DEBUG` and `methodtrace` (36 edges) | agree; I reached it blind | "Rulings for batch 6", tinytag: an environment variable that the package reads for a value of its own counts when its documentation sets it (`docs/tutorial.rst:127-136`, `docs/faq.rst:17`); `_setup_log` runs before any backend import |
| J2 `synchronized` (24 + 11 edges) | agree; blind too | micro-benchmark: a call of a decorated name calls what the decorator returned; the README's decorator clause (fabric) |
| J3 `IBackend` as a receiver (2 in, 17 out) | agree; blind too | B1 (a plain public documented base is a receiver of its own methods) with B3 (no object left behind by a failure: an `IBackend` backend never yields a `Device`) |
| J4 versions, implementations, platforms | agree | "Implementation, version and platform combinations"; IronPython and Jython have no Python 3.9 |
| J5 finalization | agree | README "Implicit calls" (`__del__`); callback rule for `finalize.__call__` |
| J6 dead `os.strerror` | agree | B1: a branch that the package's own values never take (bytes never equal a str) |
| J7 `NullHandler.emit` | agree | B5, configuration selection: no documented configuration lowers the `usb` logger's level |
| J8 ctypes names | agree, with F1 added | the mss rulings; "a callable wrapper object uses its concrete class's `__call__`" |
| J9 isochronous callback | agree | mss ruling: a package function entered through a C callback thunk is a callee of the foreign call that runs it (`libusb_handle_events`) |
| J10 lazy iterators | agree | uncertainties ruling on a lazy iterator consumed through another library iterator |
| J11 `functiontrace` | agree | B (uncalled private function judged as public), B5 |

## For the lead

- No case needs a ruling: every judgement and F1 follow from an existing
  rule or ruling.
- R1 (README): one clause on ctypes module-level function-pointer objects
  (`memset`, `memmove`) would fix the name that F1 asks for.
- R2 (dependency sources): PyPy's `_thread.RLock` cannot be checked in the
  dependency sources; at most 2 outside edges depend on it. Accept the
  writer's name, or add PyPy's interpreter modules to `deps/`.

## Re-check (the committed ground truth at `d407603`)

`d407603` changes `pyusb.ledger`, `pyusb.json`, `pyusb.added.json` and
`pyusb.md` only. `check.py pyusb` reports no errors; `--origin`: 97 trace
edges, 2 rejected, 95 traced (37 / 58), 828 added (512 / 316), 923 graph
edges (549 / 374), as before.

| Id | Re-check | Open |
|---|---|---|
| F1 | The four sites `openusb.py` 653:15, 663:15, 673:15, 683:15 now name `ctypes.CFUNCTYPE.CFunctionType.__call__`, each with a note; the graph diff replaces `ctypes.memset` by that name in the four callers `_OpenUSB.bulk_write`, `bulk_read`, `intr_write`, `intr_read` and changes nothing else. I checked `memset = CFUNCTYPE(...)(_memset_addr)` again in CPython 3.15.2 `Lib/ctypes/__init__.py:595` and PyPy 3.9 `lib-python/3/ctypes/__init__.py:498` (the other versions in the finding). `pyusb.md` J8 names it. | no |
| R2 | PyPy's interpreter modules are now in the dependency sources. In PyPy 3.9, 3.10 and 3.11, `pypy/module/thread/moduledef.py:24` puts `'RLock': 'os_lock.W_RLock'` in `interpleveldefs` (unconditional), and `os_lock.py` gives `W_RLock` the TypeDef `"_thread.RLock"` with `acquire` and `release` (`:306-310`; 3.11 `:316-320`). `lib-python/3/threading.py:46` then takes `_CRLock = _thread.RLock`, so `threading.RLock()` returns it: `_thread.RLock.acquire` and `.release` hold on PyPy too, and no `threading._RLock` name is needed. The ledger note at `core.py:112:30` and `pyusb.md` cite these lines. | no |
| R1 | For the lead (README); no change in the ground truth. | no (lead) |

Nothing is open: the audit is closed at `d407603` (923 edges, 549 inside,
374 outside).

## Codex round 1 re-check (against `bc2e034`)

The findings are in `selection/batch-8-proposal/codex-audits/round-1/pyusb.md`
(6 missing, 3 unsure); the writer applied M1 to M6 in `2f0af85` and U1 to
U3 with one extension in `bc2e034` (`pyusb.md`, "Codex round 1", J7, J9).
`check.py pyusb` at `bc2e034`: no errors, 933 edges (559 inside, 374
outside), 95 confirmed by the trace. The graph has `NullHandler.emit` from
exactly six callers and `_IsoTransferHandler.__callback` from exactly
five; nothing else changed in pyusb's files.

**M1 to M6 (6 inside edges): agree.** Witness: `PYUSB_DEBUG` unset, so
`_setup_log` gives the `usb` logger the level `CRITICAL + 10` and the
package's `NullHandler` (`usb/__init__.py:94-103`); the client then lowers
the `usb` logger through logging's public interface, which the nodeenv
ruling ("Rulings for batch 8") admits. The module loggers (`usb.core`,
`usb.libloader`, `usb.backend.libusb0`, `libusb1`, `openusb`) are
children of `usb` with no level of their own, so their records pass the
level test and `callHandlers` walks up to `usb` and calls `hdlr.handle`,
which calls `self.emit` (CPython 3.9 `logging/__init__.py:1645-1665`,
`939-952`; 3.15 `:1733-1753`, `1014-1030`; PyPy 3.9 the same lines as
CPython 3.9, PyPy 3.11 `:1690-1710`, `965-978`). A grep of the
source finds 14 logging calls; the 13 that the writer marks are every one
reached without `PYUSB_DEBUG` (`libusb0.py` 744, 747; `libusb1.py` 971,
974; `openusb.py` 751, 755, 758; `core.py` 1318; `libloader.py` 144, 184,
190, 203), each reachable on its branch. The 14th,
`_trace_function_call`'s `logger.debug` (`_debug.py:45`), runs only
through `do_trace`, which exists only with `PYUSB_DEBUG` set, when the
`usb` logger has a `FileHandler` or `StreamHandler` and no `NullHandler`
(or through `functiontrace`, a client logger, B5): the writer's exclusion
holds.

**U1 to U3 and the extension (4 inside edges): agree.** Checked in libusb
1.0.30 (`deps/libusb/1.0.30/libusb/`, commit `87a5563`):

- Callbacks run only in the thread that handles events
  (`io.c:549-552`); `usbi_handle_transfer_completion` calls
  `transfer->callback` (`io.c:1723-1725`) from the backend's event
  handling (`handle_events`, `io.c:2287`), for any transfer of the
  context. Every backend that `grep` finds completes transfers through
  that path (`usbi_handle_transfer_completion` or
  `usbi_signal_transfer_completion`, handled later in `handle_events`).
- The synchronous transfers submit and then wait in
  `sync_transfer_wait_for_completion`, a loop on
  `libusb_handle_events_completed(ctx, completed)` (`sync.c:49-55`;
  control `sync.c:139`, bulk and interrupt `sync.c:200`). A waiter that
  takes the event lock does the context's event handling itself
  (`io.c:2370-2376`), so another thread's isochronous transfer can
  complete there and its callback, `_IsoTransferHandler.__callback`, runs
  inside `__write`'s `fn(...)` (`libusb1.py:934:20`), `__read`'s
  (`950:20`) or `ctrl_transfer`'s (`897:54`) foreign call (the mss
  ruling on C callback thunks).
- A second thread is admitted: libusb is thread-safe (`io.c:808`); the
  path ruling (c) puts no restriction to one thread on a witness;
  pyusb's libusb1 backend is one object with one context (`get_backend`,
  `libusb1.py:964-968`); `Device.read`/`write` call the backend outside
  `_ResourceManager`'s lock. Thread A: `dev.read` on an isochronous
  endpoint (`iso_read`, `submit` in flight, `685`); thread B: a bulk,
  interrupt or control transfer on the same backend.
- Windows `set_configuration` (`816:49`): `libusb_set_configuration` goes
  through `windows_set_configuration` (`os/windows_common.c:708-713`) to
  WinUSB's `winusb_set_configuration`, a synchronous
  `libusb_control_transfer` (`os/windows_winusb.c:2464-2469`), and WinUSB
  submits isochronous transfers (`:2605-2606`). UsbDk's
  `set_configuration` does nothing (`windows_usbdk.c:451-456`), which does
  not remove the WinUSB edge.
- The writer's exclusions hold in 1.0.30. The only synchronous transfers
  that libusb makes inside its own API are three `libusb_control_transfer`
  calls (`grep` over `core.c`, `descriptor.c`, `os/`): the
  `libusb_get_configuration` fallback (`core.c:1716-1719`), Solaris's
  `clear_halt` (`os/sunos_usb.c:1360-1363`) and WinUSB's
  `set_configuration`. The fallback needs `LIBUSB_ERROR_NOT_SUPPORTED`,
  which no `get_configuration` of an admitted platform returns (Linux
  `linux_usbfs.c:1495-1520` with `usbfs_get_active_config`, `:886-925`,
  which does its own ioctl; macOS `darwin_usb.c:1684-1690`; WinUSB
  `windows_winusb.c:2451-2457`; UsbDk `windows_usbdk.c:442-449`; NetBSD
  `netbsd_usb.c:278-290`, whose errno mapping has no `NOT_SUPPORTED`;
  OpenBSD `openbsd_usb.c:306-313`; Solaris `sunos_usb.c:1071-1078`).
  Solaris refuses isochronous submissions (`sunos_usb.c:1416-1426`), so no
  `__callback` is in flight there. `libusb_close` takes the event lock and
  runs `do_close`, which unlinks in-flight transfers without completing
  them and calls no `handle_events` (`core.c:1551-1600`, `1606-1660`).

**The version claim: agree for the edges, with two remarks.** `setup.py`
declares "libusb 1.x"; 1.0.30 (ChangeLog: 2026-05-17) satisfies it and
batch 7's ruling on admitted releases sets no date bound, so the four
callback edges rest on an admitted release; the WinUSB isochronous support
that the Windows edge needs dates from 1.0.23 (ChangeLog line 117), before
the CI's 1.0.24.

- CR1 (low, for the lead): the exclusions (no `get_configuration` or
  `clear_halt` edge outside Solaris) are read in 1.0.30 only. The tablib
  ruling on which releases are read asks for the floor of the declared
  range as well (libusb 1.0 is one minor series, so its oldest admitted
  release); the floor is not in the dependency sources, and the
  ChangeLog shows that the backends' `get_configuration` changed over the
  series (OpenBSD, 1.0.21 section, "make get_configuration() no longer
  generate I/O"). At most one inside edge
  (`_LibUSB.get_configuration -> __callback`) could depend on it.
- CR2 (low, for the lead): on FreeBSD, a declared platform,
  `find_library` resolves the candidate `usb` (`libusb1.py:288`) to the
  base system's own implementation of the libusb 1.0 API, which is not in
  the dependency sources. The four edges do not depend on it (they hold on
  Linux, macOS and Windows); only the exclusions could.

No disagreement with any applied edge: M1 to M6 and the four callback
edges stand (933 edges: 559 inside, 374 outside). CR1 and CR2 are open
for the lead's decision; they can only add edges, never remove one.

## Re-check of CR1 and CR2 (against `39c665c` and `b2baa08`)

The lead added libusb 1.0.0 and 1.0.12 (`deps/libusb/`) and FreeBSD's own
`lib/libusb` at `release/14.5.0` and `release/15.1.0`
(`deps/freebsd-libusb/`). `39c665c` answers both remarks in `pyusb.md`
only; `b2baa08` adds `_LibUSB.get_configuration ->
_IsoTransferHandler.__callback` at `libusb1.py:821:49` (the graph diff
adds that one name and nothing else). `check.py pyusb` at `b2baa08`: no
errors, 934 edges (560 inside, 374 outside), 95 confirmed by the trace.

**CR1, the floor of libusb 1.0: agree (+1 inside edge).**

- The floor claim. An `ast` listing of `_setup_prototypes`
  (`libusb1.py:293-591`) gives the 34 symbols that it loads outside a
  `try` or `if hasattr` (`libusb_alloc_transfer` to
  `libusb_unref_device`; `libusb_strerror`, `libusb_get_device_speed`,
  `libusb_get_port_number` and `libusb_get_port_numbers` are guarded, and
  `libusb_fill_iso_transfer` and `libusb_set_iso_packet_lengths` are
  stores). Every one is defined as exported in 1.0.12 (`API_EXPORTED`, or
  `DEFAULT_VISIBILITY` on the line before: `libusb_get_parent`
  `core.c:722-723`, `libusb_ref_device` `875-876`, `libusb_alloc_transfer`
  in `io.c`) and listed in `libusb-1.0.def`. 1.0.0 lacks
  `libusb_get_parent` (absent from its `libusb.h`) and
  `libusb_get_max_iso_packet_size`, so `_setup_prototypes` raises
  `AttributeError`, `get_backend` catches it (`libusb1.py:973`) and no
  libusb1 backend exists: 1.0.0 adds nothing. 1.0.30's ChangeLog dates
  `libusb_get_parent` to v1.0.12 (2012-06-15, line 274), so no release
  between 1.0.0 and 1.0.12 can be loaded either, and 1.0.12 is the floor
  that the tablib ruling asks to read.
- The edge. In 1.0.12, `libusb_get_configuration` falls back to a
  synchronous `libusb_control_transfer` on `LIBUSB_ERROR_NOT_SUPPORTED`
  (`core.c:1234-1247`), and Linux's `op_get_configuration` returns it when
  `sysfs_can_relate_devices != 1` (`os/linux_usbfs.c:1319-1324`), which
  holds when `/sys/bus/usb/devices` is no directory or no `usbN` root hub
  there has `busnum`, `devnum` and `bConfigurationValue` (`:355-420`).
  That is a state of the file system of an admitted Linux system (no
  sysfs mounted, as in some containers), and the path ruling (c) admits
  any possible file-system state; enumeration then goes through usbfs, so
  the backend still works. The control transfer waits in
  `libusb_handle_events_completed` on the context (`sync.c:104-105`),
  whose event handling runs a completed transfer's callback
  (`io.c:1487-1488`), and Linux submits isochronous transfers
  (`linux_usbfs.c:1977-1978`). With another thread's isochronous transfer
  in flight, `__callback` runs inside `get_configuration`'s foreign call:
  the edge holds.
- No other edge from 1.0.12: its only synchronous transfers inside libusb
  are `core.c:1246` (this fallback) and Windows `set_configuration`
  (`os/windows_usb.c:1736`), already an edge.

**CR2, FreeBSD's own libusb: agree with the edges, one wording finding
(W2).** FreeBSD is admitted (classifier `Operating System :: POSIX :: BSD
:: FreeBSD`; a CI matrix does not narrow a declared platform). Its base
library is `libusb.so.3` (`Makefile`: `LIB= usb`, `SHLIB_MAJOR= 3`), and
`ctypes.util.find_library` on FreeBSD matches `-l<name>` in `ldconfig -r`
(CPython 3.13 `ctypes/util.py:205-226`), so the candidate `usb`
(`libusb1.py:288`) loads it. In 15.1.0 every one of the 34 symbols is
defined (`libusb10.c`, `libusb10_io.c`, `libusb10_desc.c`; `libusb_get_parent`
`libusb10.c:894`). There: callbacks run only from `libusb_handle_events`'s
done queue (`libusb10_io.c:197-219`), which `libusb10_complete_transfer`
fills (`libusb10.c:1198-1219`); bulk and interrupt transfers wait in
`libusb_handle_events(ctx)` (`libusb10_io.c:576-583`), so U1 and U2 hold;
`libusb_control_transfer` is `libusb20_dev_request_sync` (`:498`), no event
handling, so U3 does not hold on FreeBSD but holds elsewhere;
`libusb_get_configuration` reads a descriptor (`libusb10.c:736-753`),
`libusb_set_configuration` closes this device's transfers, whose
completion only queues, and sets the configuration by ioctl (`757-799`),
and `libusb_clear_halt` is `libusb20_tr_clear_stall_sync` (`915-942`): no
callback runs in them. No edge changes, as the writer says.

| Id | Kind | Site or edge | Evidence | Edges | Decision |
|---|---|---|---|---|---|
| W2 | wording (low) | `pyusb.md`, "Audit remarks after the re-check", CR2: "FreeBSD's `libusb.so` exports the libusb 1.0 API with every symbol that `_setup_prototypes` needs" for 14.5.0 and 15.1.0 | `libusb_get_parent` is in 15.1.0 (`libusb10.c:894`, `libusb.h:526`) but nowhere in 14.5.0's tree (`libusb.h:492-494` has the port calls only). On FreeBSD 14.5, `_setup_prototypes` raises `AttributeError` at `libusb1.py:311` and `get_backend` returns None: pyusb's libusb1 backend works only on FreeBSD 15.1 of the two releases read. | 0 (the FreeBSD analysis rests on 15.1.0, where it holds) | the writer corrects the sentence |

No disagreement on any edge: CR1's edge stands (934 edges: 560 inside,
374 outside) and CR2 changes none. W2 is open for the writer.
