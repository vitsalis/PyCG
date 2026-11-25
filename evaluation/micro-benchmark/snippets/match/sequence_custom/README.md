A sequence pattern on a `collections.abc.Sequence` subclass calls its `__len__` and, through the inherited `Sequence.__iter__`, its `__getitem__` (implicit calls from `main`).
Precision: there is no edge `main -> main.func1`.
