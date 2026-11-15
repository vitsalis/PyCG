`getattr` fetches a method whose name is an f-string converted by `lower()`:
`"visit_"` and the name of the node's class, lower-cased. The lower-cased
name is never `visit_Field`, so `main.Visitor.visit_Field` is never called.
