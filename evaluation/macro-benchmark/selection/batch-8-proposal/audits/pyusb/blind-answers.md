# pyusb: blind answers (seed 20261124)

Written from the source (`usb/`, release v1.3.1, commit
`89ea84d6c9e4cb81bc6e40d7df849d0cbd7dfd47`), `setup.py`, `docs/`,
`tests/`, the README's rules and the dependency sources, before any file of
the writer was opened. Skeleton made without a ledger in a scratch copy
(`check.py --benchmark-dir <scratch> --skeleton pyusb`): 2564 sites (975
call, 88 decorator, 1267 getattr, 101 op, 62 getitem, 57 iter, 11 mapping,
3 setitem); 29 value sites. Explicit sites (call, decorator) are 1063 of
2564; the implicit sites are 1501, and 1267 of them are attribute loads
whose only candidates are the two `__getattr__` of libusb1 (1300 sites
each). Draw (`draw.py`): one `random.Random(20261124)`,
`rng.sample(explicit, 100)` then `rng.sample(implicit, 40)` (the mss
split of batch 7 for a doubled audit), then the 28 value sites not drawn
(one value site, `libusb1.py:776:49`, was drawn as explicit): 168 sites.

## Conventions I apply (decided before reading the ledger)

- **Versions, implementations, platforms.** `python_requires='>=3.9.0'`
  with no upper bound: CPython 3.9 to 3.14 and later (the final classifier,
  3.13, is no upper bound); PyPy (classifier); IronPython and Jython have no
  Python 3.9 and are not admitted. Platforms: macOS, Windows, Free/Net/
  OpenBSD, Linux, Solaris (classifiers), also the tox job platforms.
- **Tracing (J-trace).** `PYUSB_DEBUG` is documented (`docs/tutorial.rst:
  127-136`, `docs/faq.rst:17`): it is admitted configuration (the tinytag
  ruling on package-owned environment variables). `usb/__init__.py:106`
  calls `_setup_log()` before any backend module is imported, so with
  `PYUSB_DEBUG` set `methodtrace(_logger)` returns `do_trace` for each of
  the 70 decorated methods. A call of a decorated method then has
  `usb._debug.methodtrace.decorator_logging.do_trace` as callee, beside the
  method itself (without the variable the decorator returns `f`). `do_trace`
  calls the 70 methods (`_debug.py:62:21`).
- **`@synchronized`.** The 11 decorated methods of `_ResourceManager` are
  bound to `usb.core.synchronized.wrapper`: a call of one has `wrapper` as its
  callee, never the method; `wrapper` calls the 11 (`core.py:113:21`).
- **Backends.** A backend is a documented `IBackend` (`backend/__init__.py:
  37-69`, tutorial 517-526). Package values: `IBackend` itself (a plain
  public class), libusb0 `_LibUSB`, libusb1 `_LibUSB`, openusb `_OpenUSB`
  (from the public `get_backend`). Client subclasses are client code. A
  `Device` cannot exist with an `IBackend()` backend: `Device.__init__`
  calls `backend.get_device_descriptor(dev)` (`core.py:800`), which raises;
  `find` calls `enumerate_devices` first, which raises. So at dispatch sites
  on the backend of a built `Device`, `IBackend`'s own methods are callees
  only where a package backend inherits them (libusb0: `get_parent`,
  `attach_kernel_driver`; openusb: `get_parent`, `iso_write`, `iso_read`,
  `is_kernel_driver_active`, `detach_kernel_driver`,
  `attach_kernel_driver`).
