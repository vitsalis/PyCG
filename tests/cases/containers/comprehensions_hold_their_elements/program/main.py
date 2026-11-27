def f(): pass
def g(): pass
def h(): pass

[x for x in (f,)][0]()
{k: v for k, v in [("a", g)]}["a"]()
for y in (x for x in [h]):
    y()
