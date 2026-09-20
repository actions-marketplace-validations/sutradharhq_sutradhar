---
description: Run one mechanized improvement round - read the stop rule, pick one target from the defect corpus, author the case before the guard, prove it through the four-command selection gate, and commit locally for review. Use when asked to run an improvement round or propose a guard.
---

# Improvement round

The procedure is kept in one canonical file so that every harness reads the
same text. Read it now, in full, and follow it:

    ${CLAUDE_PLUGIN_ROOT}/skills/improvement-round/improvement-round.md

That file is a byte-identical copy of `agent/skills/improvement-round.md` in
<https://github.com/sutradharhq/sutradhar>, kept in step by
`plugin/sync_guards.py`. If it is not there, this copy of the plugin is
incomplete. Say so rather than improvising the procedure from memory - the
value of the loop is in its specifics, and a half-remembered version of it
is a code review with a longer name.

The corpus the round reads and the guards it calls for are available as MCP
tools from the `sutradhar-guards` server this plugin registers, and as CLIs
under `python/sutradhar_guards/`.
