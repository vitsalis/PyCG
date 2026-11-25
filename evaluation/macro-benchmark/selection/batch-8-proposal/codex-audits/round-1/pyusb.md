Package: **pyusb**. Codex audit round: **1**.

Found **6 missing edges** and **3 unsure edges**. No false or naming
findings.

Read all 301 functions, including five lambdas, and all 14 module bodies.
Checked all 923 existing graph edges: 899 function edges and 24 module
edges. The permitted checker report found zero undecided sites and zero
unaccounted trace edges. No package code was run or imported.

**1. Coverage**

Counts below are unique outgoing edges in the existing graph, before
applying findings. Function names are relative to the stated module.

| Module | Functions read | Function edges | Module-body edges |
|---|---:|---:|---:|
| `usb` | 3 | 15 | 2 |
| `usb._debug` | 8 | 80 | 0 |
| `usb._interop` | 1 | 4 | 0 |
| `usb._lookup` | 0 | 0 | 0 |
| `usb._objfinalizer` | 8 | 24 | 0 |
| `usb.backend` | 26 | 26 | 0 |
| `usb.backend.libusb0` | 33 | 91 | 6 |
| `usb.backend.libusb1` | 54 | 155 | 6 |
| `usb.backend.openusb` | 32 | 124 | 5 |
| `usb.control` | 10 | 22 | 0 |
| `usb.core` | 81 | 278 | 4 |
| `usb.legacy` | 28 | 45 | 0 |
| `usb.libloader` | 3 | 12 | 1 |
| `usb.util` | 14 | 23 | 0 |
| **Total** | **301** | **899** | **24** |

`usb`

| Function read | Edges checked |
|---|---:|
| `_get_extended_version_info` | 3 |
| `_setup_log` | 12 |
| `_setup_log.NullHandler.emit` | 0 |

`usb._debug`

| Function read | Edges checked |
|---|---:|
| `_trace_function_call` | 4 |
| `enable_tracing` | 0 |
| `functiontrace` | 0 |
| `functiontrace.decorator_logging` | 1 |
| `functiontrace.decorator_logging.do_trace` | 1 |
| `methodtrace` | 0 |
| `methodtrace.decorator_logging` | 1 |
| `methodtrace.decorator_logging.do_trace` | 73 |

`usb._interop`

| Function read | Edges checked |
|---|---:|
| `as_array` | 4 |

`usb._lookup` contains no functions; its module body was read.

`usb._objfinalizer`

| Function read | Edges checked |
|---|---:|
| `AutoFinalizedObject.__new__` | 4 |
| `AutoFinalizedObject.finalize` | 2 |
| `_AutoFinalizedObjectBase.__del__` | 1 |
| `_AutoFinalizedObjectBase.__new__` | 2 |
| `_AutoFinalizedObjectBase._do_finalize_object` | 12 |
| `_AutoFinalizedObjectBase._finalize_object` | 0 |
| `_AutoFinalizedObjectBase.finalize` | 1 |
| `_do_finalize_object_ref` | 2 |

`usb.backend`

| Function read | Edges checked |
|---|---:|
| `IBackend.attach_kernel_driver` | 1 |
| `IBackend.bulk_read` | 1 |
| `IBackend.bulk_write` | 1 |
| `IBackend.claim_interface` | 1 |
| `IBackend.clear_halt` | 1 |
| `IBackend.close_device` | 1 |
| `IBackend.ctrl_transfer` | 1 |
| `IBackend.detach_kernel_driver` | 1 |
| `IBackend.enumerate_devices` | 1 |
| `IBackend.get_configuration` | 1 |
| `IBackend.get_configuration_descriptor` | 1 |
| `IBackend.get_device_descriptor` | 1 |
| `IBackend.get_endpoint_descriptor` | 1 |
| `IBackend.get_interface_descriptor` | 1 |
| `IBackend.get_parent` | 1 |
| `IBackend.intr_read` | 1 |
| `IBackend.intr_write` | 1 |
| `IBackend.is_kernel_driver_active` | 1 |
| `IBackend.iso_read` | 1 |
| `IBackend.iso_write` | 1 |
| `IBackend.open_device` | 1 |
| `IBackend.release_interface` | 1 |
| `IBackend.reset_device` | 1 |
| `IBackend.set_configuration` | 1 |
| `IBackend.set_interface_altsetting` | 1 |
| `_not_implemented` | 1 |

`usb.backend.libusb0`