- **ctypes names** (the mss rulings): a foreign call through a `CDLL` or
  `WinDLL` object is `ctypes.CDLL.__init__._FuncPtr.__call__`; `POINTER`,
  `cast`, `byref`, `sizeof` as `ctypes.<name>`; a simple type call by its
  access path (`ctypes.c_int`, `ctypes.c_void_p` for the alias
  `_libusb_device_handle`, `ctypes.c_uint64` for the openusb aliases); a
  package structure `__init__` through `super()` is
  `ctypes.Structure.__init__`; `POINTER(T)()` is
  `ctypes.T.__pointer_type__` when `T` is a ctypes class (CPython 3.14,
  admitted) and has no callee when `T` is a package structure; an array
  class `(c_uint8 * 7)()` has no callee. `memset` is an instance of
  `CFUNCTYPE(...)`'s class (`ctypes/__init__.py:533` on 3.13, `:606` on
  3.14, PyPy 3.11 `:502`): `ctypes.CFUNCTYPE.CFunctionType.__call__`
  ("a callable wrapper object uses its concrete class's `__call__`").
  `_libusb_transfer_cb_fn_p` is that class: `ctypes.CFUNCTYPE.CFunctionType`.
- **Descriptors of libusb1.** `_ConfigDescriptor` and `_WrapDescriptor`
  forward missing attributes with `__getattr__`; a load of a descriptor
  field on them, and `getattr(input, f)` in `core._set_attr`, call it back.
  Every other receiver of the 1267 attribute loads (modules, ctypes
  structures, CDLL objects, package objects without `__getattr__`) does not.
- **Weak references.** `self._finalizer()` is `weakref.finalize.__call__`,
  which calls `_do_finalize_object_ref` back (`weakref.py:586-591`);
  `obj_ref()` is `weakref.ref.__call__` (bottle precedent). A finalizer that
  runs at garbage collection or at exit is no edge (the `__del__` rule).
- Builtin exception classes: `<builtin>.ValueError` and so on; `str(x)`
  is `<builtin>.str`, with a package `__str__`/`__repr__` only where `x`
  can be a package object.

## Answers

Format: `#n site`: callees; rejections. "R(gattr)" = both
`_ConfigDescriptor.__getattr__` and `_WrapDescriptor.__getattr__` rejected.

### usb/__init__.py

- #6 `60:15 int(major)`: `<builtin>.int`.
- #14 `70:28 os.getenv('PYUSB_DEBUG')`: `os.getenv`.
- #26 `82:49 getattr logging.CRITICAL`: none; R(gattr): the receiver is the
  `logging` module.
- #30 `86:42 logging.FileHandler(filename)`: `logging.FileHandler` (with
  `filename` None the body raises; the bare `except` catches it).
- #41 `101:24 logger.setLevel(...)`: `logging.Logger.setLevel`
  (`logging.getLogger('usb')`).

### usb/_debug.py

- #69 `61:55 getitem args[1:]`: none; reject the five candidates: `args`
  is the tuple of the call's positional arguments.
- #71 value `62:21 f(*args, **named_args)` (methodtrace's `do_trace`):
  the 70 methods decorated with `@methodtrace(_logger)`: libusb0
  `_LibUSB.{enumerate_devices, get_device_descriptor,
  get_configuration_descriptor, get_interface_descriptor,
  get_endpoint_descriptor, open_device, close_device, set_configuration,
  get_configuration, set_interface_altsetting, claim_interface,
  release_interface, bulk_write, bulk_read, intr_write, intr_read,
  iso_write, iso_read, ctrl_transfer, clear_halt, reset_device,
  is_kernel_driver_active, detach_kernel_driver}` (23); libusb1
  `_Device._finalize_object`, `_LibUSB.{__init__, _finalize_object,
  enumerate_devices, get_parent, get_device_descriptor,
  get_configuration_descriptor, get_interface_descriptor,
  get_endpoint_descriptor, open_device, close_device, set_configuration,
  get_configuration, set_interface_altsetting, claim_interface,
  release_interface, bulk_write, bulk_read, intr_write, intr_read,
  iso_write, iso_read, ctrl_transfer, clear_halt, reset_device,
  is_kernel_driver_active, detach_kernel_driver, attach_kernel_driver}`
  (28); openusb `_OpenUSB.{enumerate_devices, get_device_descriptor,
  get_configuration_descriptor, get_interface_descriptor,
  get_endpoint_descriptor, open_device, close_device, set_configuration,
  get_configuration, set_interface_altsetting, claim_interface,
  release_interface, bulk_write, bulk_read, intr_write, intr_read,
  ctrl_transfer, reset_device, clear_halt}` (19). Note: `f` is the method
  that `decorator_logging` wrapped; only with `PYUSB_DEBUG` (J-trace).
  The tests' own decorated functions are client code.
