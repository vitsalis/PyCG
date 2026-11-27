
class E(Exception):
    def m(self): pass
inner = (E,)
outer = (inner,)
def run():
    try:
        pass
    except (inner, outer) as error:
        error.m()
run()
