class User:
    @property
    def name(self):
        return "ada"

message = "{.name}".format(User())
