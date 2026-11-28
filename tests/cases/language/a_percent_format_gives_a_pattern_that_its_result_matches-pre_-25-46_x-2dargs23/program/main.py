
def f(): pass
def g(): pass
table = {'pre_65.000000_x': f, "zz_other": g}
table['pre_%F_x' % (65,)]()
