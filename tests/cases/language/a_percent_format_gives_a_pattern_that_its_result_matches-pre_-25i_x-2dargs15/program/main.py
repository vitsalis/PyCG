
def f(): pass
def g(): pass
table = {'pre_65_x': f, "zz_other": g}
table['pre_%i_x' % (65,)]()
