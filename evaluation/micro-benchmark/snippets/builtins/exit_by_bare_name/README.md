`exit` is not a function: `site` binds it in `builtins` to an instance of
`_sitebuiltins.Quitter`, so the bare call `exit(code)` calls
`Quitter.__call__`, as `builtins.exit(code)` does.
