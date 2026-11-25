The wrapper of a decorator is itself decorated with `functools.wraps(func)`.
`wraps` returns a `functools.partial` object, and applying it to the wrapper
calls that object.
