# CLAUDE.md

Guidance for any Claude agent working in this repository.

## What this is

An Omarchy plugin. **`prd.md` is the source of truth for product context** — read it before doing
anything substantive in this repo.

## Working agreement

- **Read `prd.md` first.** It holds the product context, scope, and the reasoning behind decisions.
- **Surface contradictions, don't paper over them.** If something the user says contradicts `prd.md`,
  or if the PRD itself is ambiguous or internally inconsistent, **ask the user** rather than guessing
  or silently picking an interpretation.
- **Keep the PRD current.** When the user resolves a contradiction or changes direction, update
  `prd.md` to match — the PRD should never drift out of sync with reality.
- **Work is file-scoped and verb-scoped.** The user typically hands over a specific file along with
  one of these verbs. Do that verb, on that file, and don't silently widen the scope:
  - **audit** — review it, report findings; don't rewrite unless asked
  - **expand** — build out what's already there
  - **integrate** — wire it into the rest of the system
  - **implement** — write the thing
  - **suggest** — propose options; don't apply them yet
- If the verb is unclear, ask which one is meant.
