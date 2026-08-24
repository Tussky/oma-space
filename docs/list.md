# list

`oma-space list [--json]` — all ten workspaces and what is saved for each. The
other half of `live` (prd.md F1): what is *saved*, whether or not anything of
theirs is running.

## Contract

- `--json`: one JSON **array of exactly ten** on stdout, single line, in index
  order, **normalised** — round-tripped through the model, every key present at
  its default, so the panel never guards against a missing field.
- **An empty slot is a Workspace with no name**, not a gap and not `null`. A
  workspace nobody has saved yet is the normal state, so the renderer draws ten
  rows and reads `name === ""` for "free", with no second shape to handle.
- Without `--json`: one line per workspace, occupied or empty, for a terminal.
- A file that fails to parse is named on **stderr** and skipped. One bad
  definition never costs the user the rest of them, and never breaks the array.
- Exit `0` even when nothing is saved — an empty directory is a first run, not an
  error.

```json
[{"index":1,"name":"Coding","icon":"","layout":"scrolling","shortcut":"Super+1","apps":[…]},
 {"index":2,"name":"","icon":"","layout":"dwindle","shortcut":"Super+2","apps":[]}, …]
```

```
  1  Coding            3 apps  scrolling
  2  —                 empty
```

## Checks

```bash
oma-space list --json | jq -e 'length == 10'
test "$(oma-space list --json | wc -l)" = 1
oma-space list --json | jq -e '[.[].index] == [range(1;11)]'
```
