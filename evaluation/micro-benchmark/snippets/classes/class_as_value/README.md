A class is a value: it is assigned to a variable, passed to a function, and
instantiated there. `kind` refers to `Dog` only after the call, so the edge
`main.build -> main.Dog.__init__` must not appear.
