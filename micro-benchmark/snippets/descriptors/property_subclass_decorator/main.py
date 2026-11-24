def read():
    return 0


def write():
    pass


def clear():
    pass


class tracked(property):
    def describe(self):
        return "tracked"


class Account:
    @tracked
    def balance(self):
        return read()

    @balance.setter
    def balance(self, value):
        write()

    @balance.deleter
    def balance(self):
        clear()


def show(account):
    return account.balance


def update(account):
    account.balance = 1


def close(account):
    del account.balance


account = Account()
show(account)
update(account)
close(account)
