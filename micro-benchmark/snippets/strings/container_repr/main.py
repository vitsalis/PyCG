class Validator:
    def __str__(self):
        return "str"

    def __repr__(self):
        return "Validator()"


class Key:
    def __repr__(self):
        return "Key()"


validators = (Validator(), Validator())
text = f"{validators!r}"
mapping = {Key(): [Validator()]}
shown = str(mapping)
