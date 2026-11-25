`warn(0, 13, "unsupported")` passes three of the four arguments that `warn`
requires, so Python raises `TypeError` before `warn` starts and `start`
never reaches `cleanup()`.
