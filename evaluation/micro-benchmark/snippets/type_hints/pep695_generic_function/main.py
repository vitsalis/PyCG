def first[T](items: list[T]) -> T:
    return items[0]


class Job:
    def run(self):
        pass


first([Job()]).run()
