The default value of a lambda parameter is another lambda. Defaults are evaluated in the enclosing scope, so the inner lambda is `main.<lambda2>`, not `main.<lambda1>.<lambda1>`.
