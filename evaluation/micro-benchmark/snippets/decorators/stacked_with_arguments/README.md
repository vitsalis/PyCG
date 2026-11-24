One decorator factory is applied twice with different arguments. The outer
wrapper calls the inner wrapper, which is the same function, so the wrapper
calls itself.
