import time
import uuid
from datetime import datetime
from . import db


def new_pipeline_id() -> str:
    return datetime.now().strftime("P%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]


class MeterContext:
    def __init__(self, pipeline_id: str, phase: str, target_file: str):
        self.pipeline_id = pipeline_id
        self.phase = phase
        self.target_file = target_file
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_tokens = 0
        self.context_window_size = 0
        self.context_window_max = 0
        self.retry_attempt = 0
        self.skeleton_savings = 0
        self._start = 0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        dur = int((time.perf_counter() - self._start) * 1000)
        db.log_token_metric(
            self.pipeline_id, self.phase, self.target_file,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cached_tokens=self.cached_tokens,
            context_window_size=self.context_window_size,
            context_window_max=self.context_window_max,
            retry_attempt=self.retry_attempt,
            skeleton_savings=self.skeleton_savings,
            duration_ms=dur)


def summary(pipeline_id: str) -> str:
    rows = db.get_metrics_for_pipeline(pipeline_id)
    if not rows:
        return f"[poorify] No metrics found for pipeline {pipeline_id}"

    lines = []
    lines.append("-" * 78)
    lines.append(f"  Pipeline: {pipeline_id}")
    lines.append("-" * 78)
    h = f"  {'Phase':<16} {'Input':>8} {'Output':>8} {'Cached':>8} {'Ctx%':>7} {'Dur(ms)':>8} {'Retry':>6} {'Saved':>8}"
    lines.append(h)
    lines.append("  " + "-" * 75)
    tot_in = tot_out = tot_cached = tot_dur = tot_saved = 0
    max_ctx = 0
    max_ctx_max = 1
    for r in rows:
        tot_in += r["input_tokens"]
        tot_out += r["output_tokens"]
        tot_cached += r["cached_tokens"]
        tot_dur += r["duration_ms"]
        tot_saved += r["skeleton_savings"]
        if r["context_window_max"] > max_ctx_max:
            max_ctx_max = r["context_window_max"]
            max_ctx = r["context_window_size"]
        ctx_pct = (r["context_window_size"] / r["context_window_max"] * 100
                   ) if r["context_window_max"] else 0
        lines.append(
            f"  {r['phase']:<16} {r['input_tokens']:>8} {r['output_tokens']:>8} {r['cached_tokens']:>8} {ctx_pct:>6.1f}% {r['duration_ms']:>8} {r['retry_attempt']:>6} {r['skeleton_savings']:>8}")
    lines.append("  " + "-" * 75)
    ctx_pct = (max_ctx / max_ctx_max * 100) if max_ctx_max else 0
    lines.append(
        f"  {'TOTAL':<16} {tot_in:>8} {tot_out:>8} {tot_cached:>8} {ctx_pct:>6.1f}% {tot_dur:>8} {rows[-1]['retry_attempt'] if len(rows)==1 else '':>6} {tot_saved:>8}")
    lines.append("-" * 78)
    return "\n".join(lines)


def overall_stats() -> str:
    agg = db.get_aggregate_metrics()
    if not agg:
        return "[poorify] No metrics recorded yet."

    lines = []
    lines.append("-" * 75)
    lines.append("  Aggregate Statistics (All Pipelines)")
    lines.append("-" * 75)
    h = f"  {'Phase':<16} {'Runs':>6} {'AvgIn':>8} {'AvgOut':>8} {'AvgCached':>8} {'MaxCtx':>8} {'AvgDur':>8} {'Saved':>8}"
    lines.append(h)
    lines.append("  " + "-" * 72)
    for r in agg:
        lines.append(
            f"  {r['phase']:<16} {r['runs']:>6} {r['avg_input']:>8.0f} {r['avg_output']:>8.0f} {r['avg_cached']:>8.0f} {r['max_ctx']:>8} {r['avg_dur']:>8.0f} {r['total_saved']:>8}")
    lines.append("-" * 75)
    return "\n".join(lines)


def print_dashboard(pipeline_id: str | None = None) -> None:
    if pipeline_id:
        print(summary(pipeline_id))
    else:
        pipelines = db.get_all_pipeline_ids()
        if not pipelines:
            print("[poorify] No pipelines recorded yet.")
            return
        print(summary(pipelines[0]["pipeline_id"]))
        print()
        print(overall_stats())
