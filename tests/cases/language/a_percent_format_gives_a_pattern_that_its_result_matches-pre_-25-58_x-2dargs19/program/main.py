
def f(): pass
def g(): pass
table = {'pre_41_x': f, "zz_other": g}
table['pre_%X_x' % (65,)]()
