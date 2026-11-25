`super(dict, self)` starts the lookup after `dict` in the MRO of
`Results`, so `__init__` is that of `Mixin`.
