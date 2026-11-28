def f(): pass
def g(): pass
def h(): pass

def run(name, **options):
    options["callback"]()
    for key in options:
        pass
run("x", callback=f, other=g)
