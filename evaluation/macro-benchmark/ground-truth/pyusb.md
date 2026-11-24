# pyusb: judgements of the ground truth

Status (writer, batch 8, 2026-11-24): complete; the doubled blind audit
(`pyusb.audit.md`: 167 of 168 sites agree, no missing and no false edge)
is applied: F1 renamed 4 outside edges (J8), and R2 named the PyPy lock
from PyPy's sources (no edge changed); see "Audit". Codex round 1 is
applied: M1 to M6 added 6 inside edges (J7); U1 to U3, decided from
libusb 1.0.30's sources, added 3, and the same check added 1 more; the
audit remark CR1, decided from libusb 1.0.12, added 1 more (J9).
`check.py --write pyusb` and `check.py pyusb` report no error; every site
is decided; the two trace edges that the graph lacks are in
`pyusb.rejected.json` (J5).

Release v1.3.1 (commit `89ea84d`). Analysed source: `usb/` (root `.`), 14
modules, 301 functions (5 lambdas), 67 classes. `usb/_version.py` is not
in the checkout (it is written at build time); `usb/__init__.py:51-54`
falls back to `'0.0.0'`, which changes no edge.

The trace is thin: 16 tests ran (`test_find.py`, `test_interop.py`,
`test_util.py`) through the tests' fake backends, without libusb, and
`FindDescriptorTest::runTest` failed as declared (`NoBackendError`). 39 of
301 functions ran. The three ctypes backends (`usb/backend/libusb0.py`,
`libusb1.py`, `openusb.py`), `usb.legacy`, `usb.control` and most of
`usb.core` come from reading only.

Drafting: a script of the writer (in its scratch directory, not committed)
wrote the ledger from per-site decisions written by hand after reading
every function, and from naming patterns decided by hand for the plain
sites: builtins, `ctypes` helpers (`POINTER`, `byref`, `cast`, `memset`,
`sizeof`, `addressof`, `c_void_p()`, `c_int()`, `c_uint8()`,
`c_uint32()`), foreign-function calls `_lib.x(...)` and `self.lib.x(...)`,
each backend module's `_check`, `errno.__dict__.get`, the module loggers,
`array.buffer_info()`, and the decorators `@methodtrace(_logger)`,
`@synchronized` and `@property`. Every generated entry was reviewed
against the source.

## Supported versions, implementations and platforms

- `setup.py`: `python_requires='>=3.9.0'`; classifiers Python 3.9 to 3.13
  (the last one is not an upper bound: CPython 3.9 to 3.15 count) and the
  implementations CPython, IronPython, Jython and PyPy. No IronPython or
  Jython release implements Python 3.9 or later (IronPython 3.4 targets
  3.4, Jython is 2.7), so only CPython and PyPy 3.9 to 3.11 count (README,
  "Implementation, version and platform combinations": only combinations
  on which the implementation exists). No edge depends on this.
- Platforms (classifiers): macOS, Windows (Vista, 7, 10), FreeBSD, NetBSD,
  OpenBSD, Linux and Solaris; the CI (`.github/workflows/run_tox.yml`)
  runs Ubuntu, macOS and Windows, Python 3.9 to 3.13. Every branch of
  these runs:
  `load_library -> ctypes.WinDLL` (libusb1 on win32, `libusb1.py:283`);
  `locate_library -> platform.machine` and `os.path.isfile` (macOS on
  arm64, `libloader.py:95`, `113`); `usb.backend.libusb0 -> os.pathconf`
  (Linux, `libusb0.py:59`).
- Cygwin (`sys.platform == 'cygwin'`, `libloader.py:142`, `176`;
  `libusb0.py:56`, `68`) and DragonFly BSD (`libusb0.py:648`) are not
  declared. No edge depends on them: the cygwin branch of
  `load_locate_library` calls `load_library` and raises
  `NoLibraryCandidatesException`, which the other branches also do, and
  `startswith('dragonfly')` runs on every platform that is not FreeBSD.
- Python-version names: `POINTER(c_void_p)()` and `POINTER(c_uint64)()`
  are named `ctypes.c_void_p.__pointer_type__` and
  `ctypes.c_uint64.__pointer_type__` (CPython 3.14 and later; mss J2);
  `from_address` of an array type has the CPython and the PyPy name (J8).

## Values and architecture, as the ledger uses them

