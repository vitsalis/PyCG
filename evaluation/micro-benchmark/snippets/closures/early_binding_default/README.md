Lambdas created in a loop bind the loop variable through a default value (`lambda f=f: f()`), so each lambda keeps the function of its iteration.
Precision: there is no edge `main.build.<lambda1> -> main.func2`.
