`functools.lru_cache(16)` returns its decorator, which is applied with an
explicit call. The result is the cache object that wraps `square`, so calling
it calls `square`.
