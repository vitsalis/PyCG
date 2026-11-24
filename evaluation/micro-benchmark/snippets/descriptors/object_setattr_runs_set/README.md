`object.__setattr__(self, "value", value)` is Python's own attribute store. It
looks `value` up on the class, finds a data descriptor and calls its
`__set__`, as `self.value = value` would.
