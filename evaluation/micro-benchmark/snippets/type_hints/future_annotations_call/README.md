With `from __future__ import annotations`, annotations are stored as strings and
not evaluated. The calls in them never run, so the edge
`main -> main.make_type` must not appear.
