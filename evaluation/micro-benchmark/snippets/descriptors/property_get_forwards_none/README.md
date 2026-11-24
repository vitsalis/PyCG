A subclass `__get__` forwards its arguments to `property.__get__`: a load
through the class passes None as the instance, so the builtin gives the
property and the getter does not run.