| Function read | Edges checked |
|---|---:|
| `_DeviceDescriptor.__init__` | 0 |
| `_LibUSB.__get_driver_name` | 7 |
| `_LibUSB.__iso_transfer` | 6 |
| `_LibUSB.__read` | 5 |
| `_LibUSB.__write` | 5 |
| `_LibUSB.bulk_read` | 1 |
| `_LibUSB.bulk_write` | 1 |
| `_LibUSB.claim_interface` | 2 |
| `_LibUSB.clear_halt` | 2 |
| `_LibUSB.close_device` | 2 |
| `_LibUSB.ctrl_transfer` | 4 |
| `_LibUSB.detach_kernel_driver` | 4 |
| `_LibUSB.enumerate_devices` | 3 |
| `_LibUSB.get_configuration` | 4 |
| `_LibUSB.get_configuration_descriptor` | 2 |
| `_LibUSB.get_device_descriptor` | 1 |
| `_LibUSB.get_endpoint_descriptor` | 4 |
| `_LibUSB.get_interface_descriptor` | 4 |
| `_LibUSB.intr_read` | 1 |
| `_LibUSB.intr_write` | 1 |
| `_LibUSB.is_kernel_driver_active` | 3 |
| `_LibUSB.iso_read` | 3 |
| `_LibUSB.iso_write` | 3 |
| `_LibUSB.open_device` | 2 |
| `_LibUSB.release_interface` | 2 |
| `_LibUSB.reset_device` | 2 |
| `_LibUSB.set_configuration` | 2 |
| `_LibUSB.set_interface_altsetting` | 2 |
| `_check` | 4 |
| `_has_iso_transfer` | 1 |
| `_load_library` | 1 |
| `_setup_prototypes` | 2 |
| `get_backend` | 5 |

`usb.backend.libusb1`

| Function read | Edges checked |
|---|---:|
| `_strerror` | 2 |
| `_get_iso_packet_list` | 3 |
| `_load_library` | 1 |
| `_setup_prototypes` | 2 |
| `_setup_prototypes.libusb_set_iso_packet_lengths` | 1 |
| `_setup_prototypes.libusb_fill_iso_transfer` | 1 |
| `_check` | 4 |
| `_Device.__init__` | 1 |
| `_Device._finalize_object` | 2 |
| `_WrapDescriptor.__init__` | 0 |
| `_WrapDescriptor.__getattr__` | 1 |
| `_ConfigDescriptor.__init__` | 0 |
| `_ConfigDescriptor._finalize_object` | 2 |
| `_ConfigDescriptor.__getattr__` | 1 |
| `_DevIterator.__init__` | 5 |
| `_DevIterator.__iter__` | 3 |
| `_DevIterator._finalize_object` | 2 |
| `_DeviceHandle.__init__` | 4 |
| `_IsoTransferHandler.__init__` | 10 |
| `_IsoTransferHandler._finalize_object` | 2 |
| `_IsoTransferHandler.submit` | 6 |
| `_IsoTransferHandler.__compute_size_transf_data` | 2 |
| `_IsoTransferHandler.__set_packets_length` | 3 |
| `_IsoTransferHandler.__callback` | 0 |
| `_LibUSB.__init__` | 5 |
| `_LibUSB._finalize_object` | 2 |
| `_LibUSB.enumerate_devices` | 2 |
| `_LibUSB.get_parent` | 3 |
| `_LibUSB.get_device_descriptor` | 6 |
| `_LibUSB.get_configuration_descriptor` | 7 |
| `_LibUSB.get_interface_descriptor` | 6 |
| `_LibUSB.get_endpoint_descriptor` | 6 |
| `_LibUSB.open_device` | 1 |
| `_LibUSB.close_device` | 1 |
| `_LibUSB.set_configuration` | 2 |
| `_LibUSB.get_configuration` | 4 |
| `_LibUSB.set_interface_altsetting` | 2 |
| `_LibUSB.claim_interface` | 2 |
| `_LibUSB.release_interface` | 2 |
| `_LibUSB.bulk_write` | 1 |
| `_LibUSB.bulk_read` | 1 |
| `_LibUSB.intr_write` | 1 |
| `_LibUSB.intr_read` | 1 |
| `_LibUSB.iso_write` | 3 |
| `_LibUSB.iso_read` | 3 |
| `_LibUSB.ctrl_transfer` | 5 |
| `_LibUSB.clear_halt` | 2 |
| `_LibUSB.reset_device` | 2 |
| `_LibUSB.is_kernel_driver_active` | 3 |
| `_LibUSB.detach_kernel_driver` | 2 |
| `_LibUSB.attach_kernel_driver` | 2 |
| `_LibUSB.__write` | 7 |
| `_LibUSB.__read` | 7 |
| `get_backend` | 6 |

