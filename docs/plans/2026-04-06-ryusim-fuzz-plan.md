# RyuSim-Fuzz Implementation Plan

**Goal:** Build a differential fuzzing harness that generates Verilog via Chimera and VlogHammer, simulates with RyuSim/Verilator/Iverilog through cocotb, compares VCD waveforms, and auto-files findings as GitHub issues.

**Architecture:** Two git submodules (Chimera, VlogHammer) feed generated designs into a shared Python harness (`harness/`). The harness creates temporary cocotb environments per design, runs all three simulators via `make SIM=<sim>`, diffs VCDs with `vcddiff`, and saves discrepancies to `findings/`. A CLI (`run_fuzz.py`) orchestrates everything.

**Tech Stack:** Python 3.10+, cocotb (Seiraiyu fork), Jinja2, PyYAML, vcddiff, CMake (Chimera build), Clang (VlogHammer build)

| Task | Description | Status | Tested | Pushed |
|------|-------------|--------|--------|--------|
| 1 | Repo scaffold: .gitignore, CLAUDE.md, README, requirements.txt | pending | no | no |
| 2 | Add Chimera git submodule | pending | no | no |
| 3 | Add VlogHammer git submodule | pending | no | no |
| 4 | Chimera setup script + generate wrapper | pending | no | no |
| 5 | VlogHammer setup script + generate wrapper | pending | no | no |
| 6 | Cocotb Makefile + testbench Jinja2 templates | pending | no | no |
| 7 | Verilog port parser for auto-detecting modules | pending | no | no |
| 8 | Simulator harness (simulate.py) | pending | no | no |
| 9 | VCD comparator (compare.py) | pending | no | no |
| 10 | Triage module (triage.py) | pending | no | no |
| 11 | GitHub issue reporter (report.py) | pending | no | no |
| 12 | CLI entry point (run_fuzz.py) | pending | no | no |
| 13 | CI workflow: nightly | pending | no | no |
| 14 | CI workflow: weekly deep | pending | no | no |
| 15 | CI workflow: on-demand | pending | no | no |

---

### Task 1: Repo scaffold

**Files:**
- Create: `RyuSim-Fuzz/.gitignore`
- Create: `RyuSim-Fuzz/CLAUDE.md`
- Create: `RyuSim-Fuzz/README.md`
- Create: `RyuSim-Fuzz/requirements.txt`
- Create: `RyuSim-Fuzz/harness/__init__.py`
- Create: `RyuSim-Fuzz/harness/templates/.gitkeep`
- Create: `RyuSim-Fuzz/findings/.gitkeep`
- Create: `RyuSim-Fuzz/results/.gitkeep`
- Create: `RyuSim-Fuzz/scripts/.gitkeep`

**Step 1: Create .gitignore**

```
# RyuSim-Fuzz/.gitignore
__pycache__/
*.pyc
*.egg-info/
.eggs/
*.so
*.o
obj_dir/
sim_build/
*.vcd
*.xml
build/

# Generated designs (ephemeral)
generated/

# Results are CI artifacts, not committed
results/*.json

# Findings are committed (they're the whole point)
!findings/
```

**Step 2: Create CLAUDE.md**

```markdown
# CLAUDE.md

## Project Purpose

RyuSim-Fuzz is a differential fuzzing harness for [RyuSim](https://github.com/Seiraiyu/RyuSimAlt). It generates thousands of Verilog designs via Chimera (grammar-based) and VlogHammer (expression-level), simulates each with RyuSim, Verilator, and Icarus Verilog through cocotb, and flags any discrepancies via VCD waveform comparison.

## Architecture

Two generators feed into a shared harness:

| Directory | Source | Purpose |
|-----------|--------|---------|
| `chimera/` | [lac-dcc/chimera](https://github.com/lac-dcc/chimera) (submodule) | Grammar-based Verilog design generator |
| `vloghammer/` | [YosysHQ/VlogHammer](https://github.com/YosysHQ/VlogHammer) (submodule) | Expression-level differential test generator |
| `harness/` | This repo | Shared orchestration: generate → simulate → compare → triage |

### Pipeline

1. **Generate** — Chimera/VlogHammer produce `.sv`/`.v` files
2. **Filter** — Discard designs with unsupported constructs (`initial`, `$display`, `#` delays)
3. **Simulate** — Create temp cocotb env, run `make SIM=ryusim`, `make SIM=verilator`, `make SIM=icarus`
4. **Compare** — `vcddiff` between RyuSim VCD and each reference
5. **Triage** — Save findings to `findings/` with metadata
6. **Report** — Auto-file GitHub issues on RyuSimAlt

