An annotation contains a call. Python 3.14 evaluates it when
`__annotations__` is read (in `inspect_scale`); Python 3.12 and 3.13 when
`scale` is defined. An annotation scope is not a node, so in both cases the
call belongs to the scope that defines `scale`: the module.
