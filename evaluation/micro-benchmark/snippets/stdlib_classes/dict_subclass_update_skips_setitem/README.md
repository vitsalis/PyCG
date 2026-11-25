A `dict` subclass overrides `__setitem__`. Subscript assignment calls it, but
the C implementation of `dict.update` does not, so the edge
`main.bulk -> main.Tracked.__setitem__` must not appear.
