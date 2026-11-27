def f(): pass
def g(): pass
def h(): pass

table = {"aba": g, "abba": f}
def read(name):
    table[f"ab{name}ba"]()
read("x")
