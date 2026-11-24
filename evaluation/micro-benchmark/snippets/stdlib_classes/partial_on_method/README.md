`functools.partial` binds the first argument of a bound method. Calling the
partial object calls `functools.partial.__call__`, which calls the method.
