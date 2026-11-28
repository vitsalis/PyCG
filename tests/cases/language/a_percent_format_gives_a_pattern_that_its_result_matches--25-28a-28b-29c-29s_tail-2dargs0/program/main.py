
def f(): pass
def g(): pass
table = {'hit_tail': f, "zz_other": g}
table['%(a(b)c)s_tail' % {'a(b)c': 'hit'}]()