- #76 `74:24 getattr logging.DEBUG`: none; R(gattr) (module).
- #83 value `76:21 f(*args, **named_args)` (functiontrace's `do_trace`):
  no callee. The package never applies `functiontrace` (private module
  `_debug`); judged as public, `f` is a client callable (B3: no arbitrary
  package function).

### usb/_objfinalizer.py

- #113 value `99:18 obj_ref()`: `weakref.ref.__call__` (the only value is
  `weakref.ref(instance)`, `_objfinalizer.py:134-136`).
- #126 value `142:24 self._finalizer()`: `weakref.finalize.__call__`,
  `usb._objfinalizer._do_finalize_object_ref` (called back by
  `finalize.__call__` with the registered function).

### usb/backend/__init__.py

- #127 `83:30 NotImplementedError(func.__name__)`:
  `<builtin>.NotImplementedError`.
- #142 `178:25 _not_implemented(self.open_device)`:
  `usb.backend._not_implemented`; reject `IBackend.open_device` and the
  three backend `open_device`: passed as an argument, `_not_implemented`
  reads only `__name__` and raises.
- #148 `207:25 _not_implemented(self.get_configuration)`: same;
  reject also `usb.control.get_configuration` (not this attribute).
- #156 `253:25 ... bulk_write`, #158 `268:25 ... bulk_read`,
  #160 `283:25 ... intr_write`: `usb.backend._not_implemented`; the
  passed methods rejected as at #142.
