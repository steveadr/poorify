# Poorify — Caveman Harness Scaffold

**Anti-RAG · Flat-SQLite · JIT Surgical Discovery · Executable Spec**

Poorify is a deterministic scaffold engine for AI coding agents. It replaces vector databases and complex RAG with a flat SQLite database, a 4-phase surgical pipeline, and strict token-budget discipline.

When loaded into a coding agent (Claude CLI, Copilot, OpenCode, etc.) via MCP, Poorify gives the agent tools that control how it modifies code.

## MCP Setup

Add to your OpenCode config (`.opencode/opencode.json` or equivalent):

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

### One-shot auto-setup prompt

Copy-paste this to your AI agent (Claude CLI / Copilot / OpenCode) to wire Poorify automatically:

> I want to use the Poorify harness system in this project. It exposes an MCP server at `python -m poorify.mcp_server`. Please detect which AI client I'm running (OpenCode, Claude CLI, or Copilot), find the correct MCP config file, and add the `poorify` server entry. The config format is:
> ```json
> {"mcpServers": {"poorify": {"command": "python", "args": ["-m", "poorify.mcp_server"]}}}
> ```
> After adding it, read `AGENTS.md` and give me a summary of the available commands.

Once connected, Poorify registers:
- **Tools** — `init`, `requirements`, `ingestion`, `develop`, `gate`, `inspect`, `metrics`
- **Resources** — `poorify://agents/` (phase prompt templates), `poorify://summary` (latest metrics)
- **Prompts** — `requirements_prompt`, `development_prompt`, `gate_prompt`

## Quick Start

Talk to your coding agent. Say:

```
/init
/execute "Add VIP 15% discount to the banner"
/inspect trading
/metrics
```

The agent discovers Poorify's MCP tools at connection time and runs the pipeline automatically.

## Pipeline

```
[User Request] ──► 1. Requirements ──► (Gen Spec, Mock JSON → SQLite)
                              │
                              ▼
               2. Ingestion Routing ──► (Complexity → SKELETON / FULL)
                              │
                              ▼
               3. Development Loop ──► (Search/Replace + Self-Heal ≤3 retries)
                              │
                              ▼
               4. Testing Gate ──► (Assertions + Diff + Human [Y/N/M])
```

## How It Works

| You say | Agent does |
|---------|-----------|
| `/init` | Calls `init()` tool → creates `.poorify/core/harness_state.db` |
| `/execute <task>` | Reads prompt from `poorify://agents/requirements_agent.md` → produces XML spec → calls `requirements()` tool → reads `poorify://agents/development_agent.md` → writes Search/Replace patches → calls `develop()` tool (self-heal ≤3) → reads `testing_agent.md` → calls `gate()` tool for human Y/N/M → calls `metrics()` |
| `/metrics` | Calls `metrics()` tool → shows latest pipeline stats |
| `/inspect <module>` | Calls `inspect("module")` tool → returns on-disk files + DB state |

## Architecture Flow (Memo 1 → 24)

### STATE & MEMORY (Memos 1–4)
| Memo | Component | Location |
|------|-----------|----------|
| 1–2 | SQLite persistence — all state in a single flat DB | `.poorify/core/harness_state.db` |
| 3 | Dual-tier log management — short-term `execution_logs` + long-term `long_term_milestones`; auto-compresses at 20 rows | `db.py:compress_logs()` |
| 4 | Ephesian pruning — deletes logs irrelevant to current mission | `db.py:prune_irrelevant_logs()` |

### REQUIREMENTS & ISOLATION (Memos 5–10)
| Memo | Component | Location |
|------|-----------|----------|
| 5–6 | State machine matrix — precise `pre_conditions` / `post_conditions` / `strict_constraints` | `technical_specs` table |
| 7–8 | Workspace anchor — finds project root boundary and isolates file operations | `utils.py:find_workspace_anchor()` |
| 9–10 | Code style sampling — extracts 3 adjacent files for formatting context | `utils.py:sample_adjacent_files()` |

### INGESTION & JIT DISCOVERY (Memos 11–14)
| Memo | Component | Location |
|------|-----------|----------|
| 11–12 | JIT grep discovery — locate files by keyword (ripgrep wrapper, zero tokens) | `utils.py:grep_files()` |
| 13–14 | Complexity routing — AST/regex analysis; SKELETON (<5) saves 90% tokens; FULL (≥5) preserves hidden logic | `router.py` |

