def weight(item):
    return item

max([1, 2], key=lambda item: weight(item))
