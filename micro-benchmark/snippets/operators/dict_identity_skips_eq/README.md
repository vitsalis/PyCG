A dictionary lookup compares keys by identity before it calls `__eq__`. The
same object is stored and looked up, so the edge `main -> main.Key.__eq__`
must not appear.