- #161 `283:31 getattr self.intr_write`, #173 `363:31 getattr
  self.reset_device`: none; R(gattr): `self` is an `IBackend` or a package
  backend, which define no `__getattr__`.

### usb/backend/libusb0.py

- #211 `111:39 POINTER(_usb_interface_descriptor)`, #212 `123:38
  POINTER(_usb_interface)`: `ctypes.POINTER`.
- #228 `176:34 getattr desc.bDeviceClass`: none; R(gattr): `desc` is the
  `_usb_device_descriptor` field of a `_usb_device` structure.
- #293 `420:15 hasattr(lib, 'usb_cancel_async')`: `<builtin>.hasattr`.
- #312 `447:19 USBError(errmsg, ret)`: `usb.core.USBError.__init__`.
- #354 `482:29 IndexError(...)`: `<builtin>.IndexError`.
- #369 `492:50 self.get_interface_descriptor(dev, intf, alt, config)`:
  `usb.backend.libusb0._LibUSB.get_interface_descriptor`,
  `usb._debug.methodtrace.decorator_logging.do_trace`; reject
  `IBackend.get_interface_descriptor` and the libusb1 and openusb methods:
  `self` is a libusb0 `_LibUSB`, which overrides it.
- #371 `494:29 IndexError(...)`: `<builtin>.IndexError`.
- #372 `494:61 str(ep)`: `<builtin>.str`; reject the nine `__str__`/
  `__repr__`: `ep` is an endpoint index (an int).
- #421 decorator `539:6 @methodtrace(_logger)`, #446 decorator `578:6`:
  `usb._debug.methodtrace.decorator_logging`.
- #485 `620:17 methodtrace(_logger)`: `usb._debug.methodtrace`.
- #527 `669:24 iter buf.buffer_info()`: none; reject all: unpacking the
  tuple that `array.buffer_info` returns.
- #540 `680:24 getattr data.itemsize`: none; R(gattr): `data` is an
  `array.array` (IBackend's documented contract; `core.Device.write`
  passes `_interop.as_array(data)`).
- #543 value `681:29 fn(...)`: `ctypes.CDLL.__init__._FuncPtr.__call__`
  (`fn` is `_lib.usb_bulk_write` or `_lib.usb_interrupt_write`).
- #551 value `692:28 fn(...)`: `ctypes.CDLL.__init__._FuncPtr.__call__`
  (`_lib.usb_bulk_read`, `_lib.usb_interrupt_read`).
- #552 `695:25 cast(address, c_char_p)`: `ctypes.cast`.

### usb/backend/libusb1.py

- #612 `130:41`, #618 `132:43`, #624 `164:45`, #636 `168:49`
  `errno.__dict__.get(...)`: `<builtin>.dict.get`.
- #641 `174:36 _lib.libusb_strerror(errcode)`:
  `ctypes.CDLL.__init__._FuncPtr.__call__`.
- #691 `389:20 POINTER(_libusb_device_descriptor)`: `ctypes.POINTER`.
- #732 `581:13 getattr lib.libusb_get_port_numbers`: none; R(gattr)
  (a CDLL object).
- #745 `604:27 USBError(...)`: `usb.core.USBError.__init__`.
- #750 `611:44 _lib.libusb_ref_device(devid)`:
  `ctypes.CDLL.__init__._FuncPtr.__call__`.
- #757 `625:23 getattr(self.desc, name)`: `<builtin>.getattr`; reject
  both `__getattr__`: `self.desc` is a `_libusb_interface_descriptor` or
  `_libusb_endpoint_descriptor` structure (`:793-795`, `:802-804`).
- #760 `632:19 hasattr(self, 'desc')`: `<builtin>.hasattr`; reject both
  `__getattr__`: `__init__` sets `desc` first, so the lookup never falls
  back to `_ConfigDescriptor.__getattr__`.
- #767 `638:34 getattr _objfinalizer.AutoFinalizedObject`, #792 `658:41`:
  none; R(gattr) (module).
- #769 value `640:42 POINTER(c_void_p)()`: `ctypes.c_void_p.__pointer_type__`
  (CPython 3.14 names the class; no public path on 3.9-3.13 or PyPy).
- #784 value `654:44 _libusb_device_handle()`: `ctypes.c_void_p` (alias,
  `:246`).
- #786 `656:15 _check(...)`: `usb.backend.libusb1._check`; reject the
  libusb0 and openusb `_check` (other modules).
- #805 `667:14 getattr _lib.libusb_fill_iso_transfer`: none; R(gattr)
  (the CDLL object; the attribute is the Python function stored at `:553`).
- #806 value `667:38 _lib.libusb_fill_iso_transfer(...)`:
  `usb.backend.libusb1._setup_prototypes.libusb_fill_iso_transfer` (the
  Python function that `_setup_prototypes` stores on the same `_lib`,
  `:526-553`, `get_backend` `:965-966`).
- #811 value `673:63 _libusb_transfer_cb_fn_p(self.__callback)`:
  `ctypes.CFUNCTYPE.CFunctionType`; reject
  `_IsoTransferHandler.__callback`: wrapped as a C callback, it runs when
  `libusb_handle_events` dispatches the transfer (`:688`), not here.
- #817 `681:38 _lib.libusb_free_transfer(self.transfer)`:
  `ctypes.CDLL.__init__._FuncPtr.__call__`.
- #833 value `692:31 usb.USBError(...)`: `usb.core.USBError.__init__`
  (`usb` re-exports `legacy.USBError = core.USBError`).
- #845 value `703:43 _lib.libusb_set_iso_packet_lengths(...)`:
  `usb.backend.libusb1._setup_prototypes.libusb_set_iso_packet_lengths`.
- #876 decorator `729:6`, #1083 decorator `922:6`:
  `usb._debug.methodtrace.decorator_logging`.
- #878 `731:28 _DevIterator(self.ctx)`:
  `usb._objfinalizer.AutoFinalizedObject.__new__`,
  `usb.backend.libusb1._DevIterator.__init__`; reject
  `_AutoFinalizedObjectBase.__new__` (reached through `super()` inside
  `AutoFinalizedObject.__new__`) and openusb `_DevIterator.__init__`.
- #882 `735:24 getattr self.lib`, #1079 `919:33`: none; R(gattr).
- #886 `739:27 _Device(_parent)`: `AutoFinalizedObject.__new__`,
  `usb.backend.libusb1._Device.__init__`; reject the base `__new__`.
- #906 `750:62 self.lib.libusb_get_device_speed(...)`:
  `ctypes.CDLL.__init__._FuncPtr.__call__`.
- #912 value `762:33 (c_uint8 * 7)()`: no callee (a generated array class
  with no public path).
- #923 `776:49 POINTER(_libusb_config_descriptor)()`: no callee (the
  pointer class of a package structure).
- #951 `795:31 _WrapDescriptor(intf_desc, cfg)`:
  `usb.backend.libusb1._WrapDescriptor.__init__`.
- #969 `810:17 methodtrace(_logger)`: `usb._debug.methodtrace`.
- #979 `816:49 self.lib.libusb_set_configuration(...)`:
  `ctypes.CDLL.__init__._FuncPtr.__call__`.
- #983 `820:23 c_int()`, #1101 `933:28`, #1115 `949:28`: `ctypes.c_int`.
- #1015 `841:28 self.__write(...)`: `usb.backend.libusb1._LibUSB.__write`;
  reject libusb0 `_LibUSB.__write` (another class).
- #1039 `878:24 getattr handler.submit`: none; R(gattr).
- #1060 `903:59 POINTER(c_ubyte)`: `ctypes.POINTER`.
- #1102 value `934:20 fn(...)`, #1116 value `950:20 fn(...)`:
  `ctypes.CDLL.__init__._FuncPtr.__call__` (`self.lib.libusb_bulk_transfer`
  or `libusb_interrupt_transfer`).

### usb/backend/openusb.py

- #1135 `81:28 logging.getLogger(...)`: `logging.getLogger`.
- #1153 `124:38`, #1165 `133:40 errno.__dict__.get(...)`:
  `<builtin>.dict.get`.
- #1154 `125:28 getattr errno.__dict__`: none; R(gattr).
- #1192 `202:52 super(_openusb_ctrl_request, self).__init__()`:
  `ctypes.Structure.__init__`; reject all 25 package `__init__`: the next
  class of the MRO is `ctypes.Structure`.
- #1215 `290:20 POINTER(c_uint32)`, #1271 `499:20
  POINTER(_openusb_isoc_request)`: `ctypes.POINTER`.
- #1273 `505:15 hasattr(ret, 'value')`: `<builtin>.hasattr`.
- #1275 `508:12 op ret != 0`: none; reject `Device.__eq__`: `ret` is an
  int (`c_int32` results, or `.value`).
- #1286 value `518:38 _openusb_handle()`: `ctypes.c_uint64`.
- #1298 value `526:47 POINTER(_openusb_busid)()`, #1318 value `541:47
  POINTER(_openusb_devid)()`: `ctypes.c_uint64.__pointer_type__`.
- #1300 `528:15 _check(...)`: `usb.backend.openusb._check`; reject the
  other two.
- #1343 `559:38 _DevIterator(bus)`: `AutoFinalizedObject.__new__`,
  `usb.backend.openusb._DevIterator.__init__`; reject the base `__new__`
  and libusb1 `_DevIterator.__init__`.
- #1366 `592:55 getattr _ctx.handle`, #1372 `606:21 getattr
  _lib.openusb_parse_endpoint_desc`, #1400 `636:23 getattr config.value`,
  #1439 `664:40 getattr buff.buffer_info`, #1464 `678:24 getattr
  request.result`: none; R(gattr).
- #1378 value `620:37 _openusb_dev_handle()`: `ctypes.c_uint64`.
- #1385 `624:17`, #1402 `638:17 methodtrace(_logger)`:
  `usb._debug.methodtrace`.
- #1405 `640:43`, #1410 `644:44 _lib.openusb_*(...)`:
  `ctypes.CDLL.__init__._FuncPtr.__call__`.
- #1435 `663:15 memset(byref(request), 0, sizeof(request))`:
  `ctypes.CFUNCTYPE.CFunctionType.__call__`.
- #1441 `665:31`, #1500 `719:31 cast(payload, POINTER(c_uint8))`:
  `ctypes.cast`.
- #1485 `708:40 _openusb_ctrl_request()`:
  `usb.backend.openusb._openusb_ctrl_request.__init__`.

### usb/control.py

- #1538 `73:20 isinstance(...)`: `<builtin>.isinstance`.
- #1543 `76:37 getattr core.Endpoint`, #1596 `244:26 getattr
  util.build_request_type`: none; R(gattr).
- #1578 value `180:23 USBError('Invalid descriptor')`:
  `usb.core.USBError.__init__` (`USBError = core.USBError`, `:67`).

### usb/core.py

- #1619 value decorator `109:6 @functools.wraps(f)`:
  `functools.partial.__call__`.
- #1625 value `113:21 f(self, *args, **kwargs)`: the 11 synchronized
  methods: `usb.core._ResourceManager.{managed_open, managed_close,
  managed_set_configuration, managed_claim_interface,
  managed_release_interface, managed_set_interface, setup_request,
  get_interface_and_endpoint, get_active_configuration,
  release_all_interfaces, dispose}`.
- #1651 `152:36 MockConfiguration()`:
  `usb.core._ResourceManager.managed_set_configuration.MockConfiguration.__init__`.
- #1670 decorator `170:6 @synchronized`: `usb.core.synchronized`.
- #1673 `174:22 isinstance(intf, Interface)`: `<builtin>.isinstance`.
- #1692 `193:22 getattr self._claimed_intf`: none; R(gattr).
- #1712 `212:83 str(alt)`: `<builtin>.str`; reject the nine: `alt` is an
  int or None (`set_interface_altsetting`; legacy converts an Interface).
- #1740 `243:54 self.get_active_configuration(device)`:
  `usb.core.synchronized.wrapper`; reject
  `_ResourceManager.get_active_configuration` (the attribute is the
  `synchronized` wrapper, which calls it at `113:21`) and
  `Device.get_active_configuration` (`self` is a `_ResourceManager`).
- #1751 `251:29 ValueError(...)`: `<builtin>.ValueError`.
- #1759 `259:46 getattr self.backend`: none; reject `Device.backend` (a
  `_ResourceManager` instance attribute) and R(gattr).
- #1763 `262:31 USBError('Configuration not set')`:
  `usb.core.USBError.__init__`.
- #1809 `395:28 _try_lookup(...)`: `usb.core._try_lookup`.
- #1842 `445:30 getitem _lu.ep_attributes[...]`: none; reject the five: a
  dict with int keys.
- #1847 `485:48 backend.get_interface_descriptor(...)`:
  libusb0 `_LibUSB.get_interface_descriptor`, libusb1
  `_LibUSB.get_interface_descriptor`, openusb
  `_OpenUSB.get_interface_descriptor`, `do_trace`; reject
  `IBackend.get_interface_descriptor` (no `Device` with an `IBackend`
  backend; every package backend overrides it).
- #1879 `555:45 getattr self.bInterfaceNumber`: none; R(gattr).
- #1921 `618:18 _set_attr(...)`: `usb.core._set_attr`.
- #1934 `653:23 range(self.bNumInterfaces)`: `<builtin>.range`.
- #1980 `711:28 _try_get_string(...)`: `usb.core._try_get_string`.
- #2016 `795:37 _ResourceManager(dev, backend)`:
  `usb.core._ResourceManager.__init__`.
- #2030 `844:29 int(desc.speed)`: `<builtin>.int`.
- #2033 `863:17 getattr self._langids`, #2091 `973:14`, #2103 `976:14
  getattr self._ctx`, #2144 `1036:26 getattr util.endpoint_type`, #2247
  `1193:29 getattr self.bLength`, #2255 `1198:42 getattr self.bcdUSB`:
  none; R(gattr).
- #2037 decorator `870:6 @property`: `<builtin>.property`.
- #2120 `1001:39 util.endpoint_type(...)`: `usb.util.endpoint_type`.
- #2122 value `1003:18 fn(...)` (write): libusb0 `_LibUSB.bulk_write`,
  `.intr_write`, `.iso_write`; libusb1 `_LibUSB.bulk_write`, `.intr_write`,
  `.iso_write`; openusb `_OpenUSB.bulk_write`, `.intr_write`;
  `usb.backend.IBackend.iso_write` (openusb inherits it); `do_trace`.
- #2147 `1038:22 isinstance(...)`: `<builtin>.isinstance`.
- #2151 value `1043:17 fn(...)` (read): the same with `*_read`:
  libusb0 and libusb1 `bulk_read`, `intr_read`, `iso_read`; openusb
  `bulk_read`, `intr_read`; `IBackend.iso_read`; `do_trace`.
- #2209 `1132:47 self._ctx.backend.detach_kernel_driver(...)`:
  libusb0 `_LibUSB.detach_kernel_driver`, libusb1
  `_LibUSB.detach_kernel_driver`, `usb.backend.IBackend.detach_kernel_driver`
  (openusb inherits it), `do_trace`; reject `Device.detach_kernel_driver`.
- #2230 `1168:29 ValueError(...)`: `<builtin>.ValueError`.
- #2239 `1182:30 str(self.bcdUSB & 0xf)`: `<builtin>.str`; reject the nine
  (an int).
- #2245 `1191:53 len(headstr)`: `<builtin>.len`.
- #2248 `1194:28 op "..." % (...)`: none; reject the nine: the `%s`
  operand is the str from `_try_lookup`.
- #2259 `1202:24 _try_lookup(...)`: `usb.core._try_lookup`.
- #2303 value `1307:68 custom_match(d)`: no callee (client callback:
  documented lambdas and the client class `find_class`).
- #2305 `1316:36 m.get_backend()`: `usb.backend.libusb1.get_backend`,
  `usb.backend.openusb.get_backend`, `usb.backend.libusb0.get_backend`.
- #2325 `1345:33 op "%s\n\n" % str(device)`: none; reject the nine (a str).

### usb/legacy.py

- #2330 `107:28 getattr ep.bInterval`: none; R(gattr) (`ep` is a
  `core.Endpoint`).
- #2341 `120:35 Endpoint(e)`: `usb.legacy.Endpoint.__init__`; reject
  `usb.core.Endpoint.__init__`.
- #2366 `160:30 self.dev.write(...)`: `usb.core.Device.write`; reject
  `usb.core.Endpoint.write` (`self.dev` is the `core.Device` that
  `legacy.Device.open` passes).
- #2396 `263:22`, #2415 `310:22 isinstance(...)`: `<builtin>.isinstance`.
- #2405 `277:42 self.dev.set_interface_altsetting(...)`:
  `usb.core.Device.set_interface_altsetting`; reject the four backend
  methods.
- #2407 `289:21 getattr util.get_string`: none; R(gattr).
- #2438 `334:30 str(...)`: `<builtin>.str`; reject the nine (int).
- #2453 `354:37 getitem self.devices[0]`: none; reject the five (a list).

### usb/libloader.py

- #2478 `95:54 platform.machine()`: `platform.machine`.
- #2483 value `104:31 find_library(candidate)`: `ctypes.util.find_library`
  (the default, and the package's `None` from every `get_backend`); a
  client's function is opaque.
- #2487 value `131:27 lib_cls(lib)`: `ctypes.WinDLL` (libusb1 passes
  `win_cls=WinDLL` on win32, `libusb1.py:282-291`); other classes are a
  client's.
- #2499 `182:29 locate_library(...)`: `usb.libloader.locate_library`.

### usb/util.py

- #2526 value `181:68 custom_match(d)`: no callee (client callback; the
  package never passes one).
- #2534 `203:40 device._ctx.managed_claim_interface(...)`:
  `usb.core.synchronized.wrapper`; reject
  `_ResourceManager.managed_claim_interface` (called by the wrapper).
- #2542 `278:11 len(buf)`, #2555 `308:20 len(langids)`: `<builtin>.len`.
- #2544 `278:41 getitem buf[0]`: none; reject the five (an
  `array.array`).
