An `ExceptionGroup` is handled with `except*`. Every clause that matches part of
the group runs. The group has no `KeyError`, so the edge
`main -> main.on_key` must not appear.
