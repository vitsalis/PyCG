`property.__set__` returns None whatever the setter returns: the result is not
callable, and the function that the setter returns is never called.
