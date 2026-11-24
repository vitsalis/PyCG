The value of a `type` statement (PEP 695) is evaluated lazily, on the first
access to `__value__`. Nothing reads it, so the edge
`main -> main.make_handler_type` must not appear. The alias is not a node.
