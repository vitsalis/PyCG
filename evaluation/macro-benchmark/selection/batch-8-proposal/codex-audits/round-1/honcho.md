Honcho, round 1: **no findings**.

Read all 73 function/lambda definitions, represented by 70 graph nodes,
and all 15 modules. Checked all **297 existing edges**: 269 from functions
and 28 from modules. Counts below are distinct outgoing graph edges;
alternate definitions share their node’s union count.

| Function read | Edges checked |
|---|---:|
| `honcho.colour.get_colours` | 2 |
| `honcho.command._add_common_args` | 1 |
| `honcho.command._check_output_encoding` | 4 |
| `honcho.command._compact` | 1 |
| `honcho.command._mkdir` | 4 |
| `honcho.command._parse_concurrency` | 3 |
| `honcho.command._parse_concurrency.<lambda1>` | 0 |
| `honcho.command._parse_quiet` | 1 |
| `honcho.command._port` | 3 |
| `honcho.command._procfile` | 3 |
| `honcho.command._read_env` | 8 |
| `honcho.command._write_file` | 6 |
| `honcho.command.command_check` | 6 |
| `honcho.command.command_export` | 20 |
| `honcho.command.command_help` | 2 |
| `honcho.command.command_run` | 8 |
| `honcho.command.command_start` | 18 |
| `honcho.command.command_version` | 2 |
| `honcho.command.main` | 11 |
| `honcho.command.map_from` | 7 |
| `honcho.compat.ProcessManager.kill` | 2 |
| `honcho.compat.ProcessManager.terminate` | 2 |
| `honcho.environ.Env.__init__` | 0 |
| `honcho.environ.Env.load_procfile` | 4 |
| `honcho.environ.Env.port` | 2 |
| `honcho.environ.Env.procfile` | 1 |
| `honcho.environ.Procfile.__init__` | 1 |
| `honcho.environ.Procfile.add_process` | 0 |
| `honcho.environ.expand_processes` | 11 |
| `honcho.environ.expand_processes.<lambda1>` | 0 |
| `honcho.environ.parse` | 7 |
| `honcho.environ.parse_procfile` | 5 |
| `honcho.export.base.BaseExport.__init__` | 7 |
| `honcho.export.base.BaseExport.get_template` | 1 |
| `honcho.export.base.BaseExport.get_template_loader` | 1 |
| `honcho.export.base.BaseExport.render` | 1 |
| `honcho.export.base.File.__init__` | 0 |
| `honcho.export.base._default_template_env` | 1 |
| `honcho.export.base.dashrepl` | 2 |
| `honcho.export.base.percentescape` | 1 |
| `honcho.export.runit.Export.get_template_loader` | 1 |
| `honcho.export.runit.Export.render` | 9 |
| `honcho.export.supervisord.Export.get_template_loader` | 1 |
| `honcho.export.supervisord.Export.render` | 6 |
| `honcho.export.systemd.Export.get_template_loader` | 1 |
| `honcho.export.systemd.Export.render` | 8 |
| `honcho.export.systemd.Export.render.<lambda1>` | 1 |
| `honcho.export.upstart.Export.get_template_loader` | 1 |
| `honcho.export.upstart.Export.render` | 9 |
| `honcho.export.upstart.Export.render.<lambda1>` | 1 |
| `honcho.manager.Manager.__init__` | 4 |
| `honcho.manager.Manager._all_started` | 3 |
| `honcho.manager.Manager._all_stopped` | 3 |
| `honcho.manager.Manager._any_stopped` | 3 |
| `honcho.manager.Manager._killall` | 5 |
| `honcho.manager.Manager._start` | 4 |
| `honcho.manager.Manager._system_print` | 2 |
| `honcho.manager.Manager.add_process` | 4 |
| `honcho.manager.Manager.kill` | 1 |
| `honcho.manager.Manager.loop` | 13 |
| `honcho.manager.Manager.loop._terminate` | 2 |
| `honcho.manager.Manager.terminate` | 1 |
| `honcho.printer.Printer.__init__` | 2 |
| `honcho.printer.Printer.write` | 9 |
| `honcho.printer._ansi` | 1 |
| `honcho.printer._colour_string` | 2 |
| `honcho.process.Popen.__init__` | 4 |
| `honcho.process.Process.__init__` | 1 |
| `honcho.process.Process._send_message` | 2 |
| `honcho.process.Process.run` | 6 |
| **70 function/lambda nodes** | **269** |

Both definitions of `ProcessManager.terminate`, `ProcessManager.kill`, and
`_colour_string` were read.

| Module read | Edges checked |
|---|---:|
| `honcho` | 0 |
| `honcho.__main__` | 1 |
| `honcho.colour` | 3 |
| `honcho.command` | 15 |
| `honcho.compat` | 2 |
| `honcho.environ` | 3 |
| `honcho.export` | 0 |
| `honcho.export.base` | 2 |
| `honcho.export.runit` | 0 |
| `honcho.export.supervisord` | 0 |
| `honcho.export.systemd` | 0 |
| `honcho.export.upstart` | 0 |
| `honcho.manager` | 0 |
| `honcho.printer` | 2 |
| `honcho.process` | 0 |
| **15 modules** | **28** |

The review covered value-site provenance, class dispatch, argument binding,
implicit operations, callbacks, all nine export templates, and outside
callee names against the supplied dependency sources. The allowed checker
reports no undecided sites, no default rejections, and no unaccounted trace
edges. The package was neither imported nor executed.

The findings table is empty.

| Id | Kind | Caller | Site (file:line:col) | Edge | Evidence | Rule |
|---|---|---|---|---|---|---|

| Missing | False | Naming | Ruling | Unsure |
|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 0 |

No open-path or open-receiver exclusions affect these totals.