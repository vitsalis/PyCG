
class A:
    def run(self): pass
class B:
    def run(self): pass
def use(xs: "list['A | None'] | list['B | None']"):
    for x in xs:
        x.run()
