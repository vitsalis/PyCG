`start` creates a coroutine and passes it to `wait_for_it`, which awaits it. The edge comes from the scope that calls the coroutine function, `main.start`.
There is no edge from `main.wait_for_it` to `main.fetch`.
