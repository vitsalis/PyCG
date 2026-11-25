`functools.cache` wraps a function in a C-implemented cache object. Calling the
decorated name calls that object, which calls the function on the first call
only.
