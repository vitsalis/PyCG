def read():
    return 0


def write():
    pass


def clear():
    pass


class Account:
    def __init__(self):
        self.balance = 0

    @property
    def balance(self):
        return read()

    @balance.setter
    def balance(self, value):
        write()

    @balance.deleter
    def balance(self):
        clear()


account = Account()
account.balance
del account.balance