- **Backends.** `usb.core.find(backend=...)` and `Device(dev, backend)`
  take a backend object. Package values: the backend objects that
  `get_backend()` of `usb.backend.libusb0`, `libusb1` and `openusb`
  return (`_LibUSB` of libusb0 and libusb1, `_OpenUSB`; `find` picks one
  when none is given, `core.py:1310-1321`, and the documentation passes
  them, `docs/tutorial.rst:579`), and an `IBackend` itself at the first
  call only (J3). A client backend, a client subclass of `IBackend` too,
  is opaque (B5): the tests' fake backends are client code. libusb0 and
  openusb inherit some methods from `IBackend` (`get_parent`;
  `attach_kernel_driver` in libusb0; `iso_write`, `iso_read`,
  `is_kernel_driver_active`, `detach_kernel_driver`,
  `attach_kernel_driver` in openusb), so those `IBackend` methods are
  callees through them.
- **Every backend method is wrapped** (`@methodtrace(_logger)`, 70
  methods): a call of one has the method and `do_trace` as callees (J1).
- **`_ResourceManager`** (private) is the `_ctx` of each `Device`
  (`core.py:795`); its backend is the Device's backend. Its eleven methods
  are wrapped by `synchronized`: every call of one has `wrapper` as its
  callee (J2).
- **Descriptors.** `Device` iterates to `Configuration`, `Configuration`
  to `Interface`, `Interface` to `Endpoint` (`core.py:1148`, `651`, `530`);
  subscripts likewise (`1153`, `662`, `540`). `Configuration` and
  `Interface` are not hashed or compared by the package. libusb1 returns a
  `_ConfigDescriptor` (`libusb1.py:780`) and `_WrapDescriptor`s (`795`,
  `804`), whose fields are read through `__getattr__`; libusb0 and
  openusb return ctypes structures.
- **Buffers.** The data of a backend transfer is the `array.array` of
  `_interop.as_array` or `util.create_buffer` (`core.py:1007`, `1041`,
  `1080`), so `x.buffer_info()` is `array.array.buffer_info`.
- **Libraries.** `_lib` and `self.lib` are the `ctypes.CDLL` (or the
  `ctypes.WinDLL` of libusb1 on win32) that `load_locate_library` returns;
  a call of one of their foreign functions is
  `ctypes.CDLL.__init__._FuncPtr.__call__`, but for the two Python
  functions that libusb1 assigns to the CDLL
  (`libusb_set_iso_packet_lengths`, `libusb_fill_iso_transfer`,
  `libusb1.py:508`, `553`), which are package callees. Restypes: the
  `*_strerror` functions return `c_char_p`, so bytes.
- **Loggers** are `logging.getLogger(...)` results, `logging.Logger`.
- **Client callables** (no callee, B5): `custom_match` of `find` and
  `find_descriptor`; the `find_library` that a client gives `get_backend`
  (`docs/tutorial.rst:556`); a client `lib_cls` of `load_library`; the
  function and logger of `functiontrace`, which no package code calls.
- **Client keys** of `find(**args)` and `find_descriptor(**args)` name
  descriptor fields in the documentation and tests, never a property
  (B3): `getattr(d, key)` has no property callee (`core.py:71`,
  `util.py:180`).

## Default rejections

Six lines (first lines of the ledger), 22 candidates:

| Candidates | Reason | Accepted at |
|---|---|---|
| `_ConfigDescriptor.__getattr__` | the receiver is no `_ConfigDescriptor`, or has the attribute | `libusb1.py` 782:29, 782:48, 788:24, 790:17; `getattr(input, f)` `core.py:67` |
| `_WrapDescriptor.__getattr__` | the receiver is no `_WrapDescriptor`, or has the attribute | `libusb1.py` 800:19, 802:21; `core.py:67` |
| `__getitem__` of `Configuration`, `Device`, `Interface` | the subscripted object is a ctypes pointer, dict, tuple, array, list, str or match | `core.py` 144:25, 187:20, 206:27, 265:22 |
| `Device.__eq__`, `Device.__hash__` | no Device is compared or hashed by the package | nowhere |
| `__str__` and `__repr__` of the four descriptors, `_DescriptorInfo.__repr__` | nothing formatted is a descriptor | `str(endpoint)`, `str(interface)`, `str(configuration)`, `str(device)` (`core.py` 517, 640, 773, 1345) |
| `__iter__` of the six iterable classes | nothing iterated is one | `util.py:179`; `legacy.py` 120, 134, 339; `core.py` 243, 516, 522, 639, 645, 772, 784, 1304; `openusb.py` 558, 559 |