`usb.backend.openusb`

| Function read | Edges checked |
|---|---:|
| `_BusIterator.__init__` | 6 |
| `_BusIterator.__iter__` | 1 |
| `_BusIterator._finalize_object` | 2 |
| `_Context.__init__` | 4 |
| `_Context._finalize_object` | 2 |
| `_DevIterator.__init__` | 6 |
| `_DevIterator.__iter__` | 1 |
| `_DevIterator._finalize_object` | 2 |
| `_OpenUSB.bulk_read` | 9 |
| `_OpenUSB.bulk_write` | 9 |
| `_OpenUSB.claim_interface` | 2 |
| `_OpenUSB.clear_halt` | 4 |
| `_OpenUSB.close_device` | 1 |
| `_OpenUSB.ctrl_transfer` | 8 |
| `_OpenUSB.enumerate_devices` | 5 |
| `_OpenUSB.get_configuration` | 4 |
| `_OpenUSB.get_configuration_descriptor` | 4 |
| `_OpenUSB.get_device_descriptor` | 4 |
| `_OpenUSB.get_endpoint_descriptor` | 4 |
| `_OpenUSB.get_interface_descriptor` | 4 |
| `_OpenUSB.intr_read` | 9 |
| `_OpenUSB.intr_write` | 9 |
| `_OpenUSB.open_device` | 4 |
| `_OpenUSB.release_interface` | 1 |
| `_OpenUSB.reset_device` | 2 |
| `_OpenUSB.set_configuration` | 2 |
| `_OpenUSB.set_interface_altsetting` | 2 |
| `_check` | 3 |
| `_load_library` | 1 |
| `_openusb_ctrl_request.__init__` | 2 |
| `_setup_prototypes` | 1 |
| `get_backend` | 6 |

`usb.control`

| Function read | Edges checked |
|---|---:|
| `_parse_recipient` | 3 |
| `clear_feature` | 3 |
| `get_configuration` | 2 |
| `get_descriptor` | 4 |
| `get_interface` | 2 |
| `get_status` | 2 |
| `set_configuration` | 1 |
| `set_descriptor` | 2 |
| `set_feature` | 2 |
| `set_interface` | 1 |

`usb.core`

| Function read | Edges checked |
|---|---:|
| `Configuration.__getitem__` | 1 |
| `Configuration.__init__` | 5 |
| `Configuration.__iter__` | 2 |
| `Configuration.__repr__` | 1 |
| `Configuration.__str__` | 4 |
| `Configuration._get_full_descriptor_str` | 5 |
| `Configuration._get_power_multiplier` | 0 |
| `Configuration._str` | 1 |
| `Configuration.interfaces` | 2 |
| `Configuration.set` | 1 |
| `Device.__eq__` | 2 |
| `Device.__get_def_tmo` | 0 |
| `Device.__get_timeout` | 0 |
| `Device.__getitem__` | 1 |
| `Device.__hash__` | 2 |
| `Device.__init__` | 8 |
| `Device.__iter__` | 2 |
| `Device.__repr__` | 1 |
| `Device.__set_def_tmo` | 1 |
| `Device.__str__` | 5 |
| `Device._finalize_object` | 2 |
| `Device._get_full_descriptor_str` | 5 |
| `Device._str` | 0 |
| `Device.attach_kernel_driver` | 4 |
| `Device.backend` | 0 |
| `Device.clear_halt` | 6 |
| `Device.configurations` | 2 |
| `Device.ctrl_transfer` | 10 |
| `Device.detach_kernel_driver` | 5 |
| `Device.get_active_configuration` | 1 |
| `Device.is_kernel_driver_active` | 5 |
| `Device.langids` | 1 |
| `Device.manufacturer` | 1 |
| `Device.parent` | 5 |
| `Device.product` | 1 |
| `Device.read` | 16 |
| `Device.reset` | 5 |
| `Device.serial_number` | 1 |
| `Device.set_configuration` | 1 |
| `Device.set_interface_altsetting` | 1 |
| `Device.write` | 14 |
| `Endpoint.__init__` | 5 |
| `Endpoint.__repr__` | 1 |
| `Endpoint.__str__` | 4 |
| `Endpoint._str` | 1 |
| `Endpoint.clear_halt` | 1 |
| `Endpoint.read` | 1 |
| `Endpoint.write` | 1 |
| `Interface.__getitem__` | 1 |
| `Interface.__init__` | 5 |
| `Interface.__iter__` | 2 |
| `Interface.__repr__` | 1 |
| `Interface.__str__` | 4 |
| `Interface._get_full_descriptor_str` | 4 |
| `Interface._str` | 1 |
| `Interface.endpoints` | 2 |
| `Interface.set_altsetting` | 1 |
| `USBError.__init__` | 1 |
| `_DescriptorInfo.__repr__` | 0 |
| `_ResourceManager.__init__` | 2 |
| `_ResourceManager.dispose` | 2 |
| `_ResourceManager.get_active_configuration` | 8 |
| `_ResourceManager.get_interface_and_endpoint` | 6 |
| `_ResourceManager.managed_claim_interface` | 7 |
| `_ResourceManager.managed_close` | 4 |
| `_ResourceManager.managed_open` | 4 |
| `_ResourceManager.managed_release_interface` | 8 |
| `_ResourceManager.managed_set_configuration` | 12 |
| `_ResourceManager.managed_set_configuration.MockConfiguration.__init__` | 0 |
| `_ResourceManager.managed_set_interface` | 11 |
| `_ResourceManager.release_all_interfaces` | 2 |
| `_ResourceManager.setup_request` | 2 |
| `_set_attr` | 4 |
| `_try_get_string` | 1 |
| `_try_getattr` | 1 |
| `_try_lookup` | 0 |
| `find` | 7 |
| `find.device_iter` | 11 |
| `show_devices` | 5 |
| `synchronized` | 2 |
| `synchronized.wrapper` | 13 |

