A `collections.defaultdict` calls its factory, a lambda, for a missing key; the lambda returns the function that the caller calls. The factory call belongs to `main`, which reads the key.
