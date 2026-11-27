class Session:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def query(self):
        pass


with Session() as session:
    session.query()
