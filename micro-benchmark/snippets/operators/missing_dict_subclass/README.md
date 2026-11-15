Subscription of a `dict` subclass calls `__missing__` for an absent key.
`dict.get` does not, so the edge `main.safe_lookup -> main.Defaults.__missing__`
must not appear.
