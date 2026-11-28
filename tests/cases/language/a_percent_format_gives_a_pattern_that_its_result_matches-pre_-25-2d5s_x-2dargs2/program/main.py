
def f(): pass
def g(): pass
table = {'pre_a    _x': f, "zz_other": g}
table['pre_%-5s_x' % ('a',)]()
