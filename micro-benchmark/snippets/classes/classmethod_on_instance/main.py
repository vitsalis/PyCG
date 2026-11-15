class Counter:
    total = 0

    @classmethod
    def increment(cls):
        cls.total += 1
        cls.report()

    @classmethod
    def report(cls):
        pass


Counter.increment()
counter = Counter()
counter.increment()
