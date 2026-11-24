`sys.stdout` and `sys.stderr` are `io.TextIOWrapper` objects: a write to one, directly or through a parameter whose default is the stream, calls `io.TextIOWrapper.write`.
