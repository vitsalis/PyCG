
class Indexed:
    def __getitem__(self, index): return index
class Plain:
    pass
def loop(values):
    for value in values:
        pass
loop(Indexed()); loop(Indexed()); loop(Indexed())
loop(Plain()); loop(Plain())
