---
name: holospec
description: Schema-driven workflow guidance for spec-driven changes. Use whenever this project has a holospec/ or openspec/ directory at its root and the user asks to plan, propose, scope, design, implement, or fix a bug/feature - even if they don't say "holospec" or "openspec" by name. Also use when they explicitly mention HoloSpec, OpenSpec, or ask to continue/resume a tracked change. Explains how to call the holospec CLI to discover actions and work them in order.
---

# HoloSpec Protocol

This project uses HoloSpec for schema-driven workflow guidance. HoloSpec is a
stateless lookup tool — it never tracks progress or reads your work-in-progress
files. You are responsible for all file I/O and for judging what's done.

## Protocol

1. Run `holospec workflow` to see the full list of actions, their
   dependencies, and the order to work them in. Its output includes
   `root` — use that path as the base for every file you read or write;
   never assume a directory name yourself.
2. Run `holospec action <id>` for the action you're about to work on. This
   also returns `root`, plus its instruction, checklist, and any
   file-generation metadata (`generates`/`template`) verbatim from the
   schema. Join `generates` paths against `root`. The checklist is that
   action's definition of done.
3. Do the work yourself: read/write files under `root`, then check your work
   against the action's checklist before deciding it's complete. Move to the
   next action in the order `workflow` reported once every checklist item
   holds.
4. Repeat for each action as your own judgment dictates, using each action's
   checklist as the completion bar. HoloSpec never tells you "you're done" or
   "what's next" — that's on you.

Any domain-specific rules for a given action (e.g. how to merge documents,
validation rules, file layout conventions) live in that schema's own fields —
read and follow those rather than assuming a fixed convention across schemas.

## Understanding the tool itself

If you're helping a user understand how HoloSpec's schema.yaml/config.yaml
work — to create a new one for a project or extend an existing one — rather
than executing a workflow, run `holospec explain` first. It explains how
the two files relate and returns the JSON Schema field reference for each,
so you can validate field names and shapes against the real format instead
of guessing from an example.

After every edit to a schema, run `holospec schemacheck <path>` before
considering the change done.
