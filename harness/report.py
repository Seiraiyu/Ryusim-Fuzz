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
