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
