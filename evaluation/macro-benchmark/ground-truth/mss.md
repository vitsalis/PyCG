# mss: judgements of the ground truth

Status: complete (2026-11-23). Every site is decided; `check.py --write
mss` and `check.py mss` report no error; the second review pass of the
entries against the source and the binding check of every call of a
package function are done (no call that cannot bind). The blind audit
(`mss.audit.md`: 192 of 194 sites agree, no missing and no false edge) and
the referee's rulings (`b7-ruling-mss.md`, `b7-ruling-mss-2.md` in the
audit records, adopted by the lead, 2026-11-23) are applied:
+1 outside edge (J2), wording of J1, J3 and two decorator notes.

Counts: 198 nodes (19 modules, 179 functions, no lambda); 590 edges (261
inside, 329 outside), all from reading (after Codex round 1, below); 62 value sites; 7 default
rejection lines (17 candidates, 2515 candidate-site pairs); 3 exclusions.

Release v10.2.0 (commit `b7f4d62`). Analysed source: `src/mss/` (root
`src`), 19 modules, 179 functions, 108 classes. `src/xcbproto` (the
generator of `linux/xcbgen.py`) and `src/tests` are not analysed;
`linux/xcbgen.py` is source (it is in the package and the wheel).

mss has **no trace** (the maintainer's decision, 2026-11-22: its session
fixture needs an X display). Every edge comes from reading. The ledger is
`mss.ledger`; `mss.json` and `mss.added.json` are generated from it. There
is no `mss.rejected.json` (nothing was traced).

Scratch drafting: the plain call sites (builtins, `ctypes` helpers,
`POINTER(...)`, the foreign-function calls of the XCB wrappers, decorators,
`ScreenShotError(...)` with its one candidate) were filled by a script of
the writer that applies naming rules to the site text; every other entry
was written by hand, and every generated entry was reviewed against the
source.

## Supported versions, implementations and platforms

- `pyproject.toml`: `requires-python = ">= 3.9"`; classifiers CPython and
  PyPy, Python 3.9 to 3.14, MacOS, Windows, Unix.
  `docs/source/support.rst:21` reports PyPy tested on Windows. So CPython
  and PyPy 3.9 and later count, on the declared Unix family (GNU/Linux
  among it), macOS and Windows (README, "Implementation, version and
  platform combinations"; part 4 of `b7-ruling-mss.md`: the Unix classifier
  is a family declaration, and a narrower CI matrix or documentation list
  does not narrow it). On a Unix other than GNU/Linux, `_choose_impl`
  takes no Linux branch (its comparisons decide) and raises its
  unsupported-system `ScreenShotError` (`base.py:167`): no edge changes.
- `MSS()` picks the implementation with `platform.system()` (`base.py:147`,
  `__main__.py:16`): every platform branch runs, and so do both
  `locale.getencoding` (3.11+) and `locale.getpreferredencoding`
  (`linux/xlib.py:314`).
- `src/mss/windows/gdi.py` imports `WINFUNCTYPE` and `WinError`, which
  ctypes has only on Windows; it is imported only there.

## Architecture, as the ledger uses it

- `mss.MSS` (`base.py:171`) holds one implementation object in the private
  `_impl`, made by `_choose_impl`: `MSSImplDarwin`, `MSSImplXlib`,
  `MSSImplXGetImage`, `MSSImplXShmGetImage` or `MSSImplGdi`.
  `MSSImplementation` and `MSSImplXCBBase` are abstract (`grab` is
  abstract and `MSSImplXCBBase` does not define it): no instances. The
  three `MSS` subclasses of `darwin`, `linux` and `windows` are deprecated
  aliases with a warning; `mss.MSS` is `mss.base.MSS`.
- Native calls go through ctypes. A call of a foreign function (an
  attribute of a `CDLL`/`WinDLL`) is
  `ctypes.CDLL.__init__._FuncPtr.__call__` (the Sublist3r precedent:
  `CDLL.__init__` defines the class `_FuncPtr` for each library, and
  `WinDLL` inherits that `__init__`; checked on CPython 3.12 to 3.14 and in
  the PyPy 3.11 `lib-python` ctypes).
- `_cfactory` sets `argtypes`, `restype` and, when given, `errcheck`.
  ctypes calls the errcheck after each call of the function. So every
  call of an Xlib function in `linux/xlib.py:366` but `XSetErrorHandler`
  has `_validate_x11` as a callee, and every call of a Windows function
  with `_errcheck` in `windows/gdi.py:138` has `_errcheck` (callback rule,
  B5). CoreGraphics functions have no errcheck.
