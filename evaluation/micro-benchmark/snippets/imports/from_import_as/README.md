`from formatting import render as show` imports a function under another name, and `show()` calls it.
The module also defines its own `render`, which is never called: there is no edge to `main.render`.
