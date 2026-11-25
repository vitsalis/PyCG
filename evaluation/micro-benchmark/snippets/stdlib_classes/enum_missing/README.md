Calling an enum class looks a member up by value; for an unknown value the
library calls `_missing_`. The value `"active"` exists, so the edge
`main.parse_known -> main.Status._missing_` must not appear.