- The XCB backends (`linux/xcb.py`, `xcbgen.py`, `xcbhelpers.py`) call
  `LIB.<lib>.xcb_*` function pointers; a typed request returns a cookie
  whose class `initialize_xcb_typed_func` makes as a subclass of
  `ReplyCookieBase` (`xcbhelpers.py:351`), so `.reply(c)` is
  `ReplyCookieBase.reply`, and the `*_checked` void requests return a
  `VoidCookie` (`.check`).
- The XCB value types `XID` (and its subclasses `Window`, `Atom`,
  `RandrOutput`, ...), `Visualid`, `Keycode` and `Timestamp` subclass
  `c_uint32`/`c_uint8` and define `__eq__` and `__hash__`. ctypes returns a
  field or an array item of such a subclass as an instance of it, so the
  comparisons of `linux/base.py:73`, `112`, `294`, `369`, `458` and
  `linux/xshmgetimage.py:175` run `XID.__eq__` or `Visualid.__eq__` (`!=`
  through `object.__ne__`; `in` over a ctypes array, which has no
  `__contains__`, through `==` on each item). Nothing hashes them.

## Default rejections

Seven defaults (first lines of the ledger): the `__eq__` of `Keycode` and
`Timestamp`; `XID.__eq__` and `Visualid.__eq__` (accepted at the six sites
above); the four `__hash__`; the five `__repr__` (accepted at the two
format sites of `CGRect.__repr__`, `darwin.py:97`); the two `__str__`
(accepted at `str(arg)`, `linux/xshmgetimage.py:73`, and at the `print` of
`__main__.py:124`); `MSS.__enter__` and `MSS.__exit__` (accepted at
`__main__.py:102`). `check.py --report mss` gives the counts.

## Judgements (for the lead)

J1. **The Xlib error handler** (`linux/xlib.py:291`, installed at `461`;
confirmed by the referee for all ten sites). Rule: "A handler registered
with a C library is a callee only at package calls that can dispatch it
while installed, as established by source or authoritative documentation;
registration alone adds no callback edge." `MSSImplXlib.__init__` installs
`_error_handler` with `XSetErrorHandler`. The ledger names it at the ten
Xlib calls that can dispatch it: `XOpenDisplay` (`463:59`),
`XCloseDisplay` (`478:40`), `XQueryExtension` (`505:42`),
`XRRQueryVersion` (`539:35`), `XGetWindowAttributes` (`543:43`),
`XRRGetScreenResourcesCurrent` (`556:58`), `XRRGetScreenResources`
(`558:51`), `XRRGetCrtcInfo` (`562:45`), `XGetImage` (`584:41`) and
`XFixesGetCursorImage` (`620:54`). Documentary support (the referee's
citations): the Xlib specification says that requests which return
server information wait for a reply or an error, and that received
protocol errors invoke the installed handler (also for an error of an
earlier request); the `XCloseDisplay` manual specifies a final `XSync`
that reports pending errors; the `XResourceManagerString` documentation
says that `XOpenDisplay` reads the `RESOURCE_MANAGER` property when it
opens the connection (a server reply beyond the handshake); the RandR
protocol gives `QueryVersion`, `GetScreenResources`,
`GetScreenResourcesCurrent` and `GetCrtcInfo` replies, and the XFixes
protocol a `GetCursorImage` reply. No edge at `XSetErrorHandler` (only
registration), `XDefaultRootWindow` (cached display data),
`XDestroyImage` and `XRRFree*` (client-side freeing). Ten site-callee
pairs give **6 graph edges** (one per caller: `__init__`, `close`,
`_is_extension_enabled`, `monitors`, `grab`, `cursor`), all inside.

J2. **Generated ctypes types** (final ruling). Rule: "A ctypes-generated
pointer or array class is named through a public class path rooted
outside the analysed package when an admitted runtime provides one;
otherwise the constructor site keeps a note and no callee, since neither
an alias through a package class nor generated class-name metadata
supplies an outside name." CPython 3.14 documents `T.__pointer_type__` as
the class that `POINTER(T)` returns, so `POINTER(c_char_p)()`
(`linux/xcbhelpers.py:217:49`) has the callee
`ctypes.c_char_p.__pointer_type__` (+1 outside edge; the versions rule
takes the union over admitted runtimes, so its absence on 3.12 and 3.13
does not remove it). `POINTER(XcbErrorsContext)()` (`212:44`) and
`POINTER(GenericErrorStructure)()` (`309:47`) would be named only through
a package class (`mss.linux.xcbhelpers.XcbErrorsContext.__pointer_type__`),
which is not an outside name in this format, and the generated names
(`LP_<T>`, `c_uint_Array_<n>`, with the creating module as `__module__`
on CPython 3.12 and 3.13) are no module attributes; so these two sites
and `(c_uint32 * n)()` (`darwin.py:191:57`) keep a note and no callee.

