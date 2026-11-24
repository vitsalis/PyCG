import ext

class Repository(ext.Model):
    def save(self):
        super().save()

Repository().save()
