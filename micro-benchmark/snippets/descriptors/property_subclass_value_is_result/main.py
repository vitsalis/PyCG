class Report:
    def describe(self):
        return "report"


class tracked(property):
    def describe(self):
        return "tracked"


def read(self):
    return Report()


class Item:
    value = tracked(read)


def show(item):
    return item.value.describe()


show(Item())
