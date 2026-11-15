A condition calls `__bool__`, or `__len__` if the class has no `__bool__`.
`Flag` defines both, so the edge `main -> main.Flag.__len__` must not appear.
