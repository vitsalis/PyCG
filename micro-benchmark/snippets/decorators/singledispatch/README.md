`functools.singledispatch` selects an implementation by the type of the first
argument. Implementations are registered with the `register` decorator. No
`str` is passed, so the edge `main -> main.describe_str` must not appear.
