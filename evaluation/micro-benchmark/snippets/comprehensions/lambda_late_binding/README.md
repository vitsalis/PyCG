A list comprehension creates lambdas that capture the comprehension variable. Lambdas in a comprehension are numbered in the enclosing scope, so all of them are `main.<lambda1>`. The variable holds the last function when the first lambda runs.
Precision: there is no edge `main.<lambda1> -> main.func1`.
