
def f(): pass
def g(): pass
table = {'pre_A_x': f, "zz_other": g}
table['pre_%c_x' % (65,)]()
