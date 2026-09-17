"""
CLI Runner for BCA RAG System Benchmark Evaluation.

Executes reproducible benchmarks over the evaluation dataset, evaluates retrieval
ablations, generation faithfulness, and stage latencies, and exports structured JSON reports.

Usage:
    python scripts/run_rag_benchmark.py --kb-id <UUID> [--limit <N>] [--output <path>]
"""

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

# Ensure repository root is on sys.path
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.app.db.session import get_db_session  # noqa: E402
from backend.app.services.evaluation.dataset import EvaluationDatasetLoader  # noqa: E402
from backend.app.services.evaluation.runner import RAGEvaluationRunner  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run RAG system evaluation benchmark.")
    parser.add_argument(
        "--kb-id",
        type=str,
        required=True,
        help="Target Knowledge Base UUID containing indexed benchmark documents.",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Optional path to custom evaluation dataset JSON (defaults to evaluation_dataset_v1.json).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional output path for benchmark JSON report (defaults to storage/evaluation/report_<run_id>.json).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of dataset queries to run (for smoke testing).",
    )
    args = parser.parse_args()

    try:
        kb_uuid = uuid.UUID(args.kb_id)
    except ValueError:
        print(f"Error: Invalid knowledge base UUID format '{args.kb_id}'.")
        return 1

    print("[*] Loading evaluation dataset...")
    loader = EvaluationDatasetLoader(args.dataset)
    dataset = loader.load_dataset()
    if args.limit:
        dataset.items = dataset.items[: args.limit]
        print(f"[*] Limited evaluation to first {len(dataset.items)} queries.")
    else:
        print(
            f"[*] Loaded {len(dataset.items)} evaluation queries from dataset v{dataset.version}."
        )

    runner = RAGEvaluationRunner()

    print(f"[*] Starting benchmark execution across pipeline stages on KB {kb_uuid}...")
    with get_db_session() as session:
        report = await runner.evaluate_dataset(
            dataset=dataset,
            session=session,
            knowledge_base_id=kb_uuid,
        )

    # Output formatted terminal summary
    print("\n" + "=" * 70)
    print(f"BENCHMARK REPORT SUMMARY (Run ID: {report.run_id})")
    print("=" * 70)
    print(f"Total Queries Evaluated : {report.total_queries}")
    print(f"Reranker Lift (MRR)     : {report.reranker_lift_mrr:+.4f}")
    print(f"Mean Citation Validity  : {report.mean_citation_validity_rate:.4f}")
    print(f"Mean Citation Coverage  : {report.mean_citation_coverage:.4f}")
    print(f"Mean Claim Support Rate : {report.mean_claim_support_rate:.4f}")
    print(f"Mean Unsupported Rate   : {report.mean_unsupported_claim_rate:.4f}")
    print(f"Correct Refusal Rate    : {report.correct_refusal_rate:.4f}")
    print(f"False Refusal Rate      : {report.false_refusal_rate:.4f}")

    print("\n--- RETRIEVAL ABLATION COMPARISON ---")
    print(f"{'Stage':<25} | {'HitRate':<8} | {'Recall':<8} | {'Prec':<8} | {'MRR':<8}")
    print("-" * 70)
    for stage, metrics in report.ablation_summary.items():
        print(
            f"{stage:<25} | {metrics['mean_hit_rate']:<8.4f} | {metrics['mean_recall']:<8.4f} | "
            f"{metrics['mean_precision']:<8.4f} | {metrics['mean_mrr']:<8.4f}"
        )

    print("\n--- LATENCY BENCHMARKS (Exclusive Stage Timings) ---")
    print(f"{'Stage':<25} | {'Mean (ms)':<10} | {'Median (ms)':<12} | {'P95 (ms)':<10}")
    print("-" * 70)
    for stage, stats in report.latency_summary.items():
        print(f"{stage:<25} | {stats.mean:<10.2f} | {stats.median:<12.2f} | {stats.p95:<10.2f}")

    if report.failure_counts:
        print("\n--- DETECTED FAILURE DISTRIBUTION ---")
        for f_mode, count in sorted(
            report.failure_counts.items(), key=lambda x: x[1], reverse=True
        ):
            pct = (count / report.total_queries) * 100.0 if report.total_queries else 0.0
            print(f"  {f_mode:<25}: {count:>3} ({pct:.1f}%)")

    # Export report to JSON file
    if args.output:
        out_path = Path(args.output)
    else:
        out_dir = _REPO_ROOT / "storage" / "evaluation"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"benchmark_report_{report.run_id}.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2, default=str)

    print(f"\n[+] Full benchmark report saved to: {out_path}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
