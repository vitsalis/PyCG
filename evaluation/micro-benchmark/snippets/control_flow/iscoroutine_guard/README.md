`inspect.iscoroutine(value)` is `isinstance(value, types.CoroutineType)`,
and no class derives from `types.CoroutineType`: in the branch where it
holds, `value` is the coroutine, so `value.close()` calls
`CoroutineType.close` and never `Result.close`.
