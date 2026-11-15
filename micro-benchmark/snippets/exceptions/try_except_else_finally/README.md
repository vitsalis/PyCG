Two `try` statements with calls in every clause. `else` runs only without an
exception and `except` only with one, so the edges `main -> main.after_risky`
and `main -> main.on_safe_error` must not appear.
