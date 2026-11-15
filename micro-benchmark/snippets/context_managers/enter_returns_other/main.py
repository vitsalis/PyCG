class Connection:
    def execute(self):
        pass


class Pool:
    def __enter__(self):
        return Connection()

    def __exit__(self, *args):
        pass

    def execute(self):
        pass


with Pool() as conn:
    conn.execute()
