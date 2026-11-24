A dictionary calls `__hash__` of every key it stores or looks up. It calls
`__eq__` when a stored key has the same hash but is another object.
