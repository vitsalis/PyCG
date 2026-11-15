The first `except` clause that matches the exception class runs. A `KeyError`
also matches `LookupError`, but the earlier `KeyError` clause wins: the edges
`main -> main.on_value_error` and `main -> main.on_lookup_error` must not
appear.
