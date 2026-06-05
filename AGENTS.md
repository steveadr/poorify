# AGENTS.md — Poorify Agent Instructions

This file guides any AI coding agent working on the Poorify project.

## MCP Setup

Poorify exposes its full API via MCP (Model Context Protocol). Add this to your `.opencode/opencode.json` or equivalent:

```json
{
  "mcpServers": {
    "poorify": {
      "command": "python",
      "args": ["-m", "poorify.mcp_server"]
    }
  }
}
```

Once connected, Poorify registers:
- **Tools** — `init`, `requirements`, `ingestion`, `develop`, `gate`, `inspect`, `metrics`
- **Resources** — `poorify://agents/` (phase prompt templates), `poorify://summary` (latest metrics)
- **Prompts** — `requirements_prompt`, `development_prompt`, `gate_prompt` (phase templates)

## Available Commands

When a human invokes one of these commands:

| Command | MCP Tool | Purpose |
|---------|----------|---------|
| `/init` | `init()` | Initialize the harness database |
| `/execute <task>` | Run phases in sequence | Full pipeline: requirements → ingestion → develop → gate |
| `/metrics` | `metrics()` | View pipeline statistics |
| `/inspect <module>` | `inspect(keyword)` | Understand a module (on-disk files + DB state) |

## Pipeline Overview

4 phases, executed in strict order:
1. **Requirements** — `requirements()` → saves tech spec + assertion
2. **Ingestion** — `ingestion()` → routes file SKELETON/FULL based on complexity
3. **Development** — `develop()` → Search/Replace patches, self-healing loop (max 3)
4. **Testing Gate** — `gate()` → git diff analysis + assertion check

## Key Invariants (Hard Rules)

- NO unsolicited refactoring — do NOT touch code outside the assigned fix
- NO changing public API signatures — function headers, params, exports are frozen
- NO adding new dependencies — use only what is already imported
- Patches must be the minimal delta — never rewrite entire files
- Always run `init()` before first use

## Agent Protocol

### Phase execution order

```
requirements → ingestion → development → gate
```

### Agent prompt loading

Before each phase, read the corresponding prompt from `poorify://agents/`:

| Phase | Resource | Purpose |
|-------|----------|---------|
| Requirements | `poorify://agents/requirements_agent.md` | Decompose user request → XML spec + assertion |
| Development | `poorify://agents/development_agent.md` | Apply Search/Replace patches, self-heal on failure |
| Testing Gate | `poorify://agents/testing_agent.md` | Analyze diff, return XML pass/fail judgment |

### Output formats

**Requirements** — XML blocks:
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

**Development** — Search/Replace blocks:
```
<<<<<<< SEARCH
    let discount = 0;
=======
    let discount = if user.is_vip { amount * 0.15 } else { 0.0 };
>>>>>>> REPLACE
```

**Testing gate** — XML judgment:
```xml
<test_judgment>
STATUS: PASSED
SUMMARY: Change is minimal and fulfills the business criteria.
</test_judgment>
```

### Self-healing

When the development loop fails:
1. Engine auto-restores `.bak` (physical rollback)
2. Re-read error from build output
3. Fix the patch and re-apply via `develop()`
4. Max 3 retries — hard cap

### SQLite state

DB at `.poorify/core/harness_state.db`. Key tables:

| Table | Contents |
|-------|----------|
| `technical_specs` | Current task's pre/post conditions and constraints |
| `business_assertions` | Mock input/output JSON for validation |
| `token_metrics` | Per-phase token counts and timing |
| `migration_router` | Complexity mode (SKELETON/FULL) per file |
| `cascade_tasks` | Pending cascade repair jobs |
| `execution_logs` | Short-term action log |

### Error recovery

- SEARCH block must match 100% — no fuzzy matching
- Build fails → inspect stderr, fix exact line, re-apply
- Never disable cascade repair — process PENDING tasks one by one
- Never exceed `MAX_RETRIES = 3`

## CLI (Debugging Only)

For manual testing, the CLI at `python -m src.poorify.main` is available:

```bash
python -m src.poorify.main --init
python -m src.poorify.main --inspect "keyword"
python -m src.poorify.main --metrics latest
python -m src.poorify.main --metrics-all
```

See `commands/` for the original protocol files (kept as reference).
