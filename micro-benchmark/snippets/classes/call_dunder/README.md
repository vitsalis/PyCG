Calling an instance runs `__call__` of its class. Both classes define
`__call__`, but only the `Adder` instance is called: the edge
`main.apply -> main.Doubler.__call__` must not appear.
