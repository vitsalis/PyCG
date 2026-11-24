**Status (2026-11-23):** complete and re-checked. The writer applied W1 and the referee's rulings (`e1a8099`, 592 edges); the re-check passed (section "Re-check" at the end). Nothing is left.

# mss: blind audit of the ground truth

Release v10.2.0, commit `b7f4d62c6c5dc68fd60d43600f0e91012c8bc2e0` (batch 7;
no trace). Audited files: `mss.ledger` (3021 lines, 7 default
rejection lines with 17 candidates), `mss.json` (198 nodes, 591 edges: 263
in the package, 328 outside), `mss.added.json` and `mss.md` (judgements J1
to J8), at commit `c461fe1` of the ground-truth branch `b7-gt` (the writer's first commit
`a9b685d` plus the PyPy name of `in_dll`; no later commit changes an mss
file but this audit). `check.py mss` reports no errors.

I judged the files by the scope rules A, B1 to B5 and C of
`macro-benchmark/README.md`, with its clarifications and the rulings for
batch 6. I read the package's source (all 19 modules), `pyproject.toml`,
`docs/source/usage.rst`, `docs/source/examples/*.py`, and, from the
dependency sources (read only), CPython 3.10 and 3.11 `Lib/ctypes/__init__.py`
and PyPy 3.9 and 3.11 `lib-python/3/ctypes/__init__.py` and
`lib_pypy/_ctypes/{basics,structure}.py`. I did not run or import the
package, and I ran no analysis tool on it. The only tools I ran were
`check.py` (skeleton, size report, `--report`, `--report --default`) and
scripts of my own on the text of the skeleton, the ledger, the graph and the
source (`ast` only, for the binding check). I did not read libX11's source
(it is not among the dependency sources); see J1.

**Final state.** No edge that is missing, and no edge that cannot happen.
192 of the 194 sites re-derived blind agree; the 2 others are my own naming
error (I left out the PyPy name of `in_dll`). 1 wording finding (W1), 2
remarks on the README (R1, R2). Every judgement call of the writer is
supported by the nearest rule; J2 is an extension of an existing rule, and
I give the ruling I think is the smaller one. No finding changes the graph:
591 edges.

## Findings