J3. **ctypes names.** (a) An instance of a package `Structure` subclass is
built by `ctypes.Structure.__init__` (`CGRect()`, `XWindowAttributes()`,
`BITMAPINFO()`, `MONITORINFOEXW()`, `DISPLAY_DEVICEW()`), and an instance
of an `XID` subclass (`Atom(n)`, `ShmSeg(...)`) by
`ctypes.c_uint32.__init__` (the first `__init__` of the MRO is
`_SimpleCData.__init__`, named through the nearest outside base by the
name the package imports; `c_uint32` is `c_uint`). (b) Plain ctypes
classes keep the name the package imports: `ctypes.c_uint32`,
`ctypes.c_int`, `ctypes.c_void_p`, `ctypes.wintypes.LPVOID` (which is
`c_void_p`). (c) `XcbExtension.in_dll` (`xcbhelpers.py:495`, `502`, `509`,
`516`) is a method of the structure metaclass, which has no public path.
It is named by the class of the receiver (micro-benchmark README,
"Names": methods take the class of the instance, a private class keeps
its path, as `functools._lru_cache_wrapper.__call__`; this README: also
when that class inherits the method): `_ctypes.PyCStructType.in_dll` on
CPython and `_ctypes.structure.StructureMeta.in_dll` on PyPy (lib_pypy
3.11 `_ctypes/structure.py:340`, which inherits `in_dll` from
`_CDataMeta`, `basics.py:101`). Both names are kept by the rule for two
receiver classes on admitted runtimes: 8 site-callee pairs, which give **2 graph edges**
(`LibContainer.initialize` to each name), both outside.

Outside names were checked against the conventions on names of
`micro-benchmark/README.md` (2026-11-23, at the lead's instruction): the
only change was the PyPy name of `in_dll` (first written by its defining
class `_CDataMeta`). (d) The decorators
made by `CFUNCTYPE(...)` and `WINFUNCTYPE(...)` (`xlib.py:291`,
`gdi.py:279`) are classes defined in those functions:
`ctypes.CFUNCTYPE.CFunctionType` and `ctypes.WINFUNCTYPE.WinFunctionType`
(the external class is the callee; the notes no longer say that its
`__init__` is `object.__init__`, which is false on PyPy, where
`CFuncPtr.__init__` exists). The referee confirmed J3's names and the
platform branches as written.

J4. **The cursor of the macOS and Windows implementations**
(`base.py:319:71`). `MSS.grab` calls `self._impl.cursor()` only when
`self._impl.with_cursor` is true. `MSSImplDarwin` and `MSSImplGdi` call
`MSSImplementation.__init__` without `with_cursor`, and `MSS.__init__`
passes `with_cursor` only on Linux (`base.py:219`); `_impl` is private, so
a client cannot install another implementation. So their `cursor` is no
callee (B1, the state rule). `MSSImplementation.cursor` is abstract and
overridden by every class.

J5. **The impossible branch of `_validate_x11`** (`xlib.py:347-349`).
ctypes calls this errcheck only for the functions of `CFUNCTIONS`, whose
restypes give `None`, a pointer, an `XBool`, an `XStatus`, an `XID` or an
`int`; the annotation of `retval` names the same types. Every value takes
an earlier branch, so `type(retval)` and `AssertionError(msg)` have no
callee (B1: a check that cannot fail under the package's own values; the
python-barcode ruling 11 precedent).

J6. **`str()` of the XCB errors.** `_shm_report_issue` (private) receives
a version tuple, `OSError`s and `XProtoError`s (from `shm_attach_fd`
through `VoidCookie.check`, and from the shm `GetImage` reply), so
`str(arg)` (`xshmgetimage.py:73:46`) has `XProtoError.__str__`. The
`print("[ERROR]", exc)` of the `__main__` block (`__main__.py:124`) prints
the `ScreenShotError` that `main()` re-raises: on GNU/Linux it can be the
Xlib `XError` (raised by `_validate_x11`) or an `XProtoError`, so both
`__str__` are callees there.

J7. **Client values** (B5): `MSS.save`'s `callback` (the documented
example passes the client's `on_exists`) and a client `cls_image` (the
documented `custom_cls_image` example assigns a client subclass) are
client code; the package value of `cls_image` is `ScreenShot`
(`base.py:243`). `LibContainer.initialize(callbacks)` gets
`[xcbgen.initialize]` from the package (`xcb.py:344`); client callbacks
are opaque.

