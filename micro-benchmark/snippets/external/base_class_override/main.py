import ext

class Repository(ext.Model):
    def validate(self):
        pass

    def save(self):
        self.validate()
        self.commit()

Repository().save()
