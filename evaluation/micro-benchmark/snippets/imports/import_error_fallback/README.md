The first import fails because the module `accel.native` does not exist, and the `except ImportError` branch imports `compute` from `accel.pure`.
There is no edge to `accel.native.compute`.
