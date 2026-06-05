import os
import sys
import json
from mcp.server.fastmcp import FastMCP
from . import db
from . import engine
from . import router
from . import gate as gate_mod
from . import metrics as met

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
AGENTS_DIR = os.path.join(PROJECT_ROOT, ".poorify", "agents")

mcp = FastMCP("poorify", instructions="""Poorify — a Caveman Harness scaffold for AI coding agents.

4-phase pipeline:
1. Requirements — save technical spec + business assertion
2. Ingestion — route file as SKELETON or FULL based on complexity
3. Development — apply Search/Replace patches with self-healing (max 3 retries)
4. Testing Gate — git diff analysis + assertion check + human confirmation

Resources at poorify://agents/ expose the phase prompt templates.
Use inspect() to understand a module before modifying it.""")


# ── Tools ────────────────────────────────────────────────────────────────

@mcp.tool(description="Initialize the Poorify SQLite database")
def init() -> str:
    db.init_db()
    return json.dumps({"status": "ok", "path": db.DB_PATH})


@mcp.tool(description="Run requirements phase: save technical spec + business assertion")
def requirements(
    target_file: str,
    requirement: str = "",
    pre_conditions: str = "",
    post_conditions: str = "",
    constraints: str = "",
    mock_input: str = "{}",
    mock_output: str = "{}",
    rule_key: str = "RULE_001",
    pipeline_id: str = "",
) -> str:
    pid = pipeline_id or met.new_pipeline_id()
    engine.run_requirements_phase(
        pid, target_file, requirement, pre_conditions, post_conditions,
        constraints, mock_input, mock_output, rule_key,
    )
    return json.dumps({"pipeline_id": pid, "status": "saved", "target_file": target_file})


@mcp.tool(description="Analyze file complexity and route as SKELETON or FULL")
def ingestion(filepath: str, pipeline_id: str = "") -> str:
    pid = pipeline_id or met.new_pipeline_id()
    mode = engine.run_ingestion_phase(pid, filepath)
    entry = db.get_router_entry(filepath)
    cx = entry["cyclomatic_complexity"] if entry else 0
    savings = router.get_skeleton_savings(filepath)
    return json.dumps({
        "pipeline_id": pid,
        "mode": mode,
        "complexity": cx,
        "savings": savings,
    })


@mcp.tool(description="Apply Search/Replace patches with self-healing loop (max 3 retries)")
def develop(
    filepath: str,
    patches_json: str,
    build_command: list[str] | None = None,
    pipeline_id: str = "",
) -> str:
    pid = pipeline_id or met.new_pipeline_id()
    patches = json.loads(patches_json) if isinstance(patches_json, str) else patches_json
    patch_tuples = [(p["old"], p["new"]) if isinstance(p, dict) else (p[0], p[1]) for p in patches]
    cmd = build_command or ["python", "-m", "pytest"]
    success = engine.run_development_loop(pid, filepath, patch_tuples, cmd)
    cascade_ok = engine.handle_cascade_repair(cmd)
    return json.dumps({
        "pipeline_id": pid,
        "status": "passed" if (success and cascade_ok) else "failed",
        "retries": engine.MAX_RETRIES,
    })


@mcp.tool(name="gate", description="Run testing gate: diff analysis + assertion check")
def testing_gate(target_file: str, pipeline_id: str = "") -> str:
    pid = pipeline_id or met.new_pipeline_id()
    status = engine.run_testing_gate(pid, target_file)
    evaluation = gate_mod.evaluate_gate(target_file)
    return json.dumps({
        "pipeline_id": pid,
        "status": status,
        "evaluation": evaluation,
    })


@mcp.tool(description="Inspect a module: on-disk files + DB state")
def inspect(keyword: str) -> str:
    files = []
    for root, dirs, fnames in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", ".poorify")]
        for f in fnames:
            if f.endswith(".pyc"):
                continue
            path = os.path.normpath(os.path.join(root, f))
            if keyword.lower() in path.lower():
                info = router.analyze_file(path)
                info["file_path"] = path
                files.append(info)

    db_data = db.inspect_module(keyword)
    return json.dumps({
        "files": files,
        "specs": [dict(r) for r in db_data["specs"]],
        "router": [dict(r) for r in db_data["router"]],
        "assertions": [dict(r) for r in db_data["assertions"]],
        "cascade": [dict(r) for r in db_data["cascade"]],
        "metrics_count": len(db_data["metrics"]),
        "logs_count": len(db_data["logs"]),
    }, default=str)


@mcp.tool(description="Get pipeline metrics (latest, specific ID, or aggregate)")
def metrics(pipeline_id: str = "", all: bool = False) -> str:
    if all:
        return met.overall_stats()
    if pipeline_id:
        return met.summary(pipeline_id)
    pipelines = db.get_all_pipeline_ids()
    if not pipelines:
        return "[poorify] No pipelines recorded yet."
    return met.summary(pipelines[0]["pipeline_id"])


# ── Resources ────────────────────────────────────────────────────────────

@mcp.resource("poorify://agents/{filename}")
def get_agent_prompt(filename: str) -> str:
    path = os.path.join(AGENTS_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Agent prompt not found: {filename}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@mcp.resource("poorify://summary")
def get_latest_summary() -> str:
    pipelines = db.get_all_pipeline_ids()
    if not pipelines:
        return "[poorify] No pipelines recorded yet."
    return met.summary(pipelines[0]["pipeline_id"])


# ── Prompts ──────────────────────────────────────────────────────────────

@mcp.prompt(description="Requirements phase: decompose user request into XML spec + assertion")
def requirements_prompt(task: str = "") -> str:
    return f"""You are running the Poorify Requirements phase.

Task: {task}

1. Read the prompt template at poorify://agents/requirements_agent.md
2. Decompose the task into:
   - Workspace anchor (sub_project_root, target_file)
   - Technical specification (pre/post conditions, strict constraints)
   - Business assertion blueprint (rule_key, mock input JSON, expected output JSON)
3. Output XML blocks exactly as specified in the prompt template.
4. Call the `requirements()` tool with the parsed values."""


@mcp.prompt(description="Development phase: convert spec into Search/Replace patches")
def development_prompt(spec: str = "") -> str:
    return f"""You are running the Poorify Development phase.

Spec: {spec}

1. Read the prompt template at poorify://agents/development_agent.md
2. Read the target file content (use inspector if needed)
3. Produce Search/Replace patches in the format:
   <<<<<<< SEARCH
   old code
   =======
   new code
   >>>>>>> REPLACE
4. Call the `develop()` tool with the patches as a JSON array.
5. If it fails, fix the patch and retry (max 3)."""


@mcp.prompt(description="Testing gate: analyze diff and return XML judgment")
def gate_prompt(diff: str = "") -> str:
    return f"""You are running the Poorify Testing Gate phase.

Diff: {diff}

1. Read the prompt template at poorify://agents/testing_agent.md
2. Analyze the git diff and business assertions
3. Output XML:
   <test_judgment>
   STATUS: PASSED or FAILED
   SUMMARY: ...
   </test_judgment>
4. Call gate() with the target file."""


# ── Entry point ──────────────────────────────────────────────────────────

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
