An explicit `__get__` of a class method binds the function to the owner (an
explicit owner wins over the class of the instance; an outside class is an
owner too), or to the type of the instance where no owner is passed (the
metaclass for a class, also where an unpacking may pass none); `False` is an
instance, not the absence of one. A static method's `__get__` gives the
function. Each bound function calls a method of the class that it got, so the
class is observed.
