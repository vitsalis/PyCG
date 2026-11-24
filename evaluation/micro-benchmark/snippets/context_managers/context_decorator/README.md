A context manager that subclasses `contextlib.ContextDecorator` is used as a
decorator. Decorating calls the inherited `ContextDecorator.__call__`; calling
the decorated name runs the library wrapper, which enters the manager, calls
the function, and exits the manager.
