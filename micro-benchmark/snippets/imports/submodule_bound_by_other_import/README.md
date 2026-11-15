`main` imports only the package `pkg`. The module `loader` imports `pkg.extra`, which binds the submodule as the attribute `extra` of the package, so `pkg.extra.run()` in `main` works.
