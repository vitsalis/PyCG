Audited **flit-core 4.2.0, round 1**. Found **four naming errors and one
additional missing edge**.

All 122 function bodies and 13 module bodies were reviewed. Counts below
are distinct existing graph edges checked, including incorrect edges.
A zero means the body was reviewed and has no existing outgoing edges.
All names in the coverage tables have the prefix `flit_core.`.

| Function | Edges checked |
|---|---:|
| `buildapi.build_editable` | 2 |
| `buildapi.build_sdist` | 3 |
| `buildapi.build_wheel` | 2 |
| `buildapi.get_requires_for_build_wheel` | 5 |
| `buildapi.prepare_metadata_for_build_wheel` | 13 |
| `common.Metadata.__init__` | 5 |
| `common.Metadata._normalise_field_name` | 2 |
| `common.Metadata._normalise_requires_dist` | 8 |
| `common.Metadata.supports_py2` | 2 |
| `common.Metadata.write_metadata_file` | 8 |
| `common.Module.__init__` | 14 |
| `common.Module.file` | 0 |
| `common.Module.iter_files` | 5 |
| `common.Module.iter_files._include` | 2 |
| `common.Module.version_files` | 3 |
| `common.VCSError.__init__` | 0 |
| `common.VCSError.__str__` | 0 |
| `common._module_load_ctx` | 0 |
| `common.check_version` | 4 |
| `common.dist_info_name` | 1 |
| `common.get_docstring_and_version_via_ast` | 7 |
| `common.get_docstring_and_version_via_import` | 9 |
| `common.get_info_from_module` | 9 |
| `common.hash_file` | 6 |
| `common.is_version_str_assignment` | 1 |
| `common.make_metadata` | 3 |
| `common.normalise_core_metadata_name` | 2 |
| `common.normalize_dist_name` | 3 |
| `common.normalize_file_permissions` | 0 |
| `common.parse_entry_point` | 3 |
| `common.path_is_within_directory` | 2 |
| `common.walk_data_dir` | 3 |
| `common.write_entry_points` | 3 |
| `config.EntryPointsConflict.__str__` | 0 |
| `config.LoadedConfig.__init__` | 0 |
| `config.LoadedConfig.add_scripts` | 0 |
| `config._check_glob_patterns` | 8 |
| `config._check_list_of_str` | 3 |
| `config._check_type` | 3 |
| `config._check_types` | 5 |
| `config._expand_requires_extra` | 3 |
| `config._license_files_from_globs` | 15 |
| `config.description_from_file` | 9 |
| `config.isabs_ish` | 2 |
| `config.name_is_valid` | 2 |
| `config.normalise_compound_license_expr` | 13 |
| `config.normalise_license_exception` | 2 |
| `config.normalise_simple_license_expr` | 5 |
| `config.normalize_import_name` | 6 |
| `config.normalize_pkg_name` | 2 |
| `config.pep621_people` | 8 |
| `config.prep_toml_config` | 16 |
| `config.read_flit_config` | 5 |
| `config.read_pep621_metadata` | 45 |
| `sdist.FilePatterns.__init__` | 8 |
| `sdist.FilePatterns.match_dir` | 3 |
| `sdist.FilePatterns.match_file` | 3 |
| `sdist.SdistBuilder.__init__` | 2 |
| `sdist.SdistBuilder.apply_includes_excludes` | 16 |
| `sdist.SdistBuilder.build` | 28 |
| `sdist.SdistBuilder.dir_name` | 1 |
| `sdist.SdistBuilder.from_ini_path` | 5 |
| `sdist.SdistBuilder.prep_entry_points` | 5 |
| `sdist.SdistBuilder.select_files` | 4 |
| `sdist._normalize_for_match` | 1 |
| `sdist._symlink_target_escapes` | 5 |
| `sdist.clean_tarinfo` | 2 |
| `vendor.tomli._parser.Flags.__init__` | 0 |
| `vendor.tomli._parser.Flags.is_` | 0 |
| `vendor.tomli._parser.Flags.set` | 2 |
| `vendor.tomli._parser.Flags.set_for_relative_key` | 2 |
| `vendor.tomli._parser.Flags.unset_all` | 1 |
| `vendor.tomli._parser.NestedDict.__init__` | 0 |
| `vendor.tomli._parser.NestedDict.append_nest_to_list` | 3 |
| `vendor.tomli._parser.NestedDict.get_or_create_nest` | 2 |
| `vendor.tomli._parser.create_dict_rule` | 7 |
| `vendor.tomli._parser.create_list_rule` | 8 |
| `vendor.tomli._parser.is_unicode_scalar_value` | 0 |
| `vendor.tomli._parser.key_value_rule` | 7 |
| `vendor.tomli._parser.load` | 2 |
| `vendor.tomli._parser.loads` | 9 |
| `vendor.tomli._parser.parse_array` | 5 |
| `vendor.tomli._parser.parse_basic_str` | 4 |
| `vendor.tomli._parser.parse_basic_str_escape` | 4 |
| `vendor.tomli._parser.parse_basic_str_escape_multiline` | 1 |
| `vendor.tomli._parser.parse_hex_char` | 6 |
| `vendor.tomli._parser.parse_inline_table` | 10 |
| `vendor.tomli._parser.parse_key` | 2 |
| `vendor.tomli._parser.parse_key_part` | 4 |
| `vendor.tomli._parser.parse_key_value_pair` | 4 |
| `vendor.tomli._parser.parse_literal_str` | 1 |
| `vendor.tomli._parser.parse_multiline_str` | 3 |
| `vendor.tomli._parser.parse_one_line_basic_str` | 1 |
| `vendor.tomli._parser.parse_value` | 13 |
| `vendor.tomli._parser.skip_chars` | 0 |
| `vendor.tomli._parser.skip_comment` | 1 |
| `vendor.tomli._parser.skip_comments_and_array_ws` | 2 |
| `vendor.tomli._parser.skip_until` | 4 |
| `vendor.tomli._parser.suffixed_err` | 2 |
| `vendor.tomli._parser.suffixed_err.coord_repr` | 3 |
| `vendor.tomli._re.cached_tz` | 3 |
| `vendor.tomli._re.match_to_datetime` | 7 |
| `vendor.tomli._re.match_to_localtime` | 4 |
| `vendor.tomli._re.match_to_number` | 3 |
| `versionno.normalise_version` | 13 |
| `wheel.WheelBuilder.__init__` | 2 |
| `wheel.WheelBuilder._add_file` | 26 |
| `wheel.WheelBuilder._write_to_zip` | 16 |
| `wheel.WheelBuilder.add_data_directory` | 4 |
| `wheel.WheelBuilder.add_pth` | 6 |
| `wheel.WheelBuilder.build` | 6 |
| `wheel.WheelBuilder.copy_module` | 5 |
| `wheel.WheelBuilder.dist_info` | 1 |
| `wheel.WheelBuilder.from_ini_path` | 4 |
| `wheel.WheelBuilder.wheel_filename` | 2 |
| `wheel.WheelBuilder.write_metadata` | 9 |
| `wheel.WheelBuilder.write_record` | 6 |
| `wheel._set_zinfo_mode` | 0 |
| `wheel._write_wheel_file` | 2 |
| `wheel.main` | 9 |
| `wheel.make_wheel_in` | 13 |
| `wheel.zip_timestamp_from_env` | 3 |
| **122 functions** | **622** |

