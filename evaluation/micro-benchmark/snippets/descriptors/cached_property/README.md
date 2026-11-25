`functools.cached_property` calls the decorated method on the first read and
stores the result on the instance. The library calls the method, so the edge
belongs to the scope that reads the attribute.