## Judgement calls

**J1. `PYUSB_DEBUG` and `methodtrace`** (`usb/__init__.py:67-106`,
`_debug.py:53-65`; 36 edges). Rule: an environment variable that the
package reads to set a value of its own counts as configuration when the
package's documentation sets it (README, "Rulings for batch 6",
tinytag). `docs/tutorial.rst:127-136` and `docs/faq.rst:17` document
`PYUSB_DEBUG` and `PYUSB_LOG_FILENAME`. With `PYUSB_DEBUG` set,
`_setup_log` calls `_debug.enable_tracing(True)` before any backend module
is imported (they import `usb` first), so every `@methodtrace(_logger)`
returns `do_trace` and the 70 backend methods are `do_trace` closures.
Edges: the debug branch of `_setup_log` (7: `enable_tracing`,
`dict.get`, `FileHandler`, `StreamHandler`, `Formatter` and the two
`setFormatter`) and `do_trace` as a callee of every call of a backend
method (29 callers, at each site beside the method itself). Without the
variable the decorator returns the method: both are callees. The 70 edges
`do_trace -> <method>` hold by rule A whatever the configuration (`f` is
what `decorator_logging` receives, `_debug.py:62`). Alternative: the
configuration is not considered; rejected, the documentation sets it.

**J2. `synchronized`** (`core.py:108-116`; 24 edges to `wrapper`, 11 from
it). Every method of `_ResourceManager` has `@synchronized`, which
returns `wrapper` (with `functools.wraps`). A call such as
`self._ctx.managed_open()` calls `wrapper`, which calls the method
(`f(self, ...)`, a value site with the eleven methods). The trace confirms
the shape (`Device._finalize_object -> wrapper`, `wrapper -> dispose`).
The method itself is rejected at the call sites. Alternative: edges
straight to the methods; rejected, Python calls the wrapper.

**J3. `IBackend` as a receiver** (`backend/__init__.py:85`; 2 edges in,
17 left out). Rule B1: a plain public class documented for subclassing is
a receiver of its own methods; the client's subclasses are client code.
`IBackend()` is a valid backend for `find` and `Device`: `find`'s
`device_iter` calls its `enumerate_devices` (`core.py:1304`), and
`Device.__init__` its `get_device_descriptor` (`core.py:800`). Both raise
`NotImplementedError`, so no `Device` with an `IBackend` backend is ever
made: the `_ResourceManager` and the half-built Device are dropped with
the exception (B3: an object that the package leaves behind after an
error is not considered). So an `IBackend` itself is no receiver at the
17 later backend calls of `core.py` (`managed_open` to `ctrl_transfer`),
where only the get_backend backends count (and the `IBackend` methods
that libusb0 and openusb inherit). Alternative: `IBackend` at every
backend site (+17 inside edges); rejected by B3.

**J4. Versions, implementations and platforms**: see above (no edge
depends on IronPython, Jython, Cygwin or DragonFly BSD).

**J5. Finalization** (`_objfinalizer.py`). `AutoFinalizedObject.__new__`
registers `weakref.finalize(instance, _do_finalize_object_ref, ...)`
(`134`): registration only, no edge to the callback there. The callback
runs when the object is collected, at interpreter exit, or when
`AutoFinalizedObject.finalize` calls the finalizer (`142`), the one
package site, which gets `weakref.finalize.__call__` and
`_do_finalize_object_ref` (trace-confirmed). `__del__` runs when the last
reference goes: not an edge (README, "Implicit calls"). So the trace
edges `find -> _AutoFinalizedObjectBase.__del__` and `device_iter ->
_AutoFinalizedObjectBase.__del__` are rejected (`pyusb.rejected.json`).
`_do_finalize_object` calls `self._finalize_object()` on any
`AutoFinalizedObject`: the ten overrides, the base method (IBackend,
libusb0 and openusb backends inherit it) and `do_trace` (two libusb1
overrides are wrapped, J1).

