Cooperative multiple inheritance in a diamond. The MRO of `Both` is
`Both, Left, Right, Root`, so `super()` in `Left` reaches `Right`, not `Root`.
The edge `main.Left.setup -> main.Root.setup` must not appear.
