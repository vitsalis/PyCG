`super(Middle, obj)` accepts only a receiver that is an instance of
`Middle` or of a subclass. For a `Child` it finds `Base.run`; for an
`Other` it raises `TypeError` before any lookup, so neither
`main.Other.run` nor `main.Middle.run` is called.
