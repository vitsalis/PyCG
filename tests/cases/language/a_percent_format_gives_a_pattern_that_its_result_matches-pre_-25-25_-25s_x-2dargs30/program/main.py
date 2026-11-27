
def f(): pass
def g(): pass
table = {'pre_%_a_x': f, "zz_other": g}
table['pre_%%_%s_x' % ('a',)]()
