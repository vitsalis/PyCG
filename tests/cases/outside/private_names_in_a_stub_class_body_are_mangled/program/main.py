
import other
class C:
    from other import __T as T
    import other
    def use(self, x):
        x.run()
    def use_attribute(self, x):
        x.run()
