`start` calls the coroutine function `task` and closes the coroutine without awaiting it, so the body of `task` never runs.
There is an edge to `main.task`, but no edge from `main.task` to `main.side_effect`.
