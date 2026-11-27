
def f(): pass
def g(): pass
table = {'pre_  a_x': f, "zz_other": g}
table['pre_%*s_x' % (3, 'a')]()
