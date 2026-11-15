`main` replaces the function `mailer.send` at run time. `mailer.notify` looks up `send` in its module globals when it runs, so it calls the replacement.
There is no edge from `mailer.notify` to `mailer.send`.
