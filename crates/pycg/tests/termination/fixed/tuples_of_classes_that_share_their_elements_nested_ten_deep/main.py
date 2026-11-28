t0 = (int, str)
t1 = (t0, t0, t0)
t2 = (t1, t1, t1)
t3 = (t2, t2, t2)
t4 = (t3, t3, t3)
t5 = (t4, t4, t4)
t6 = (t5, t5, t5)
t7 = (t6, t6, t6)
t8 = (t7, t7, t7)
t9 = (t8, t8, t8)
def f(x=1):
    if isinstance(x, t9):
        x.bit_length()
    if not isinstance(x, t9):
        x.upper()