Module bodies were also checked:

| Module suffix | Edges checked |
|---|---:|
| Package root, `flit_core` | 0 |
| `_spdx_data` | 0 |
| `buildapi` | 2 |
| `common` | 4 |
| `config` | 2 |
| `sdist` | 3 |
| `vendor` | 0 |
| `vendor.tomli` | 0 |
| `vendor.tomli._parser` | 4 |
| `vendor.tomli._re` | 3 |
| `vendor.tomli._types` | 0 |
| `versionno` | 2 |
| `wheel` | 5 |
| **13 modules** | **25** |

The findings below use source paths relative to
`macro-benchmark/projects/flit-core/flit_core/flit_core/`.
Dependency paths are relative to
`macro-benchmark/selection/batch-8-proposal/deps/cpython/`.
Caller names retain the `flit_core.` prefix.

The shared evidence and rules are:

- **E1 — SHA-256 class export.** CPython 3.8–3.11 exports the concrete
  class as `_sha256.SHA256Type`: `3.8.20/Modules/sha256module.c:726`,
  `3.9.25/Modules/sha256module.c:720`,
  `3.10.22/Modules/sha256module.c:725`, and
  `3.11.18/Modules/sha256module.c:728`. The lowercase `sha256` is a
  factory function. The internal type name `_sha256.sha256` does not
  remove the exported class path.
