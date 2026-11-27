
def hit(): pass
exec("__name__ = 'other'")
if __name__ == "other":
    hit()
