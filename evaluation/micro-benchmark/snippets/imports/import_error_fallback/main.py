try:
    from accel.native import compute
except ImportError:
    from accel.pure import compute

compute()
