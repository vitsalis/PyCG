An operator, a subscript, a slice, an iteration or an f-string on a str
constant gives a str, whose methods are called: `("ab" * count).upper()`,
`"abc"[0].isalpha()`, `f"{a}.{b}".rstrip("0")`.
