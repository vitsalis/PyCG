The `main` module imports the `nested.to_import` module which in turn imports `nested.to_import2` via a relative path.
We define functions accordingly with `test_chained_import`. The import is of the form `from . import to_import`.
