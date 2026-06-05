import argparse
import os
import sys
from . import db
from . import engine
from . import gate
from . import router
from . import utils
from . import metrics


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="poorify",
        description="Caveman Harness Scaffold — Anti-RAG, Flat-SQLite, JIT Surgical Engine")
    parser.add_argument("target_file", nargs="?", help="Target file to operate on")
    parser.add_argument("--init", action="store_true", help="Initialize the harness database")
    parser.add_argument("--phase", choices=["requirements", "ingestion", "develop", "gate", "pipeline"],
                        default="pipeline", help="Pipeline phase to run")
    parser.add_argument("--requirement", help="Raw user requirement text")
    parser.add_argument("--pre", help="Pre-conditions text")
    parser.add_argument("--post", help="Post-conditions text")
    parser.add_argument("--constraints", help="Strict constraints")
    parser.add_argument("--mock-input", default="{}", help="Mock input JSON")
    parser.add_argument("--mock-output", default="{}", help="Expected output JSON")
    parser.add_argument("--rule-key", default="RULE_001", help="Business assertion rule key")
    parser.add_argument("--build-cmd", nargs="+", default=["python", "-m", "pytest"],
                        help="Build/test command (e.g. cargo check)")
    parser.add_argument("--metrics", nargs="?", const="latest", default=None,
                        help="Show metrics for a pipeline ID (or 'latest')")
    parser.add_argument("--metrics-all", action="store_true",
                        help="Show aggregate statistics across all pipelines")
    parser.add_argument("--pipeline-id", help="Explicit pipeline ID (auto-generated if omitted)")
    parser.add_argument("--inspect", nargs="?", const=True, default=None,
                        help="Inspect architecture state for a module keyword")

    args = parser.parse_args()

    if args.inspect:
        _print_inspect(args.inspect)
        return

    if args.metrics_all:
        print(metrics.overall_stats())
        return

    if args.metrics:
        if args.metrics == "latest":
            pipelines = db.get_all_pipeline_ids()
            if not pipelines:
                print("[poorify] No pipelines recorded yet.")
                return
            print(metrics.summary(pipelines[0]["pipeline_id"]))
        else:
            print(metrics.summary(args.metrics))
        return

    if args.init:
        db.init_db()
        print("[poorify] Database initialized at .poorify/core/harness_state.db")
        return

    if not args.target_file:
        parser.print_help()
        sys.exit(1)

    pid = args.pipeline_id or metrics.new_pipeline_id()

    if args.phase == "requirements":
        engine.run_requirements_phase(
            pid, args.target_file, args.requirement or "",
            args.pre or "", args.post or "",
            args.constraints or "",
            args.mock_input, args.mock_output, args.rule_key)
        print(f"[poorify] Pipeline {pid} — Requirements phase complete.")

    elif args.phase == "ingestion":
        mode = engine.run_ingestion_phase(pid, args.target_file)
        print(f"[poorify] Pipeline {pid} — Ingestion mode: {mode}")

    elif args.phase == "develop":
        patches = utils.parse_search_replace(args.requirement or "")
        success = engine.run_development_loop(
            pid, args.target_file, patches, args.build_cmd)
        if success:
            print(f"[poorify] Pipeline {pid} — Development loop completed.")
        else:
            print(f"[poorify] Pipeline {pid} — Development loop failed after {engine.MAX_RETRIES} retries.")
            sys.exit(1)

    elif args.phase == "gate":
        status = engine.run_testing_gate(pid, args.target_file)
        print(f"[poorify] Pipeline {pid} — Testing gate: {status}")
        gate.human_gate(args.target_file)
        print()
        print(metrics.summary(pid))

    elif args.phase == "pipeline":
        patches = utils.parse_search_replace(args.requirement or "")
        engine.full_pipeline(
            args.target_file, args.requirement or "",
            args.pre or "", args.post or "",
            patches, args.build_cmd,
            args.constraints or "",
            args.mock_input, args.mock_output)