**J6. The dead `os.strerror` of libusb0** (`libusb0.py:440-441`; 1 edge
left out). `usb_strerror` returns `c_char_p` (restype, `357`), so
`errmsg` is bytes, and `errmsg.lower() == 'no error'` compares bytes with
a str: always false (with `-bb` it raises). `os.strerror(-ret)` never
runs (B1: a check that cannot succeed under the package's own values).
`<builtin>.bytes.lower` stays.

**J7. `NullHandler.emit`** (`usb/__init__.py:94-96`; 6 inside edges,
after Codex round 1). Without `PYUSB_DEBUG`, the `usb` logger gets the
level `CRITICAL + 10` and the package's `NullHandler`. A client may lower
that level through logging's public interface: the nodeenv ruling (README,
"Rulings for batch 8": a logger level lowered through logging's documented
interface is library configuration, not a change of package internals).
A record of a module logger (`usb.core`, `usb.libloader`,
`usb.backend.libusb0`, `libusb1`, `openusb`) then propagates to the `usb`
logger, whose handler's `handle` calls `emit` (CPython 3.9
`logging/__init__.py:1645-1665`, `939-952`; 3.15 `:1733-1753`,
`1014-1030`; PyPy 3.11 `lib-python/3/logging/__init__.py:1690-1710`,
`965-978`). So every logging call of the package is a call-back site of
`NullHandler.emit` (13 sites, 6 callers: `find`, `load_library`,
`load_locate_library` and the three `get_backend`). With `PYUSB_DEBUG`
set, the handler is a `FileHandler` or `StreamHandler` (outside code), and
`_trace_function_call`'s `logger.debug` runs only then: no `emit` edge
there. The first version left `emit` without a caller (the configuration
was taken as undocumented); Codex round 1 (M1 to M6) corrected it.

**J8. ctypes names** (the mss rulings). A foreign function call is
`ctypes.CDLL.__init__._FuncPtr.__call__` (also for the WinDLL of libusb1
and for `fn(...)` value sites that hold one, `libusb0.py:681`, `692`;
`libusb1.py:934`, `950`). An instance of a package `Structure` without
`__init__` is built by `ctypes.Structure.__init__` (libusb1 `743`,
openusb `564`, `579`, `591`, `605`, `652`, `662`, `672`, `682`, and
`super().__init__()` in `_openusb_ctrl_request`, `202`). Plain ctypes
classes keep the imported name, also through a package alias:
`_libusb_device_handle()` is `ctypes.c_void_p`, `_openusb_handle()` and
`_openusb_dev_handle()` are `ctypes.c_uint64`. Generated classes:
`POINTER(c_void_p)()` (libusb1 `640:42`) and `POINTER(c_uint64)()`
(openusb `526:47`, `541:47`, through `_openusb_busid` and
`_openusb_devid`) are the `__pointer_type__` of the simple class (CPython
3.14 and later); `POINTER(_libusb_config_descriptor)()` (`776:49`) and
`(c_uint8 * 7)()` (`762:33`) have no outside name: a note and no callee.
`CFUNCTYPE(None, ...)` is `ctypes.CFUNCTYPE`; calling its result is
`ctypes.CFUNCTYPE.CFunctionType` (`673:63`). `ctypes.memset` is no
function but an instance of that class (`memset = CFUNCTYPE(c_void_p,
c_void_p, c_int, c_size_t)(_memset_addr)`: CPython `Lib/ctypes/__init__.py`
of 3.9 `:499`, 3.12 `:507`, 3.14 `:606`, 3.15 `:595`; PyPy
`lib-python/3/ctypes/__init__.py` of 3.9 and 3.10 `:498`, 3.11 `:502`), so
`memset(...)` (openusb `653`, `663`, `673`, `683`) is
`ctypes.CFUNCTYPE.CFunctionType.__call__` (a call of an instance is the
`__call__` of its class; audit F1). `ctypes.cast` is a Python function on
every runtime (CPython 3.9 `:509`, 3.14 `:616`; PyPy 3.9 and 3.10 `:507`, 3.11 `:511`), so it keeps its name.
`list_type.from_address(...)`
on an array type (`271:34`) is a method of the metaclass:
`_ctypes.PyCArrayType.from_address` on CPython
(`Modules/_ctypes/_ctypes.c`, type name `_ctypes.PyCArrayType`) and
`_ctypes.array.ArrayMeta.from_address` on PyPy (`lib_pypy/_ctypes/array.py:76`,
3.9 to 3.11), both kept (two receiver classes on admitted runtimes).

