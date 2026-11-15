`main` imports `process` from an external module and then defines its own `process`, which replaces the imported name before the call.
There is no edge to `ext.process`.
