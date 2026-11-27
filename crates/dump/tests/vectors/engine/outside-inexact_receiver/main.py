class Box:
    def __init__(self, items):
        self.items = items


box = Box([1, 2])
copied = box.items.__class__(box.items)
copied.append(3)
