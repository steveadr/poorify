## /init

Initialize the Caveman Harness database for the current project.

### Action
Call `poorify --init` in the current project root directory.

### What it does
- Creates `.poorify/core/` directory
- Creates `harness_state.db` with all tables:
  - `execution_logs` — short-term action log
  - `long_term_milestones` — compressed log summaries
  - `technical_specs` — pre/post conditions and constraints
  - `migration_router` — complexity mode per file
  - `business_assertions` — mock input/output test data
  - `cascade_tasks` — compiler cascade repair queue
  - `token_metrics` — per-phase token and timing data

### When to run
Once per project before first `/execute`, or if `.poorify/core/harness_state.db` is missing.
