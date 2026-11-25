A store through a property calls its setter and never writes the instance
dictionary, so the stored `Pairs` does not reach the load: the load calls the
getter, which returns the `Rows`, and only `main.Rows.index` is called.
