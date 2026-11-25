A mapping pattern on a `collections.abc.Mapping` subclass calls its `__len__` and, through the inherited `Mapping.get`, its `__getitem__` (implicit calls from `main`). It does not call `__iter__`.
Precision: there is no edge `main -> main.Config.__iter__`.
