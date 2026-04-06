# RyuSim-Fuzz: Differential Fuzzing for RyuSim

**Status:** Planned
**Repo:** `Seiraiyu/RyuSim-Fuzz`
**Date:** 2026-04-06

## Goal

Discover bugs in RyuSim by generating thousands of Verilog designs via two complementary fuzzing tools, simulating each design with RyuSim, Verilator, and Icarus Verilog, and flagging any discrepancies in behavior or output waveforms.

## Constraints

- RyuSim does not support standalone simulation yet — all simulation must go through cocotb Makefiles with `SIM=ryusim`
- RyuSim only supports synthesizable constructs (no `initial`, `#` delays, `fork`/`join`, `$readmemh`, `$display`)
- Generated designs must be filtered to exclude unsupported constructs before feeding to RyuSim
- Chimera and VlogHammer are consumed as git submodules, not vendored
- All three simulators (RyuSim, Verilator, Iverilog) use the same cocotb Makefile structure — only the `SIM=` variable changes between runs. One Makefile template, three `make` invocations.
- Reference simulators: Verilator and Icarus Verilog (two independent references for high confidence)
- VCD waveform diff is the comparison oracle (consistent with RyuSim-Validation Level 2)

## Architecture

```
RyuSim-Fuzz/
├── chimera/                  # git submodule: lac-dcc/chimera
├── vloghammer/               # git submodule: YosysHQ/VlogHammer
├── harness/                  # Shared orchestration (Python)
│   ├── __init__.py
│   ├── generate.py           # Wrappers around each generator
│   ├── simulate.py           # Compile + simulate via cocotb for each sim
│   ├── compare.py            # VCD diff + result classification
│   ├── triage.py             # Minimize reproducer, write finding
│   ├── report.py             # GitHub issue creation
│   └── templates/            # Cocotb Makefile + testbench templates
│       ├── Makefile.j2
│       └── test_generated.py.j2
├── findings/                 # Discovered discrepancies
│   └── YYYY-MM-DD-NNNN/     # Per-finding directory
│       ├── design.sv         # Minimal reproducer
│       ├── finding.yaml      # Metadata
│       ├── ryusim.vcd        # RyuSim output
│       ├── verilator.vcd     # Verilator output
│       └── iverilog.vcd      # Iverilog output
├── scripts/
│   ├── setup_chimera.sh      # Build ChiGen from submodule
│   ├── setup_vloghammer.sh   # Build VlogHammer from submodule
│   └── setup_ryusim.sh       # Install RyuSim binary
├── run_fuzz.py               # Main CLI entry point
├── requirements.txt
├── conftest.py               # pytest fixtures (optional)
├── docs/
│   └── plans/
│       └── 2026-04-06-ryusim-fuzz-design.md  # This file
├── .github/
│   └── workflows/
│       ├── nightly.yml       # ~100 designs, 30-min budget
│       ├── weekly.yml        # ~1000 designs, 2-hr budget
│       └── on-demand.yml     # workflow_dispatch, configurable
├── .gitmodules
├── CLAUDE.md
└── README.md
```

## Components

### 1. Generators (`harness/generate.py`)

Thin Python wrappers around each upstream tool that produce `.sv`/`.v` files.

**Chimera/ChiGen wrapper:**
- Invokes the built ChiGen binary with a pre-trained grammar from `chimera/json/`
- Configurable: token count (`-t`), seed (`--seed`), count of designs
- Runs Verible formatter on output for readability
- Filters output: strips any `initial`, `$display`, `$readmemh`, `#` delay constructs (designs using these are discarded, not patched — patching changes semantics)

**VlogHammer wrapper:**
- Invokes VlogHammer's generation scripts from `vloghammer/scripts/`
- Produces small single-expression modules
- These are inherently synthesizable (combinational expressions), so no filtering needed

**Generator interface:**
```python
def generate_designs(generator: str, count: int, output_dir: Path, seed: int = None) -> list[Path]:
    """Generate Verilog designs, return list of .sv/.v file paths."""
```

### 2. Simulator harness (`harness/simulate.py`)

For each generated design, creates a temporary cocotb test environment and runs it with each simulator.

**Per-design workflow:**
1. Create temp directory with:
   - The generated `.sv`/`.v` file
   - A single cocotb `Makefile` (from Jinja2 template) with the correct `TOPLEVEL`, `MODULE`, and `VERILOG_SOURCES`. The `SIM` variable is passed on the command line, not hardcoded — the same Makefile is reused for all three simulators.
   - A generic cocotb testbench (`test_generated.py`) that: toggles clock for N cycles, optionally drives random stimulus to inputs, enables VCD tracing
