class Base:
    def save(self):
        pass


class Middle(Base):
    def save(self):
        pass


class Child(Middle):
    def save(self):
        super(Middle, self).save()


Child().save()
