`import shop.pricing as pricing` binds `pricing` to the submodule, not to the package, and `pricing.total()` is called.
There is no edge to `shop.total`, which the package `__init__.py` also defines.
