An alternative constructor, a `@classmethod` that returns `cls(1)`, is called on
a subclass. `cls` is `Square`, so the edge `main.Shape.unit -> main.Shape.__init__`
must not appear.