| Id | Kind | Site or edge | Evidence | Edges | Decision |
|---|---|---|---|---|---|
| W1 | wording (low) | `mss.md` J1 and J3(c) | J1 says the error handler is named at ten Xlib calls "(10 edges)". The ten are sites; the graph has 6 edges to `_error_handler` (callers `MSSImplXlib.__init__`, `close`, `_is_extension_enabled`, `monitors`, `grab`, `cursor`). J3(c) says "8 edges, 4 of them the PyPy name" for `in_dll`: these are 8 site-callee pairs at 4 sites (`xcbhelpers.py:495`, `502`, `509`, `516`), and 2 graph edges (`LibContainer.initialize -> _ctypes.PyCStructType.in_dll`, `-> _ctypes.structure.StructureMeta.in_dll`). | 0 | the writer corrects the two counts |
| R1 | README (low) | "Callees outside the package" and B5 | The README has no sentence on ctypes. The writer and I derived the same three rules from the callback rule and the naming rules: (a) a foreign call is `ctypes.CDLL.__init__._FuncPtr.__call__` (Sublist3r and segno precedents); (b) an `errcheck` function and a C callback that a foreign call runs are callees of the package site of that call; (c) a handler that the package registers with a C library is a callee only of the calls during which the library can call it (the signal-handler rule, applied to C). They decide 68 edges here (50; 12: `_validate_x11` 6, `_errcheck` 5, `MSSImplGdi.monitors.callback` 1; 6). One sentence under "Callees outside the package" would fix them for the next writer. | 0 | for the lead |
| R2 | README (low) | "Callees outside the package": "One class reached through two import paths is one callee when the class is known" | The graph names `ctypes.c_void_p` at `xcbhelpers.py:327` and `ctypes.wintypes.LPVOID` (the same class) at `gdi.py:205` and `362`, in different callers, each by the path that the module imports. I read the sentence as one name per site (the writer's reading, `gdi.py:205` note); a reader could take it as one name per graph. The README could say which. | 0 (2 edges would change name under the other reading) | for the lead; no change proposed |

## Step 1: blind re-derivation

**Skeleton.** I copied `projects.toml` and `projects/mss` (`cp -R`) to
`$TMPDIR/b7-audit-mss/` and ran `check.py --benchmark-dir <scratch>
--skeleton mss`. It has 1468 sites: 1031 call, 26 decorator, 19 with, 85 op,
130 getitem, 46 setitem, 1 delitem, 54 getattr, 76 format; 62 value sites.
Sixteen candidates sit at 50 or more sites (the `__eq__` and `__hash__` of
the four XCB value types, five `__repr__`, two `__str__`,
`ScreenShotError.__init__`).

**Sample, drawn by kind.** Explicit sites (call, decorator) are 1057 of the
1468 (72 %). I numbered the sites in (module order of the skeleton, line,
column) and drew with one `random.Random(20261123)`:
`rng.sample(explicit, 100)`, then `rng.sample(implicit, 40)` (the tinytag
split, doubled for a package without a trace). I added the 62 value sites;
8 were already drawn. 194 sites. I wrote my callees for each in
`$TMPDIR/b7-audit-mss/blind-answers.md` (with the draw script `draw.py`, the
sample `sample.txt` and the draw `draw.json`) before I opened any file of
the writer.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Explicit (call, decorator) | 100 | 98 | 2 |
| Implicit (12 getitem, 5 setitem, 11 op, 5 getattr, 4 format, 3 with) | 40 | 40 | 0 |
| Value sites not in the draw | 54 | 54 | 0 |
| **Total** | **194** | **192** | **2** |

The 2 disagreements, classified:

- **I was wrong (2, naming):** `xcbhelpers.py:495:52` and `502:53`,
  `XcbExtension.in_dll(...)`. I wrote only `_ctypes.PyCStructType.in_dll`
  and left the PyPy name unchecked. mss declares PyPy
  (`pyproject.toml:30`), and PyPy's structure metaclass is
  `_ctypes.structure.StructureMeta` (lib_pypy 3.9 and 3.11,
  `_ctypes/structure.py:334` and `:340`), which inherits `in_dll` from
  `_CDataMeta` (`basics.py:98`, `:101`). The writer's two names follow the
  rule for two receiver classes on admitted runtimes.
- **The writer missed an edge (0). The writer has an edge that cannot happen (0).**

My conventions, written before I read the ledger, are the writer's:
`ctypes.CDLL.__init__._FuncPtr.__call__` for every foreign call;
`_validate_x11` and `_errcheck` at the calls whose function has them as
errcheck; `_error_handler` at the same ten Xlib calls as J1; no callee for
`POINTER(T)()` and `(c_uint32 * n)()`; `ctypes.CFUNCTYPE.CFunctionType` and
`ctypes.WINFUNCTYPE.WinFunctionType` for the two decorators;
`ctypes.c_uint32.__init__` for an `XID` subclass and
`ctypes.Structure.__init__` for a package structure; `cursor()` only of the
Linux implementations. The 38 implicit sites without a package callee are
all left to the defaults or rejected; the 2 with one (`base.py:396:25`
`MSS.monitors`, `screenshot.py:42:92` `ScreenShot.height`) agree.

## Step 2: exhaustive checks

**Dispatch over `self._impl` (`base.py:285`, `312`, `319`, `348`).**
`_choose_impl` makes one of five classes; `MSSImplementation` and
`MSSImplXCBBase` are abstract (`grab`), so neither is a receiver. Every row
is the ledger's.

| Site | Callees |
|---|---|
| `self._impl.close()` `:285` | `MSSImplementation.close` (Darwin inherits it), `MSSImplGdi.close`, `MSSImplXlib.close`, `MSSImplXCBBase.close` (XGetImage inherits it), `MSSImplXShmGetImage.close` |
| `self._impl.grab(monitor)` `:312` | the `grab` of the five classes |
| `self._impl.cursor()` `:319` | `MSSImplXlib.cursor`, `MSSImplXCBBase.cursor`; not Darwin or Gdi (J4) |
| `self._impl.monitors()` `:348` | Darwin, Gdi, Xlib, `MSSImplXCBBase.monitors` |
| `self._impl.performance_status`, `.max_displays`, `.with_cursor` | slots: no callee |

The `MSS` methods (`self.grab`, `self.close`, `self.monitors`,
`self._merge`) have `MSS` and its three deprecated subclasses as receivers,
which override nothing: the ledger names only `mss.base.MSS.*`. The
`_set_cfunctions` and `_cfactory` sites pick the receiver's own class
(`MSSImplementation._cfactory` for `self._cfactory`; `MSS._cfactory` is
never called).

**Default rejections (2515 candidate-site pairs).** I listed every site of
each default with `--report mss --default <candidate>` and checked the
operand types against the source:

- `XID.__eq__` and `Visualid.__eq__` (257 sites each). The XCB value types
  reach a comparison only through reply fields and array items (ctypes
  returns a subclass instance for a field or item of a subclass of a simple
  type). I checked every `==`, `!=`, `in` and `not in` of `linux/base.py`,
  `xshmgetimage.py`, `xcb.py` and `xcbhelpers.py` against the field types
  of `xcbgen.py` (`Screen.root: Window`, `root_visual: Visualid`,
  `Visualtype.visual_id: Visualid`, `GetImageReply.visual` and
  `ShmGetImageReply.visual: Visualid`, `RandrGetOutputPrimaryReply.output:
  RandrOutput`; `depth`, `class_`, `status`, `num_outputs`,
  `image_byte_order` are `c_uint8`/`c_uint16`, read as int; `type_.value`
  and `atom_as_xid.value` are ints). Exactly the six accepted sites compare
  such instances: `linux/base.py:73`, `112`, `294`, `369`, `458`,
  `xshmgetimage.py:175`.
- `Keycode.__eq__`, `Timestamp.__eq__` (260 each) and the four `__hash__`
  (204 each): no Keycode is read; timestamps are only passed on to
  requests; no XID instance is a dict key or set member (the dict and set
  keys are str, int, threads, IntEnum members). The `hash(self.value)` sites
  hash ints.
- The five `__repr__` (91 or 92) and two `__str__` (85, 86): I read every
  format, `%`, `str()`, `print()` and `.format()` site. The formatted values
  are str, bytes, int, bool, tuples of ints, dicts of these, argparse's
  `ArgumentError`, a `datetime`, the CoreGraphics fields of `CGRect.__repr__`
  (accepted, `darwin.py:97`), the `XProtoError`s of `_shm_report_issue`
  (accepted, `xshmgetimage.py:73:46`) and the exceptions of the `__main__`
  block (accepted, `__main__.py:124`). The package never formats a
  `ScreenShot`, a `_PlatformSpecific` or a bare `CGPoint`/`CGSize`.
  `super().__str__()` in the two exception classes reaches
  `Exception.__str__`.
- `MSS.__enter__`/`__exit__` (18 each): the other 18 `with` sites hold
  locks, `suppress` objects, a memoryview and a file.

**Value sites (62).** All 62 agree (above). `cls_image` and `cls` are
`ScreenShot` (the documented `custom_cls_image` example assigns a client
subclass); `callback` of `save` is a client callable
(`docs/source/examples/callback.py:22`); `x()` is `xcbgen.initialize`
(`xcb.py:344`); the iterator, accessor, length and reply functions are
foreign functions of `LIB`; `int_`, `pack`, `crc32` are aliases.

**Functions that no site calls (73 nodes, modules included).** I checked
each against the source: the deprecated constructors and `factory.mss`
(client entries), `ScreenShot.from_size`, `bgra`, `pixel`,
`__array_interface__` (clients and NumPy), `MSS.shot`, `primary_monitor` and
the three slot properties (clients), `MSS._cfactory` (never used), the
abstract methods, the `cursor` of Darwin and Gdi (J4), the unused
xcbgen requests and accessors (`get_property`, the render functions,
`shm_create_segment`, `shm_detach`, ...), `CookieBase.discard`,
`LibContainer.reset`, the `__hash__` methods, `Keycode`/`Timestamp.__eq__`,
`CGRect.__repr__`, `ScreenShot.__repr__` and `_PlatformSpecific.__repr__`.
None has a package caller that the ledger misses.

**Special methods and properties.** I listed the 54 getattr sites. The
package's property loads are `MSS.monitors` (`base.py:364`, `396`),
`ScreenShot.rgb` (`base.py:408`, `424`, `__main__.py:106`), and the
`ScreenShot` properties inside its own methods; every other load of a
property name (`width`, `height`, `left`, `top`, `pixels`, `with_cursor`,
`max_displays`, `performance_status`, `monitors`) is a ctypes field, a named
tuple field, a slot of an implementation or an argparse attribute, each
rejected with that reason. No package class defines `__getattr__`,
`__bool__`, `__len__`, `__iter__`, `__call__`, `__del__`, `__init_subclass__`
or `__set_name__`.

**Callees outside the package, and the ctypes names.** I listed the 115
outside names of the graph with their edge counts and checked each against
the micro-benchmark's naming rules and the dependency sources:

- `ctypes.CDLL.__init__._FuncPtr.__call__` (50 edges): `CDLL.__init__`
  defines `class _FuncPtr(_CFuncPtr)` on CPython 3.10 and 3.11
  (`ctypes/__init__.py:368`, `:370`) and on PyPy 3.9 and 3.11 (`:369`,
  `:372`);
  `WinDLL` inherits that `__init__`; `cdll.LoadLibrary` and `windll.X` make
  `CDLL`/`WinDLL` objects. Every foreign call of the package is on such an
  object; no `restype` or `argtypes` is a package callable.
- errcheck: every call of an Xlib function of `CFUNCTIONS` but
  `XSetErrorHandler` has `_validate_x11` (15 sites; `XFixesGetCursorImage`
  only when `xfixes` exists, `xlib.py:520`); every call of a GDI function
  with `_errcheck` has it (11 sites; not `GetSystemMetrics`,
  `EnumDisplayDevicesW`, `GdiFlush`, nor `SetProcessDpiAwareness` and
  `SetProcessDPIAware`, which are not in `CFUNCTIONS`). The fresh `CDLL` of
  `_error_handler` (`xlib.py:295`) has no errcheck. CoreGraphics and XCB
  functions have none.
- `ctypes.CFUNCTYPE.CFunctionType`, `ctypes.WINFUNCTYPE.WinFunctionType`:
  classes defined in those functions (CPython `:102`, `:126`; PyPy `:103`,
  `:127`/`:130`), named as definitions without an attribute path.
- `ctypes.POINTER`, `byref`, `addressof`, `sizeof`, `cast`,
  `create_string_buffer`, `wstring_at`, `WinError`, `util.find_library`,
  `LibraryLoader.LoadLibrary`, `WinDLL`, `c_int`, `c_uint32`, `c_void_p`,
  `wintypes.LPVOID`: the paths the package imports (ctypes has no
  `__all__`). `ctypes.c_uint32.__init__` (3 edges) and
  `ctypes.Structure.__init__` (5) name the inherited `__init__` through the
  base the package names. `_ctypes.PyCStructType.in_dll` and
  `_ctypes.structure.StructureMeta.in_dll`: see Step 1.
- The others (`threading.*`, `mmap.mmap.close`, `io.BufferedWriter.*`,
  `argparse.ArgumentParser.*`, `datetime.datetime.now`, `locale.*`,
  `weakref.finalize`, `copy.copy`, `enum.auto`, `<builtin>.Exception.__str__`
  and `__init__`, ...) follow the receiver-class and import-path rules.
  `os.memfd_create`, `locale.getencoding` and `mmap` run on some admitted
  versions or platforms, as their branches say.

**Binding check.** A script of mine (`$TMPDIR/b7-audit-mss/bind.py`, `ast`
only) matched every call site in the ledger with a package callee against
the callee's signature (positional and keyword counts, positional-only and
keyword-only parameters, `*`/`**` at the call). It flags only the 34
call-back pairs, where ctypes, Xlib, Windows or `print`/`str` make the call
with their own arguments (`errcheck(result, func, args)` matches
`_validate_x11(retval, func, args, /)` and `_errcheck(result, func,
arguments)`; the C thunk passes two arguments to `_error_handler(display,
event)`). No direct call fails to bind.

