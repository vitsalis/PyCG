Calling a class runs `__call__` of its metaclass. Here it calls `type.__call__`,
which calls `__init__`, so the edge comes from the metaclass method:
`main -> main.Config.__init__` must not appear.
