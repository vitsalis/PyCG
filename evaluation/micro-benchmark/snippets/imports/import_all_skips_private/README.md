`from tools import *` without `__all__` skips names that start with an underscore, so it does not replace the `_reset` of `main`.
There is no edge to `tools._reset`.
