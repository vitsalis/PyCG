`__getattribute__` runs for every attribute read on an instance, also for
methods. It delegates to `object.__getattribute__`.
