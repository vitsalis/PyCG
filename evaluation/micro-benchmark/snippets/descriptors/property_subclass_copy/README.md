`a.getter(second)` gives a copy with the new getter; `a` keeps its own. A load
of `a` calls `first` only, a load of `b` calls `second` only.
