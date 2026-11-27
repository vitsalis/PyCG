
def f(): pass
def g(): pass
def h(): pass

import ext
def first():
    handler = None or f
    handler()
def second():
    def one(): pass
    def two(): pass
    handler = one and two
    handler()
def third():
    def one(): pass
    handler = one or f
    handler()
def unknown():
    handler = ext.value or f
    handler()
def chain():
    def one(): pass
    def two(): pass
    handler = () or (one and two) or f
    handler()
def module_names():
    handler = f and g
    handler()
