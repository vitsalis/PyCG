An external call is guarded by `except ext.Timeout`. The stub of the missing module `ext` never raises, so the handler does not run.
There is no edge to `main.recover`.