`usb.legacy`

| Function read | Edges checked |
|---|---:|
| `Bus.__init__` | 2 |
| `Configuration.__init__` | 7 |
| `Configuration.__init__.<lambda1>` | 0 |
| `Configuration.__init__.<lambda2>` | 0 |
| `Device.__init__` | 3 |
| `Device.open` | 2 |
| `DeviceHandle.__init__` | 0 |
| `DeviceHandle._finalize_object` | 2 |
| `DeviceHandle.bulkRead` | 1 |
| `DeviceHandle.bulkWrite` | 1 |
| `DeviceHandle.claimInterface` | 2 |
| `DeviceHandle.clearHalt` | 1 |
| `DeviceHandle.controlMsg` | 1 |
| `DeviceHandle.detachKernelDriver` | 2 |
| `DeviceHandle.getDescriptor` | 1 |
| `DeviceHandle.getString` | 2 |
| `DeviceHandle.interruptRead` | 1 |
| `DeviceHandle.interruptWrite` | 1 |
| `DeviceHandle.releaseInterface` | 1 |
| `DeviceHandle.reset` | 1 |
| `DeviceHandle.resetEndpoint` | 1 |
| `DeviceHandle.setAltInterface` | 2 |
| `DeviceHandle.setConfiguration` | 2 |
| `Endpoint.__init__` | 1 |
| `Interface.__init__` | 2 |
| `busses` | 6 |
| `busses.<lambda1>` | 0 |
| `busses.<lambda2>` | 0 |

`usb.libloader`

| Function read | Edges checked |
|---|---:|
| `load_library` | 3 |
| `load_locate_library` | 6 |
| `locate_library` | 3 |

`usb.util`

| Function read | Edges checked |
|---|---:|
| `build_request_type` | 0 |
| `claim_interface` | 1 |
| `create_buffer` | 1 |
| `ctrl_direction` | 0 |
| `dispose_resources` | 1 |
| `endpoint_address` | 0 |
| `endpoint_direction` | 0 |
| `endpoint_type` | 0 |
| `find_descriptor` | 2 |
| `find_descriptor.desc_iter` | 6 |
| `get_langids` | 5 |
| `get_langids.<lambda1>` | 0 |
| `get_string` | 6 |
| `release_interface` | 1 |

**2. Findings**

Source locations are relative to `macro-benchmark/projects/pyusb/`.
Positions use the ledger’s one-based line and column convention.

Rule **L** means B5’s library-callback rule together with the
[batch-8 logger-configuration ruling](macro-benchmark/README.md:2973).
Rule **C** means B5 together with the
[batch-7 ctypes callback ruling](macro-benchmark/README.md:2785).

