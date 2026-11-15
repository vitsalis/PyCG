Without `__contains__`, `in` iterates over the right operand, so it calls
`__iter__`.
