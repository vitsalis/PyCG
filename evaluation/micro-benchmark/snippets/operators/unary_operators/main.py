class Signal:
    def __neg__(self):
        return self

    def __pos__(self):
        return self

    def __invert__(self):
        return self

    def __abs__(self):
        return self


s = Signal()
-s
+s
~s
abs(s)
