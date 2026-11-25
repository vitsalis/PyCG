class Record:
    @property
    def name(self):
        return "n"

    @property
    def size(self):
        return 1

    @property
    def owner(self):
        return "o"

    @property
    def kind(self):
        return "k"

    @property
    def mode(self):
        return "m"

    def fields(self):
        names = []
        for key in Record.__dict__:
            if isinstance(getattr(Record, key, None), property):
                names.append(key)
        return [getattr(self, key) for key in names]


Record().fields()
