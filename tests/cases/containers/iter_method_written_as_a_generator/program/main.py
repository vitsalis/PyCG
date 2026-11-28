
def f(): pass
class Items:
    def __iter__(self):
        yield f
for item in Items():
    item()
