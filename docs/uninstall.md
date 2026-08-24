# uninstall

`oma-space uninstall` — the tabs off the bar, and Omarchy's strip back.
Rationale lives in prd.md F6; this is the interface.

Not optional, and not something Omarchy can do for us. `install` removes
`omarchy.workspaces` from the bar layout, and `omarchy plugin remove` never puts it
back — worse, the shell's disable path drops **one** layout entry per plugin id, so a
strip of ten tabs would leave nine dead slots behind and a bar with no workspace
navigation at all.

## Contract

- Diagnostics to **stderr**. Exit `0`, `1` on failure, `2` on usage.
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
| `--dry-run` | print what would change and write nothing |

## In Python

```python
import uninstall

layout, notes = uninstall.restore_layout(layout, pid)
```

Takes and returns a plain `bar.layout` dict, so the restore rule is testable without
a shell, a bar, or a config file.
