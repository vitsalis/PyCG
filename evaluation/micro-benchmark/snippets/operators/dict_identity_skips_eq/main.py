class Key:
    def __hash__(self):
        return 1

    def __eq__(self, other):
        return True


key = Key()
table = {key: 1}
table[key]
