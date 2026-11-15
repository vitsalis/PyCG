An exception in the body of the `with` statement is thrown into the generator
at the `yield`, where a handler catches it and suppresses it. The rest of the
body does not run, so the edge `main -> main.never` must not appear.