**Rejected trace edges.** None: mss has no trace.

## The writer's judgement calls

- **J1, the Xlib error handler.** Supported. The micro-benchmark's callback
  rule ("a snippet function that builtin or library code calls belongs to
  the snippet scope whose call made that code run") and B5's library
  call-back rule ("starts library code that dispatches to an object which
  the package's ... setup registers") cover a C library that calls a
  handler the package registered; here the package's own `__init__`
  registers it (`xlib.py:461`). The signal-handler sentence of "Implicit
  calls" limits it to the calls during which the library can run it, and
  `signal.signal`'s precedent gives no edge at `XSetErrorHandler` itself.
  The calls are the ten of the writer: those that send a request and read a
  reply or sync (`XOpenDisplay`, `XCloseDisplay`, `XQueryExtension`,
  `XRRQueryVersion`, `XGetWindowAttributes`, `XRRGetScreenResourcesCurrent`,
  `XRRGetScreenResources`, `XRRGetCrtcInfo`, `XGetImage`,
  `XFixesGetCursorImage`); not `XDefaultRootWindow` (a display accessor),
  `XDestroyImage`, `XRRFreeCrtcInfo`, `XRRFreeScreenResources`
  (client-side frees) or `XSetErrorHandler`. An error reply is the server's
  answer, which "Judgements" says decides a branch that runs. Neither of us
  read libX11; the least certain call is `XOpenDisplay` (its round trip
  after the connection setup), and it alone decides 1 edge
  (`MSSImplXlib.__init__ -> _error_handler`); `XCloseDisplay` alone decides
  `close -> _error_handler`. The other 4 edges have several sure calls.
  My opinion: keep the 6 edges.
- **J2, ctypes types made at run time.** The README does not decide it. The
  nearest rule is B4's "a documented class that has no public path cannot
  be named: the site keeps a note and no callee", written for client
  values. The smaller extension: a class that library code makes at run
  time without a definition in source (`POINTER(T)`, `T * n`) has no name,
  so its call keeps a note and no callee; a class that a `class` statement
  inside a library function defines keeps its definition-site name (J3(d),
  and `_FuncPtr`). I agree with the writer (4 sites, 3 edges not made).
- **J3, ctypes names.** Supported by the naming rules ("Inherited methods",
  "Calls of instances", "Functions without an attribute path", the two
  receiver classes of admitted runtimes). See R2 for `LPVOID`.
- **J4, cursor on macOS and Windows.** Supported: B1's state sentence
  ("where the package makes every instance of a private class in one
  state, a branch that this state never takes adds no edge") applies to the
  private `_impl`, whose Darwin and Gdi objects always have `with_cursor`
  false (`base.py:219`, `darwin.py:141`, `gdi.py:194`).
- **J5, the impossible branch of `_validate_x11`.** Supported: B1's "a check
  that cannot fail under the package's own values has no callee" (ruling 11
  of batch 5). I checked the restypes of the 14 functions of `xlib.py:366-387`
  that get this errcheck (all but `XSetErrorHandler`): None, `c_int`, `XID`,
  `XStatus`, `XBool` and `POINTER(...)`; a subclass of a
  simple type comes back as an instance on CPython and PyPy, so each value
  takes an earlier branch.
- **J6, `str()` of the XCB errors.** Supported (B2: the private
  `_shm_report_issue` gets what the package passes, `xshmgetimage.py:89`,
  `102`, `108`, `118`, `225`).
- **J7, client values.** Supported (B5; ruling 2 of batch 5 for a
  documented assignment of `cls_image`).
- **J8, named tuples.** Supported ("Callees outside the package", the
  `NamedTuple` sentence).

One branch that I expected a judgement on: `gdi.py:257`, the Windows 6.0 to
6.2 branch of `_set_dpi_awareness`. CPython 3.9 and later do not support
Windows 7, but `sys.getwindowsversion()` reports 6.2 to a process without a
compatibility manifest (an embedding or frozen executable). The ledger
keeps the branch; no edge depends on it, because its callee
(`_FuncPtr.__call__`) is also the callee of line 256.

## Platforms and implementations (batch-7 ruling, `fb7ffd8`)

The ruling: supported platforms are those that the release declares
(classifiers, documentation) or establishes through its own platform test
jobs; a platform branch in the code admits none. What mss 10.2.0 declares:

| Source | Platforms | Implementations and versions |
|---|---|---|
| `pyproject.toml:9`, `:17-41` classifiers | `Environment :: MacOS X`; `Operating System :: MacOS`, `Microsoft :: Windows`, `Unix` | `Implementation :: CPython`, `Implementation :: PyPy`; Python 3, 3.9 to 3.14; `requires-python = ">= 3.9"` |
| `docs/source/support.rst:7-8`, `:21` | "OS: GNU/Linux, macOS, and Windows" | "Python: 3.9 and newer"; "Tested successfully on Pypy 5.1.0 on Windows" |
| `.github/workflows/tests.yml:57-77` | test jobs on `ubuntu-latest`, `macos-latest`, `windows-latest` | CPython 3.9 to 3.14 (no PyPy job); `release.yml` and the quality and documentation jobs run on Ubuntu only |

So Linux (docs, CI, inside the declared Unix family), macOS and Windows are
declared, each three ways. The ledger uses exactly these three (`mss.md`,
"Supported versions, implementations and platforms"; the Darwin, Linux and
Windows branches of `base.py:149-164`, `__main__.py:17-28`, and the modules
`darwin`, `linux.*`, `windows.*`). It names no other platform.

`Operating System :: Unix` is a family (the websocket-client ruling). Its
other members (the BSDs, Solaris, AIX) admit no further edge: there
`platform.system()` is neither "darwin", "linux" nor "windows", so
`_choose_impl` raises (`base.py:166-167`, an edge the graph has) and
`_backend_cli_choices` returns `["default"]`; the package has no other
branch on the platform; a client that builds an XCB or Xlib implementation
itself there reaches the same code, and its library calls
(`ctypes.util.find_library`, `os.memfd_create` behind `hasattr`, `mmap`,
`os.ftruncate`) keep the names the graph has. The `hasattr` branches that
these platforms could take (`xshmgetimage.py:96`, `xlib.py:314`) are
already in the graph for admitted CPython versions.

PyPy is declared by its classifier (and the documentation's PyPy line), so
by the ruling "Implementation, version and platform combinations" it
counts with the declared bounds and platforms: PyPy 3.9, 3.10 and 3.11 on
Linux, macOS and Windows, which the ledger uses (`mss.md`, first bullet).
The missing PyPy CI job does not exclude it. The only outside name that
differs on PyPy is `in_dll` (checked in Step 2: `_FuncPtr`,
`CFunctionType`, `WinFunctionType`, the inherited `__init__` and the
imported paths are the same on PyPy 3.9 and 3.11).

**The writer's change of the PyPy `in_dll` name (`c461fe1`).** The current
ledger names `_ctypes.structure.StructureMeta.in_dll` beside
`_ctypes.PyCStructType.in_dll` at `xcbhelpers.py:495`, `502`, `509`, `516`
(it was the defining class `_ctypes.basics._CDataMeta`). The receiver is
the class `XcbExtension`; its class on PyPy is the metaclass of
`Structure`, `StructureMeta` (lib_pypy 3.9 `_ctypes/structure.py:334`,
3.11 `:340`), which inherits `in_dll` from `_CDataMeta` (`basics.py:98`,
`:101`). "A method of an outside object is named by the class of the
receiver, also when that class inherits it": the new name is right, and
it is the name of my blind answer's rule. The CPython name is the
receiver's class too. 2 graph edges, unchanged in count.

No finding of this audit changes; the platform ruling changes no edge of
mss.

## For the lead

- No ruling is needed for the graph. J1 and J2 are the writer's
  extensions of existing rules; I agree with both (J1: 6 edges, J2: 0).
- R1 and R2 ask for one sentence each in the README.

## Re-check (the committed ground truth at `e1a8099`)

I compared the mss files of `c461fe1` (the ledger I audited) with `HEAD`
(`git diff c461fe1 HEAD`). Only `mss.ledger` (5 entries), `mss.json`,
`mss.added.json` and `mss.md` changed; `check.py mss` reports no errors
and 592 edges (263 inside, 329 outside).

- **The added callee.** `mss.linux.xcbhelpers 217:49 POINTER(c_char_p)()`
  now has `-> ctypes.c_char_p.__pointer_type__` with a note that cites
  CPython 3.14 and the README's ctypes rule (referee, `b7-ruling-mss.md`
  part 2 as replaced by `b7-ruling-mss-2.md`). The graph has the one new
  edge `XProtoError.__init__ -> ctypes.c_char_p.__pointer_type__`, and
  `mss.added.json` has it with its site and note. I checked the claim in
  the CPython sources on this machine
  (`~/.local/share/uv/python/cpython-3.14.9-macos-aarch64-none`):
  `ctypes/__init__.py:271-294` defines `POINTER(cls)`, which returns
  `cls.__pointer_type__` when it exists and otherwise makes the type
  ("create pointer type and set `__pointer_type__` for cls");
  `libpython3.14.dylib` holds the strings `__pointer_type__` and
  "has no attribute '__pointer_type__'" (the C side that sets and reads
  it); `c_char_p` is a class of `ctypes/__init__.py:257`. CPython 3.13.12's
  `ctypes/__init__.py` has no `__pointer_type__`. So the attribute is new
  in 3.14, an admitted version, and the union over versions keeps the
  edge. I could not check the documentation text itself: no `Doc/`
  directory is on this machine; the source and the binary agree with the
  referee's citation. The other three sites (`212:44`, `309:47`,
  `darwin.py:191:57`) keep a note and no callee, with notes that state
  the rule (a path through a package class is no outside name; an array
  class has no such attribute). I agree.
- **J1.** The ten ledger sites are unchanged (`xlib.py` `463:59`,
  `478:40`, `505:42`, `539:35`, `543:43`, `556:58`, `558:51`, `562:45`,
  `584:41`, `620:54`), each with `_error_handler` and `_validate_x11`; no
  edge at `XSetErrorHandler`, `XDefaultRootWindow`, `XDestroyImage` or
  `XRRFree*`. `mss.md` J1 now gives each call its site and the
  documentation the referee cited: the Xlib specification (requests that
  return data wait for a reply or an error; received errors invoke the
  handler) for all ten, the `XCloseDisplay` manual (final `XSync`), the
  `XResourceManagerString` text (`XOpenDisplay` reads `RESOURCE_MANAGER`),
  the RandR protocol (the four RandR replies) and the XFixes protocol
  (`GetCursorImage`). Each call is matched with the source that covers it.
  I did not open the external documents (no network use); the citations
  agree with my reading of the protocol.
- **W1.** `mss.md` J1 now says 10 site-callee pairs and **6 graph edges**
  (one per caller), J3(c) 8 site-callee pairs and **2 graph edges**. Both
  counts match the graph. W1 is closed.
- **The two decorator notes** (`xlib.py:291:2`, `gdi.py:279:10`) no longer
  say that the class's `__init__` is `object.__init__`; they say the
  external class is the callee. The callees are unchanged. Right: PyPy's
  `CFuncPtr` defines `__init__` (lib_pypy 3.11 `_ctypes/function.py:206`),
  and the micro-benchmark rule names the class for an outside class call
  either way.
- **Nothing else changed:** the diff has no other ledger line; `mss.md`
  changed only in its status, counts, J1, J2, J3(c) and J3(d).

Verdict: the re-check passes. W1, R1 (now the README's ctypes rule,
"Rulings for batch 7") and R2 (the referee keeps both spellings at
different sites) are closed.
