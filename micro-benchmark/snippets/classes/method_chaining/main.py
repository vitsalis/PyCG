class Query:
    def select(self):
        return self

    def where(self):
        return self

    def run(self):
        pass


Query().select().where().run()
