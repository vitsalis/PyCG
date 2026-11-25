`+=` calls `__iadd__` if the class defines it and falls back to `__add__`
otherwise. `Buffer` defines `__iadd__`, so the edge
`main -> main.Buffer.__add__` must not appear.
