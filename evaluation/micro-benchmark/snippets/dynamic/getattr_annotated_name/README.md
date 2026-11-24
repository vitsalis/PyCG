`getattr` with a parameter annotated as `str` whose default is a constant
string fetches a method, which is then called. The call omits the argument,
so the name is the default. There is no edge to `main.Service.stop`.
