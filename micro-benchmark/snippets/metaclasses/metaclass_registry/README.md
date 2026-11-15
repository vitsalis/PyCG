A metaclass stores every class it creates in a dictionary by name. Only
`Alpha` is taken from the registry, so the edges `main -> main.Beta.run` and
`main -> main.Base.run` must not appear.
