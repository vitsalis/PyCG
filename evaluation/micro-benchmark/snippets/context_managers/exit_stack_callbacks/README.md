`contextlib.ExitStack` enters a manager and registers a callback. The library
calls `__enter__` at once and `__exit__` and the callback when the stack
closes. `close_socket` is never registered, so the edge
`main -> main.close_socket` must not appear.
