class Buffer:
    def __iadd__(self, other):
        return self

    def __add__(self, other):
        return self


class Counter:
    def __add__(self, other):
        return self


buffer = Buffer()
buffer += 1
counter = Counter()
counter += 1
