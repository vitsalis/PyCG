A call that cannot bind its arguments raises `TypeError` before the callee
starts. `Named()` misses the required argument `name`, so the edge
`main.make -> main.Named.__init__` must not appear.
