# get-shit-done (GSD) Deep Analysis

> Research task T02 — Comprehensive analysis of the GSD meta-prompting and context-engineering framework for NineS adoption.
>
> **Source:** `/home/agent/reference/get-shit-done`
> **Last updated:** 2026-04-11

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Agent Skill Mechanism](#2-agent-skill-mechanism)
3. [Multi-Runtime Installation](#3-multi-runtime-installation)
4. [Workflow Orchestration](#4-workflow-orchestration)
5. [SDK for Headless Execution](#5-sdk-for-headless-execution)
6. [Config-Driven Behavior](#6-config-driven-behavior)
7. [Artifact Graph](#7-artifact-graph)
8. [Hooks System](#8-hooks-system)
9. [Security Patterns](#9-security-patterns)
10. [Design Patterns for NineS Adoption](#10-design-patterns-for-nines-adoption)

---

## 1. Architecture Overview

GSD is a JS/TS meta-prompting framework that delivers a structured software development workflow (discuss → plan → execute → verify → ship) to AI coding agents across 14+ host runtimes (Claude Code, Cursor, Codex, Copilot, Windsurf, Augment, Trae, Qwen, Cline, OpenCode, Gemini, Kilo, Antigravity, CodeBuddy).

**Repository structure:**

```
get-shit-done/
├── bin/install.js           # Single 6600+ line installer with all runtime converters
├── commands/gsd/*.md        # 74 Claude-native command definitions (source of truth)
├── agents/                  # 31 specialized agent definitions (gsd-executor, gsd-planner, etc.)
├── get-shit-done/
│   ├── workflows/*.md       # 72 detailed workflow implementations (expanded versions)
│   ├── references/*.md      # 44 reference documents (gates, patterns, configs)
│   ├── templates/*.md       # 36 artifact templates (STATE, ROADMAP, PLAN, SUMMARY, etc.)
│   ├── contexts/*.md        # 3 context modes (dev, research, review)
│   └── bin/                 # gsd-tools.cjs runtime utility
├── hooks/                   # 10 event-driven hook scripts
├── sdk/                     # TypeScript SDK for programmatic/headless execution
└── tests/                   # 150+ test files covering all features
```

The core innovation is **single-source multi-target**: commands are authored once in Claude Code markdown format (`commands/gsd/*.md`), then the installer transpiles them into the skill format of each target runtime at install time.

---

## 2. Agent Skill Mechanism

### 2.1 Command Definition Format (Source of Truth)

Each command in `commands/gsd/*.md` uses a YAML frontmatter + XML body structure:

```yaml
---
name: gsd:execute-phase
description: Execute all plans in a phase with wave-based parallelization
argument-hint: "<phase-number> [--wave N] [--gaps-only] [--interactive]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - Task
  - TodoWrite
  - AskUserQuestion
---
```

**File:** `commands/gsd/execute-phase.md` (lines 1-15)

The body uses semantic XML tags: `<objective>`, `<execution_context>`, `<runtime_note>`, `<context>`, `<process>`, `<success_criteria>`. The `<execution_context>` tag references expanded workflow files via `@~/.claude/get-shit-done/workflows/execute-phase.md`.

### 2.2 Command-to-Skill Conversion Pipeline

At install time, `bin/install.js` reads each `commands/gsd/*.md` file and applies a runtime-specific converter function. There are 10+ converter functions, each implementing a distinct protocol:

| Converter Function | Target Runtime | Key Transformations |
|---|---|---|
| `convertClaudeCommandToClaudeSkill` | Claude Code | Minimal: convert `gsd:xxx` → `gsd-xxx`, preserve YAML list format |
| `convertClaudeCommandToCursorSkill` | Cursor | Add adapter header, `$ARGUMENTS` → `{{GSD_ARGS}}`, tool name mapping, `.claude/` → `.cursor/` |
| `convertClaudeCommandToWindsurfSkill` | Windsurf | Adapter header, `Bash` → `Shell`, `Edit` → `StrReplace`, brand replacement |
| `convertClaudeCommandToCopilotSkill` | Copilot | YAML list → comma-separated string, Claude → Copilot tool name mapping |
| `convertClaudeCommandToCodexSkill` | Codex | YAML → plain markdown, agent sandbox config |
| `convertClaudeCommandToAugmentSkill` | Augment | `Bash` → `launch-process`, `Edit` → `str-replace-editor`, `Read` → `view` |
| `convertClaudeCommandToAntigravitySkill` | Antigravity | `.claude/` → `.gemini/antigravity/`, Gemini tool names |
| `convertClaudeCommandToTraeSkill` | Trae | Tool mapping, adapter header |
| `convertClaudeCommandToCodebuddySkill` | CodeBuddy | Tool mapping, adapter header |
| `convertClaudeCommandToQwenSkill` | Qwen | `CLAUDE.md` → `QWEN.md`, `.claude/` → `.qwen/` |

**File:** `bin/install.js` (lines 856-1700)

### 2.3 Adapter Header Pattern

For runtimes without native slash-command support (Cursor, Windsurf, Augment, Trae, CodeBuddy), the converter injects an **adapter header** that teaches the agent how to invoke the skill:

```markdown
<cursor_skill_adapter>
## A. Skill Invocation
- This skill is invoked when the user mentions `gsd-execute-phase` or describes a task matching this skill.
- Treat all user text after the skill mention as `{{GSD_ARGS}}`.
- If no arguments are present, treat `{{GSD_ARGS}}` as empty.

## B. Subagent Spawning
When the workflow needs to spawn a subagent:
- Use `Task(subagent_type="generalPurpose", ...)`
- The `model` parameter maps to Cursor's model options (e.g., "fast")
</cursor_skill_adapter>
```

**File:** `bin/install.js` (lines 1100-1135, Cursor adapter; lines 1228-1252, Windsurf adapter)

This pattern is critical because it bridges the gap between runtimes that have `$ARGUMENTS` built-in (Claude Code) and those that require soft invocation via conversational context.

### 2.4 Expanded Workflows vs. Compact Commands

The `commands/gsd/*.md` files are compact summaries (1-5 KB) that reference expanded workflow files in `get-shit-done/workflows/*.md` (5-63 KB). The command says "execute the workflow from @~/.claude/get-shit-done/workflows/execute-phase.md end-to-end" and the agent reads the full instructions at runtime.

This two-layer design means the command is a "launcher" that sets the scope, tools, and arguments, while the workflow contains the actual step-by-step instructions. GSD installs both layers — the command goes into the skills directory, the workflow into a reference directory.

---

## 3. Multi-Runtime Installation

### 3.1 Directory Mapping

Each runtime has a well-defined directory structure. The `getDirName()` function maps runtime identifiers to directory names:

| Runtime | Local Dir | Global Dir | Skills Dir | Agents Dir |
|---|---|---|---|---|
| Claude Code | `.claude` | `~/.claude` | `.claude/commands/gsd/` | `.claude/agents/` |
| Cursor | `.cursor` | `~/.cursor` | `.cursor/skills/` | `.cursor/agents/` |
| Windsurf | `.windsurf` | `~/.codeium/windsurf/` | `.windsurf/skills/` | `.windsurf/agents/` |
| Copilot | `.github` | `~/.copilot` | `.github/skills/` | `.github/agents/` |
| Codex | `.codex` | `~/.codex` | `.codex/skills/` | `.codex/agents/` |
| Augment | `.augment` | `~/.augment` | `.augment/skills/` | `.augment/agents/` |
| Trae | `.trae` | `~/.trae` | `.trae/skills/` | `.trae/agents/` |
| Qwen | `.qwen` | `~/.qwen` | `.qwen/commands/gsd/` | `.qwen/agents/` |
| Cline | `.cline` | `~/.cline` | `.cline/rules/` | — |
| OpenCode | `.opencode` | `~/.config/opencode/` | `.opencode/commands/gsd/` | `.opencode/agents/` |
| Gemini | `.gemini` | `~/.gemini` | `.gemini/skills/` (TOML) | `.gemini/agents/` |

**File:** `bin/install.js` (lines 138-188)

### 3.2 Content Transformation Pipeline

When a `.md` file is being installed, it goes through a runtime-specific content transformation pipeline (`bin/install.js` lines 4100-4180):

1. **Path replacement**: `~/.claude/` → runtime-specific global path; `./.claude/` → runtime-specific local path
2. **Tool name mapping**: Claude tool names → runtime equivalents (e.g., `Bash` → `Shell` for Cursor/Windsurf)
3. **Brand replacement**: `Claude Code` → runtime brand name; `CLAUDE.md` → runtime config file name
4. **Command name normalization**: `gsd:xxx` → `gsd-xxx` for runtimes without colon support
5. **Agent reference neutralization**: `neutralizeAgentReferences()` replaces `CLAUDE.md` with the runtime's config file
6. **Frontmatter format conversion**: YAML multiline list → comma-separated (Copilot), YAML → TOML (Gemini)
7. **Adapter header injection**: For runtimes without native slash commands

### 3.3 Tool Name Mapping Tables

GSD maintains per-runtime tool name mappings as lookup objects. Example for Copilot (`bin/install.js` lines 38-53):

```javascript
const claudeToCopilotTools = {
  Read: 'read',
  Write: 'edit',
  Edit: 'edit',
  Bash: 'execute',
  Grep: 'search',
  Glob: 'search',
  Task: 'agent',
  WebSearch: 'web',
  WebFetch: 'web',
  TodoWrite: 'todo',
  AskUserQuestion: 'ask_user',
  SlashCommand: 'skill',
};
```

And for Augment (`bin/install.js` lines 1294-1318):

```javascript
const claudeToAugmentTools = {
  Bash: 'launch-process',
  Edit: 'str-replace-editor',
  AskUserQuestion: null,      // No direct equivalent
  SlashCommand: null,
  TodoWrite: 'add_tasks',
};
```

The `null` mapping means the tool is excluded; the converter then replaces body references with alternative approaches (e.g., `AskUserQuestion` → "conversational prompting").

---

## 4. Workflow Orchestration

### 4.1 Phase Loop

The core lifecycle is a state machine with phases: **discuss → research → plan → execute → verify → advance**.

The `PhaseRunner` class in `sdk/src/phase-runner.ts` (line 65) implements this:

```typescript
export class PhaseRunner {
  async run(phaseNumber: string, options?: PhaseRunnerOptions): Promise<PhaseRunnerResult> {
    // ── Init: query phase state ──
    phaseOp = await this.tools.initPhaseOp(phaseNumber);

    // ── Step 1: Discuss (unless skipped) ──
    // ── Step 2: Research (unless skipped or gate says skip) ──
    // ── Step 3: Plan ──
    // ── Step 4: Plan-check ──
    // ── Step 5: Execute ──
    // ── Step 6: Verify ──
    // ── Step 7: Advance ──
  }
}
```

Each step is gated by config flags. The `PhaseRunner` reads config from `.planning/config.json` and skips steps based on boolean flags:

- `workflow.skip_discuss` — skip the discuss phase entirely
- `workflow.research` — enable/disable research step
- `workflow.plan_check` — enable/disable plan verification before execution
- `workflow.verifier` — enable/disable post-execution verification
- `workflow.auto_advance` — automatically advance to the next phase on success

**File:** `sdk/src/phase-runner.ts` (lines 84-120)

### 4.2 Wave-Based Parallel Execution

Within the execute phase, work is organized into **waves** — groups of plans that can execute in parallel because they have no inter-dependencies.

From `get-shit-done/workflows/execute-phase.md` (lines 1-7):

> Execute all plans in a phase using wave-based parallel execution. Orchestrator stays lean — delegates plan execution to subagents.
>
> Orchestrator coordinates, not executes. Each subagent loads the full execute-plan context. Orchestrator: discover plans → analyze deps → group waves → spawn agents → handle checkpoints → collect results.

Each plan's YAML frontmatter includes a `wave` number and a `depends_on` list. The execute-phase workflow:

1. Discovers all PLAN.md files in the phase directory
2. Reads `wave` and `depends_on` from each plan's frontmatter
3. Groups plans by wave number
4. Executes each wave sequentially; plans within a wave run in parallel via subagents
5. After all waves complete, runs verification

The orchestrator can filter execution with `--wave N` (run only one wave) or `--gaps-only` (run only gap closure plans created by verification failures).

**File:** `commands/gsd/execute-phase.md` (lines 16-58)

### 4.3 Runtime-Specific Subagent Dispatch

The workflow adapts subagent spawning to the host runtime. From `get-shit-done/workflows/execute-phase.md` (lines 9-24):

- **Claude Code**: `Task(subagent_type="gsd-executor", ...)` — blocks until complete
- **Copilot**: Sequential inline execution (subagent spawning unreliable)
- **Other runtimes**: Check for `Task` tool availability at runtime; fall back to sequential inline execution

### 4.4 Milestone Runner

Above individual phases, the SDK provides a milestone runner that iterates over all incomplete phases, executing each through the full lifecycle. From `sdk/src/index.ts` (lines 168-248):

```typescript
async run(prompt: string, options?: MilestoneRunnerOptions): Promise<MilestoneRunnerResult> {
  const initialAnalysis = await tools.roadmapAnalyze();
  const incompletePhases = this.filterAndSortPhases(initialAnalysis.phases);

  while (currentPhases.length > 0) {
    const result = await this.runPhase(phase.number, options);
    // Re-discover phases after each completion (catch dynamically inserted phases)
    const updatedAnalysis = await tools.roadmapAnalyze();
    currentPhases = this.filterAndSortPhases(updatedAnalysis.phases);
  }
}
```

The re-discovery after each phase completion is notable — it handles dynamically inserted phases that may appear during execution.

---

## 5. SDK for Headless Execution

### 5.1 Architecture

The SDK (`sdk/`) provides a TypeScript API for running GSD workflows programmatically via the Claude Agent SDK. Core modules:

| Module | Purpose | File |
|---|---|---|
| `index.ts` | `GSD` class — public API composing all modules | `sdk/src/index.ts` |
| `session-runner.ts` | Orchestrates `query()` calls to Agent SDK | `sdk/src/session-runner.ts` |
| `phase-runner.ts` | Phase lifecycle state machine | `sdk/src/phase-runner.ts` |
| `plan-parser.ts` | Parses PLAN.md YAML frontmatter + XML tasks | `sdk/src/plan-parser.ts` |
| `prompt-builder.ts` | Assembles executor prompts from parsed plans | `sdk/src/prompt-builder.ts` |
| `config.ts` | Loads `.planning/config.json` with defaults merge | `sdk/src/config.ts` |
| `context-engine.ts` | Resolves context files per phase type | `sdk/src/context-engine.ts` |
| `event-stream.ts` | Typed event bus with transport support | `sdk/src/event-stream.ts` |
| `tool-scoping.ts` | Maps phase types to allowed tool sets | `sdk/src/tool-scoping.ts` |
| `research-gate.ts` | Validates RESEARCH.md for unresolved questions | `sdk/src/research-gate.ts` |
| `prompt-sanitizer.ts` | Prompt injection scanning for SDK inputs | `sdk/src/prompt-sanitizer.ts` |

### 5.2 Execution Model

The SDK uses the `@anthropic-ai/claude-agent-sdk` `query()` function. From `sdk/src/session-runner.ts` (lines 55-98):

```typescript
export async function runPlanSession(plan, config, options, agentDef, eventStream, streamContext) {
  const executorPrompt = buildExecutorPrompt(plan, agentDef);
  const allowedTools = options?.allowedTools ?? parseAgentTools(agentDef);
  const model = resolveModel(options, config);

  const queryStream = query({
    prompt: `Execute this plan:\n\n${plan.objective}`,
    options: {
      systemPrompt: { type: 'preset', preset: 'claude_code', append: executorPrompt },
      allowedTools,
      permissionMode: 'bypassPermissions',
      maxTurns,
      maxBudgetUsd,
      cwd,
    },
  });

  return processQueryStream(queryStream, eventStream, streamContext);
}
```

Key design decisions:
- Uses `preset: 'claude_code'` as the base system prompt, appending GSD-specific instructions
- Tool restrictions are derived from agent definitions or per-phase defaults
- Budget and turn limits are configurable per session
- The async iterable stream maps SDK messages to typed GSD events

### 5.3 Event System and Transports

The `GSDEventStream` extends `EventEmitter` with typed events (`GSDEventType.MilestoneStart`, `SessionComplete`, `CostUpdate`, etc.) and supports pluggable transports:

- `CLITransport` — renders events to terminal (progress bars, cost summaries)
- `WSTransport` — streams events over WebSocket for UI dashboards

**File:** `sdk/src/event-stream.ts` (lines 1-80)

### 5.4 Tool Scoping per Phase

Different phases get different tool access, enforced by `tool-scoping.ts` (lines 17-23):

```typescript
const PHASE_DEFAULT_TOOLS: Record<PhaseType, string[]> = {
  [PhaseType.Research]: ['Read', 'Grep', 'Glob', 'Bash', 'WebSearch'],
  [PhaseType.Execute]:  ['Read', 'Write', 'Edit', 'Bash', 'Grep', 'Glob'],
  [PhaseType.Verify]:   ['Read', 'Bash', 'Grep', 'Glob'],
  [PhaseType.Discuss]:  ['Read', 'Bash', 'Grep', 'Glob'],
  [PhaseType.Plan]:     ['Read', 'Write', 'Bash', 'Glob', 'Grep', 'WebFetch'],
};
```

Research is read-only + web search; verify is read-only; execute gets full write access. This implements the principle of least privilege per phase.

---

## 6. Config-Driven Behavior

### 6.1 Config Structure

Configuration lives in `.planning/config.json` and is loaded with an "absent = enabled" defaults pattern. From `sdk/src/config.ts` (lines 60-94):

```typescript
export const CONFIG_DEFAULTS: GSDConfig = {
  model_profile: 'balanced',
  commit_docs: true,
  parallelization: true,
  search_gitignored: false,
  git: {
    branching_strategy: 'none',
    phase_branch_template: 'gsd/phase-{phase}-{slug}',
  },
  workflow: {
    research: true,
    plan_check: true,
    verifier: true,
    auto_advance: false,
    skip_discuss: false,
    max_discuss_passes: 3,
  },
  hooks: {
    context_warnings: true,
  },
  agent_skills: {},
};
```

### 6.2 Three-Level Deep Merge

Config loading performs a structured merge — top-level fields are overwritten, but nested objects (`git`, `workflow`, `hooks`, `agent_skills`) are merged one level deep. This means a user only needs to specify the fields they want to override.

**File:** `sdk/src/config.ts` (lines 142-161)

### 6.3 Model Profile Resolution

The `model_profile` field maps to concrete model IDs via a profile map in `session-runner.ts` (lines 28-34):

```typescript
const profileMap: Record<string, string> = {
  balanced: 'claude-sonnet-4-6',
  quality: 'claude-opus-4-6',
  speed: 'claude-haiku-4-5',
};
```

Priority chain: explicit `--model` flag > `model_profile` in config > SDK default.

---

## 7. Artifact Graph

### 7.1 File-Backed State System

GSD maintains project state entirely through a file system graph under `.planning/`. Key artifacts per phase:

| Artifact | Purpose | Created By |
|---|---|---|
| `STATE.md` | Current project state, active milestone, phase status | `gsd-tools.cjs` |
| `ROADMAP.md` | Phase breakdown for the active milestone | `new-milestone` workflow |
| `REQUIREMENTS.md` | Detailed requirements per phase | `new-project` workflow |
| `{phase}-CONTEXT.md` | User decisions from the discuss phase | `discuss-phase` workflow |
| `{phase}-RESEARCH.md` | Technical research findings | `research-phase` workflow |
| `{phase}-{plan}-PLAN.md` | Executable plan with YAML frontmatter + tasks | `plan-phase` workflow |
| `{phase}-{plan}-SUMMARY.md` | Execution results, commit hashes, deviations | `execute-phase` (subagent) |
| `{phase}-VERIFICATION.md` | Post-execution verification report | `verify-work` workflow |
| `{phase}-UAT.md` | User acceptance testing results | `verify-work` workflow |
| `config.json` | Project-level configuration | `new-project` or manual |

### 7.2 Context Engine Resolution

The `ContextEngine` class (`sdk/src/context-engine.ts` lines 42-72) defines which artifacts each phase type reads:

```typescript
const PHASE_FILE_MANIFEST: Record<PhaseType, FileSpec[]> = {
  [PhaseType.Execute]:  [STATE.md (required), config.json (optional)],
  [PhaseType.Research]: [STATE.md, ROADMAP.md, CONTEXT.md (required), REQUIREMENTS.md (optional)],
  [PhaseType.Plan]:     [STATE.md, ROADMAP.md, CONTEXT.md (required), RESEARCH.md, REQUIREMENTS.md (optional)],
  [PhaseType.Verify]:   [STATE.md, ROADMAP.md (required), REQUIREMENTS.md, PLAN.md, SUMMARY.md (optional)],
  [PhaseType.Discuss]:  [STATE.md (required), ROADMAP.md, CONTEXT.md (optional)],
};
```

This is a directed acyclic graph where each phase reads artifacts from previous phases and writes new ones for downstream phases:

```
discuss → CONTEXT.md → research → RESEARCH.md → plan → PLAN.md → execute → SUMMARY.md → verify → VERIFICATION.md
```

### 7.3 Context Reduction

Large artifacts are automatically truncated to stay within context window budgets (`context-truncation.ts`). ROADMAP.md is narrowed to the current milestone using `extractCurrentMilestone()`. Files exceeding the threshold are reduced to headings + first paragraphs per section.

### 7.4 Research Gate

A quality gate between research and planning validates that `RESEARCH.md` has no unresolved open questions. From `sdk/src/research-gate.ts` (lines 29-94): if a `## Open Questions` section exists without a `(RESOLVED)` suffix and contains unresolved items, the gate blocks transition to planning.

---

## 8. Hooks System

### 8.1 Hook Types

GSD installs event-driven hooks that fire at specific points in the agent lifecycle. All hooks are in `hooks/`:

| Hook | Event | Purpose |
|---|---|---|
| `gsd-prompt-guard.js` | `PreToolUse` | Prompt injection scanning on Write/Edit to `.planning/` |
| `gsd-workflow-guard.js` | `PreToolUse` | Warns when edits bypass GSD workflow tracking |
| `gsd-read-guard.js` | `PreToolUse` | Guards read operations on sensitive files |
| `gsd-context-monitor.js` | `PostToolUse` | Monitors context state after tool operations |
| `gsd-phase-boundary.sh` | `PostToolUse` | Detects phase boundary crossings |
| `gsd-check-update.js` | `SessionStart` | Checks for GSD version updates |
| `gsd-session-state.sh` | `SessionStart` | Initializes session state |
| `gsd-validate-commit.sh` | `PreToolUse` | Validates commit content |
| `gsd-statusline.js` | status line | Renders project status in terminal |

### 8.2 Hook Registration

For Claude Code, hooks are registered in `settings.json` under the `hooks` key, keyed by event type (`PreToolUse`, `PostToolUse`, `SessionStart`). The installer writes these entries, and validates them with a strict schema to prevent silent rejection:

From `bin/install.js` (lines 4296-4372): the `validateHookFields()` function checks that every hook entry has the required fields — because Claude Code uses a strict Zod schema, and if ANY hook has an invalid schema, the ENTIRE `settings.json` is silently discarded.

### 8.3 Advisory-Only Model

All hooks follow an **advisory-only** model — they emit warnings but never block operations. From `hooks/gsd-prompt-guard.js` (lines 7-12):

> This is a SOFT guard — it advises, not blocks. The edit still proceeds. The warning nudges Claude to use /gsd-quick or /gsd-fast instead of making direct edits that bypass state tracking.

Hooks communicate by writing JSON to stdout with a `hookSpecificOutput` object containing `additionalContext`. The host runtime injects this as advisory context into the agent's next turn.

---

## 9. Security Patterns

### 9.1 Prompt Injection Scanning

GSD implements multi-layer prompt injection defense:

**Layer 1 — Runtime hook (`hooks/gsd-prompt-guard.js`):** Scans content being written to `.planning/` files (agent context files) for injection patterns. Checks for:
- Instruction overrides: `ignore previous instructions`, `disregard all previous`
- Role manipulation: `you are now a`, `act as a`, `pretend you're`
- System prompt extraction: `print your system prompt`, `reveal your instructions`
- Fake boundaries: `<system>`, `[SYSTEM]`, `[INST]`, `<<SYS>>`
- Invisible Unicode: zero-width spaces, bidirectional marks, soft hyphens

**File:** `hooks/gsd-prompt-guard.js` (lines 18-33)

**Layer 2 — CI test suite (`tests/prompt-injection-scan.test.cjs`):** Scans all files that become agent context (agents, workflows, commands, planning templates, hooks) for the same patterns. Runs in CI to catch injection attempts in PRs. Includes an allowlist for files that legitimately discuss injection (security docs, this test file itself).

**File:** `tests/prompt-injection-scan.test.cjs` (lines 1-59)

**Layer 3 — SDK sanitizer (`sdk/src/prompt-sanitizer.ts`):** Validates SDK inputs before they reach the `query()` call.

### 9.2 Tool Scoping as Security

The `tool-scoping.ts` module enforces per-phase tool restrictions: research and verify phases cannot write files, discuss cannot modify code. This limits the blast radius of any compromised phase.

### 9.3 Defense-in-Depth Philosophy

Security is layered across multiple independent mechanisms:
1. **Hook-level**: Runtime scanning of tool inputs
2. **CI-level**: Static analysis of all context-bound files
3. **SDK-level**: Input validation before API calls
4. **Phase-level**: Tool restrictions limiting capabilities per workflow step
5. **Advisory model**: Never block, always warn — avoids false-positive deadlocks while maintaining visibility

---

## 10. Design Patterns for NineS Adoption

Based on this analysis, the following design patterns from GSD are directly applicable to NineS. NineS should implement these concepts in Python for its Agent Skill delivery mechanism.

### Pattern 1: Single-Source Multi-Target Transpilation

**GSD implementation:** Commands authored once in Claude Code format, transpiled per-runtime at install time via converter functions.

**NineS adoption:** Define skills in a canonical Python-based format (e.g., Python dataclass or YAML), then implement per-runtime emitters that generate the target format. Use a registry of `SkillEmitter` classes:

```python
class SkillEmitter(Protocol):
    def emit_skill(self, skill: CanonicalSkill) -> str: ...
    def emit_agent(self, agent: CanonicalAgent) -> str: ...

class CursorEmitter(SkillEmitter): ...
class ClaudeEmitter(SkillEmitter): ...
```

### Pattern 2: Adapter Header Injection

**GSD implementation:** For runtimes without native slash-command support, a `<runtime_skill_adapter>` block is prepended that teaches the agent how to invoke the skill, parse arguments, and dispatch subagents.

**NineS adoption:** Generate per-runtime adapter preambles that normalize skill invocation. Include: invocation trigger pattern, argument extraction, tool name mapping, subagent dispatch syntax.

### Pattern 3: Tool Name Mapping Tables

**GSD implementation:** Per-runtime dictionaries mapping canonical tool names to runtime equivalents, with `null` for unsupported tools and fallback descriptions.

**NineS adoption:** Maintain a `tool_mapping.py` module with `Dict[str, Dict[str, Optional[str]]]` mapping `canonical_name → {runtime: native_name}`. Include fallback behavior descriptions for `null`-mapped tools.

### Pattern 4: Config-Driven Defaults with "Absent = Enabled"

**GSD implementation:** `CONFIG_DEFAULTS` merged with user config via three-level deep merge. Missing config means all features enabled. Users opt-out rather than opt-in.

**NineS adoption:** Use Python `dataclasses` with default values for all fields. Load user config from YAML/JSON and merge with `dataclasses.replace()`. This ensures zero-config works out of the box while allowing progressive customization.

### Pattern 5: Phase-Gated Tool Scoping

**GSD implementation:** `PHASE_DEFAULT_TOOLS` restricts which tools each workflow phase can access — research is read-only, verify is read-only, execute gets write access.

**NineS adoption:** Implement a `PhaseToolPolicy` that returns the allowed tool set for each pipeline stage. Enforce at the skill execution layer so skills cannot exceed their phase's capability.

### Pattern 6: File-Backed Artifact DAG

**GSD implementation:** State is entirely file-based under `.planning/`. Each phase reads upstream artifacts and produces downstream ones. No database, no server — just markdown files on disk.

**NineS adoption:** Use a `.nines/` directory with a similar artifact structure. Define a `ContextManifest` that maps each stage to its required and produced artifacts:

```python
CONTEXT_MANIFEST = {
    "research": {"reads": ["STATE.md"], "writes": ["RESEARCH.md"]},
    "plan":     {"reads": ["STATE.md", "RESEARCH.md"], "writes": ["PLAN.md"]},
    "execute":  {"reads": ["PLAN.md"], "writes": ["SUMMARY.md"]},
    "verify":   {"reads": ["PLAN.md", "SUMMARY.md"], "writes": ["VERIFICATION.md"]},
}
```

### Pattern 7: Advisory Hooks with Silent-Fail Semantics

**GSD implementation:** Hooks emit warnings via `hookSpecificOutput.additionalContext` but never block operations. All hooks catch errors and `process.exit(0)` silently — a hook failure must never break the host agent.

**NineS adoption:** Implement hooks as Python callables that return `Optional[str]` (advisory message or `None`). Wrap every hook invocation in a try/except that logs and continues. Never let a hook crash the pipeline.

### Pattern 8: Event Stream with Pluggable Transports

**GSD implementation:** `GSDEventStream` extends `EventEmitter`, maps SDK messages to typed events, supports `CLITransport` and `WSTransport` for different consumers. Includes per-session cost tracking.

**NineS adoption:** Implement an `EventBus` with typed Python events (dataclasses) and pluggable subscribers. Support at minimum: CLI renderer, JSON-lines file writer, WebSocket forwarder. Include cost/token tracking per session.

### Pattern 9: Research Gate Quality Checks

**GSD implementation:** `checkResearchGate()` validates that `RESEARCH.md` has no unresolved open questions before allowing the plan phase to proceed. Parses markdown structure (headings, lists) to detect unresolved items.

**NineS adoption:** Implement stage transition gates as pure functions: `def check_gate(artifact_content: str) -> GateResult`. Each gate validates that the upstream artifact meets quality criteria before allowing downstream work. Include gates for: research completeness, plan specificity, test coverage.

### Pattern 10: Context Window-Adaptive Prompt Engineering

**GSD implementation:** The execute-phase workflow reads `CONTEXT_WINDOW` size and adapts prompt enrichment — large context windows (>=500K) get richer cross-phase context, small windows (<200K) get thinned prompts with on-demand reference loading.

**NineS adoption:** Make prompt assembly context-window-aware. Detect the model's capacity and adjust: full context for large-window models, compressed/on-demand context for small-window models. Implement a `PromptBudgetPlanner` that allocates token budget across prompt sections.

### Pattern 11: Wave-Based Parallel Scheduling

**GSD implementation:** Plans are annotated with `wave` number and `depends_on` list. Waves execute sequentially, plans within a wave execute in parallel.

**NineS adoption:** Model task dependencies as a DAG. Implement a wave scheduler that groups independent tasks into parallel batches. Each wave only starts after all plans in the previous wave complete successfully.

### Pattern 12: Multi-Layer Prompt Injection Defense

**GSD implementation:** Three independent layers — runtime hooks, CI test suite, SDK sanitizer — each scanning for injection patterns independently.

**NineS adoption:** Implement a `SecurityScanner` class used across: (1) pre-execution hook scanning tool inputs, (2) CI tests scanning all context-bound files, (3) SDK-level input validation. Share pattern definitions but run checks independently at each layer.

---

## Summary

GSD's architecture demonstrates that a single-source, multi-target approach to AI agent skill delivery is both practical and scalable across 14+ runtimes. The key enablers are: (a) a canonical command format with well-defined frontmatter schema, (b) per-runtime converter functions that handle tool names, paths, frontmatter format, and adapter headers, (c) a file-backed state system that works across all runtimes without external dependencies, and (d) layered security that defends without blocking.

NineS should adopt the core patterns (single-source transpilation, adapter headers, tool mapping, config-driven defaults, artifact DAG, advisory hooks, event streams, quality gates) while implementing them in Python to match NineS's technology stack. The file-backed state system is particularly attractive for NineS because it enables operation across any runtime without requiring a shared database or server.