2. Run `make SIM=ryusim` — capture exit code, stdout, stderr, VCD
3. Run `make SIM=verilator` — same Makefile, different SIM
4. Run `make SIM=icarus` — same Makefile, different SIM
5. Return per-simulator results

**Cocotb testbench template (`test_generated.py.j2`):**
```python
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
import random

@cocotb.test()
async def test_generated(dut):
    """Generic stimulus: clock + random inputs for N cycles."""
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())

    # Drive random values on all input ports
    for cycle in range({{ num_cycles }}):
        for port in [{{ input_ports }}]:
            getattr(dut, port).value = random.randint(0, (1 << {{ port_width }}) - 1)
        await RisingEdge(dut.clk)
```

**Challenges:**
- Auto-detecting the top module name and its ports from generated Verilog. Options:
  - Parse with `slang` (RyuSim's own frontend) to extract module/port info
  - Use `verible-verilog-syntax` (already a Chimera dependency) to parse
  - Simple regex-based extraction for well-formed generated code
- Designs without a `clk` port need a different testbench (combinational-only stimulus)
- Timeout per design: 60s default, configurable

**Simulator interface:**
```python
@dataclass
class SimResult:
    simulator: str          # "ryusim", "verilator", "icarus"
    exit_code: int
    vcd_path: Path | None
    stdout: str
    stderr: str
    duration: float

def simulate_design(design_path: Path, simulators: list[str], num_cycles: int = 100) -> list[SimResult]:
    """Run design through each simulator, return results."""
```

### 3. Comparator (`harness/compare.py`)

Compares simulation outputs across simulators.

**Comparison levels:**
1. **Compile check**: Did all three simulators accept the design? If RyuSim rejects but both references accept → potential parser bug
2. **Exit code check**: Did simulation complete without crash? Crash in RyuSim only → simulator bug
3. **VCD diff**: Run `vcddiff` between RyuSim VCD and each reference VCD. Mismatch where both references agree → functional bug in RyuSim

**Result classification:**
| RyuSim | Verilator | Iverilog | Classification |
|--------|-----------|----------|----------------|
| crash  | ok        | ok       | **ryusim_crash** — likely RyuSim bug |
| ok     | ok        | ok       | VCD diff decides: match=pass, mismatch=**ryusim_mismatch** |
| reject | ok        | ok       | **ryusim_parse_reject** — potential parser bug |
| reject | reject    | reject   | **all_reject** — invalid design, discard |
| ok     | crash     | ok       | **verilator_bug** — interesting but not our problem |
| ok     | ok        | crash    | **iverilog_bug** — interesting but not our problem |
| crash  | crash     | ok       | **ambiguous** — needs manual triage |
| ok     | mismatch  | match    | **verilator_mismatch** — Verilator disagrees with both |

**Comparator interface:**
```python
@dataclass
class CompareResult:
    design: Path
    classification: str     # from table above
    details: str            # human-readable summary
    sim_results: dict[str, SimResult]
    vcd_diffs: dict[str, str]  # vcddiff output per pair

def compare_results(sim_results: list[SimResult]) -> CompareResult:
    """Classify the discrepancy type from simulation results."""
```

### 4. Triage (`harness/triage.py`)

When the comparator flags a RyuSim-specific issue (`ryusim_crash`, `ryusim_mismatch`, `ryusim_parse_reject`), the triage module:

1. **Saves the finding** to `findings/YYYY-MM-DD-NNNN/`:
   - `design.sv` — the original generated design
   - `finding.yaml` — metadata (classification, generator, seed, RyuSim version, reference versions, timestamps)
   - VCD files from all simulators
   - stdout/stderr from RyuSim
2. **Attempts minimization** (stretch goal, Phase 2):
   - Iteratively remove modules/statements and re-check if the bug reproduces
   - Output `design_minimal.sv` alongside the original

**finding.yaml schema:**
```yaml
id: "2026-04-06-0001"
classification: ryusim_mismatch
generator: chimera
seed: 42
design: design.sv
minimal_design: null  # or design_minimal.sv after minimization
ryusim_version: "0.1.0-dev"
verilator_version: "5.022"
iverilog_version: "12.0"
timestamp: "2026-04-06T03:14:00Z"
github_issue: null  # or URL after filing
notes: ""
```

### 5. Reporter (`harness/report.py`)

Auto-files GitHub issues on `Seiraiyu/RyuSimAlt` (the main RyuSim repo) for confirmed findings.

**Issue template:**
```markdown
## Differential fuzzing finding: {classification}

**Generator:** {generator}
**Seed:** {seed}
**RyuSim version:** {version}

### Reproducer

```systemverilog
{design content}
```

### Expected behavior
Verilator and Icarus Verilog both produce identical output.

### Actual behavior
{description of discrepancy}

### VCD diff
```
{vcddiff output}
```

Found by [RyuSim-Fuzz](https://github.com/Seiraiyu/RyuSim-Fuzz) nightly run.
```

Uses `gh issue create` via subprocess — requires `GITHUB_TOKEN` in CI.

### 6. CLI (`run_fuzz.py`)

Main entry point, mirroring the `run_tests.py` / `run_benchmarks.py` pattern from RyuSim-Validation.

```bash
# Run both generators with defaults
python run_fuzz.py --all --count 100 --output results/fuzz-nightly.json

# Run specific generator
python run_fuzz.py --generator chimera --count 50 --seed 42
python run_fuzz.py --generator vloghammer --count 200

# Configure simulation
python run_fuzz.py --all --count 100 --cycles 200 --timeout 120

# File issues for findings
python run_fuzz.py --all --count 100 --file-issues

# Re-run a specific finding
python run_fuzz.py --reproduce findings/2026-04-06-0001/

# Output JSON report
python run_fuzz.py --all --count 100 --output results/fuzz.json --verbose
```

**CLI arguments:**
- `--all`: Run all generators
- `--generator chimera|vloghammer`: Specific generator
- `--count N`: Number of designs to generate (default: 100)
- `--seed N`: Reproducibility seed
- `--cycles N`: Simulation cycles per design (default: 100)
- `--timeout N`: Per-design timeout in seconds (default: 60)
- `--output FILE`: JSON report output
- `--file-issues`: Auto-file GitHub issues for findings
- `--reproduce DIR`: Re-run a saved finding
- `--verbose / -v`: Progress output

**JSON output format:**
```json
{
  "total": 100,
  "passed": 87,
  "ryusim_crash": 3,
  "ryusim_mismatch": 2,
  "ryusim_parse_reject": 1,
  "all_reject": 5,
  "reference_bug": 2,
  "generator_counts": {
    "chimera": {"total": 50, "passed": 42, ...},
    "vloghammer": {"total": 50, "passed": 45, ...}
  },
  "ryusim_version": "0.1.0-dev",
  "verilator_version": "5.022",
  "iverilog_version": "12.0",
  "timestamp": "2026-04-06T03:14:00Z",
  "findings": [
    {"id": "2026-04-06-0001", "classification": "ryusim_mismatch", "generator": "chimera", ...}
  ]
}
```

## Data Flow

```
┌─────────────┐     ┌──────────────┐
│   Chimera    │     │  VlogHammer  │
│  (ChiGen)   │     │  (scripts)   │
└──────┬──────┘     └──────┬───────┘
       │ .sv/.v files      │ .v files
       └────────┬──────────┘
                │
        ┌───────▼────────┐
        │    Filter       │  Discard designs with
        │  (synthesizable │  unsupported constructs
        │   check)        │
        └───────┬────────┘
                │ valid designs
        ┌───────▼────────┐
        │   Simulate      │  For each design:
        │                 │  make SIM=ryusim
        │  (cocotb +      │  make SIM=verilator
        │   3 simulators) │  make SIM=icarus
        └───────┬────────┘
                │ SimResult per simulator
        ┌───────▼────────┐
        │   Compare       │  vcddiff between
        │                 │  RyuSim vs references
        └───────┬────────┘
                │ CompareResult
        ┌───────▼────────┐
        │   Triage        │  Save finding + VCDs
        │                 │  to findings/ dir
        └───────┬────────┘
                │ finding.yaml
        ┌───────▼────────┐
        │   Report        │  gh issue create
        │                 │  on RyuSimAlt
        └────────────────┘
```

## CI Workflows

### Nightly (`nightly.yml`)

- **Trigger:** `schedule: cron: '0 3 * * *'` + `workflow_dispatch`
- **Budget:** 30 minutes
- **Scope:** 50 Chimera designs + 50 VlogHammer designs
- **Matrix:** Single runner (ubuntu-24.04) — fuzzing doesn't need multi-distro
- **Steps:**
  1. Checkout with submodules
  2. Install RyuSim, Verilator, Iverilog, cocotb, vcddiff
  3. Build ChiGen, set up VlogHammer
  4. `python run_fuzz.py --all --count 100 --output results/fuzz-nightly.json --file-issues --verbose`
  5. Upload `results/` and `findings/` as artifacts (30-day retention)

### Weekly deep (`weekly.yml`)

- **Trigger:** `schedule: cron: '0 2 * * 0'` (Sunday 2 AM) + `workflow_dispatch`
- **Budget:** 2 hours
- **Scope:** 500 Chimera + 500 VlogHammer designs
- **Same single runner, same steps, larger `--count 1000`

### On-demand (`on-demand.yml`)

- **Trigger:** `workflow_dispatch` only
- **Inputs:** generator (chimera/vloghammer/all), count, seed, cycles, file-issues (bool)
- **Allows targeted reproduction and investigation**

## Dependencies

| Tool | Purpose | Install method |
|------|---------|----------------|
| `ryusim` | Simulator under test | `setup_ryusim.sh` |
| `cocotb` | Simulation framework (Seiraiyu fork) | `pip install git+...` |
| `verilator` | Reference simulator | `apt install` or source build |
| `iverilog` | Reference simulator | `apt install` |
| `vcddiff` | VCD waveform comparison | `pip install` or source build |
| `verible` | Verilog parser/formatter (Chimera dep) | Binary in chimera submodule |
| `gcc/g++` | Build ChiGen from source | `apt install` |
| `python 3.10+` | Harness, CLI, cocotb | System or `setup-python` |
| `jinja2` | Makefile/testbench templates | `pip install` |
| `pyyaml` | Finding metadata | `pip install` |
| `gh` | GitHub CLI for issue filing | `apt install` or `gh-cli` action |

## Error handling

- **Generator failure**: Log and skip. Don't fail the entire run for one bad generation.
- **Compile timeout**: Kill after `--timeout` seconds, classify as timeout, continue.
- **Simulation hang**: Same timeout handling.
- **vcddiff failure**: If VCD files are malformed or missing, classify as error, save raw output.
- **GitHub issue filing failure**: Log warning, don't fail. Finding is still saved locally.
- **All three simulators reject**: Discard silently (invalid design, not a bug).

## Phase tracking

| Phase | Description | Status | Tested | Pushed |
|-------|-------------|--------|--------|--------|
| 1 | Repo scaffold: submodules, directory structure, CLAUDE.md, README | pending | no | no |
| 2 | Chimera integration: build script, generate wrapper, filter | pending | no | no |
| 3 | VlogHammer integration: setup script, generate wrapper | pending | no | no |
| 4 | Simulator harness: cocotb templates, simulate.py | pending | no | no |
| 5 | Comparator: compare.py with vcddiff, result classification | pending | no | no |
| 6 | Triage: finding storage, metadata YAML | pending | no | no |
| 7 | CLI: run_fuzz.py with full argument support, JSON output | pending | no | no |
| 8 | Reporter: GitHub issue auto-filing via gh CLI | pending | no | no |
| 9 | CI workflows: nightly, weekly, on-demand | pending | no | no |
| 10 | Minimizer (stretch): iterative design reduction for findings | pending | no | no |

## Decisions log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Generators | Chimera + VlogHammer | Complementary coverage: full-design vs expression-level. TransFuzz excluded (Yosys IR level, closed-source fork dependency). |
| Reference simulators | Verilator + Iverilog | Two independent references. If both agree and RyuSim differs → high confidence RyuSim bug. |
| Simulation method | cocotb Makefiles (`SIM=` variable) | RyuSim doesn't support standalone sim yet. Consistent with RyuSim-Validation patterns. |
| Comparison oracle | VCD waveform diff via vcddiff | Proven approach from RyuSim-Validation Level 2. Catches functional mismatches, not just crashes. |
| Dependency management | Git submodules | Clean provenance, easy to update, keeps repo small. |
| Repo location | Seiraiyu/RyuSim-Fuzz (separate repo) | Different workflow, CI profile, and lifecycle from RyuSim-Validation. |
| Design doc location | In the new repo (`docs/plans/`) | Per user request. |
| Findings pipeline | Save locally + auto-file GitHub issues | Balance of automation and human review. Manual port to RyuSim-Validation for regression tests. |
| CI cadence | Nightly (100 designs) + weekly (1000) | Balances compute cost with discovery frequency. On-demand for investigation. |
