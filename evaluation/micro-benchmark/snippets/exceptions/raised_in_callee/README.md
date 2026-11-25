A callee raises and the caller handles the exception by calling a function. The
call after the `raise` is dead code, so the edge `main.check -> main.audit`
must not appear.
