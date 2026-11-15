A failing `assert` evaluates its message, so the function in the message runs.
The `assert` statement creates the `AssertionError` without a call expression,
so there is no edge to `<builtin>.AssertionError`.
