**nodeenv — Codex audit, round 1: no findings.**

Read all 66 functions, including both lambdas, and checked all 439
distinct graph edges: 428 from functions and 11 from module scope.
Reviewed value-site notes, callbacks, implicit calls, argument binding,
supported branches, and outside names against dependency sources.

`python3 -I -B macro-benchmark/check.py --report nodeenv` reports zero
undecided sites and zero unaccounted trace edges. No package code was
executed or imported.

Function names below have the prefix `nodeenv.`. Counts are distinct
outgoing edges checked against the source.

| Function read | Edges checked |
|---|---:|
| `Config._load` | 22 |
| `Config._dump` | 6 |
| `clear_output` | 2 |
| `remove_env_bin_from_path` | 3 |
| `find_system_node` | 2 |
| `parse_version` | 6 |
| `_pad_version` | 2 |
| `_is_exact_version` | 1 |
| `_is_wildcard` | 0 |
| `_comparator_constraints` | 3 |
| `_parse_comparator` | 2 |
| `parse_node_range` | 5 |
| `match_node_range` | 7 |
| `node_version_from_args` | 5 |
| `get_installed_node_version` | 8 |
| `create_logger` | 7 |
| `create_logger.emit` | 4 |
| `PrintCompletionAction.__call__` | 6 |
| `make_parser` | 2 |
| `parse_args` | 6 |
| `mkdir` | 5 |
| `make_executable` | 1 |
| `writefile` | 13 |
| `callit` | 18 |
| `get_root_url` | 1 |
| `is_x86_64_musl` | 3 |
| `is_riscv64` | 1 |
| `get_node_bin_url` | 5 |
| `get_node_src_url` | 1 |
| `tarfile_open` | 2 |
| `_download_node_file` | 10 |
| `_extract_zip` | 12 |
| `download_node_src` | 17 |
| `download_node_src.<lambda1>` | 0 |
| `make_certifi_context` | 4 |
| `get_proxy_settings` | 1 |
| `_urlopen` | 2 |
| `split_url_auth` | 9 |
| `urlopen` | 10 |
| `copytree` | 9 |
| `copy_node_from_prebuilt` | 11 |
| `build_node_from_src` | 19 |
| `build_node_from_src.<lambda1>` | 2 |
| `install_node` | 3 |
| `report_node_download_error` | 7 |
| `install_node_wrapped` | 14 |
| `install_npm` | 8 |
| `install_npm_win` | 18 |
| `_read_packages` | 4 |
| `install_packages` | 8 |
| `is_python_venv_script` | 5 |
| `install_activate` | 16 |
| `set_predeactivate_hook` | 2 |
| `create_environment` | 17 |
| `_get_versions_json` | 5 |
| `get_node_versions` | 2 |
| `print_node_versions` | 6 |
| `_has_platform_build` | 2 |
| `_is_prerelease` | 0 |
| `_get_last_node_version` | 8 |
| `_get_last_node_version.version_filter` | 2 |
| `get_last_stable_node_version` | 1 |
| `get_last_lts_node_version` | 1 |
| `resolve_node_version` | 14 |
| `get_env_dir` | 7 |
| `main` | 23 |
| **Functions subtotal** | **428** |
| Module scope (`nodeenv`) | 11 |
| **Total** | **439** |

Findings: none.

| Id | Kind | Caller | Site (file:line:col) | Edge | Evidence | Rule |
|---|---|---|---|---|---|---|

| Missing | False | Naming | Ruling | Unsure |
|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 0 |

No findings were excluded from the totals as open path or receiver sets.