## Key Constraints

- All simulation goes through cocotb Makefiles (`SIM=` variable) — same Makefile, three invocations
- RyuSim only supports synthesizable constructs — generated designs are filtered
- VCD waveform diff is the comparison oracle

## Commands

```bash
# Setup
bash scripts/setup_chimera.sh    # Build ChiGen from submodule
bash scripts/setup_vloghammer.sh # Build VlogHammer from submodule
bash scripts/setup_ryusim.sh     # Install RyuSim binary

# Run fuzzing
python run_fuzz.py --all --count 100
python run_fuzz.py --generator chimera --count 50 --seed 42
python run_fuzz.py --generator vloghammer --count 200
python run_fuzz.py --all --count 100 --file-issues --output results/fuzz.json

# Reproduce a finding
python run_fuzz.py --reproduce findings/2026-04-06-0001/
```

## Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| `ryusim` | Simulator under test | `scripts/setup_ryusim.sh` |
| `cocotb` | Simulation framework (Seiraiyu fork) | `pip install -r requirements.txt` |
| `verilator` | Reference simulator | `apt install verilator` |
| `iverilog` | Reference simulator | `apt install iverilog` |
| `vcddiff` | VCD comparison | `pip install vcdvcd` (includes vcddiff) |
| `cmake`, `g++` | Build ChiGen | `apt install cmake g++` |
| `clang` | Build VlogHammer generate.cc | `apt install clang` |
```

**Step 3: Create README.md**

```markdown
# RyuSim-Fuzz

