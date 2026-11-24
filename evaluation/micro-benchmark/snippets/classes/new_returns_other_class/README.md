`__new__` returns an instance of another class, so Python does not call
`__init__` of the instantiated class. The edge `main -> main.Proxy.__init__`
must not appear.
