# personal-claude-skills

Personal Claude skills, preferences, and context for akshaykumar09081993.

## About
This repo is automatically read by Claude Code at the start of every session.
Add custom instructions, skill definitions, project context, or preferences here.

## How to use
- Add markdown files with instructions or context you want Claude to always know
- Claude will read this repo at session start

## Push everything reusable here
Anything reusable built with Claude that isn't already here — skills, helper scripts,
reference docs, persistent context — should be committed and pushed to this repo, so every
future session automatically has it (a SessionStart hook pulls this repo and installs the
skills on each launch).

## Available skills

| Skill | What it does |
|-------|--------------|
| [`accessing-google-drive`](skills/accessing-google-drive/SKILL.md) | List, search, browse, read, and download the user's Google Drive files. Bypasses the broken `drivemcp` MCP by calling the Google Drive REST API with the token stored in the macOS keychain. |

---

## Standard way to create skills (read this before authoring a new skill)

**All sessions: when asked to create a skill, always use the Anthropic Agent
Skills standard format below — do not invent an ad-hoc format.** This is the same
structure the Anthropic **skill-creator** produces. If the `skill-creator` skill is
installed in the session, invoke it; otherwise follow this format by hand (it is
identical output).

### Layout
```
skills/
  <skill-name>/            # lowercase-hyphenated, matches the frontmatter name
    SKILL.md               # required — instructions + YAML frontmatter
    scripts/               # optional — bundled executable helpers
    references/            # optional — extra docs loaded on demand
    assets/                # optional — templates/files the skill outputs
```

### SKILL.md frontmatter (required)
```yaml
---
name: <skill-name>            # lowercase, hyphens, matches the directory name
description: >-               # WHAT it does + WHEN to use it (this is what gets matched).
  Write in the third person. Lead with the trigger conditions so a future session
  knows when to reach for it. Mention key constraints (OS, auth, gotchas).
---
```

### Body guidance
- Start with **why the skill exists** / the problem it solves.
- Give a **Quick start** with copy-pasteable commands.
- Document the **manual fallback** so it works even if a bundled script is missing.
- Note **auth, prerequisites, and platform constraints**.
- Keep instructions concrete and runnable; prefer bundled scripts over long prose.

### Authoring checklist
1. Pick a clear lowercase-hyphenated name; create `skills/<name>/`.
2. Write `SKILL.md` with the frontmatter above; make the `description` trigger-rich.
3. Add and `chmod +x` any helper scripts under `scripts/`.
4. **Test the scripts actually run** before committing.
5. Add a row to the **Available skills** table above.
6. Commit and push to this repo.
