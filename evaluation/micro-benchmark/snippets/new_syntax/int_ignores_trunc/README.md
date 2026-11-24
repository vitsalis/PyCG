Since Python 3.14, `int()` no longer calls `__trunc__`, so `int(Measure())` raises `TypeError`. `math.trunc` still calls `__trunc__`.
The only edge to `main.Measure.__trunc__` comes from the call of `math.trunc`.
