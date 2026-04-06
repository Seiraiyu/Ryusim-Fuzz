#!/usr/bin/env python3
"""harness/triage.py — Save findings with reproducers and metadata."""

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

from harness.compare import CompareResult

log = logging.getLogger(__name__)

# Classifications that indicate a RyuSim bug worth saving
RYUSIM_FINDINGS = {"ryusim_crash", "ryusim_mismatch", "ryusim_parse_reject"}


def is_ryusim_finding(result: CompareResult) -> bool:
    """Should this result be saved as a finding?"""
    return result.classification in RYUSIM_FINDINGS


def _next_finding_id(findings_dir: Path, date_str: str) -> str:
    """Generate the next sequential finding ID for today."""
    existing = sorted(findings_dir.glob(f"{date_str}-*"))
    if not existing:
        return f"{date_str}-0001"
    last = existing[-1].name
    try:
        seq = int(last.split("-")[-1]) + 1
    except ValueError:
        seq = len(existing) + 1
    return f"{date_str}-{seq:04d}"


def save_finding(
    result: CompareResult,
    findings_dir: Path,
    generator: str,
    seed: int | None = None,
    ryusim_version: str = "unknown",
    verilator_version: str = "unknown",
    iverilog_version: str = "unknown",
) -> Path:
    """Save a finding to the findings directory.

    Creates a subdirectory with the design file, VCDs, and metadata YAML.

    Returns:
        Path to the finding directory.
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    finding_id = _next_finding_id(findings_dir, date_str)

    finding_dir = findings_dir / finding_id
    finding_dir.mkdir(parents=True, exist_ok=True)

    # Copy design file
    design_dst = finding_dir / "design.sv"
    shutil.copy2(result.design, design_dst)

    # Copy VCD files
    for sim_name, sim_result in result.sim_results.items():
        if sim_result.vcd_path and sim_result.vcd_path.exists():
            shutil.copy2(sim_result.vcd_path, finding_dir / f"{sim_name}.vcd")

    # Save stdout/stderr from RyuSim
    ryusim_result = result.sim_results.get("ryusim")
    if ryusim_result:
        (finding_dir / "ryusim_stdout.txt").write_text(ryusim_result.stdout)
        (finding_dir / "ryusim_stderr.txt").write_text(ryusim_result.stderr)

    # Write metadata
    metadata = {
        "id": finding_id,
        "classification": result.classification,
        "details": result.details,
        "generator": generator,
        "seed": seed,
        "design": "design.sv",
        "minimal_design": None,
        "ryusim_version": ryusim_version,
        "verilator_version": verilator_version,
        "iverilog_version": iverilog_version,
        "timestamp": now.isoformat(),
        "github_issue": None,
        "notes": "",
    }
    (finding_dir / "finding.yaml").write_text(
        yaml.dump(metadata, default_flow_style=False, sort_keys=False)
    )

    # Save VCD diffs if any
    if result.vcd_diffs:
        diff_text = ""
        for pair, diff in result.vcd_diffs.items():
            diff_text += f"--- {pair} ---\n{diff}\n\n"
        (finding_dir / "vcd_diffs.txt").write_text(diff_text)

    log.info("Finding saved: %s (%s)", finding_id, result.classification)
    return finding_dir
