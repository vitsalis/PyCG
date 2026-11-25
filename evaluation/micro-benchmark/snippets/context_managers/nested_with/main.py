class Transaction:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def commit(self):
        pass


class Database:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def transaction(self):
        return Transaction()


with Database() as db:
    with db.transaction() as tx:
        tx.commit()
