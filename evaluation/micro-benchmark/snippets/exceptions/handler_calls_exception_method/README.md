A handler for a base exception class calls a method on the caught exception.
The object is a `DbError`, so the edges `main -> main.AppError.report` and
`main -> main.NetError.report` must not appear.
