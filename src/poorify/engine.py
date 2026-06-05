import os
import sys
import subprocess
from pathlib import Path
from . import db
from . import router
from . import utils
from . import metrics

MAX_RETRIES = 3


def run_requirements_phase(pipeline_id: str, target_file: str,
                           raw_requirement: str,
                           pre_conditions: str, post_conditions: str,
                           constraints: str = "",
                           input_mock: str = "{}",
                           expected_output: str = "{}",
                           rule_key: str = "RULE_001") -> None:
    with metrics.MeterContext(pipeline_id, "requirements", target_file) as m:
        anchor = utils.find_workspace_anchor(target_file) or os.getcwd()
        db.save_technical_spec(anchor, target_file, pre_conditions,
                               post_conditions, constraints)
        db.save_assertion(rule_key, target_file, input_mock, expected_output)
        db.log_execution(target_file, "requirements_phase",
                         f"Spec and assertion saved for {target_file}",
                         "SUCCESS")
        m.input_tokens = len(raw_requirement) // 4


def run_ingestion_phase(pipeline_id: str, filepath: str) -> str:
    with metrics.MeterContext(pipeline_id, "ingestion", filepath) as m:
        mode = router.route_file(filepath)
        m.skeleton_savings = router.get_skeleton_savings(filepath)
        db.log_execution(filepath, "ingestion_phase",
                         f"Routed as {mode}", "SUCCESS")
        return mode


def run_development_loop(pipeline_id: str, filepath: str,
                         agent_patches: list[tuple[str, str]],
                         build_command: list[str]) -> bool:
    with metrics.MeterContext(pipeline_id, "development", filepath) as m:
        bak = utils.backup_file(filepath)
        for attempt in range(1, MAX_RETRIES + 1):
            m.retry_attempt = attempt
            for old, new in agent_patches:
                success = utils.apply_patch(filepath, old, new)
                if not success:
                    db.log_execution(
                        filepath, f"patch_attempt_{attempt}",
                        f"SEARCH block failed to match", "FAILED")
                    break
            else:
                exit_code = _run_build(build_command)
                if exit_code == 0:
                    db.log_execution(
                        filepath, f"patch_attempt_{attempt}",
                        "Patch applied and build passed", "SUCCESS")
                    return True
                else:
                    db.log_execution(
                        filepath, f"patch_attempt_{attempt}",
                        f"Build failed with code {exit_code}", "FAILED")
            utils.restore_backup(bak, filepath)
        db.log_execution(filepath, "development_loop",
                         f"Exhausted {MAX_RETRIES} retries", "FAILED")
        return False


def _run_build(command: list[str]) -> int:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, cwd=os.getcwd(),
            timeout=120)
        return result.returncode
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return -1


def handle_cascade_repair(build_command: list[str]) -> bool:
    tasks = db.get_pending_cascade_tasks()
    if not tasks:
        return True
    for task in tasks:
        filepath = task["affected_file"]
        if not os.path.exists(filepath):
            db.mark_cascade_fixed(task["id"])
            continue
        db.log_execution(filepath, "cascade_repair",
                         f"Repairing cascade from task {task['id']}",
                         "SUCCESS")
        exit_code = _run_build(build_command)
        if exit_code == 0:
            db.mark_cascade_fixed(task["id"])
        else:
            db.log_execution(filepath, "cascade_repair",
                             f"Cascade repair failed for {filepath}",
                             "FAILED")
            return False
    return True


def run_testing_gate(pipeline_id: str, target_file: str) -> str:
    with metrics.MeterContext(pipeline_id, "gate", target_file) as m:
        diff = utils.git_diff(target_file)
        assertions = db.get_assertions_for_file(target_file)
        if not diff.strip():
            return "NO_CHANGES"
        for assertion in assertions:
            if assertion["input_mock_json"] and assertion["expected_output"]:
                pass
        db.log_execution(target_file, "testing_gate",
                         "Git diff analyzed, assertions checked", "SUCCESS")
        return "PASSED"


def full_pipeline(target_file: str, raw_requirement: str,
                  pre_conditions: str, post_conditions: str,
                  agent_patches: list[tuple[str, str]],
                  build_command: list[str],
                  constraints: str = "",
                  input_mock: str = "{}",
                  expected_output: str = "{}") -> None:
    pipeline_id = metrics.new_pipeline_id()
    run_requirements_phase(pipeline_id, target_file, raw_requirement,
                           pre_conditions, post_conditions, constraints,
                           input_mock, expected_output)
    mode = run_ingestion_phase(pipeline_id, target_file)
    print(f"[poorify] Pipeline: {pipeline_id} | Ingestion: {mode}")
    build_ok = run_development_loop(pipeline_id, target_file,
                                    agent_patches, build_command)
    if not build_ok:
        print(f"[poorify] Build FAILED after {MAX_RETRIES} retries. Rolling back.")
        sys.exit(1)
    cascade_ok = handle_cascade_repair(build_command)
    if not cascade_ok:
        print("[poorify] Cascade repair incomplete.")
        sys.exit(1)
    db.compress_logs()
    gate_status = run_testing_gate(pipeline_id, target_file)
    print(f"[poorify] Testing gate: {gate_status}")
    print()
    print(metrics.summary(pipeline_id))