**J9. The isochronous transfer callback** (`libusb1.py:673`, `688`; 6
edges, 5 of them after Codex round 1). `_IsoTransferHandler.__init__`
registers `self.__callback` in the transfer through a `CFUNCTYPE` object.
By the mss ruling (a package function entered through a C callback thunk
is a callee of the package call whose library execution invokes it,
established by source or authoritative documentation), the callee sites
are the libusb calls that can run it. From libusb 1.0.30's sources
(`deps/libusb/1.0.30`, tag v1.0.30, commit `87a5563`):

- libusb runs the callback of a completed transfer in the thread that
  handles the context's events, and nowhere else (`libusb/io.c:549-552`;
  `usbi_handle_transfer_completion` calls `transfer->callback`,
  `io.c:1723-1725`, from the backend's event handling, `handle_events`,
  `io.c:2287`).
- The synchronous transfers are built on the asynchronous API (`io.c:813-816`)
  and wait in `libusb_handle_events_completed` on the context
  (`sync.c:49-55`; control `sync.c:139`, bulk and interrupt `sync.c:200`).
  When the waiting thread gets the event lock it handles all the
  context's events itself (`io.c:2370-2374`); otherwise it waits for the
  thread that holds it (`io.c:1150-1155`).
- libusb is thread-safe (`io.c:808`), and pyusb's libusb1 backend is one
  object with one context (`get_backend`, `libusb1.py:964-968`; `self.ctx`,
  `722`), from which every device handle comes (`641`, `656`). A second
  thread doing an isochronous `read` or `write` (its `submit` in flight,
  `685`) beside a first thread's bulk, interrupt or control transfer is
  admitted use (no restriction to one thread: the path ruling; pyusb
  itself locks its per-device state with an RLock, `core.py:127`).

So `__callback` is a callee of `submit`'s `libusb_handle_events`
(`688:45`), and of the synchronous calls that can hold the event lock
while the other thread's transfer completes: `_LibUSB.__write` (`934:20`),
`_LibUSB.__read` (`950:20`), `_LibUSB.ctrl_transfer` (`897:54`), and
`_LibUSB.get_configuration` (`821:49`) with libusb 1.0.12 on Linux without
sysfs's USB attributes (audit remark CR1, below), and
`_LibUSB.set_configuration` (`816:49`) on Windows, where WinUSB's
`set_configuration` sends a synchronous control transfer
(`os/windows_winusb.c:2464-2469`) and isochronous transfers are supported
(`windows_winusb.c:2605`; ChangeLog, v1.0.23). No edge at the wrapping
(`673:63`). Not callees: `_LibUSB.clear_halt` on Solaris, whose
`clear_halt` is a synchronous control transfer (`os/sunos_usb.c:1360-1363`)
but whose backend refuses isochronous transfers (`sunos_usb.c:1416-1426`),
so no isochronous callback is ever in flight there;
in 1.0.30, `libusb_get_configuration`'s fallback control transfer
(`core.c:1716-1719`) runs only when the backend lacks `get_configuration`
or returns `LIBUSB_ERROR_NOT_SUPPORTED`, and no backend of an admitted
platform does (Linux `os/linux_usbfs.c:1495-1520`, macOS `darwin_usb.c:1684`,
Windows `windows_winusb.c:2451`, `windows_usbdk.c:442`, NetBSD
`netbsd_usb.c:278`, OpenBSD `openbsd_usb.c:306`, Solaris
`sunos_usb.c:1071`); `libusb_close` takes the event lock but runs no
callback (`core.c:1551-1600`, `1651`).

libusb is a system library that pyusb does not pin: `setup.py` says
"libusb 1.x", and the CI installs libusb 1.0.24 on Windows
(`.github/workflows/run_tox.yml:27`). The design holds across libusb 1.0:
in 1.0.0 too (`deps/libusb/1.0.0`) a synchronous transfer waits by
`libusb_handle_events` on the device's context (`sync.c:104-109`,
`172-177`), which takes the event lock and handles all the context's
events (`io.c:1705-1710`, `1664-1666`; `handle_events` `1530`, backend
`1595`) and runs the completion callbacks (`io.c:1194-1195`); 1.0.9 only
added the completion-checking variant (`io.c:906-909` of 1.0.30). The
ChangeLog records no change of where callbacks run, and WinUSB
isochronous transfers exist since 1.0.23 (ChangeLog), before 1.0.24. When `set_configuration` on WinUSB became a
control transfer the ChangeLog does not say; it is so in 1.0.30, a 1.x
release.

