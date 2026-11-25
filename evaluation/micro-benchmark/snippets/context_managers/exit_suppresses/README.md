`__exit__` returns `True` and so suppresses the exception that the body raises.
The rest of the body does not run, so the edge `main -> main.never` must not
appear.
