The module `app.api.handlers` imports `save` from a sibling package with `from ..storage.disk import save` and calls it.
The top-level package `storage` has the same layout but is never imported: there is no edge to `storage.disk.save`.