**J10. Lazy iterators.** `tuple(map(lambda ...))` in `get_langids`
(`util.py:281`) and the `groupby`/`sorted` key functions of
`legacy.Configuration.__init__` and `legacy.busses` are consumed in the
function that makes them: callees at the making site. `legacy.Bus.__init__`
iterates a group of the `groupby` of `busses` (`legacy.py:353`, `358`);
advancing a group advances the groupby, which calls `busses.<lambda2>`:
`Bus.__init__ -> busses.<lambda2>` (the uncertainties ruling on a lazy
iterator consumed through another library iterator; 1 edge).

**J11. `functiontrace`** (`_debug.py:68-79`) has no caller in the
package; by B its parameters are judged as public ones: `logger` is a
client object without a documented type, so `logger.getEffectiveLevel()`
has no callee (`74:57`), and `f` is a client callable (`76:21`).
`_trace_function_call`'s `logger.debug` is `logging.Logger.debug` (the
backend loggers of `methodtrace`).

## Callees outside the package

- Builtin exceptions through the nearest outside base:
  `<builtin>.OSError.__init__` for the libloader exceptions,
  `<builtin>.ValueError.__init__` for `NoBackendError`,
  `<builtin>.IOError.__init__` for the explicit `IOError.__init__(self,
  ...)` in `USBError.__init__` (`core.py:304`, the name the code uses; the
  trace lists it as an alias of `OSError.__init__`).
- `os.pathconf` (the trace names it `posix.pathconf`, alias `os.pathconf`),
  `weakref.ref` and `weakref.ref.__call__` (trace: `weakref.ReferenceType`,
  alias `weakref.ref`).
- `threading.RLock()` gives `_thread.RLock`: `_thread.RLock.acquire` and
  `.release` (`core.py:112`, `115`). CPython: the C RLock (trace-confirmed).
  PyPy 3.9 to 3.11: `pypy/module/thread/moduledef.py:24` exports
  `'RLock': 'os_lock.W_RLock'`, whose TypeDef is named `"_thread.RLock"`
  with `acquire` and `release` (`pypy/module/thread/os_lock.py:306-310`;
  3.11 `:316-320`), and `lib-python/3/threading.py:46` takes
  `_CRLock = _thread.RLock`, so `threading.RLock()` returns it (audit R2).
- `functools.wraps(f)` returns a `functools.partial`:
  `functools.partial.__call__` at the decorator `@functools.wraps(f)`.
- `logging.FileHandler.setFormatter` and `logging.StreamHandler.setFormatter`
  through the receiver class (inherited from `Handler`).
- `array.array.buffer_info`, `array.array.tobytes`, `re.Match.groups`,
  `<builtin>.bytes.decode` and `<builtin>.bytes.lower` (restype
  `c_char_p`), `<builtin>.str.find` and `<builtin>.str.startswith` on
  `sys.platform`.
- ctypes: J8.

## Audit

`pyusb.audit.md` (blind answers `8386c11`, audit `cb1ead8`): 168 sites
re-derived blind (seed 20261124), 167 agree.

- F1 (naming): `memset(...)` at `openusb.py` 653:15, 663:15, 673:15,
  683:15 named `ctypes.memset`; applied: `ctypes.CFUNCTYPE.CFunctionType.__call__`
  (4 outside edges renamed; the graph stays at 923; J8).
- R1: for the lead (README, "Rulings for batch 8"); nothing to apply here.
- R2: the PyPy name of `threading.RLock()` was taken from memory; applied:
  read in PyPy's `pypy/module/thread` sources (deps), `_thread.RLock` on
  PyPy 3.9 to 3.11 too; no edge changed ("Callees outside the package").

## Codex round 1

`selection/batch-8-proposal/codex-audits/round-1/pyusb.md`: 6 missing, 3
unsure, no false or naming finding.

- M1 to M6 (missing, `-> usb._setup_log.NullHandler.emit` from the three
  `get_backend`, `core.find`, `libloader.load_library` and
  `load_locate_library`): applied, 6 inside edges (J7). Checked against
  the logging sources of CPython 3.9 and 3.15 and PyPy 3.11 and the
  nodeenv ruling; every module logger is a child of `usb`.
