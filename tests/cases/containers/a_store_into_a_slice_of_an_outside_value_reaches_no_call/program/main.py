
import somelib
def f(): pass
def use():
    somelib.items[0:1] = [f]
    somelib.items[0]()
