# AGENTS.md — Poorify Agent Instructions

This file guides any AI coding agent working on the Poorify project.

## Available Commands

When a human invokes one of these commands, follow the protocol in the referenced file:

| Command | Protocol File | Purpose |
|---------|--------------|---------|
| `/init` | `commands/init.md` | Initialize the harness database |
| `/execute <task>` | `commands/execute.md` | Run the full pipeline |
| `/metrics` | `commands/metrics.md` | View pipeline statistics |
| `/inspect <module>` | `commands/inspect.md` | Query architecture state for a module |

## Pipeline Overview

The Poorify pipeline has 4 phases, executed in strict order:
1. **Requirements** — Parse user request into technical spec + business assertions
2. **Ingestion** — Route files as SKELETON or FULL based on cyclomatic complexity
3. **Development** — Search/Replace patching with self-healing loop (max 3 retries)
4. **Testing Gate** — Git diff analysis + assertion checks + human confirmation

## Key Invariants (Hard Rules)

- NO unsolicited refactoring — do NOT touch code outside the assigned fix
- NO changing public API signatures — function headers, params, exports are frozen
- NO adding new dependencies — use only what is already imported
- Patches must be the minimal delta — never rewrite entire files
- Always run `poorify --init` before first use
- Use `poorify --phase pipeline` for full end-to-end runs

## Project Structure

```
.poorify/core/       — SQLite database location
.poorify/agents/     — Prompt modules for each agent role
.poorify/backup/     — Automatic rollback backups
src/poorify/         — Python scaffold engine package
tests/               — Test suite
```

---

## AI Agent Protocol

This section defines how an AI coding agent MUST interact with Poorify. Follow these rules precisely.

### 1. Phase Execution Order

Phases MUST be executed in sequence. Never skip a phase:

```
requirements → ingestion → development → gate
```

### 2. Agent Prompt Loading

Before each phase, load the corresponding system prompt from `.poorify/agents/`:

| Phase | Prompt File | Purpose |
|-------|------------|---------|
| Requirements | `requirements_agent.md` | Decompose user request → XML spec + assertion |
| Development | `development_agent.md` | Apply Search/Replace patches, self-heal on failure |
| Testing Gate | `testing_agent.md` | Analyze diff, return XML pass/fail judgment |

### 3. CLI Commands

Use the `poorify` CLI to drive each phase. The protocol for each user-facing command is in `commands/`:

| User Command | Refer to |
|-------------|----------|
| `/init` | `commands/init.md` |
| `/execute <task>` | `commands/execute.md` |
| `/metrics` | `commands/metrics.md` |

The underlying CLI flags for each phase:

```bash
poorify <target_file> --phase requirements --pre "..." --post "..." --mock-input '{...}' --mock-output '{...}'
poorify <target_file> --phase ingestion
poorify <target_file> --phase develop --requirement "SEARCH/REPLACE blocks" --build-cmd <cmd>
poorify <target_file> --phase gate
```

### 4. Output Format Requirements

Each phase has a strict output format that MUST be followed:

**Requirements phase** — return XML blocks:
```xml
<workspace_anchor>
SUB_PROJECT_ROOT: projects/payment/
TARGET_FILE: src/processor.rs
</workspace_anchor>
<technical_specification>
PRE_CONDITIONS: ...
POST_CONDITIONS: ...
STRICT_CONSTRAINTS: NO refactoring
</technical_specification>
<business_assertion_blueprint>
RULE_KEY: VIP_DISCOUNT
INPUT_MOCK_JSON: {"user_type":"vip"}
EXPECTED_OUTPUT_JSON: {"discount":15.0}
</business_assertion_blueprint>
```

**Development phase** — return patches as Search/Replace blocks:
```
<<<<<<< SEARCH
    let discount = 0;
=======
    let discount = if user.is_vip { amount * 0.15 } else { 0.0 };
>>>>>>> REPLACE
```

**Testing gate** — return XML judgment:
```xml
<test_judgment>
STATUS: PASSED
SUMMARY: Change is minimal and fulfills the business criteria.
</test_judgment>
```

### 5. Self-Healing Protocol

When the development loop fails:
1. The engine automatically restores the `.bak` file (physical rollback)
2. Re-read the error from the build command output
3. Fix the patch and re-apply
4. Max 3 retries — after that the pipeline aborts

### 6. SQLite State Access

The database at `.poorify/core/harness_state.db` is readable by the agent. Key tables:

| Table | Contents |
|-------|----------|
| `technical_specs` | Current task's pre/post conditions and constraints |
| `business_assertions` | Mock input/output JSON for validation |
| `token_metrics` | Per-phase input/output/cached tokens and timing |
| `migration_router` | Complexity mode (SKELETON/FULL) per file |
| `cascade_tasks` | Pending cascade repair jobs from compiler failures |
| `execution_logs` | Short-term log of every action taken |

### 7. Error Recovery Rules

- If a SEARCH block fails to match 100%, the patch is rejected — do NOT guess or fuzzy-match
- If the build fails, inspect stderr, fix the exact line, and re-apply
- Never disable the cascade repair — process PENDING tasks one by one
- Never exceed `MAX_RETRIES = 3` — the hard cap is enforced by the engine