- U1 to U3 (unsure, `_LibUSB.__write`, `__read` and `ctrl_transfer ->
  _IsoTransferHandler.__callback` at `libusb1.py:934:20`, `950:20`,
  `897:54`): first answered with an opinion (no libusb source in deps);
  after the lead added libusb 1.0.30's sources, decided from them and
  applied (3 inside edges; J9 gives the evidence). The writer's extension
  to other libusb calls that handle events internally, checked against
  the same sources: `_LibUSB.set_configuration -> __callback` (`816:49`,
  Windows) added (1 inside edge); `clear_halt` (Solaris, no isochronous
  transfers), `get_configuration` (no admitted backend takes the control
  fallback) and `close_device` (no callback) are no callees (J9).

### Audit remarks after the re-check (`63eff45`)

The auditor agreed with all ten edges and raised two remarks; the lead
added the sources to decide them. CR1 added 1 inside edge; CR2 changed
none.

- CR1 (libusb 1.0.0, the floor of the series; then 1.0.12). 1.0.0's
  synchronous wait handles all the context's events too (J9): the earlier
  "since 1.0.9" was wrong in wording only, 1.0.9 added the completion
  check. But pyusb 1.3.1 cannot use libusb 1.0.0: `_setup_prototypes` sets
  `lib.libusb_get_parent.argtypes` unconditionally (`libusb1.py:311`),
  1.0.0 has no `libusb_get_parent` (`libusb.h`), so the attribute load
  raises `AttributeError`, which `get_backend` catches (`libusb1.py:973`)
  and returns None. By the ruling on which releases of a dependency are
  read (the floor is the oldest release that the package can run with),
  the floor is 1.0.12 (ChangeLog, v1.0.12: "Add topology calls: ...
  libusb_get_parent()"), which the lead added (`deps/libusb/1.0.12`, tag
  v1.0.12, commit `8b49ddf2`). 1.0.12 is the floor: it exports every
  symbol that `_setup_prototypes` sets unconditionally (all defined with
  `DEFAULT_VISIBILITY`/`API_EXPORTED`, `libusb_get_parent` at
  `core.c:722-723`, `libusb_ref_device` `876`, `libusb_alloc_transfer`
  `io.c:1225-1226`; `libusb_strerror` is guarded by `hasattr`,
  `libusb1.py:484`, and `libusb_get_port_numbers` by `try`, `577-588`).
  In 1.0.12, `libusb_get_configuration` falls back to a synchronous
  control transfer when the backend returns `LIBUSB_ERROR_NOT_SUPPORTED`
  (`core.c:1240-1247`), and the Linux backend does so when sysfs cannot
  relate devices (`os/linux_usbfs.c:1319-1324`): when
  `/sys/bus/usb/devices` is missing or its root hubs lack `busnum`,
  `devnum` or `bConfigurationValue` (`358-416`), a possible state of an
  admitted Linux system (the path ruling: a possible state of the file
  system). The fallback waits in `libusb_handle_events_completed` on the
  context (`sync.c:104-105`; `io.c:2025`, `1855`, `1949`), which runs a
  completed transfer's callback (`io.c:1488`), and Linux supports
  isochronous transfers (`linux_usbfs.c:1977`). So
  `_LibUSB.get_configuration -> __callback` holds (`821:49`, +1 inside
  edge; J9). Nothing else that pyusb calls runs a synchronous transfer
  inside 1.0.12 but WinUSB's `set_configuration`
  (`os/windows_usb.c:1728-1739`), already an edge (J9); `core.c` calls
  `libusb_control_transfer` only at `1246`.
