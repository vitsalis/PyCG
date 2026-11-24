A parameter is annotated with an abstract class of the standard library
(`collections.abc.Sequence`). It receives an instance of a snippet class that
derives from that class. The argument comes back from a `pickle` round trip,
so data flow inside the snippet does not give its type: the annotation and the
class hierarchy do. `Ticker` has the methods of a sequence but does not derive
from `Sequence`, and no code passes one to `first`: the edges
`main.first -> main.Ticker.__getitem__` and `main.first -> main.Ticker.__len__`
must not appear.
