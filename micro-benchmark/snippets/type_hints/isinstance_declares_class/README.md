`pickle.loads` returns a value of any type. In the branch where `isinstance(obj, Plugin)` holds, `obj` is a `Plugin`, so `obj.run()` calls `Plugin.run`.