### IMPLEMENTATION & PATCHING (Memos 17–20)
| Memo | Component | Location |
|------|-----------|----------|
| 17–18 | Spec + assertion injection — payload builder for agent prompts | `engine.py:run_requirements_phase()` |
| 19 | Surgical Search/Replace engine — strict patch format with 100% literal match enforcement | `utils.py:parse_search_replace()` / `apply_patch()` |
| 20 | Self-healing loop — max 3 retries with physical `.bak` rollback on failure | `engine.py:run_development_loop()` |

### CASCADE REPAIR (Memo 21)
| Memo | Component | Location |
|------|-----------|----------|
| 21 | Compiler cascade queue — parses build errors, inserts `cascade_tasks`, processes iteratively | `engine.py:handle_cascade_repair()` |

### TESTING & METRICS (Memos 23–24)
| Memo | Component | Location |
|------|-----------|----------|
| 23 | Testing gate — git diff analysis + business assertion checks + human [Y/N/M] prompt | `gate.py` |
| 24 | Token metrics — per-phase input/output/cached/ctx/duration/savings dashboard | `metrics.py` |

## Metrics & Statistics

Each pipeline run is logged to `token_metrics`. View results via the `metrics()` tool or:

```
──────────────────────────────────────────────────────────────────────────────
  Pipeline: P20260604-191500-a1b2c3
──────────────────────────────────────────────────────────────────────────────
  Phase              Input   Output   Cached    Ctx%   Dur(ms)   Retry    Saved
  ---------------------------------------------------------------------------
  requirements        300       80        0    3.8%      1200        0        0
  ingestion             0        0        0    0.0%       300        0     2400
  development         1200      420      180   15.0%      8400        2        0
  gate                180       90        0    2.2%       400        0        0
  ---------------------------------------------------------------------------
  TOTAL              1680      590      180   15.0%     10300                 2400
──────────────────────────────────────────────────────────────────────────────
```

## Project Structure

```
.poorify/
├── core/                SQLite database (harness_state.db)
├── agents/              Prompt modules for each pipeline phase
│   ├── requirements_agent.md
│   ├── development_agent.md
│   └── testing_agent.md
└── backup/              Automatic .bak rollback files

src/poorify/
├── mcp_server.py        MCP server (tools, resources, prompts)
├── main.py              CLI entry point (debugging only)
├── db.py                SQLite CRUD (7 tables)
├── router.py            Complexity analysis + SKELETON/FULL routing
├── engine.py            Pipeline orchestration + self-healing loop
├── gate.py              Testing gate + human [Y/N/M] prompt
├── metrics.py           Token metrics dashboard
└── utils.py             Search/Replace patching, git diff, backup, grep

.agignore                Git ignore patterns
AGENTS.md                Agent behavioral spec
commands/                Legacy protocol files (kept as reference)
```

## CLI Reference (Debugging Only)

For manual testing:

```bash
python -m src.poorify.main --init
python -m src.poorify.main --inspect "keyword"
python -m src.poorify.main --metrics latest
python -m src.poorify.main --metrics-all
python -m src.poorify --help
```

| Flag | Default | Description |
|------|---------|-------------|
| `--init` | — | Initialize `.poorify/core/harness_state.db` |
| `--phase` | `pipeline` | Phase to run: `requirements`, `ingestion`, `develop`, `gate`, `pipeline` |
| `target_file` | — | File to operate on (required for `--phase`) |
| `--requirement` | `""` | Raw user requirement or Search/Replace blocks for dev phase |
| `--pre` | `""` | Pre-conditions (state before modification) |
| `--post` | `""` | Post-conditions (state after modification) |
| `--constraints` | `""` | Strict invariants (e.g. "NO refactoring") |
| `--mock-input` | `{}` | Mock input JSON for business assertion |
| `--mock-output` | `{}` | Expected output JSON for business assertion |
| `--rule-key` | `RULE_001` | Business assertion rule key |
| `--build-cmd` | `python -m pytest` | Build/test command (e.g. `cargo check`, `npm run build`) |
| `--pipeline-id` | auto | Explicit pipeline ID (auto-generated if omitted) |
| `--metrics` | `latest` | Show metrics for a pipeline ID |
| `--metrics-all` | — | Show aggregate statistics across all pipelines |

## License

MIT
