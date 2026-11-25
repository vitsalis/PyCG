class Stack:
    def __init__(self):
        self.items = []

    def append(self, item):
        self.items.append(item)

def use_list():
    values = []
    values.append(1)

def use_stack():
    Stack().append(1)

use_list()
use_stack()
