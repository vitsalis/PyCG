An exception object stores a function and the handler calls it. Only `fetch`
raises, so the edge `main -> main.retry_store` must not appear.
