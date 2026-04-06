#!/usr/bin/env python3
"""run_fuzz.py — Differential fuzzing CLI for RyuSim."""

import argparse
import json
import logging
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from harness.compare import CompareResult, compare_results
from harness.generate import generate_designs
from harness.report import file_github_issue
from harness.simulate import simulate_design
from harness.triage import is_ryusim_finding, save_finding

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent
FINDINGS_DIR = REPO_ROOT / "findings"
GENERATORS = ["chimera", "vloghammer"]


def get_tool_version(cmd: list[str]) -> str:
    """Get version string from a tool."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout.strip() or result.stderr.strip() or "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "not found"


def run_fuzz(
    generators: list[str],
    count: int,
    seed: int | None,
    num_cycles: int,
    timeout: int,
    file_issues: bool,
    verbose: bool,
) -> dict:
    """Run the full fuzzing pipeline."""
    ryusim_version = get_tool_version(["ryusim", "--version"])
    verilator_version = get_tool_version(["verilator", "--version"])
    iverilog_version = get_tool_version(["iverilog", "-V"])

    if verbose:
        print(f"RyuSim: {ryusim_version}", file=sys.stderr)
        print(f"Verilator: {verilator_version}", file=sys.stderr)
        print(f"Iverilog: {iverilog_version}", file=sys.stderr)

    timestamp = datetime.now(timezone.utc).isoformat()
    all_results: list[dict] = []
    all_findings: list[dict] = []
    generator_counts: dict[str, dict] = {}

    for gen in generators:
        if verbose:
            print(f"\n--- Generator: {gen} ---", file=sys.stderr)

        # Generate designs into a temp directory
        gen_dir = Path(tempfile.mkdtemp(prefix=f"ryusim_fuzz_gen_{gen}_"))
        per_gen_count = count // len(generators) if len(generators) > 1 else count

        try:
            designs = generate_designs(
                generator=gen,
                count=per_gen_count,
                output_dir=gen_dir,
                repo_root=REPO_ROOT,
                seed=seed,
            )
        except Exception as e:
            log.error("Generator %s failed: %s", gen, e)
            if verbose:
                print(f"  ERROR: {e}", file=sys.stderr)
            generator_counts[gen] = {"total": 0, "error": str(e)}
            continue

        if verbose:
            print(f"  Generated {len(designs)} designs", file=sys.stderr)

        gen_stats = {"total": len(designs), "pass": 0, "ryusim_crash": 0,
                     "ryusim_mismatch": 0, "ryusim_parse_reject": 0,
                     "all_reject": 0, "reference_bug": 0, "ambiguous": 0, "error": 0}

        for i, design in enumerate(designs):
            if verbose:
                print(f"  [{i + 1}/{len(designs)}] {design.name}...", end="", file=sys.stderr, flush=True)

            # Simulate with all three
            try:
                sim_results = simulate_design(
                    design_path=design,
                    num_cycles=num_cycles,
                    timeout=timeout,
                    random_seed=(seed + i) if seed else 42 + i,
                )
            except Exception as e:
                log.error("Simulation failed for %s: %s", design.name, e)
                if verbose:
                    print(f" ERROR: {e}", file=sys.stderr)
                gen_stats["error"] += 1
                continue

            # Compare
            compare_result = compare_results(design, sim_results)

            if verbose:
                print(f" {compare_result.classification}", file=sys.stderr)

            # Track stats
            classification = compare_result.classification
            if classification in gen_stats:
                gen_stats[classification] += 1
            elif classification in ("verilator_bug", "iverilog_bug"):
                gen_stats["reference_bug"] += 1
            else:
                gen_stats.setdefault(classification, 0)
                gen_stats[classification] += 1

            result_entry = {
                "design": design.name,
                "generator": gen,
                "classification": classification,
                "details": compare_result.details,
                "durations": {
                    sim: r.duration
                    for sim, r in compare_result.sim_results.items()
                },
            }
            all_results.append(result_entry)

            # Triage findings
            if is_ryusim_finding(compare_result):
                finding_dir = save_finding(
                    result=compare_result,
                    findings_dir=FINDINGS_DIR,
                    generator=gen,
                    seed=(seed + i) if seed else None,
                    ryusim_version=ryusim_version,
                    verilator_version=verilator_version,
                    iverilog_version=iverilog_version,
                )
                finding_entry = {
                    "id": finding_dir.name,
                    "classification": classification,
                    "generator": gen,
                    "path": str(finding_dir),
                }

                if file_issues:
                    issue_url = file_github_issue(finding_dir)
                    if issue_url:
                        finding_entry["github_issue"] = issue_url

                all_findings.append(finding_entry)

        generator_counts[gen] = gen_stats

    # Build summary
    total = sum(gc.get("total", 0) for gc in generator_counts.values())
    summary = {
        "total": total,
        "pass": sum(gc.get("pass", 0) for gc in generator_counts.values()),
        "ryusim_crash": sum(gc.get("ryusim_crash", 0) for gc in generator_counts.values()),
        "ryusim_mismatch": sum(gc.get("ryusim_mismatch", 0) for gc in generator_counts.values()),
        "ryusim_parse_reject": sum(gc.get("ryusim_parse_reject", 0) for gc in generator_counts.values()),
        "all_reject": sum(gc.get("all_reject", 0) for gc in generator_counts.values()),
        "reference_bug": sum(gc.get("reference_bug", 0) for gc in generator_counts.values()),
        "ambiguous": sum(gc.get("ambiguous", 0) for gc in generator_counts.values()),
        "error": sum(gc.get("error", 0) for gc in generator_counts.values()),
        "generator_counts": generator_counts,
        "ryusim_version": ryusim_version,
        "verilator_version": verilator_version,
        "iverilog_version": iverilog_version,
        "timestamp": timestamp,
        "findings": all_findings,
        "results": all_results,
    }

    return summary


def reproduce_finding(finding_dir: Path, timeout: int, verbose: bool) -> dict:
    """Re-run a saved finding to check if it still reproduces."""
    import yaml
    metadata_path = finding_dir / "finding.yaml"
    if not metadata_path.exists():
        print(f"Error: {metadata_path} not found", file=sys.stderr)
        sys.exit(1)

    metadata = yaml.safe_load(metadata_path.read_text())
    design_path = finding_dir / metadata.get("design", "design.sv")

    if not design_path.exists():
        print(f"Error: {design_path} not found", file=sys.stderr)
        sys.exit(1)

    if verbose:
        print(f"Reproducing finding {metadata.get('id', 'unknown')}...", file=sys.stderr)
        print(f"  Classification: {metadata.get('classification')}", file=sys.stderr)
        print(f"  Design: {design_path}", file=sys.stderr)

    sim_results = simulate_design(
        design_path=design_path,
        num_cycles=100,
        timeout=timeout,
        keep_workdir=True,
    )
    compare_result = compare_results(design_path, sim_results)

    if verbose:
        print(f"  Result: {compare_result.classification}", file=sys.stderr)
        print(f"  Details: {compare_result.details}", file=sys.stderr)

    return {
        "original_classification": metadata.get("classification"),
        "current_classification": compare_result.classification,
        "reproduced": compare_result.classification == metadata.get("classification"),
        "details": compare_result.details,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Differential fuzzing for RyuSim",
    )
    parser.add_argument("--all", action="store_true", help="Run all generators")
    parser.add_argument("--generator", type=str, choices=GENERATORS, help="Specific generator")
    parser.add_argument("--count", type=int, default=100, help="Number of designs to generate (default: 100)")
    parser.add_argument("--seed", type=int, help="Reproducibility seed (Chimera only)")
    parser.add_argument("--cycles", type=int, default=100, help="Simulation cycles per design (default: 100)")
    parser.add_argument("--timeout", type=int, default=60, help="Per-design timeout in seconds (default: 60)")
    parser.add_argument("--output", type=str, help="Output JSON file path")
    parser.add_argument("--file-issues", action="store_true", help="Auto-file GitHub issues for findings")
    parser.add_argument("--reproduce", type=str, help="Re-run a saved finding directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print progress to stderr")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(name)s: %(message)s",
        stream=sys.stderr,
    )

    if args.reproduce:
        result = reproduce_finding(Path(args.reproduce), args.timeout, args.verbose)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["reproduced"] else 1)

    if not args.all and not args.generator:
        parser.print_help()
        sys.exit(0)

    generators = GENERATORS if args.all else [args.generator]

    summary = run_fuzz(
        generators=generators,
        count=args.count,
        seed=args.seed,
        num_cycles=args.cycles,
        timeout=args.timeout,
        file_issues=args.file_issues,
        verbose=args.verbose,
    )

    print(json.dumps(summary, indent=2))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2) + "\n")
        if args.verbose:
            print(f"Results written to {args.output}", file=sys.stderr)

    # Print summary to stderr
    print(
        f"\nSummary: {summary['total']} designs — "
        f"{summary['pass']} pass, "
        f"{summary['ryusim_crash']} crashes, "
        f"{summary['ryusim_mismatch']} mismatches, "
        f"{summary['ryusim_parse_reject']} parse rejects, "
        f"{summary['all_reject']} all-reject, "
        f"{summary['reference_bug']} ref bugs, "
        f"{len(summary['findings'])} findings saved",
        file=sys.stderr,
    )

    # Exit non-zero if any RyuSim findings
    if summary["findings"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
