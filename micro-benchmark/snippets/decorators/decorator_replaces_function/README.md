A decorator returns an unrelated function and drops the decorated one. The
call runs the replacement, so the edge `main -> main.expensive` must not
appear.
