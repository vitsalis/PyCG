class JsonMixin:
    def to_json(self):
        return self.fields()


class Model:
    def fields(self):
        pass


class User(JsonMixin, Model):
    pass


User().to_json()
