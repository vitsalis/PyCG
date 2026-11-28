
def f(): pass
def g(): pass
table = {'pre_101_x': f, "zz_other": g}
table['pre_%o_x' % (65,)]()
