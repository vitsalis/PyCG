An f-string formats an object that defines only `__str__`. The inherited `object.__format__` calls it; that builtin call is implicit, so it is not an edge.
