class Key:
    def __hash__(self):
        return 1

    def __eq__(self, other):
        return True


table = {Key(): 1}


def lookup(remove):
    method = table.pop if remove else table.get
    return method(Key())
