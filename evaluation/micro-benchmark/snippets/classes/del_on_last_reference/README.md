`del` removes the last reference to an instance, so CPython calls `__del__`
at once, from the scope that runs the `del` statement.
