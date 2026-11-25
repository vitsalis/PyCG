`repr()` and `str()` of a tuple, a dict and a list call `repr()` of their
elements, also of the keys of a dict and of the elements of a nested list.
`main.Validator.__str__` is never called: a container converts its elements
with `repr()`, also in `str()`.
