A non-data descriptor (only `__get__`) stores its result in the instance
dictionary. An instance attribute takes precedence over a non-data descriptor,
so the second read does not call `__get__`: the edge
`main.second_read -> main.Lazy.__get__` must not appear.
