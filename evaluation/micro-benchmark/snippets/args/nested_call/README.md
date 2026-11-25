`main` calls `func` through the variable `c` and passes it `param_func` through
the variable `b`. `func` calls its parameter with the function `nested_func` as
the argument, and `param_func` calls its parameter. So the calls are
`main -> main.func -> main.param_func -> main.nested_func`. No function is
nested.
