`main` imports `func` from `to_import` and calls it. `func` returns
`return_func`, which `to_import` imports from `to_import2`. `main` then calls
the returned function, so the edge is `main -> to_import2.return_func`.
