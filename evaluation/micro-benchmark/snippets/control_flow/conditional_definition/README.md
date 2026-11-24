A function is defined in both branches of an `if` statement; only the definition in the branch that runs exists. Both definitions share the node `main.handler`. The call `func2()` never runs.
Precision: there is no edge `main.handler -> main.func2`.
