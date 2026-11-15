An external decorator replaces `handler` with the object that it returns, so `handler()` calls that object, named `ext.route` by its access path. The stub never calls the original function.
There is no edge to `main.handler`.
