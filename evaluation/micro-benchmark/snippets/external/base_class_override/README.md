A snippet class with an external base class overrides `validate` and calls an inherited method `commit`.
`self.validate()` calls the override: there is no edge to `ext.Model.validate`.
