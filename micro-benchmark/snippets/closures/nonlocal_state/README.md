Two closures share state through `nonlocal`: one replaces the stored function, the other calls it. The module calls the replacing closure first.
Precision: there is no edge `main.make.call -> main.func1`.
