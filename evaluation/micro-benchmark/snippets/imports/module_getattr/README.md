The module `api` defines a module-level `__getattr__` (PEP 562). `api.fetch` is not defined, so the attribute access calls `api.__getattr__`, which returns `api._fetch`.
