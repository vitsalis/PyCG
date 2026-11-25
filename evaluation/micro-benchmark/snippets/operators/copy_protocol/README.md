`copy.copy` calls `__copy__` and `copy.deepcopy` calls `__deepcopy__`. Library
code makes these calls, so they belong to the scope that calls `copy`.
