
def f(): pass
def g(): pass
table = {"pre_'a'_x": f, "zz_other": g}
table['pre_%r_x' % ('a',)]()
