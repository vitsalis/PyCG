The target of `super()` depends on the MRO of the receiver. For a `Left`
instance it is `Root`; only a `Both` instance would reach `Right`. No `Both` is
created, so the edge `main.Left.setup -> main.Right.setup` must not appear.
