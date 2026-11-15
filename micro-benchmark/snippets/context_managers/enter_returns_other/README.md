The `as` target is the return value of `__enter__`, not the manager. Here it is
a `Connection`, so the edge `main -> main.Pool.execute` must not appear.
