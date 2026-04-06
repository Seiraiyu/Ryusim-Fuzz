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
