#!/usr/bin/env python3
"""harness/simulate.py — Run generated designs through simulators via cocotb."""

import logging
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from harness.parse_ports import ModuleInfo, parse_verilog

log = logging.getLogger(__name__)

SIMULATORS = ["ryusim", "verilator", "icarus"]

TEMPLATES_DIR = Path(__file__).parent / "templates"


@dataclass
class SimResult:
    simulator: str
    exit_code: int
    vcd_path: Path | None
    stdout: str
    stderr: str
    duration: float


def _render_templates(
    module_info: ModuleInfo,
    verilog_source: str,
    work_dir: Path,
    num_cycles: int = 100,
    random_seed: int = 42,
) -> None:
    """Render cocotb Makefile and testbench into work_dir."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        keep_trailing_newline=True,
    )

    test_module = "test_generated"
    is_sequential = module_info.has_clock

    # Render Makefile
    makefile_tmpl = env.get_template("Makefile.j2")
    makefile_content = makefile_tmpl.render(
        verilog_source=verilog_source,
        top_module=module_info.name,
        test_module=test_module,
    )
    (work_dir / "Makefile").write_text(makefile_content)

    # Prepare port data for templates
    if is_sequential:
        input_ports = [
            {"name": p.name, "max_val": (1 << p.width) - 1}
            for p in module_info.non_clock_inputs
        ]
        template_name = "test_generated.py.j2"
        template_vars = {
            "top_module": module_info.name,
            "clock_port": module_info.clock_port,
            "input_ports": input_ports,
            "num_cycles": num_cycles,
            "random_seed": random_seed,
        }
    else:
        input_ports = [
            {"name": p.name, "max_val": (1 << p.width) - 1}
            for p in module_info.input_ports
        ]
        template_name = "test_combinational.py.j2"
        template_vars = {
            "top_module": module_info.name,
            "input_ports": input_ports,
            "num_vectors": num_cycles,
            "random_seed": random_seed,
        }

    test_tmpl = env.get_template(template_name)
    test_content = test_tmpl.render(**template_vars)
    (work_dir / f"{test_module}.py").write_text(test_content)


def _run_sim(
    sim: str,
    work_dir: Path,
    timeout: int = 60,
) -> SimResult:
    """Run a single simulator via make SIM=<sim>."""
    start = time.perf_counter()

    # Clean previous sim artifacts to avoid stale VCDs
    for d in ["sim_build", "obj_dir"]:
        p = work_dir / d
        if p.exists():
            shutil.rmtree(p)

    env_vars = {
        "SIM": sim,
        "COCOTB_REDUCED_LOG_FMT": "1",
    }
    # Enable VCD tracing
    env_vars["WAVES"] = "1"
    if sim == "ryusim":
        env_vars["EXTRA_ARGS"] = "--trace-vcd"
    elif sim == "verilator":
        env_vars["EXTRA_ARGS"] = "--trace -Wno-fatal"

    try:
        result = subprocess.run(
            ["make"],
            capture_output=True,
            text=True,
            cwd=str(work_dir),
            timeout=timeout,
            env={**subprocess.os.environ, **env_vars},
        )
        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired:
        return SimResult(
            simulator=sim,
            exit_code=-1,
            vcd_path=None,
            stdout="",
            stderr=f"Timeout after {timeout}s",
            duration=time.perf_counter() - start,
        )
    except FileNotFoundError:
        return SimResult(
            simulator=sim,
            exit_code=-2,
            vcd_path=None,
            stdout="",
            stderr=f"make not found or SIM={sim} not available",
            duration=time.perf_counter() - start,
        )

    duration = time.perf_counter() - start

    # Find VCD output (cocotb+icarus may produce FST instead of VCD)
    vcd_files = list(work_dir.rglob("*.vcd"))
    if not vcd_files:
        fst_files = list(work_dir.rglob("*.fst"))
        if fst_files:
            vcd_converted = fst_files[0].with_suffix(".vcd")
            try:
                subprocess.run(
                    ["fst2vcd", str(fst_files[0]), "-o", str(vcd_converted)],
                    capture_output=True,
                    timeout=30,
                )
                if vcd_converted.exists():
                    vcd_files = [vcd_converted]
            except (FileNotFoundError, subprocess.TimeoutExpired):
                log.debug("fst2vcd not available, cannot convert %s", fst_files[0])
    vcd_path = vcd_files[0] if vcd_files else None

    return SimResult(
        simulator=sim,
        exit_code=exit_code,
        vcd_path=vcd_path,
        stdout=stdout,
        stderr=stderr,
        duration=duration,
    )


def simulate_design(
    design_path: Path,
    simulators: list[str] | None = None,
    num_cycles: int = 100,
    timeout: int = 60,
    random_seed: int = 42,
    keep_workdir: bool = False,
) -> list[SimResult]:
    """Run a generated Verilog design through each simulator.

    Creates a temporary cocotb environment, renders Makefile + testbench,
    and runs make SIM=<sim> for each simulator.

    Args:
        design_path: Path to the .v/.sv file.
        simulators: List of simulators to run. Defaults to all three.
        num_cycles: Number of clock cycles / input vectors.
        timeout: Per-simulator timeout in seconds.
        random_seed: Seed for testbench random stimulus (same across all sims).
        keep_workdir: If True, don't clean up temp directory (for debugging).

    Returns:
        List of SimResult, one per simulator.
    """
    if simulators is None:
        simulators = SIMULATORS

    # Parse the design to get module/port info
    module_info = parse_verilog(design_path)
    if module_info is None:
        return [
            SimResult(
                simulator=sim,
                exit_code=-3,
                vcd_path=None,
                stdout="",
                stderr=f"Could not parse module from {design_path}",
                duration=0,
            )
            for sim in simulators
        ]

    results = []
    for sim in simulators:
        # Create a fresh temp dir per simulator to avoid cross-contamination
        work_dir = Path(tempfile.mkdtemp(prefix=f"ryusim_fuzz_{sim}_"))
        try:
            # Copy design file
            design_copy = work_dir / design_path.name
            shutil.copy2(design_path, design_copy)

            # Render templates
            _render_templates(
                module_info=module_info,
                verilog_source=design_path.name,
                work_dir=work_dir,
                num_cycles=num_cycles,
                random_seed=random_seed,
            )

            # Run simulator
            result = _run_sim(sim, work_dir, timeout=timeout)

            # If VCD was produced, copy it somewhere persistent before cleanup
            if result.vcd_path and result.vcd_path.exists():
                persistent_vcd = design_path.parent / f"{design_path.stem}_{sim}.vcd"
                shutil.copy2(result.vcd_path, persistent_vcd)
                result = SimResult(
                    simulator=result.simulator,
                    exit_code=result.exit_code,
                    vcd_path=persistent_vcd,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    duration=result.duration,
                )

            results.append(result)
        finally:
            if not keep_workdir:
                shutil.rmtree(work_dir, ignore_errors=True)

    return results
