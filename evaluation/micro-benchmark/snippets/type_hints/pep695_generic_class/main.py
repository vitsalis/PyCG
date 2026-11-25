class Box[T]:
    def __init__(self, item: T) -> None:
        self.item = item

    def get(self) -> T:
        return self.item


class Tool:
    def use(self):
        pass


Box(Tool()).get().use()
