
def f(): pass
def g(): pass
table = {'pre_a_x': f, "zz_other": g}
table['pre_%Ls_x' % ('a',)]()
