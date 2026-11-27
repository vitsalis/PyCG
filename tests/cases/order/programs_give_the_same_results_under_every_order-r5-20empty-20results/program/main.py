
class Needle:
    def __eq__(self, other):
        return False
xs = []
xs.extend([])
Needle() in xs
Needle() in [1][:0]
first, *ys = [1]
Needle() in ys
