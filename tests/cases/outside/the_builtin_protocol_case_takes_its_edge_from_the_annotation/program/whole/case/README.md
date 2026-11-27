A parameter is annotated with `typing.Iterable`, a protocol that the builtin
types implement. It receives an instance of a snippet class that derives from
`collections.abc.Sequence`, an abstract class whose protocols include
`Iterable`. The argument comes back from a `pickle` round trip, so data flow
inside the snippet does not give its type: the annotation and the class
hierarchy do. `Names` derives from `list`, a concrete builtin, and no code
passes one to `drain`: the edge `main.drain -> main.Names.__iter__` must not
appear, and `Names.__iter__` never runs.
