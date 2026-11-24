`typing.Annotated` stores functions as metadata of a type, and the program
reads them with `get_type_hints` and calls them. Only the checks of `price`
run, so the edge `main -> main.non_empty` must not appear.
