from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plugins import Plugin


class LocalPlugin:
    def start(self):
        pass


def run(plugin: "Plugin") -> None:
    plugin.start()


run(LocalPlugin())
