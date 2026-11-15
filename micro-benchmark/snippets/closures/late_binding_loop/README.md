Lambdas created in a loop capture the loop variable, not its value. When the first lambda runs, the variable holds the last function.
Precision: there is no edge `main.build.<lambda1> -> main.func1`.
