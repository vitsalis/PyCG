A snippet class and the builtin `list` both have a method `append`. Each function calls only one of them.
There is no edge from `main.use_list` to `main.Stack.append`, and none from `main.use_stack` to `<builtin>.list.append`.
