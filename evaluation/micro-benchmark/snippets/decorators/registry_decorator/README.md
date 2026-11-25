A decorator stores functions in a dictionary by key, and a dispatcher calls the
entry for one key. Only `"open"` is dispatched, so the edge
`main.dispatch -> main.on_close` must not appear.
