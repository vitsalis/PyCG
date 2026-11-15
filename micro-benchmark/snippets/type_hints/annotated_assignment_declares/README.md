An annotated assignment to an attribute (`self.parsers: list[Parser] = ...`)
declares what the attribute holds. The value comes from
`pickle.loads`, so data flow inside the snippet does not give the elements of
the list: the annotation does.
