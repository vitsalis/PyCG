A metaclass method is callable on the class, not on its instances. Instance
lookup ignores the metaclass, so `describe` resolves to `Model.describe`: the
edge `main -> main.Meta.describe` must not appear.