- **E2 — CSV class export.** CPython 3.10–3.15 exports the writer class
  as `_csv.Writer`: `3.10.22/Modules/_csv.c:1719`,
  `3.11.18/Modules/_csv.c:1753`, `3.12.16/Modules/_csv.c:1776`,
  `3.13.18/Modules/_csv.c:1760`, and
  `3.14.10/Modules/_csv.c:1799` / `3.15.2/Modules/_csv.c:1799`.
  CPython 3.8–3.9 has no such export, so its existing
  `_csv.writer.writerow` fallback remains.
- **R1 — Outside method naming.** `PyCG/micro-benchmark/README.md`,
  “Names”, requires the public import path of the receiver class.
  `macro-benchmark/README.md:1903` permits the internal type-name
  fallback only without a public path; “Outside names” at line 2249
  distinguishes a class alias from a factory.
- **R2 — Version union.** “Versions and configuration” requires names
  across admitted Python versions and retains older fallback names
  where those runtimes lack the later public path.

| Id | Kind | Caller | Site (file:line:col) | Edge | Evidence | Rule |
|---|---|---|---|---|---|---|
| N1 | naming | `flit_core.common.hash_file` | `common.py:308:23` | Replace `→ _sha256.sha256.hexdigest` with `→ _sha256.SHA256Type.hexdigest` | `hashlib.new` at line 307 can return the builtin SHA-256 object; line 308 calls its method. E1 establishes its exported class. | R1 |
| N2 | naming | `flit_core.wheel.WheelBuilder._add_file` | `wheel.py:143:31` | Replace `→ _sha256.sha256.update` with `→ _sha256.SHA256Type.update` | `hashlib.sha256()` at line 137 can select the builtin fallback; a nonempty file reaches line 143. E1 establishes its exported class. | R1 |
| N3 | naming | `flit_core.wheel.WheelBuilder._add_file` | `wheel.py:147:55` | Replace `→ _sha256.sha256.digest` with `→ _sha256.SHA256Type.digest` | Line 147 calls `digest()` on the object made at line 137. E1 establishes its exported class. | R1 |
| N4 | naming | `flit_core.wheel.WheelBuilder._write_to_zip` | `wheel.py:165:55` | Replace `→ _sha256.sha256.digest` with `→ _sha256.SHA256Type.digest` | Line 164 creates the hash object; line 165 calls its method. E1 establishes its exported class. | R1 |
| M1 | missing | `flit_core.wheel.WheelBuilder.write_record` | `wheel.py:209:32`; `wheel.py:211:28` | Add `→ _csv.Writer.writerow` | `csv.writer(f)` at line 207 returns the class exported in E2 on CPython 3.10–3.15. Both sites call `writerow`. The graph contains only the older fallback name. | R1, R2 |

The permitted `check.py --report flit-core` completed with no undecided
sites or unaccounted trace edges. The review also checked value sites,
defaults, binding, properties, implicit operations and library callbacks.
No package was run or imported, and no files were changed.

| Total | Count |
|---|---:|
| Missing, including naming | **5** |
| False, including naming | **4** |
| Naming findings | **4** |
| Ruling | **0** |
| Unsure | **0** |

There is one standalone missing finding and no standalone false finding.
None of the findings belongs to an open path or receiver set.