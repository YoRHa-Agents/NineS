# Agent Skill Installation

<!-- auto-updated: version from src/nines/__init__.py -->

NineS can be installed as an Agent Skill into Cursor or Claude Code, allowing AI coding assistants to use NineS capabilities directly from your IDE.

---

## What is an Agent Skill?

An Agent Skill is a set of instructions and command definitions that teach an AI coding assistant how to use a tool. When installed:

- **Cursor** reads `.cursor/skills/nines/SKILL.md` and per-command workflow files
- **Claude Code** reads `.claude/commands/nines/*.md` slash commands and `CLAUDE.md` context

The skill enables the AI assistant to run evaluations, collect information, analyze codebases, and execute self-improvement iterations on your behalf.

---

## Installing for Cursor

```bash
nines install --target cursor
```

This creates the following structure in your project:

```
.cursor/
└── skills/
    └── nines/
        ├── SKILL.md              # Main skill entry point
        ├── manifest.json         # Version manifest
        ├── commands/
        │   ├── eval.md           # nines eval workflow
        │   ├── collect.md        # nines collect workflow
        │   ├── analyze.md        # nines analyze workflow
        │   ├── self-eval.md      # nines self-eval workflow
        │   ├── iterate.md        # nines iterate workflow
        │   └── install.md        # nines install workflow
        └── references/
            ├── capabilities.md   # Capability model reference
            └── config.md         # Configuration reference
```

Once installed, mention any NineS command in Cursor (e.g., "run nines eval on my tasks") and the assistant will read the skill workflow and execute it.

---

## Installing for Claude Code

```bash
nines install --target claude
```

This creates slash commands and updates `CLAUDE.md`:

```
.claude/
└── commands/
    └── nines/
        ├── eval.md
        ├── collect.md
        ├── analyze.md
        ├── self-eval.md
        ├── iterate.md
        ├── install.md
        └── manifest.json
```

A NineS section is also appended to `CLAUDE.md` with usage context. Use commands like `/nines:eval`, `/nines:collect`, etc.

---

## Installing for All Runtimes

Install for every detected runtime at once:

```bash
nines install --target all
```

NineS auto-detects available runtimes by checking for `.cursor/` or `.claude/` directories and runtime binaries on `$PATH`.

---

## Global Installation

Install the skill globally (applies to all projects):

```bash
nines install --target cursor --global
```

Global installations write to `~/.cursor/skills/nines/` or `~/.claude/commands/nines/`.

---

## Verifying the Skill is Active

### Cursor

1. Open a project where the skill is installed
2. Ask the assistant: "What NineS commands are available?"
3. The assistant should list all six commands from the SKILL.md

### Claude Code

1. Type `/nines:` in the Claude Code prompt
2. Auto-complete should show available NineS commands
3. Run `/nines:self-eval --report` to test

---

## Updating Skills on Version Upgrade

When you update NineS to a new version, re-run the install command:

```bash
pip install -e .  # or uv sync
nines install --target cursor
```

NineS detects the existing installation and performs an in-place upgrade. The version in `manifest.json` is updated automatically.

!!! tip "Dry Run"
    Preview what an install or upgrade will do without writing files:
    ```bash
    nines install --target cursor --dry-run
    ```

---

## Uninstalling

Remove the NineS skill from a specific runtime:

```bash
nines install --target cursor --uninstall
```

Remove from all runtimes:

```bash
nines install --target all --uninstall
```

For Claude Code, this also removes the NineS section from `CLAUDE.md`.

---

## Version Management

| Scenario | Behavior |
|----------|----------|
| Fresh install | Creates all files |
| Same version | Skips with message (use `--force` to reinstall) |
| Upgrade | In-place update of all files |
| Downgrade | Blocked by default (use `--force` to override) |
