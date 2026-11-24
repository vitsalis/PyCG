`lazy import` (PEP 810, Python 3.15) loads a module when its name is first used. `report` is used and runs; `audit` is never used, so it never runs and is not a node.
There is no edge to `audit.record`.
