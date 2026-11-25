A generator expression is created in the module and iterated in another function. Its calls still belong to the module, where it is written.
Precision: there are no edges `main.consume -> main.func1` and `main.consume -> main.func2`.
