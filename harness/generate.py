#!/usr/bin/env python3
"""harness/generate.py — Wrappers around Chimera and VlogHammer generators."""

import logging
import re
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

# Patterns that indicate unsupported or non-synthesizable constructs
UNSUPPORTED_PATTERNS = [
    re.compile(r"\binitial\b"),
    re.compile(r"#\s*\d+"),                # # delays
    re.compile(r"\$readmemh\b"),
    re.compile(r"\$display\b"),
    re.compile(r"\$finish\b"),
    re.compile(r"\$fopen\b"),
    re.compile(r"\bfork\b"),
    re.compile(r"\bjoin\b"),
    re.compile(r"\bjoin_any\b"),
    re.compile(r"\bjoin_none\b"),
    # Exotic net types that simulators reject
    re.compile(r"\bsupply0\b"),
    re.compile(r"\bsupply1\b"),
    re.compile(r"\btri0\b"),
    re.compile(r"\btri1\b"),
    re.compile(r"\buwire\b"),
    re.compile(r"\bwor\b"),
    re.compile(r"\bwand\b"),
    re.compile(r"\binout\b"),
    re.compile(r"\breal\b"),
    # Contradictory port declarations (e.g. "output wire input reg")
    re.compile(r"\boutput\s+\w+\s+input\b"),
    re.compile(r"\binput\s+\w+\s+input\b"),
    # Hierarchical assigns (e.g. "assign modCall_1.id_3 = 0")
    re.compile(r"\bassign\s+\w+\.\s*\w+"),
]


def is_synthesizable(verilog_path: Path) -> bool:
    """Check if a Verilog file contains only synthesizable constructs."""
    content = verilog_path.read_text()
    for pattern in UNSUPPORTED_PATTERNS:
        if pattern.search(content):
            log.debug("Filtered %s: matched %s", verilog_path.name, pattern.pattern)
            return False
    return True


def generate_chimera(
    count: int,
    output_dir: Path,
    chimera_dir: Path,
    seed: int | None = None,
    token_count: int = 200,
) -> list[Path]:
    """Generate Verilog designs using ChiGen.

    Args:
        count: Number of designs to generate (will over-generate to compensate for filtering).
        output_dir: Directory to write generated .v files.
        chimera_dir: Path to the chimera submodule root.
        seed: Base seed for reproducibility. Each design gets seed+i.
        token_count: Minimum token count per design (-t flag).

    Returns:
        List of paths to generated .v files that passed the synthesizability filter.
    """
    chimera_bin = chimera_dir / "build" / "Chimera"
    if not chimera_bin.exists():
        raise FileNotFoundError(
            f"ChiGen binary not found at {chimera_bin}. Run: bash scripts/setup_chimera.sh"
        )

    # Use the pre-trained 1-gram grammar
    grammar = chimera_dir / "json" / "1gram_size_test.json"
    if not grammar.exists():
        # Fall back to any available grammar
        grammars = list((chimera_dir / "json").glob("*.json"))
        if not grammars:
            raise FileNotFoundError(f"No grammar files found in {chimera_dir / 'json'}")
        grammar = grammars[0]
        log.info("Using grammar: %s", grammar.name)

    output_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    # Over-generate by 2x to compensate for filtering
    attempt_count = count * 2
    for i in range(attempt_count):
        if len(generated) >= count:
            break

        outfile = output_dir / f"chimera_{i:04d}.v"
        cmd = [str(chimera_bin), "--printseed", "-t", str(token_count), str(grammar), "1"]
        if seed is not None:
            cmd.extend(["--seed", str(seed + i)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                log.debug("ChiGen failed for seed %s: %s", seed, result.stderr[:200])
                continue

            outfile.write_text(result.stdout)

            if is_synthesizable(outfile):
                generated.append(outfile)
            else:
                outfile.unlink()

        except subprocess.TimeoutExpired:
            log.debug("ChiGen timed out for iteration %d", i)
        except Exception as e:
            log.debug("ChiGen error for iteration %d: %s", i, e)

    log.info("Chimera: generated %d/%d designs (from %d attempts)", len(generated), count, attempt_count)
    return generated


def generate_vloghammer(
    count: int,
    output_dir: Path,
    vloghammer_dir: Path,
    seed: int | None = None,
) -> list[Path]:
    """Generate Verilog expression test modules using VlogHammer.

    VlogHammer generates via a compiled C++ program (scripts/generate.cc).
    The output is purely combinational assign statements, so all designs
    are inherently synthesizable — no filtering needed.

    Args:
        count: Number of designs to generate.
        output_dir: Directory to write generated .v files.
        vloghammer_dir: Path to the vloghammer submodule root.
        seed: Unused (VlogHammer's generator is deterministic).

    Returns:
        List of paths to generated .v files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    rtl_dir = vloghammer_dir / "rtl"

    # Build the generator if needed
    gen_cc = vloghammer_dir / "scripts" / "generate.cc"
    gen_bin = vloghammer_dir / "scripts" / "generate"
    if not gen_bin.exists():
        if not gen_cc.exists():
            raise FileNotFoundError(
                f"VlogHammer generate.cc not found at {gen_cc}. Check submodule."
            )
        log.info("Building VlogHammer generator...")
        subprocess.run(
            ["clang++", "-o", str(gen_bin), str(gen_cc)],
            check=True,
            timeout=30,
        )

    # Generate into VlogHammer's rtl/ directory then copy out
    rtl_dir.mkdir(parents=True, exist_ok=True)

    # Run the generator (use resolved absolute path so it works regardless of cwd)
    try:
        subprocess.run(
            [str(gen_bin.resolve())],
            cwd=str(vloghammer_dir),
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as e:
        log.warning("VlogHammer generator returned non-zero: %s", e.stderr[:200])

    # Also extract issue-based test cases
    issues_script = vloghammer_dir / "scripts" / "issues.v"
    if issues_script.exists():
        try:
            subprocess.run(
                ["perl", "-e", ""],  # Check perl is available
                capture_output=True,
                timeout=5,
            )
            subprocess.run(
                ["make", "gen_issues"],
                cwd=str(vloghammer_dir),
                capture_output=True,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            log.debug("Perl not available or gen_issues failed, skipping issue-based tests")

    # Collect generated .v files from rtl/
    generated = []
    if rtl_dir.is_dir():
        all_v_files = sorted(rtl_dir.glob("*.v"))
        for i, src in enumerate(all_v_files[:count]):
            dst = output_dir / f"vloghammer_{i:04d}.v"
            shutil.copy2(src, dst)
            generated.append(dst)

    log.info("VlogHammer: collected %d/%d designs", len(generated), count)
    return generated


def generate_designs(
    generator: str,
    count: int,
    output_dir: Path,
    repo_root: Path,
    seed: int | None = None,
) -> list[Path]:
    """Unified entry point for design generation.

    Args:
        generator: "chimera" or "vloghammer"
        count: Number of designs to generate.
        output_dir: Directory to write generated files.
        repo_root: Root of the RyuSim-Fuzz repo.
        seed: Reproducibility seed (Chimera only).

    Returns:
        List of paths to generated .v/.sv files.
    """
    if generator == "chimera":
        return generate_chimera(
            count=count,
            output_dir=output_dir / "chimera",
            chimera_dir=repo_root / "chimera",
            seed=seed,
        )
    elif generator == "vloghammer":
        return generate_vloghammer(
            count=count,
            output_dir=output_dir / "vloghammer",
            vloghammer_dir=repo_root / "vloghammer",
            seed=seed,
        )
    else:
        raise ValueError(f"Unknown generator: {generator}")
