Dunder methods of a metaclass apply to its classes: `len(Colors)` calls
`Meta.__len__` and iterating over `Colors` calls `Meta.__iter__`.
