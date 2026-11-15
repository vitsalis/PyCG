`enum.member` makes functions enum members instead of methods, and a method
calls the function stored in `self.value`. Only `ADD` is applied, so the edge
`main.Operation.apply -> main.subtract` must not appear.
