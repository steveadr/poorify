## /execute <task>

Execute the full Caveman Harness pipeline for a given task. The task is a natural language description of what needs to be changed (e.g. "Adjust the banner to add VIP 15% discount").

### Pre-flight
If `.poorify/core/harness_state.db` does not exist, call `poorify --init` first.

### Pipeline Steps

**Step 1 — Identify target file**
From the task context, determine the exact file path that needs modification. If unclear, search the project for relevant files using grep or similar.

**Step 2 — Requirements Phase**
Load `.poorify/agents/requirements_agent.md` as your system prompt.

Think about the task and produce:
- `<workspace_anchor>` — sub-project root and target file
- `<technical_specification>` — pre-conditions, post-conditions, strict constraints
- `<business_assertion_blueprint>` — mock input JSON and expected output JSON

Then call:
```
poorify --phase requirements <target_file> \
  --pre "<pre_conditions>" \
  --post "<post_conditions>" \
  --constraints "<strict_constraints>" \
  --mock-input '<input_json>' \
  --mock-output '<output_json>' \
  --rule-key RULE_001
```

**Step 3 — Ingestion Phase**
Call:
```
poorify --phase ingestion <target_file>
```
Note the ingestion mode (SKELETON or FULL) — this determines how much code context to read.

**Step 4 — Read current code**
Read the target file content. If mode is SKELETON, only function signatures and docstrings matter; if FULL, read the entire file.

**Step 5 — Development Phase**
Load `.poorify/agents/development_agent.md` as your system prompt.

Think about the code, the spec, and the business assertion. Produce Search/Replace patches in the exact format:
```
<<<<<<< SEARCH
[exact old code to replace]
=======
[new code]
>>>>>>> REPLACE
```

Then call:
```
poorify --phase develop <target_file> \
  --requirement "<<<<<<< SEARCH\n...\n=======\n...\n>>>>>>> REPLACE" \
  --build-cmd <auto-detect>
```

Auto-detect the build command from the project:
- `Cargo.toml` → `cargo check`
- `package.json` → `npm run build`
- `pyproject.toml` → `python -m pytest`
- `go.mod` → `go build ./...`

**Step 6 — Self-Healing Loop**
If the build fails:
1. Read the error from stderr
2. Restore from `.bak` backup (the engine does this automatically)
3. Fix the patch
4. Re-call `poorify --phase develop` with the corrected patch
5. Max 3 retries — after that the pipeline aborts

**Step 7 — Testing Gate**
Load `.poorify/agents/testing_agent.md` as your system prompt.

Review the `git diff` output against the original requirement. Produce an XML judgment:
```xml
<test_judgment>
STATUS: PASSED  (or FAILED)
REASON: ...
REMEDY_ACTION: ...
</test_judgment>
```

Then call:
```
poorify --phase gate <target_file>
```
Wait for human confirmation ([Y] accept / [N] reject / [M] manual).

**Step 8 — Metrics**
Call:
```
poorify --metrics
```
Present the metrics table to the user as the final summary.

### Error Recovery
- If a SEARCH block fails to match 100%, the patch is rejected — do NOT guess or fuzzy-match
- If cascade tasks appear (PENDING in `cascade_tasks` table), process them one by one using the same development cycle
- Never exceed MAX_RETRIES = 3
