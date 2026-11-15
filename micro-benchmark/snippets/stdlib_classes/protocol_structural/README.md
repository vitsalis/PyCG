A `typing.Protocol` types a parameter structurally; the classes that match it
do not inherit from it. Only an `English` object is passed, so the edges
`main.welcome -> main.Greeter.greet` and `main.welcome -> main.French.greet`
must not appear.
