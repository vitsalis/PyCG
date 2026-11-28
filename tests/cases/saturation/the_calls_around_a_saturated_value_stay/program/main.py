def h0(): pass
def h1(): pass
def h2(): pass
def h3(): pass
def h4(): pass
HANDLERS = [h0, h1, h2, h3, h4]
def run(handler):
    handler()
for handler in HANDLERS:
    run(handler)
