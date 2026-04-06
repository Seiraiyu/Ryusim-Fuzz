#!/usr/bin/env python3
"""harness/compare.py — Compare simulation results across simulators."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from vcdvcd import VCDVCD

from harness.simulate import SimResult

log = logging.getLogger(__name__)

# Classification constants
PASS = "pass"
RYUSIM_CRASH = "ryusim_crash"
RYUSIM_MISMATCH = "ryusim_mismatch"
RYUSIM_PARSE_REJECT = "ryusim_parse_reject"
ALL_REJECT = "all_reject"
VERILATOR_BUG = "verilator_bug"
IVERILOG_BUG = "iverilog_bug"
AMBIGUOUS = "ambiguous"
ERROR = "error"


@dataclass
class CompareResult:
    design: Path
    classification: str
    details: str
    sim_results: dict[str, SimResult] = field(default_factory=dict)
    vcd_diffs: dict[str, str] = field(default_factory=dict)


def _run_vcddiff(vcd_a: Path, vcd_b: Path, timeout: int = 30) -> tuple[bool, str]:
    """Compare two VCD files using vcdvcd library. Returns (match, diff_output)."""
    try:
        a = VCDVCD(str(vcd_a))
        b = VCDVCD(str(vcd_b))
    except Exception as e:
        return False, f"VCD parse error: {e}"

    diffs = []
    a_signals = set(a.signals)
    b_signals = set(b.signals)

    # Compare signal names (ignoring scope prefixes — just use leaf names)
    a_leaf = {s.split(".")[-1]: s for s in a_signals}
    b_leaf = {s.split(".")[-1]: s for s in b_signals}

    common_leaves = set(a_leaf.keys()) & set(b_leaf.keys())
    if not common_leaves:
        return False, f"No common signals: A has {sorted(a_leaf.keys())[:5]}, B has {sorted(b_leaf.keys())[:5]}"

    for leaf in sorted(common_leaves):
        a_sig = a[a_leaf[leaf]]
        b_sig = b[b_leaf[leaf]]
        a_tv = a_sig.tv
        b_tv = b_sig.tv

        if a_tv != b_tv:
            # Find first difference
            max_len = max(len(a_tv), len(b_tv))
            for i in range(max_len):
                a_val = a_tv[i] if i < len(a_tv) else "(end)"
                b_val = b_tv[i] if i < len(b_tv) else "(end)"
                if a_val != b_val:
                    diffs.append(f"{leaf}: first diff at index {i}: {a_val} vs {b_val}")
                    break

    if diffs:
        return False, "\n".join(diffs[:20])
    return True, "All common signals match"


def _sim_ok(r: SimResult) -> bool:
    """Did the simulator complete successfully?"""
    return r.exit_code == 0


def _sim_crashed(r: SimResult) -> bool:
    """Did the simulator crash or timeout?"""
    return r.exit_code != 0


def compare_results(
    design: Path,
    sim_results: list[SimResult],
) -> CompareResult:
    """Classify discrepancy type from simulation results.

    Compares RyuSim against Verilator and Iverilog. If both references agree
    and RyuSim differs, it's likely a RyuSim bug.
    """
    by_sim = {r.simulator: r for r in sim_results}

    ryusim = by_sim.get("ryusim")
    verilator = by_sim.get("verilator")
    icarus = by_sim.get("icarus")

    if not ryusim or not verilator or not icarus:
        return CompareResult(
            design=design,
            classification=ERROR,
            details=f"Missing simulator results: {[s for s in ['ryusim', 'verilator', 'icarus'] if s not in by_sim]}",
            sim_results=by_sim,
        )

    r_ok = _sim_ok(ryusim)
    v_ok = _sim_ok(verilator)
    i_ok = _sim_ok(icarus)

    # All reject → invalid design
    if not r_ok and not v_ok and not i_ok:
        return CompareResult(
            design=design,
            classification=ALL_REJECT,
            details="All three simulators rejected the design",
            sim_results=by_sim,
        )

    # RyuSim crashed/rejected, both references OK
    if not r_ok and v_ok and i_ok:
        # Distinguish crash vs parse rejection
        classification = RYUSIM_CRASH
        if ryusim.exit_code > 0:  # Non-zero but not signal
            classification = RYUSIM_PARSE_REJECT
        return CompareResult(
            design=design,
            classification=classification,
            details=f"RyuSim failed (exit {ryusim.exit_code}) but Verilator and Iverilog succeeded",
            sim_results=by_sim,
        )

    # Reference simulator bugs
    if r_ok and not v_ok and i_ok:
        return CompareResult(
            design=design,
            classification=VERILATOR_BUG,
            details="Verilator crashed but RyuSim and Iverilog succeeded",
            sim_results=by_sim,
        )
    if r_ok and v_ok and not i_ok:
        return CompareResult(
            design=design,
            classification=IVERILOG_BUG,
            details="Iverilog crashed but RyuSim and Verilator succeeded",
            sim_results=by_sim,
        )

    # Ambiguous cases
    if not r_ok:
        return CompareResult(
            design=design,
            classification=AMBIGUOUS,
            details=f"RyuSim failed (exit {ryusim.exit_code}), mixed reference results",
            sim_results=by_sim,
        )

    # All three succeeded — compare VCDs
    vcd_diffs = {}

    if ryusim.vcd_path and verilator.vcd_path:
        match, diff_out = _run_vcddiff(ryusim.vcd_path, verilator.vcd_path)
        vcd_diffs["ryusim_vs_verilator"] = diff_out
        if not match:
            # Check if Verilator and Iverilog agree with each other
            if icarus.vcd_path:
                vi_match, vi_diff = _run_vcddiff(verilator.vcd_path, icarus.vcd_path)
                vcd_diffs["verilator_vs_icarus"] = vi_diff
                if vi_match:
                    # Both references agree, RyuSim differs → RyuSim bug
                    return CompareResult(
                        design=design,
                        classification=RYUSIM_MISMATCH,
                        details="RyuSim VCD differs from both Verilator and Iverilog (which agree with each other)",
                        sim_results=by_sim,
                        vcd_diffs=vcd_diffs,
                    )
                else:
                    # All three disagree — ambiguous
                    return CompareResult(
                        design=design,
                        classification=AMBIGUOUS,
                        details="All three simulators produced different VCD output",
                        sim_results=by_sim,
                        vcd_diffs=vcd_diffs,
                    )
            # No Iverilog VCD to cross-check
            return CompareResult(
                design=design,
                classification=AMBIGUOUS,
                details="RyuSim VCD differs from Verilator, no Iverilog VCD for cross-check",
                sim_results=by_sim,
                vcd_diffs=vcd_diffs,
            )

    # All VCDs match (or no VCDs to compare)
    return CompareResult(
        design=design,
        classification=PASS,
        details="All simulators agree",
        sim_results=by_sim,
        vcd_diffs=vcd_diffs,
    )
