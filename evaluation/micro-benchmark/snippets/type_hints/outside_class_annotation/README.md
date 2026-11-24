A parameter is annotated with a class of the standard library
(`collections.abc.Iterator`). It receives an instance of a snippet class that
derives from that class. The argument comes back from a `pickle` round trip,
so data flow inside the snippet does not give its type: the annotation and the
class hierarchy do. `Ticker` has the methods of an iterator but does not derive
from `Iterator`, and no code passes one to `drain`: the edge
`main.drain -> main.Ticker.__next__` must not appear.
