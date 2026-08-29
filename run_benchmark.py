"""Entrypoint script to execute the Automated Evaluation Benchmark Suite (PRD Section 15)."""

import asyncio
from src.evaluation.benchmark_runner import BenchmarkRunner
from src.evaluation.report_generator import ReportGenerator

async def main():
    print("=" * 75)
    print("Executing Self-Healing Cloud Deployment Pipelines Benchmark Suite (PRD §15)")
    print("=" * 75)

    runner = BenchmarkRunner()
    summary_dict = await runner.execute_all()
    summary = runner.collector.compute_summary()

    # Generate Markdown and JSON Reports
    md_report = ReportGenerator.generate_markdown(summary, "evaluation_report.md")
    ReportGenerator.generate_json(summary, "evaluation_report.json")

    print("\nBenchmark Execution Complete!")
    print(f"- Total Scenarios Evaluated: {summary.total_scenarios_run}")
    print(f"- Agentic MTTR:              {summary.agentic_mttr_seconds:.3f} s")
    print(f"- Baseline MTTR:             {summary.baseline_mttr_seconds:.1f} s")
    print(f"- MTTR Improvement:          {summary.mttr_reduction_pct:.1f}% Reduction")
    print(f"- Diagnosis Accuracy:        {summary.diagnosis_accuracy_pct:.1f}%")
    print(f"- Repair Success Rate:       {summary.repair_success_rate_pct:.1f}%")
    print(f"- Human Intervention Rate:   {summary.human_intervention_rate_pct:.1f}%")
    print(f"- Chaos Safety Rate:         {summary.chaos_experiment_safety_rate_pct:.1f}%")
    print("\nSaved Reports:")
    print("  -> evaluation_report.md")
    print("  -> evaluation_report.json")
    print("=" * 75)

if __name__ == "__main__":
    asyncio.run(main())
