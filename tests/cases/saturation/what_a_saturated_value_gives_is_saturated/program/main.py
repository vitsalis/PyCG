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

def use(handler, item):
    handler.attribute()
    handler[0]()
    for each in handler:
        each()
    handler.stored = item
    handler.stored()
    item()
def item(): pass
for handler in HANDLERS:
    use(handler, item)
