def h0(): pass
def h1(): pass
def h2(): pass
def h3(): pass
HANDLERS = [h0, h1, h2, h3]
def run(handler):
    handler()
for handler in HANDLERS:
    run(handler)
