Builtins and unpacking that ask the length of what they iterate, before they
iterate it: `sorted`, the unpacking in a list or tuple display, a call that
unpacks an argument after a positional one, `bytes`, `bytearray.extend` and
`+=` on a list call `__len__`, else `__length_hint__`. They do so on every
supported Python version. `tuple(x)` and a call `f(*x)` with one unpacked
argument alone ask only on Python 3.12 and 3.13; they are not in this case.
