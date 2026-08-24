# install

`oma-space install` — the tabs onto the bar, in place of Omarchy's strip.
Rationale lives in prd.md F6; this is the interface.

Omarchy has no install hook: `omarchy plugin add` clones a directory and stops.
So the takeover is a verb, run once after installing and again whenever the
plugin directory changes.

## Contract

- The installed plugin directory on **stdout**, once. Nothing else on stdout, ever.
- Diagnostics to **stderr**. Exit `0`, `1` on failure, `2` on usage.
- **Nothing is changed before you agree to it.** The whole plan — the directory it
  would install, what leaves the bar, what goes on it, where the backup lands — is
  printed first, and then it asks. Answering anything but `y` exits `1` having
  written nothing: not the config, not the plugin directory.
- **Without a terminal it refuses rather than assumes.** A piped or scripted run
  with no `--yes` prints the plan, says it will not proceed unattended, and stops.
- **shell.json is never written without a backup** beside it at `shell.json.bak`. It is
  written once and then left alone: what is worth keeping is the bar as it stood before
  oma-space first touched it, which a second run would otherwise overwrite with install's
  own output. The write is atomic — a temp file in the same directory, then `os.replace` —
  so no reader ever sees a half-written bar.
- **The strip lands where Omarchy's stood.** `omarchy.workspaces` is removed and the
  tabs are inserted at its position, in its section, so nothing else on the bar moves.
- **Idempotent.** Tabs already placed are taken out and re-placed: running install
  twice leaves one strip, not two.
- **Nothing outside the bar layout is touched.** Other widgets, `position`,
  `transparent`, `centerAnchor` and every other key are carried through untouched.
- **A development symlink is replaced by a real directory.** The shell's own
  validator refuses a plugin folder containing symlinks, and `inotifywait -r` does
  not follow one, so a symlinked checkout never live-reloads. Only the link is
  removed; the working tree it pointed at is the source being copied.

```bash
oma-space install                    # nine tabs and the scratch tab, where omarchy.workspaces was
oma-space install --dry-run          # the layout it would write, on stdout
oma-space install --tabs 5           # workspaces 1-5 only
oma-space install --layout-only      # rewrite the bar; leave the directory alone
oma-space install --yes              # unattended
```

## Options

| option | notes |
|---|---|
| `--tabs N` | numbered tabs to place, 1–10. Default 9 — the scratch tab is workspace 10, so a tenth numbered tab would be a second tab on the same workspace |
| `--no-scratch` | place no scratch tab |
| `--section S` | `left`, `center` or `right`. Default: wherever `omarchy.workspaces` was, else `left` |
| `--keep-omarchy` | leave `omarchy.workspaces` on the bar beside the tabs |
| `--layout-only` | rewrite the bar layout only, for a checkout you are still editing in place |
| `--dry-run` | print the layout that would be written and change nothing. Never prompts, because it changes nothing |
| `--yes`, `-y` | do not ask. For scripts, images and unattended installs |

## After it runs

The verb asks the running shell to rescan and reload its config. A layout change
lands on that alone; a **changed `.qml` file needs `omarchy restart shell`**, because
the shell keeps the component it already compiled.

## In Python

```python
import install

entries = install.tab_entries(pid, tabs=9, scratch=True)
layout, notes = install.rewrite_layout(layout, pid, entries)
```

`rewrite_layout` takes and returns a plain `bar.layout` dict, so the placement rule
is testable without a shell, a bar, or a config file.
