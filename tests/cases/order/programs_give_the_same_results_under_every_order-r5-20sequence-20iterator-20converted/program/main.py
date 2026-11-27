
class Needle:
    def __eq__(self, other):
        return True
class Seq:
    def __getitem__(self, index):
        if index == 0:
            return 1
        raise IndexError
Needle() in list(iter(Seq()))