The common witness for M1–M6 leaves `PYUSB_DEBUG` unset. Package import
installs `NullHandler` at
[usb/__init__.py:94](macro-benchmark/projects/pyusb/usb/__init__.py:94).
The client then calls `logging.getLogger('usb').setLevel(logging.DEBUG)`
through logging’s public interface. Child loggers propagate their records
to this handler. In the supplied CPython 3.15.2 source,
`Lib/logging/__init__.py:1733–1754` dispatches to ancestor handlers, and
line 1030 calls `self.emit(record)`. This contradicts `pyusb.md` J7’s
exclusion of the configuration.

| Id | Kind | Caller | Site (file:line:col) | Edge | Evidence | Rule |
|---|---|---|---|---|---|---|
| M1 | missing | `usb.backend.libusb0.get_backend` | `usb/backend/libusb0.py:744:22`; `747:22` | `→ usb._setup_log.NullHandler.emit` | Both loading-error paths call `_logger.error`. With the common witness, these records reach the handler installed at `usb/__init__.py:103`. The graph lacks this pair. | L |
| M2 | missing | `usb.backend.libusb1.get_backend` | `usb/backend/libusb1.py:971:22`; `974:22` | `→ usb._setup_log.NullHandler.emit` | Both loading-error paths call `_logger.error`; the common witness permits propagation to the package handler. The graph lacks this pair. | L |
| M3 | missing | `usb.backend.openusb.get_backend` | `usb/backend/openusb.py:751:24`; `755:22`; `758:22` | `→ usb._setup_log.NullHandler.emit` | The successful-loading warning and both loading-error paths reach the package handler under the common witness. The graph lacks this pair. | L |
| M4 | missing | `usb.core.find` | `usb/core.py:1318:29` | `→ usb._setup_log.NullHandler.emit` | After a backend loads, `_logger.info` emits the selected-backend message. Lowering the `usb` logger admits this record and its callback. The graph lacks this pair. | L |
| M5 | missing | `usb.libloader.load_library` | `usb/libloader.py:144:22` | `→ usb._setup_log.NullHandler.emit` | A failed library load enters the exception handler and calls `_LOGGER.error`. Under the common witness, logging calls the package handler. The graph lacks this pair. | L |
| M6 | missing | `usb.libloader.load_locate_library` | `usb/libloader.py:184:26`; `190:26`; `203:26` | `→ usb._setup_log.NullHandler.emit` | The found-library debug record and the not-found/missing-symbol error records can reach the installed package handler. The graph lacks this pair. | L |
| U1 | unsure | `usb.backend.libusb1._LibUSB.__write` | `usb/backend/libusb1.py:934:20` | `→ usb.backend.libusb1._IsoTransferHandler.__callback` | `fn` receives `libusb_bulk_transfer` or `libusb_interrupt_transfer` at lines 841 and 859. The package registers its isochronous callback at 673 and submits it at 685. Native synchronous-transfer/event-loop source is needed to decide whether this call can dispatch that callback during an overlapping transfer on the same context. The graph lacks this pair. | C |
| U2 | unsure | `usb.backend.libusb1._LibUSB.__read` | `usb/backend/libusb1.py:950:20` | `→ usb.backend.libusb1._IsoTransferHandler.__callback` | `fn` receives `libusb_bulk_transfer` or `libusb_interrupt_transfer` at lines 850 and 868. Native source must establish whether its synchronous wait can dispatch the concurrently registered callback from line 673. The graph lacks this pair. | C |
| U3 | unsure | `usb.backend.libusb1._LibUSB.ctrl_transfer` | `usb/backend/libusb1.py:897:54` | `→ usb.backend.libusb1._IsoTransferHandler.__callback` | This site calls `libusb_control_transfer`. Native source must establish whether its synchronous wait dispatches a concurrent isochronous callback registered at line 673; the isochronous callers pass the backend context at lines 878 and 883. The graph lacks this pair. | C |

The supplied dependency sources contain no native libusb implementation
or API documentation that resolves U1–U3. They remain uncertainties,
rather than asserted missing edges.

`usb._debug._trace_function_call` adds no seventh logging finding: its
concrete package logger flows through tracing wrappers created with
`PYUSB_DEBUG` enabled, which selects a `FileHandler` or `StreamHandler`.
The opaque client-logger flow through `functiontrace` supplies no package
callback.

**3. Totals**

| Kind | Count |
|---|---:|
| missing | **6** |
| false | **0** |
| naming | **0** |
| ruling | **0** |
| unsure | **3** |

Counts are per caller–callee pair, not per site. None of these findings is
at an open path set or an open receiver set.