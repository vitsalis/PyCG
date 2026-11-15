The imported modules call functions at their top level. Those calls are edges of the imported modules, not of `main`: there is no edge from `main` to `pkg.setup` or `pkg.sub.register`.
