A load through an instance of a subclass of `property` gives what the getter
returns, not the property: a method that the subclass defines is not called on
the result.
