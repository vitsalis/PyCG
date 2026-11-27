def f(): pass
def g(): pass
def h(): pass

x = [f]
x.append(x)
x[1][1][0]()
d = {}
d["self"] = d
d["self"]["self"]["f"] = g
d["f"]()
xs = [h]
for item in xs:
    xs.append([item])
xs[0]()