Differential fuzzing for [RyuSim](https://github.com/Seiraiyu/RyuSimAlt) — generates Verilog designs via [Chimera](https://github.com/lac-dcc/chimera) and [VlogHammer](https://github.com/YosysHQ/VlogHammer), simulates with RyuSim + Verilator + Icarus Verilog, and flags discrepancies via VCD waveform comparison.

## Quick start

```bash
git clone --recurse-submodules https://github.com/Seiraiyu/RyuSim-Fuzz.git
cd RyuSim-Fuzz

# Install dependencies
pip install -r requirements.txt
bash scripts/setup_ryusim.sh
bash scripts/setup_chimera.sh
bash scripts/setup_vloghammer.sh

# Run 100 designs through all generators
python run_fuzz.py --all --count 100 --verbose
```

## Findings

Discovered discrepancies are saved to `findings/` with a minimal reproducer, VCD outputs from all simulators, and metadata. See [design doc](docs/plans/2026-04-06-ryusim-fuzz-design.md) for details.
```

**Step 4: Create requirements.txt**

```
cocotb @ git+https://github.com/Seiraiyu/cocotb.git@feat/ryusim-simulator-support
jinja2
pyyaml
vcdvcd
```

**Step 5: Create empty package and placeholder dirs**

```python
# RyuSim-Fuzz/harness/__init__.py
"""RyuSim-Fuzz: Differential fuzzing harness for RyuSim."""
```

Create `.gitkeep` in `harness/templates/`, `findings/`, `results/`, `scripts/`.

**Step 6: Commit**

```bash
cd /home/stonelyd/RyuSim-Fuzz
git add .gitignore CLAUDE.md README.md requirements.txt harness/__init__.py \
  harness/templates/.gitkeep findings/.gitkeep results/.gitkeep scripts/.gitkeep
git commit -m "feat: repo scaffold with CLAUDE.md, README, requirements"
```

---

### Task 2: Add Chimera git submodule

**Step 1: Add submodule**

```bash
cd /home/stonelyd/RyuSim-Fuzz
git submodule add https://github.com/lac-dcc/chimera.git chimera
```

**Step 2: Verify**

```bash
ls chimera/src/ chimera/json/ chimera/scripts/setup.sh
```

Expected: files exist, submodule is populated.

**Step 3: Commit**

```bash
git add .gitmodules chimera
git commit -m "feat: add Chimera as git submodule (lac-dcc/chimera)"
```

---

### Task 3: Add VlogHammer git submodule

**Step 1: Add submodule**

```bash
cd /home/stonelyd/RyuSim-Fuzz
git submodule add https://github.com/YosysHQ/VlogHammer.git vloghammer
```

**Step 2: Verify**

```bash
ls vloghammer/Makefile vloghammer/scripts/
```

Expected: files exist, submodule is populated.

**Step 3: Commit**

```bash
git add .gitmodules vloghammer
git commit -m "feat: add VlogHammer as git submodule (YosysHQ/VlogHammer)"
```

---

### Task 4: Chimera setup script + generate wrapper

**Files:**
- Create: `scripts/setup_chimera.sh`
- Create: `scripts/setup_ryusim.sh`
- Create: `harness/generate.py`

**Step 1: Create setup_chimera.sh**

```bash
#!/usr/bin/env bash
# scripts/setup_chimera.sh — Build ChiGen from the chimera submodule
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
CHIMERA_DIR="$REPO_DIR/chimera"

if [ ! -f "$CHIMERA_DIR/CMakeLists.txt" ] && [ ! -d "$CHIMERA_DIR/src" ]; then
    echo "Error: chimera submodule not initialized. Run: git submodule update --init" >&2
    exit 1
fi

echo "Building ChiGen from $CHIMERA_DIR..."
cd "$CHIMERA_DIR"
cmake -S src -B build/ -DCMAKE_BUILD_TYPE=Release
make -j"$(nproc)" -C build/

echo "ChiGen built: $CHIMERA_DIR/build/Chimera"
"$CHIMERA_DIR/build/Chimera" --help || true
```

**Step 2: Create setup_ryusim.sh**

```bash
#!/usr/bin/env bash
# scripts/setup_ryusim.sh — Install the RyuSim binary
set -euo pipefail

if command -v ryusim &>/dev/null; then
    echo "RyuSim already installed: $(ryusim --version 2>&1 || echo unknown)"
    exit 0
fi

echo "Installing RyuSim..."
curl -fsSL https://ryusim.seiraiyu.com/install.sh | bash

echo "RyuSim installed: $(ryusim --version 2>&1 || echo unknown)"
```

**Step 3: Create harness/generate.py**

```python
#!/usr/bin/env python3
"""harness/generate.py — Wrappers around Chimera and VlogHammer generators."""

import logging
import re
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

# Patterns that indicate unsupported RyuSim constructs
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

    # Run the generator
    try:
        subprocess.run(
            [str(gen_bin)],
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
```

**Step 4: Verify syntax**

```bash
cd /home/stonelyd/RyuSim-Fuzz
python3 -c "import ast; ast.parse(open('harness/generate.py').read()); print('OK')"
```

Expected: `OK`

**Step 5: Commit**

```bash
chmod +x scripts/setup_chimera.sh scripts/setup_ryusim.sh
git add scripts/setup_chimera.sh scripts/setup_ryusim.sh harness/generate.py
git commit -m "feat: Chimera setup script and generate wrapper with synthesizability filter"
```

---

### Task 5: VlogHammer setup script

**Files:**
- Create: `scripts/setup_vloghammer.sh`

**Step 1: Create setup_vloghammer.sh**

```bash
#!/usr/bin/env bash
# scripts/setup_vloghammer.sh — Build VlogHammer's generator from the submodule
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
VLOGHAMMER_DIR="$REPO_DIR/vloghammer"

if [ ! -f "$VLOGHAMMER_DIR/Makefile" ]; then
    echo "Error: vloghammer submodule not initialized. Run: git submodule update --init" >&2
    exit 1
fi

GEN_CC="$VLOGHAMMER_DIR/scripts/generate.cc"
GEN_BIN="$VLOGHAMMER_DIR/scripts/generate"

if [ ! -f "$GEN_CC" ]; then
    echo "Error: generate.cc not found at $GEN_CC" >&2
    exit 1
fi

echo "Building VlogHammer generator..."
clang++ -o "$GEN_BIN" "$GEN_CC"

echo "VlogHammer generator built: $GEN_BIN"

# Pre-generate RTL files
echo "Generating RTL test cases..."
cd "$VLOGHAMMER_DIR"
mkdir -p rtl
"$GEN_BIN" || true

echo "VlogHammer setup complete. Generated files in $VLOGHAMMER_DIR/rtl/"
ls rtl/*.v 2>/dev/null | wc -l | xargs -I{} echo "{} test files generated"
```

**Step 2: Commit**

```bash
chmod +x scripts/setup_vloghammer.sh
git add scripts/setup_vloghammer.sh
git commit -m "feat: VlogHammer setup script"
```

---

### Task 6: Cocotb Makefile + testbench templates

**Files:**
- Create: `harness/templates/Makefile.j2`
- Create: `harness/templates/test_generated.py.j2`
- Create: `harness/templates/test_combinational.py.j2`

**Step 1: Create Makefile template**

```makefile
{# harness/templates/Makefile.j2 — Cocotb Makefile for generated designs #}
# Auto-generated by RyuSim-Fuzz harness
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = {{ verilog_source }}
TOPLEVEL = {{ top_module }}
MODULE = {{ test_module }}

export PYTHONPATH := $(CURDIR)

include $(shell cocotb-config --makefiles)/Makefile.sim
```

**Step 2: Create sequential testbench template (designs with clk)**

```python
{# harness/templates/test_generated.py.j2 — Generic cocotb testbench for sequential designs #}
"""Auto-generated cocotb testbench for {{ top_module }}."""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
import random

random.seed({{ random_seed }})

@cocotb.test()
async def test_generated(dut):
    """Drive clock + random stimulus for {{ num_cycles }} cycles."""
    clock = Clock(dut.{{ clock_port }}, 10, units="ns")
    cocotb.start_soon(clock.start())

{% for port in input_ports %}
    dut.{{ port.name }}.value = 0
{% endfor %}

    # Let reset settle
    for _ in range(5):
        await RisingEdge(dut.{{ clock_port }})

    # Drive random stimulus
    for cycle in range({{ num_cycles }}):
{% for port in input_ports %}
        dut.{{ port.name }}.value = random.randint(0, {{ port.max_val }})
{% endfor %}
        await RisingEdge(dut.{{ clock_port }})
```

**Step 3: Create combinational testbench template (designs without clk)**

```python
{# harness/templates/test_combinational.py.j2 — Cocotb testbench for combinational designs #}
"""Auto-generated cocotb testbench for {{ top_module }}."""
import cocotb
from cocotb.triggers import Timer
import random

random.seed({{ random_seed }})

@cocotb.test()
async def test_generated(dut):
    """Drive {{ num_vectors }} random input vectors with 10ns settling time."""
    for _ in range({{ num_vectors }}):
{% for port in input_ports %}
        dut.{{ port.name }}.value = random.randint(0, {{ port.max_val }})
{% endfor %}
        await Timer(10, units="ns")
```

**Step 4: Verify templates parse as valid Jinja2**

```bash
cd /home/stonelyd/RyuSim-Fuzz
python3 -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('harness/templates'))
for name in ['Makefile.j2', 'test_generated.py.j2', 'test_combinational.py.j2']:
    env.get_template(name)
    print(f'{name}: OK')
"
```

Expected: all three print `OK`.

**Step 5: Commit**

```bash
git add harness/templates/Makefile.j2 harness/templates/test_generated.py.j2 \
  harness/templates/test_combinational.py.j2
git commit -m "feat: cocotb Makefile and testbench Jinja2 templates"
```

---

### Task 7: Verilog port parser

**Files:**
- Create: `harness/parse_ports.py`

**Step 1: Create port parser**

This module extracts top module name, port names, directions, and widths from generated Verilog using regex. It works for the well-structured output of both Chimera and VlogHammer — not a full Verilog parser.

```python
#!/usr/bin/env python3
"""harness/parse_ports.py — Extract module/port info from generated Verilog."""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PortInfo:
    name: str
    direction: str  # "input", "output", "inout"
    width: int = 1  # bit width


@dataclass
class ModuleInfo:
    name: str
    ports: list[PortInfo] = field(default_factory=list)

    @property
    def input_ports(self) -> list[PortInfo]:
        return [p for p in self.ports if p.direction == "input"]

    @property
    def output_ports(self) -> list[PortInfo]:
        return [p for p in self.ports if p.direction in ("output", "inout")]

    @property
    def has_clock(self) -> bool:
        return any(
            p.name in ("clk", "clock", "CLK", "CLOCK", "i_clk")
            for p in self.input_ports
        )

    @property
    def clock_port(self) -> str | None:
        for name in ("clk", "clock", "CLK", "CLOCK", "i_clk"):
            for p in self.input_ports:
                if p.name == name:
                    return p.name
        return None

    @property
    def non_clock_inputs(self) -> list[PortInfo]:
        clock = self.clock_port
        return [p for p in self.input_ports if p.name != clock]


def _parse_width(width_str: str | None) -> int:
    """Parse a Verilog width specifier like [7:0] to bit count."""
    if not width_str:
        return 1
    m = re.match(r"\[(\d+):(\d+)\]", width_str.strip())
    if m:
        return abs(int(m.group(1)) - int(m.group(2))) + 1
    return 1


def parse_verilog(verilog_path: Path) -> ModuleInfo | None:
    """Extract the first module definition and its ports from a Verilog file.

    Handles both ANSI-style and non-ANSI-style port declarations.
    """
    content = verilog_path.read_text()

    # Find first module declaration
    mod_match = re.search(r"\bmodule\s+(\w+)", content)
    if not mod_match:
        return None

    module_name = mod_match.group(1)
    ports = []

    # ANSI-style: module foo(input [7:0] a, output [3:0] y);
    # Non-ANSI: declarations after module header
    # Match both patterns with a single regex for port declarations
    port_re = re.compile(
        r"\b(input|output|inout)\s+"
        r"(?:wire\s+|reg\s+|logic\s+)?"  # optional wire/reg/logic
        r"(?:signed\s+)?"                 # optional signed
        r"(\[\d+:\d+\]\s*)?"              # optional width
        r"(\w+)"                          # port name
    )

    for m in port_re.finditer(content):
        direction = m.group(1)
        width = _parse_width(m.group(2))
        name = m.group(3)
        ports.append(PortInfo(name=name, direction=direction, width=width))

    return ModuleInfo(name=module_name, ports=ports)
```

**Step 2: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('harness/parse_ports.py').read()); print('OK')"
```

**Step 3: Commit**

```bash
git add harness/parse_ports.py
git commit -m "feat: regex-based Verilog port parser for generated designs"
```

---

### Task 8: Simulator harness

**Files:**
- Create: `harness/simulate.py`

**Step 1: Create simulate.py**

```python
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
    if sim == "ryusim":
        env_vars["EXTRA_ARGS"] = "--trace-vcd"
    elif sim == "verilator":
        env_vars["EXTRA_ARGS"] = "--trace"
    elif sim == "icarus":
        env_vars["SIM"] = "icarus"
        # Icarus VCD via cocotb or $dumpvars in testbench

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

    # Find VCD output
    vcd_files = list(work_dir.rglob("*.vcd"))
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
```

**Step 2: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('harness/simulate.py').read()); print('OK')"
```

**Step 3: Commit**

```bash
git add harness/simulate.py
git commit -m "feat: simulator harness — cocotb template rendering + multi-sim execution"
```

---

### Task 9: VCD comparator

**Files:**
- Create: `harness/compare.py`

**Step 1: Create compare.py**

```python
#!/usr/bin/env python3
"""harness/compare.py — Compare simulation results across simulators."""

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

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
    """Run vcddiff between two VCD files. Returns (match, diff_output)."""
    try:
        result = subprocess.run(
            ["vcddiff", str(vcd_a), str(vcd_b)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        match = result.returncode == 0
        output = result.stdout + result.stderr
        return match, output
    except FileNotFoundError:
        return False, "vcddiff not found on PATH"
    except subprocess.TimeoutExpired:
        return False, f"vcddiff timed out after {timeout}s"


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
```

**Step 2: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('harness/compare.py').read()); print('OK')"
```

**Step 3: Commit**

```bash
git add harness/compare.py
git commit -m "feat: VCD comparator with multi-simulator classification"
```

---

### Task 10: Triage module

**Files:**
- Create: `harness/triage.py`

**Step 1: Create triage.py**

```python
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
```

**Step 2: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('harness/triage.py').read()); print('OK')"
```

**Step 3: Commit**

```bash
git add harness/triage.py
git commit -m "feat: triage module — save findings with design, VCDs, and metadata"
```

---

### Task 11: GitHub issue reporter

**Files:**
- Create: `harness/report.py`

**Step 1: Create report.py**

```python
#!/usr/bin/env python3
"""harness/report.py — Auto-file GitHub issues for findings."""

import logging
import subprocess
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

ISSUE_REPO = "Seiraiyu/RyuSimAlt"
FUZZ_REPO_URL = "https://github.com/Seiraiyu/RyuSim-Fuzz"


def file_github_issue(finding_dir: Path) -> str | None:
    """File a GitHub issue for a finding. Returns the issue URL or None on failure."""
    metadata_path = finding_dir / "finding.yaml"
    if not metadata_path.exists():
        log.error("No finding.yaml in %s", finding_dir)
        return None

    metadata = yaml.safe_load(metadata_path.read_text())

    # Skip if already filed
    if metadata.get("github_issue"):
        log.info("Issue already filed: %s", metadata["github_issue"])
        return metadata["github_issue"]

    # Read design content
    design_path = finding_dir / "design.sv"
    design_content = design_path.read_text() if design_path.exists() else "(design file missing)"

    # Truncate if too long
    if len(design_content) > 5000:
        design_content = design_content[:5000] + "\n// ... truncated ..."

    # Read VCD diffs
    vcd_diff_path = finding_dir / "vcd_diffs.txt"
    vcd_diffs = vcd_diff_path.read_text() if vcd_diff_path.exists() else "(no VCD diffs)"
    if len(vcd_diffs) > 3000:
        vcd_diffs = vcd_diffs[:3000] + "\n... truncated ..."

    classification = metadata.get("classification", "unknown")
    generator = metadata.get("generator", "unknown")
    seed = metadata.get("seed", "N/A")
    ryusim_version = metadata.get("ryusim_version", "unknown")

    title = f"[RyuSim-Fuzz] {classification}: {metadata.get('id', 'unknown')}"

    body = f"""## Differential fuzzing finding: {classification}

**Generator:** {generator}
**Seed:** {seed}
**RyuSim version:** {ryusim_version}
**Finding ID:** {metadata.get('id', 'unknown')}

### Reproducer

```systemverilog
{design_content}
```

### Expected behavior

Verilator ({metadata.get('verilator_version', 'unknown')}) and Icarus Verilog ({metadata.get('iverilog_version', 'unknown')}) both produce identical output.

### Actual behavior

{metadata.get('details', 'No details')}

### VCD diff

```
{vcd_diffs}
```

---
Found by [{FUZZ_REPO_URL.split('/')[-1]}]({FUZZ_REPO_URL}) automated fuzzing run.
"""

    try:
        result = subprocess.run(
            [
                "gh", "issue", "create",
                "--repo", ISSUE_REPO,
                "--title", title,
                "--body", body,
                "--label", "fuzz-finding",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            issue_url = result.stdout.strip()
            log.info("Filed issue: %s", issue_url)

            # Update finding.yaml with issue URL
            metadata["github_issue"] = issue_url
            metadata_path.write_text(
                yaml.dump(metadata, default_flow_style=False, sort_keys=False)
            )
            return issue_url
        else:
            log.warning("gh issue create failed: %s", result.stderr[:500])
            return None

    except FileNotFoundError:
        log.warning("gh CLI not found — install GitHub CLI to auto-file issues")
        return None
    except subprocess.TimeoutExpired:
        log.warning("gh issue create timed out")
        return None
```

**Step 2: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('harness/report.py').read()); print('OK')"
```

**Step 3: Commit**

```bash
git add harness/report.py
git commit -m "feat: GitHub issue reporter for findings via gh CLI"
```

---

### Task 12: CLI entry point

**Files:**
- Create: `run_fuzz.py`

**Step 1: Create run_fuzz.py**

```python
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
```

**Step 2: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('run_fuzz.py').read()); print('OK')"
```

**Step 3: Verify CLI help**

```bash
python3 run_fuzz.py --help
```

Expected: prints usage with all arguments.

**Step 4: Commit**

```bash
git add run_fuzz.py
git commit -m "feat: run_fuzz.py CLI with generate, simulate, compare, triage, report pipeline"
```

---

### Task 13: CI workflow — nightly

**Files:**
- Create: `.github/workflows/nightly.yml`

**Step 1: Create nightly.yml**

```yaml
name: Nightly Fuzz

on:
  schedule:
    - cron: "0 3 * * *"
  workflow_dispatch:
    inputs:
      count:
        description: "Number of designs per generator"
        type: number
        default: 50
      seed:
        description: "Random seed (leave empty for random)"
        type: string
        default: ""

jobs:
  fuzz:
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    steps:
      - name: Checkout with submodules
        uses: actions/checkout@v4
        with:
          submodules: recursive

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y cmake clang g++ verilator iverilog

      - name: Install RyuSim
        run: bash scripts/setup_ryusim.sh

      - name: Build ChiGen
        run: bash scripts/setup_chimera.sh

      - name: Build VlogHammer generator
        run: bash scripts/setup_vloghammer.sh

      - name: Install Python dependencies
        run: pip install -r requirements.txt

      - name: Run fuzzing
        run: |
          SEED_ARG=""
          if [ -n "${{ inputs.seed }}" ]; then
            SEED_ARG="--seed ${{ inputs.seed }}"
          fi
          python3 -u run_fuzz.py --all \
            --count ${{ inputs.count || 100 }} \
            $SEED_ARG \
            --file-issues \
            --verbose \
            --output results/fuzz-nightly.json
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: nightly-fuzz-results
          path: |
            results/
            findings/
          retention-days: 30
```

**Step 2: Verify YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/nightly.yml')); print('OK')"
```

**Step 3: Commit**

```bash
git add .github/workflows/nightly.yml
git commit -m "ci: add nightly fuzzing workflow (100 designs, 30-min budget)"
```

---

### Task 14: CI workflow — weekly deep

**Files:**
- Create: `.github/workflows/weekly.yml`

**Step 1: Create weekly.yml**

```yaml
name: Weekly Deep Fuzz

on:
  schedule:
    - cron: "0 2 * * 0"
  workflow_dispatch:
    inputs:
      count:
        description: "Number of designs per generator"
        type: number
        default: 500

jobs:
  fuzz:
    runs-on: ubuntu-24.04
    timeout-minutes: 120
    steps:
      - name: Checkout with submodules
        uses: actions/checkout@v4
        with:
          submodules: recursive

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y cmake clang g++ verilator iverilog

      - name: Install RyuSim
        run: bash scripts/setup_ryusim.sh

      - name: Build ChiGen
        run: bash scripts/setup_chimera.sh

      - name: Build VlogHammer generator
        run: bash scripts/setup_vloghammer.sh

      - name: Install Python dependencies
        run: pip install -r requirements.txt

      - name: Run deep fuzzing
        run: |
          python3 -u run_fuzz.py --all \
            --count ${{ inputs.count || 1000 }} \
            --file-issues \
            --verbose \
            --output results/fuzz-weekly.json
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: weekly-fuzz-results
          path: |
            results/
            findings/
          retention-days: 30
```

**Step 2: Commit**

```bash
git add .github/workflows/weekly.yml
git commit -m "ci: add weekly deep fuzzing workflow (1000 designs, 2-hr budget)"
```

---

### Task 15: CI workflow — on-demand

**Files:**
- Create: `.github/workflows/on-demand.yml`

**Step 1: Create on-demand.yml**

```yaml
name: On-Demand Fuzz

on:
  workflow_dispatch:
    inputs:
      generator:
        description: "Generator to use"
        type: choice
        options:
          - all
          - chimera
          - vloghammer
        default: all
      count:
        description: "Number of designs"
        type: number
        default: 50
      seed:
        description: "Random seed (Chimera only)"
        type: string
        default: ""
      cycles:
        description: "Simulation cycles per design"
        type: number
        default: 100
      file_issues:
        description: "Auto-file GitHub issues for findings"
        type: boolean
        default: false

jobs:
  fuzz:
    runs-on: ubuntu-24.04
    timeout-minutes: 60
    steps:
      - name: Checkout with submodules
        uses: actions/checkout@v4
        with:
          submodules: recursive

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y cmake clang g++ verilator iverilog

      - name: Install RyuSim
        run: bash scripts/setup_ryusim.sh

      - name: Build ChiGen
        run: bash scripts/setup_chimera.sh

      - name: Build VlogHammer generator
        run: bash scripts/setup_vloghammer.sh

      - name: Install Python dependencies
        run: pip install -r requirements.txt

      - name: Run fuzzing
        run: |
          GEN_ARG=""
          if [ "${{ inputs.generator }}" = "all" ]; then
            GEN_ARG="--all"
          else
            GEN_ARG="--generator ${{ inputs.generator }}"
          fi
          SEED_ARG=""
          if [ -n "${{ inputs.seed }}" ]; then
            SEED_ARG="--seed ${{ inputs.seed }}"
          fi
          ISSUE_ARG=""
          if [ "${{ inputs.file_issues }}" = "true" ]; then
            ISSUE_ARG="--file-issues"
          fi
          python3 -u run_fuzz.py \
            $GEN_ARG \
            --count ${{ inputs.count }} \
            --cycles ${{ inputs.cycles }} \
            $SEED_ARG \
            $ISSUE_ARG \
            --verbose \
            --output results/fuzz-ondemand.json
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: ondemand-fuzz-results
          path: |
            results/
            findings/
          retention-days: 30
```

**Step 2: Commit**

```bash
git add .github/workflows/on-demand.yml
git commit -m "ci: add on-demand fuzzing workflow with configurable inputs"
```

---

## Verification checklist

After all tasks are complete:

1. **Syntax check all Python:**
   ```bash
   cd /home/stonelyd/RyuSim-Fuzz
   python3 -c "
   import ast
   for f in ['harness/__init__.py', 'harness/generate.py', 'harness/parse_ports.py',
             'harness/simulate.py', 'harness/compare.py', 'harness/triage.py',
             'harness/report.py', 'run_fuzz.py']:
       ast.parse(open(f).read())
       print(f'{f}: OK')
   "
   ```

2. **Validate YAML workflows:**
   ```bash
   python3 -c "
   import yaml
   for f in ['.github/workflows/nightly.yml', '.github/workflows/weekly.yml', '.github/workflows/on-demand.yml']:
       yaml.safe_load(open(f))
       print(f'{f}: OK')
   "
   ```

3. **Validate Jinja2 templates:**
   ```bash
   python3 -c "
   from jinja2 import Environment, FileSystemLoader
   env = Environment(loader=FileSystemLoader('harness/templates'))
   for name in ['Makefile.j2', 'test_generated.py.j2', 'test_combinational.py.j2']:
       env.get_template(name)
       print(f'{name}: OK')
   "
   ```

4. **CLI help renders:**
   ```bash
   python3 run_fuzz.py --help
   ```

5. **Git log shows all commits:**
   ```bash
   git log --oneline
   ```
