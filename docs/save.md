# save

`oma-space save <name>` — a definition onto disk, under a name the user chose.
Rationale lives in prd.md F3; this is the interface.

Capture only reads. This verb is the other half: it decides *where* a definition
goes, and it is the only thing in the helper that writes to
`~/.config/oma-space/workspaces/`.

## Contract

- One path on **stdout**, the file that was written. Nothing else on stdout, ever.
- Diagnostics to **stderr**. Exit `0`, `1` on failure, `2` on usage, and **`3` when
  the workspace already holds a configuration** — a refusal the caller can act on
  rather than an error, which is what lets the widget offer "Save again to replace"
  instead of a dead end.
- **Nothing is written unless the definition validates.** A capture with no name,
  no index, or an unknown layout is refused whole — never half-written.
- **An occupied workspace is never replaced without `--force`.** Capture never
  reads what is already on disk and never merges into it, so a replace discards
  hand-edited fields; that is the user's call to make, not the tool's.
- The write is atomic — a temp file in the same directory, then `os.replace` — so
  no reader of the directory ever sees a partial definition.

```bash
oma-space save --index 1 "Coding"            # capture and save in one action
oma-space capture 1 | oma-space save "Coding"
oma-space save "Coding" < reviewed.json      # save a definition edited in between
```

## Options

| option | notes |
|---|---|
| `--index N` | capture workspace `N` now, in-process. Without it the definition is read from **stdin** |
| `--icon GLYPH` | the icon the panel shows beside the name; capture cannot know it |
| `--force` | overwrite an existing definition |

Both input paths converge on the same object: `--index` calls
`capture.workspace()` directly, stdin goes through `Workspace.from_capture()`.
Piping exists so the definition can be reviewed — or edited — between reading and
writing, which is what makes "new file, overwrite, or discard" a real choice.

## Where it goes

Slot N, at `N.json`. The workspace is the identity: a workspace holds one
configuration or none, so there is no question of *which* file a save lands in and
no filename to derive from a name. `name` is a label — renaming moves nothing, and
two workspaces may share a name without anything breaking, because nothing is ever
looked up by one.

Saving therefore replaces rather than adds. `--force` is about the workspace, not
the name: `save "Writing" --index 3` on a workspace holding "Coding" is refused
until asked twice, and then workspace 3 is Writing.

`XDG_CONFIG_HOME` is honoured, and read per call rather than at import.

## On disk

`store.py` writes `Workspace.to_json()` **indented**, unlike the single-line
stdout the QML side parses: these files are meant to be opened and edited by
hand. Every key is present at its default, so a hand edit is a change to a
visible field rather than an addition to a shape the reader has to guess.

## Checks

```bash
XDG_CONFIG_HOME=$(mktemp -d) oma-space save --index 1 "Coding"   # prints one path
oma-space capture 1 | oma-space save "Coding"; echo $?           # 3 — workspace taken
oma-space capture 1 | oma-space save "Coding" --force; echo $?   # 0
echo 'not json' | oma-space save "Broken"; echo $?               # 1, nothing written
jq -e . ~/.config/oma-space/workspaces/1.json >/dev/null         # valid JSON
```
