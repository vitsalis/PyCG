`dict.get` hashes the key and compares it with the stored key that has the same hash, another object: the stored key's `__eq__` runs. The calls belong to `main`, which calls `get`.