J8. **Named tuples.** `Pos(...)` and `Size(...)` (`screenshot.py:36`,
`39`, `darwin.py:265`) are `NamedTuple` classes: no edge (README).

## Callees outside the package

- The stream of `open(output, "wb")` is `io.BufferedWriter`
  (`tools.py:190-197`).
- `ArgumentParser.add_argument` is named through the receiver class
  (`argparse.ArgumentParser.add_argument`).
- `threading.Lock`, `threading.RLock`, `threading.local`,
  `threading.current_thread` keep the imported paths.

## Codex round 1 (2026-11-23)

The full source audit (`reviews/audit-b7-r1/mss.md`): 0 missing, 1 false
(inside), 0 naming, 1 unsure, 2 metadata items. All four hold and are
applied; nothing is disputed.

- False, `MSSImplXlib.cursor -> ScreenShotError.__init__` (`xlib.py:623:34`):
  removed (-1 inside edge; confirmed by `b7-ruling-mss-3.md`). `XFixesGetCursorImage` has the restype
  `POINTER(XFixesCursorImage)` (`xlib.py:371`) and the errcheck
  `_validate_x11` (`526-527`). For a NULL result ctypes returns a NULL
  pointer instance (not None), whose truth value is false, and
  `_validate_x11` raises `XError`. A non-NULL pointer is true
  (`_ctypes._Pointer.__bool__` on CPython 3.12.12, 3.13.12 and 3.14.9,
  checked with stdlib ctypes on a dummy structure; PyPy 3.11
  `lib_pypy/_ctypes/pointer.py:135`), and its `.contents`, a Structure,
  defines neither `__bool__` nor `__len__` (CPython: checked the same way;
  PyPy: none in `structure.py` or `basics.py`), so it is true. If the
  symbol is missing, `_set_cfunctions` skips it and the attribute load in
  `cursor` raises `AttributeError` first. The only witness is the test's
  mock of the foreign function (`tests/test_gnu_linux.py:282`), a change of
  package internals (`sct._impl.xfixes`); no public call changes the
  errcheck. B1: a check that cannot fail under the package's own values.
- Unsure, `MSSImplXCBBase._choose_randr_output -> ScreenShotError.__init__`
  (`base.py:290:34`): decided as false and removed (-1 inside edge). The
  helper is private; its two callers pass only
  `randr_monitor_info_outputs(randr_monitor)` after `nOutput > 0`
  (`base.py:320`) and `randr_get_crtc_info_outputs(crtc_info)` after
  `num_outputs == 0` continues (`353`). `array_from_xcb` takes the array
  length from the `*_length` accessor, which libxcb generates from the
  protocol XML as the list's `fieldref`: `num_outputs` for GetCrtcInfo
  (`src/xcbproto/randr.xml:418-420`) and `nOutput` for MonitorInfo
  (`877-879`), the same reply bytes that the guards read. So
  `len(outputs)` is never 0, also for a server reply of any content.
  Missing for a reading of the native body: the libxcb source (not among
  the dependency sources); the decision rests on the XML and on libxcb's
  generated-accessor convention (XCB documents that its C bindings are
  generated from the protocol description). The decisive scope reason
  (`b7-ruling-mss-3.md`, the referee, adopted by the lead): a client cannot
  reconfigure the reply types through `initialize_xcb_typed_func`,
  although its path has no underscore. The release's documentation
  excludes it from the public API: `docs/source/versioning.rst:42-50` lists
  "Undocumented symbols" and "Internal modules or backend-specific
  implementation details" as not public, and adds that "Some currently
  accessible symbols may still be internal even if not prefixed with `_`";
  the public API is what the official documentation, examples and demos
  show (`versioning.rst:28-35`), and none of them names this initializer.
  So rule C does not admit it as a public configuration interface. (Were it
  admitted, a compatible reply subclass could report a positive
  `num_outputs` in Python while the native field is zero; the exclusion
  rules that witness out. A misbehaving X server does not help either: both
  reads take the same field of the same reply buffer.) The removal is
  confirmed by that ruling; no edge changes.
- Metadata, `xlib.py:466:38`: the callee is removed from this site
  (`XOpenDisplay` has `_validate_x11`, which raises for a NULL display
  before the test at 464); the pair `MSSImplXlib.__init__ ->
  ScreenShotError.__init__` stays through `430:38` and the other sites.
- Metadata, platforms: the ledger header and the section above now keep the
  declared Unix family; no edge changes.