def _find_module_files(keyword: str) -> list:
    matched = set()
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith(".pyc"):
                continue
            path = os.path.join(root, f)
            if keyword.lower() in path.lower():
                matched.add(os.path.normpath(path))
    return sorted(matched)


def _print_inspect(keyword: str) -> None:
    data = db.inspect_module(keyword)
    label = keyword if isinstance(keyword, str) else "all"

    print()
    print(f"[poorify] Inspect: \"{label}\"")
    print("=" * 60)

    files = _find_module_files(keyword)
    if files:
        print(f"\n  Files ({len(files)})")
        for fp in files:
            info = router.analyze_file(fp)
            size_kb = info["size"] / 1024
            fn_str = f"{info['functions']} fn" if info["functions"] else ""
            cl_str = f" {info['classes']} cls" if info["classes"] else ""
            imp_str = ""
            if info["imports"]:
                imp_str = "  imports: " + ", ".join(info["imports"][:5])
                if len(info["imports"]) > 5:
                    imp_str += ", ..."
            print(
                f"    {fp}  {size_kb:.1f} kB  {info['mode']:>9}  "
                f"(cx: {info['complexity']}){fn_str}{cl_str}{imp_str}"
            )
    else:
        print(f"\n  Files: no matches on disk")

    if data["specs"]:
        print(f"\n  Specs ({len(data['specs'])})")
        for s in data["specs"]:
            print(f"    {s['target_file']}   pre: {s['pre_conditions']}   post: {s['post_conditions']}")
    else:
        print(f"\n  Specs: none")

    if data["router"]:
        print(f"\n  Complexity ({len(data['router'])} files)")
        full_count = sum(1 for r in data["router"] if r["ingestion_mode"] == "FULL")
        skel_count = sum(1 for r in data["router"] if r["ingestion_mode"] == "SKELETON")
        avg_cx = sum(r["cyclomatic_complexity"] for r in data["router"]) / len(data["router"])
        print(f"    {full_count} FULL, {skel_count} SKELETON  |  avg complexity: {avg_cx:.1f}")
        for r in data["router"]:
            print(f"    {r['file_path']}  {r['ingestion_mode']} (cx: {r['cyclomatic_complexity']})")
    else:
        print(f"\n  Complexity: no files routed")

    if data["assertions"]:
        print(f"\n  Assertions ({len(data['assertions'])})")
        for a in data["assertions"]:
            last = a["last_validated"] or "never"
            print(f"    {a['rule_key']}  {a['target_file']}  (last: {last})")
    else:
        print(f"\n  Assertions: none")

    if data["metrics"]:
        total_in = sum(m["input_tokens"] for m in data["metrics"])
        total_out = sum(m["output_tokens"] for m in data["metrics"])
        total_cached = sum(m["cached_tokens"] for m in data["metrics"])
        total_saved = sum(m["skeleton_savings"] for m in data["metrics"])
        runs = len(set(m["pipeline_id"] for m in data["metrics"]))
        print(f"\n  Metrics ({runs} runs)")
        print(f"    {total_in} in / {total_out} out / {total_cached} cached / {total_saved} saved")
    else:
        print(f"\n  Metrics: none")

    if data["cascade"]:
        pending = sum(1 for c in data["cascade"] if c["status"] == "PENDING")
        print(f"\n  Cascade ({len(data['cascade'])} tasks, {pending} pending)")
        for c in data["cascade"]:
            print(f"    [{c['status']}] {c['affected_file']}: {c['error_message']}")
    else:
        print(f"\n  Cascade: none")

    if data["logs"]:
        print(f"\n  Logs ({len(data['logs'])} entries)")
        for log in data["logs"][-3:]:
            print(f"    {log['action_taken']}  {log['target_file']}  [{log['status']}]")
    else:
        print(f"\n  Logs: none")

    print()


if __name__ == "__main__":
    main()
