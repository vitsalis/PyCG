
def f(): pass
def g(): pass
table = {'pre__x': f, "zz_other": g}
table['pre_%.s_x' % ('abc',)]()
