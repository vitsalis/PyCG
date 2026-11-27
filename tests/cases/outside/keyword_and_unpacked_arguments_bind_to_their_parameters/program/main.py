
def key(x): pass
def other(): pass
options = {"key": key}
sorted([1], **options)
sorted(*[[other]])
