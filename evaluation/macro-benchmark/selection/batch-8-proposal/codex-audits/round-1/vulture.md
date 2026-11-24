Vulture, round 1: **no findings**.

Audited commit `8a5bc61d2d173bbaa834377c81bb2452b8be1091`.
Read all 97 functions, including the lambda, and all 23 module bodies.
Checked 323 distinct outgoing edges: 311 from functions and 12 from
module bodies.

The review covered all 12 value sites, four default rejections, implicit
calls, argument binding, callbacks, and outside names against the supplied
dependency sources. The permitted checker reports found no undecided sites
or unaccounted trace edges. The package was neither run nor imported.

Function names below are relative to the stated module. Counts are graph
edges, not call-site counts; zero means the body was read and checked.

For `vulture.config`:

| Function read | Edges checked |
|---|---:|
| `InputError.__init__` | 0 |
| `_check_input_config` | 3 |
| `_check_output_config` | 1 |
| `_parse_args` | 8 |
| `_parse_args.csv` | 1 |
| `_parse_toml` | 4 |
| `make_config` | 14 |

For `vulture.core`:

| Function read | Edges checked |
|---|---:|
| `Item.__eq__` | 1 |
| `Item.__hash__` | 2 |
| `Item.__init__` | 0 |
| `Item.__repr__` | 1 |
| `Item._tuple` | 0 |
| `Item.get_report` | 2 |
| `Item.get_whitelist_string` | 1 |
| `Item.size` | 0 |
| `Vulture.__init__` | 5 |
| `Vulture.__init__.get_list` | 1 |
| `Vulture._add_aliases` | 4 |
| `Vulture._define` | 6 |
| `Vulture._define.ignored` | 7 |
| `Vulture._define_variable` | 1 |
| `Vulture._handle_new_format_string` | 6 |
| `Vulture._handle_new_format_string.is_identifier` | 2 |
| `Vulture._is_locals_call` | 1 |
| `Vulture._log` | 4 |
| `Vulture.generic_visit` | 3 |
| `Vulture.get_unused_code` | 11 |
| `Vulture.get_unused_code.by_name` | 2 |
| `Vulture.get_unused_code.by_size` | 2 |
| `Vulture.report` | 4 |
| `Vulture.scan` | 10 |
| `Vulture.scan.handle_syntax_error` | 3 |
| `Vulture.scavenge` | 10 |
| `Vulture.scavenge.exclude_path` | 1 |
| `Vulture.scavenge.prepare_pattern` | 1 |
| `Vulture.unused_attrs` | 1 |
| `Vulture.unused_classes` | 1 |
| `Vulture.unused_funcs` | 1 |
| `Vulture.unused_imports` | 1 |
| `Vulture.unused_methods` | 1 |
| `Vulture.unused_props` | 1 |
| `Vulture.unused_vars` | 1 |
| `Vulture.visit` | 21 |
| `Vulture.visit_Assign` | 4 |
| `Vulture.visit_AsyncFunctionDef` | 1 |
| `Vulture.visit_Attribute` | 3 |
| `Vulture.visit_BinOp` | 5 |
| `Vulture.visit_Call` | 7 |
| `Vulture.visit_ClassDef` | 4 |
| `Vulture.visit_FunctionDef` | 5 |
| `Vulture.visit_Import` | 1 |
| `Vulture.visit_ImportFrom` | 1 |
| `Vulture.visit_MatchClass` | 1 |
| `Vulture.visit_Name` | 3 |
| `Vulture.visit_arg` | 1 |
| `_assigns_special_variable__all__` | 2 |
| `_get_unused_items` | 5 |
| `_get_unused_items.<lambda1>` | 1 |
| `_ignore_class` | 1 |
| `_ignore_function` | 2 |
| `_ignore_import` | 0 |
| `_ignore_method` | 3 |
| `_ignore_variable` | 2 |
| `_is_special_name` | 2 |
| `_is_test_file` | 3 |
| `_match` | 3 |
| `main` | 6 |

For `vulture.lines`:

| Function read | Edges checked |
|---|---:|
| `get_first_line_number` | 1 |
| `get_last_line_number` | 0 |

For `vulture.noqa`:

| Function read | Edges checked |
|---|---:|
| `_parse_error_codes` | 3 |
| `ignore_line` | 0 |
| `parse_noqa` | 6 |

For `vulture.reachability`:

| Function read | Edges checked |
|---|---:|
| `Reachability.__init__` | 1 |
| `Reachability._body_has_break` | 3 |
| `Reachability._can_else_fall_through` | 1 |
| `Reachability._can_fall_through` | 0 |
| `Reachability._can_fall_through_statements_analysis` | 5 |
| `Reachability._handle_reachability_if` | 9 |
| `Reachability._handle_reachability_if_expr` | 5 |
| `Reachability._handle_reachability_try` | 6 |
| `Reachability._handle_reachability_while` | 8 |
| `Reachability._mark_as_no_fall_through` | 1 |
| `Reachability.reset` | 1 |
| `Reachability.visit` | 7 |

For `vulture.utils`:

| Function read | Edges checked |
|---|---:|
| `LoggingList.__init__` | 2 |
| `LoggingList.append` | 3 |
| `LoggingSet.__init__` | 2 |
| `LoggingSet.add` | 3 |
| `_safe_eval` | 5 |
| `condition_is_always_false` | 1 |
| `condition_is_always_true` | 1 |
| `format_path` | 3 |
| `get_decorator_name` | 4 |
| `get_modules` | 11 |
| `is_ast_string` | 1 |
| `read_file` | 2 |

For `vulture.whitelists.whitelist_utils`:

| Function read | Edges checked |
|---|---:|
| `Whitelist.__getattr__` | 0 |

The module bodies were checked separately:

| Module read | Edges checked |
|---|---:|
| `vulture` | 0 |
| `vulture.__main__` | 1 |
| `vulture.config` | 0 |
| `vulture.core` | 2 |
| `vulture.lines` | 0 |
| `vulture.noqa` | 1 |
| `vulture.reachability` | 1 |
| `vulture.utils` | 0 |
| `vulture.version` | 0 |
| `vulture.whitelists.argparse_whitelist` | 2 |
| `vulture.whitelists.ast_whitelist` | 1 |
| `vulture.whitelists.collections_whitelist` | 1 |
| `vulture.whitelists.ctypes_whitelist` | 0 |
| `vulture.whitelists.enum_whitelist` | 0 |
| `vulture.whitelists.logging_whitelist` | 1 |
| `vulture.whitelists.pint_whitelist` | 1 |
| `vulture.whitelists.socketserver_whitelist` | 0 |
| `vulture.whitelists.ssl_whitelist` | 1 |
| `vulture.whitelists.string_whitelist` | 0 |
| `vulture.whitelists.sys_whitelist` | 0 |
| `vulture.whitelists.threading_whitelist` | 0 |
| `vulture.whitelists.unittest_whitelist` | 0 |
| `vulture.whitelists.whitelist_utils` | 0 |

The findings table has no rows.

| Id | Kind | Caller | Site (file:line:col) | Edge | Evidence | Rule |
|---|---|---|---|---|---|---|

Totals:

| Missing | False | Naming | Ruling | Unsure |
|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 0 |

Open-path or open-receiver findings excluded from the stop rule: **0**.