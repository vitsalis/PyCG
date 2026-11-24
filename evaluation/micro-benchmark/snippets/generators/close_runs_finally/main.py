def cleanup():
    pass

def gen():
    try:
        yield 1
    finally:
        cleanup()

g = gen()
next(g)
g.close()
