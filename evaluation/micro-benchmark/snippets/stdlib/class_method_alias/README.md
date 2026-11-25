The module `tarfile` binds `open = TarFile.open`, a class method, so
`tarfile.open(...)` is `TarFile.open` bound to `TarFile` and returns a
`TarFile`, whose `close` the snippet calls.
