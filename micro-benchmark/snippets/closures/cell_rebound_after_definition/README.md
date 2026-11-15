The enclosing function rebinds a captured variable after it defines the nested function. The nested function reads the variable when it runs, so it sees the new value.
Precision: there is no edge `main.outer.inner -> main.func1`.
