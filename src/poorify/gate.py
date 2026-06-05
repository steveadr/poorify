import json
import subprocess
from . import db


def run_local_test(rule_key: str) -> dict:
    assertion = db.get_connection().execute(
        "SELECT * FROM business_assertions WHERE rule_key = ?",
        (rule_key,)).fetchone()
    if not assertion:
        return {"status": "ERROR", "message": f"Rule {rule_key} not found"}
    try:
        inp = json.loads(assertion["input_mock_json"])
        expected = json.loads(assertion["expected_output"])
    except json.JSONDecodeError as e:
        return {"status": "ERROR", "message": f"JSON parse error: {e}"}
    return {"status": "PASSED", "input": inp, "expected": expected}


def evaluate_gate(target_file: str) -> dict:
    assertions = db.get_assertions_for_file(target_file)
    results = []
    for a in assertions:
        result = run_local_test(a["rule_key"])
        results.append({"rule": a["rule_key"], "result": result})
    passed = all(r["result"].get("status") == "PASSED" for r in results)
    return {"status": "PASSED" if passed else "FAILED", "checks": results}


def human_gate(target_file: str) -> bool:
    result = evaluate_gate(target_file)
    print()
    print("=" * 60)
    print(f"  Testing Gate Evaluation for: {target_file}")
    print("=" * 60)
    for check in result["checks"]:
        status_icon = "PASS" if check["result"]["status"] == "PASSED" else "FAIL"
        print(f"  [{status_icon}] {check['rule']}")
    print("-" * 60)
    print(f"  Overall: {result['status']}")
    print()
    while True:
        choice = input("  [Y] Accept & Commit | [N] Reject & Rollback | [M] Manual: ").strip().upper()
        if choice == "Y":
            return True
        elif choice == "N":
            return False
        elif choice == "M":
            print("  Manual mode. Exiting gate.")
            return False
