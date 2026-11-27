
def f(data):
    if any((hit := d) for d in data):
        return hit
