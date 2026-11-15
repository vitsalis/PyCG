def make_counter():
    class Counter:
        def __init__(self):
            self.count = 0

        def increment(self):
            self.count += 1

    return Counter


counter_class = make_counter()
counter = counter_class()
counter.increment()
