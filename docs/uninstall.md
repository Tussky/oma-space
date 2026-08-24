# uninstall

`oma-space uninstall` — the tabs off the bar, and Omarchy's strip back.
Rationale lives in prd.md F6; this is the interface.

`omarchy plugin remove` does put `omarchy.workspaces` back on its own — the manifest
declares `omarchy.clonedFrom`, and the shell restores a clone's source when the clone is
disabled. What it does not do is clean up after a plugin that owns more than one bar
entry: its disable path swaps **one** layout entry and stops, leaving the other nine tabs
behind as dead slots.

So this verb is the tidy path, not the only one: it takes every tab off, puts Omarchy's
strip back where the strip stood, and leaves nothing behind.

## Contract

- Diagnostics to **stderr**. Exit `0`, `1` on failure, `2` on usage.
- **Nothing is changed before you agree to it**, on the same terms as install: the
  plan first, then the question, and `1` with nothing written if the answer is no.
  A run with no terminal and no `--yes` refuses rather than assuming.
- **Every tab comes off**, in every section, however many there are.
- **`omarchy.workspaces` goes back where the strip stood** — the position matters:
  appending it to the end of the section would leave the bar rearranged by a plugin
  the user just removed. If it is already on the bar, nothing is added.
- **Definitions are never touched.** `~/.config/oma-space/workspaces/` survives, so
  reinstalling picks up every workspace you had saved.
- The write is atomic and goes through the same backup rule as install.
- **`--purge` refuses to delete the directory it is running from**, so uninstalling
  from a checkout removes the installed copy, and never the checkout.

```bash
oma-space uninstall                  # bar back to stock, plugin still installed
oma-space uninstall --purge          # and delete the installed plugin directory
oma-space uninstall --dry-run        # say what would change, change nothing
```

## Options

| option | notes |
|---|---|
| `--no-omarchy` | leave `omarchy.workspaces` off the bar as well — for a bar that never had it |
| `--purge` | also delete `~/.config/omarchy/plugins/<id>/` |
| `--dry-run` | print what would change and write nothing. Never prompts |
| `--yes`, `-y` | do not ask. For scripts and unattended removals |

## In Python

```python
import uninstall

layout, notes = uninstall.restore_layout(layout, pid)
```

Takes and returns a plain `bar.layout` dict, so the restore rule is testable without
a shell, a bar, or a config file.
