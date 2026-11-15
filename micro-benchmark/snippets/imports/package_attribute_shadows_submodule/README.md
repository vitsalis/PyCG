`pkg/__init__.py` binds the name `x`, and the package also has a submodule
`pkg/x.py`. `from pkg import x` reads the attribute `x` of the package, which
exists, so Python does not import `pkg/x.py`: its call never runs. `x()` calls
`pkg.hit`.
