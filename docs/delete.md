# delete

`oma-space delete <index>` — empty a workspace's slot.
Rationale lives in prd.md F2; this is the interface.

The third write, after capture and edit, and the only one that takes something
away.

## Contract

- The path it emptied on **stdout**, once. Nothing else on stdout, ever.
- Diagnostics to **stderr**. Exit `0`, `1` on failure, `2` on usage.
- **The workspace is untouched.** Whatever is open on it stays open, stays where
  it is, and keeps running. This deletes the description, not the desk.
- **A slot is emptied, never removed.** The store is the ten workspaces, so
  workspace `N` goes back to having no configuration rather than disappearing.
- **An already-empty slot is not an error.** It says so on stderr and exits `0`,
  so deleting twice is the same as deleting once.
- The name that went is named on stderr, because by the time you read it there is
  nothing left to look it up in.

```bash
oma-space delete 3
# delete: deleted "Coding" from workspace 3
# /home/you/.config/oma-space/workspaces/3.json
```

## In the panel

The `Delete` button asks twice: the first press turns it into `Delete?` and says
in the status line what will go and what will not. Any other action — picking a
different workspace, closing the panel — takes the question back. There is no
confirmation dialog, because a one-word question does not need a second surface.

## In Python

```python
import store

path, errors = store.clear(3)
```

The verb is a thin wrapper: emptying a slot is the store's own operation, and the
CLI exists for the caller that cannot import it (prd.md constraint 2).
