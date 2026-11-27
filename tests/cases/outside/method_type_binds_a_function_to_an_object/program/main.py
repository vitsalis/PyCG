
import types
def samples(self):
    return self.items
class Metric:
    def __init__(self):
        self.items = []
        self.get = types.MethodType(samples, self)
    def collect(self):
        self.get().append(1)
