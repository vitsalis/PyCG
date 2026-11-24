USE_FAST = False

if USE_FAST:
    from fast import compute
else:
    from slow import compute

compute()
