`lazy from helpers import compute` (PEP 810, Python 3.15) loads `helpers` when `run` first uses `compute`. The top-level call of `helpers` is still an edge of the module `helpers`.
There is no edge from `main.run` to `helpers.init`.
