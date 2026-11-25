A global that the module deletes is looked up in the builtins: the second
call of `check` calls the builtin `callable`, the first the lambda.