- CR2 (FreeBSD's own libusb). FreeBSD is an admitted platform: the
  classifier `Operating System :: POSIX :: BSD :: FreeBSD` (`setup.py`)
  declares it; the CI (`run_tox.yml`) does not test it, which does not
  narrow a declaration. FreeBSD's `libusb.so` exports the libusb 1.0 API,
  and `_load_library` (candidates `usb-1.0`, `libusb-1.0`, `usb`;
  `check_symbols=('libusb_init',)`) loads it. In 15.1.0 it defines every
  symbol that `_setup_prototypes` sets unconditionally (`libusb10*.c`;
  `libusb_get_parent`, `libusb10.c:894`). In 14.5.0 one is missing:
  `libusb_get_parent` is not defined (`deps/freebsd-libusb/14.5.0`), so
  on FreeBSD 14.5 the attribute load at `libusb1.py:311` raises
  `AttributeError`, `get_backend` catches it (`libusb1.py:973`) and returns
  None: no libusb1 backend exists there, and the rest of this item
  concerns 15.1.0. In `deps/freebsd-libusb/15.1.0` (14.5.0 has the same
  code at these places, but cannot be used): the completion callbacks run only in the thread that handles
  events (`libusb10_io.c:200-219`, from the `tr_done` queue that
  `libusb10_complete_transfer` fills, `libusb10.c:1198-1219`);
  `libusb_bulk_transfer` and `libusb_interrupt_transfer` wait in
  `libusb_handle_events(ctx)` (`libusb10_do_transfer`,
  `libusb10_io.c:578-583`; 14.5.0 `:572-577`), so U1 and U2 hold there
  too; isochronous transfers are supported (`libusb10.c:1547-1548`,
  `libusb10_isoc_proxy`); `libusb_control_transfer` is a synchronous
  ioctl (`libusb20_dev_request_sync`, `libusb10_io.c:498`) without event
  handling, so U3 does not hold on FreeBSD (it holds on the other
  platforms, so the edge stays); `libusb_get_configuration` reads a
  descriptor (`libusb10.c:738-753`), `libusb_set_configuration` cancels
  this device's transfers, whose callbacks only queue, and sets the
  configuration by ioctl (`757-799`), and `libusb_clear_halt` clears the
  stall by ioctl (`915-942`): none runs a callback. The four edges stay,
  and FreeBSD adds none.

## Open path sets

None.

## Rejected trace edges

`usb.core.find -> usb._objfinalizer._AutoFinalizedObjectBase.__del__` and
`usb.core.find.device_iter -> usb._objfinalizer._AutoFinalizedObjectBase.__del__`
(J5).

## Notes for the auditor

- `Device.__str__` reads `configuration.info` (`core.py:777`), which no
  `Configuration` has: the `except USBError` branch raises
  `AttributeError` there; no edge at the `%` of `777`.
- `openusb._OpenUSB.ctrl_transfer` loads `request.setup.wValue` and
  `wIndex` without assigning them (`openusb.py:711-712`); no call.
- `libusb1._LibUSB.get_endpoint_descriptor` tests `ep > i.bNumEndpoints`
  (`libusb1.py:800`), not `>=`; no edge changes.
- `load_locate_library` in the cygwin branch uses `lib` unbound
  (`libloader.py:202`, `204`: `NameError`); it logs a tuple as the message
  (`203`).
- `legacy.DeviceHandle.getString` calls `.encode('ascii')` on `None` for
  index 0 (`legacy.py:289`); `<builtin>.str.encode` stays.
- `tutorial.rst:174` takes `len()` of the generator of `find(find_all=True)`.
- `_ConfigDescriptor.__getattr__` (`libusb1.py:634`) would recurse if
  `desc` were missing; `__init__` sets it first, so no load of `desc`
  reaches `__getattr__`.
- `IBackend` methods pass the bound method to `_not_implemented`, which
  reads only `__name__`: no edge to the method.
- `_DescriptorInfo(strings)` (`core.py:1347`) has no callee: a `str`
  subclass without `__init__` (the tabulate ruling).

## Statistics

| | Count |
|---|---|
| Sites | 2564 (975 call, 88 decorator, 57 iter, 11 mapping, 101 op, 62 getitem, 3 setitem, 1267 getattr); 2081 with candidates; 29 value sites |
| Ledger entries | 1116 (1305 callee lines, 281 rejection lines of which 236 `reject *`, 148 notes, no exclusion) |
| Nodes | 315 (14 modules, 301 functions with 5 lambdas) |
| Edges | 934: 560 in the package, 374 outside |
| Confirmed by the trace | 95 of 934 (10.2%); the trace has 97 edges, 2 rejected |
| From reading only | 839 (523 inside, 316 outside) |
| Rejected trace edges | 2 |
| Functions that the tests run | 39 of 301 |

`check.py --origin pyusb`:

| Project | Trace edges | Rejected | Traced edges in the graph (inside / outside) | Added (inside / outside) | Graph edges (inside / outside) |
| --- | --- | --- | --- | --- | --- |
| pyusb | 97 | 2 | 95 (37 / 58) | 839 (523 / 316) | 934 (560 / 374) |
