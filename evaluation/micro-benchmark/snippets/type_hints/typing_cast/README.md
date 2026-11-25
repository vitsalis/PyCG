`typing.cast` returns its argument unchanged. The cast names `Base`, but the
object is an `Impl`, so the edge `main.execute -> main.Base.run` must not
appear.
