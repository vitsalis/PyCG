An import under `if TYPE_CHECKING:` never runs, so the module `plugins` is not a
node and its top-level call does not happen. The annotation names
`plugins.Plugin`, but the argument is a `LocalPlugin`.
