
def f(): pass
def g(): pass
table = {'pre_    a_x': f, "zz_other": g}
table['pre_%05s_x' % ('a',)]()
