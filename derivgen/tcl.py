"""
Reading and writing the platform script.

This is the ONLY file that knows what the script looks like. If the command
names or the argument order have to change to match a different tool, this is
the single file to edit -- design.py and everything above it stay as they are.

Format: one command per line, words separated by spaces. "#" starts a comment.
Blank lines are ignored. That is the whole grammar.
"""

import re

from .design import (
    Address, BusConnection, BusPort, Connection, Design, Instance, Port,
    Ref, TieOff,
)


# ---------------------------------------------------------------------------
# The command names. Change these to match another tool's vocabulary.
# ---------------------------------------------------------------------------

CMD_ADD_PORT = "add_port"
CMD_ADD_PORT_BUS = "add_port_bus"
CMD_ADD_INSTANCE = "add_instance"
CMD_CONNECT = "connect"
CMD_CONNECT_BUS = "connect_bus"
CMD_SET_ADDRESS = "set_address"
CMD_TIE = "tie"

DIRECTIONS = ("in", "out", "inout")
ROLES = ("master", "slave")


class TclError(Exception):
    """Raised when a script line cannot be understood. Names the line number."""


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------

# A reference is  name  or  instance/port , each optionally followed by a bit
# range such as [3:0] or [0].
_REF_RE = re.compile(r"^([A-Za-z_][\w]*)(?:/([A-Za-z_][\w]*))?(\[[\d:]+\])?$")


def parse_ref(text: str, line_no: int = 0) -> Ref:
    """Turn 'sram_ctrl0/s_axi' or 'clk' or 'bus/alert[0]' into a Ref."""
    match = _REF_RE.match(text)
    if not match:
        raise TclError(f"line {line_no}: cannot read reference {text!r}")
    first, second, bits = match.groups()
    # One slash means instance/port. No slash means a top-level pin.
    if second is None:
        return Ref(instance=None, port=first, bits=bits)
    return Ref(instance=first, port=second, bits=bits)


def format_ref(ref: Ref) -> str:
    return str(ref)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def _expect(words: list[str], count: int, line_no: int, usage: str) -> None:
    if len(words) != count:
        raise TclError(
            f"line {line_no}: {words[0]} needs {count - 1} arguments, "
            f"got {len(words) - 1}.  Usage: {usage}"
        )


def _parse_int(text: str, line_no: int, what: str) -> int:
    """Accepts decimal or 0x hex."""
    try:
        return int(text, 0)
    except ValueError:
        raise TclError(f"line {line_no}: {what} {text!r} is not a number") from None


def read_tcl(text: str, name: str) -> Design:
    """Read a platform script into a Design."""
    design = Design(name=name)

    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        words = line.split()
        cmd = words[0]

        if cmd == CMD_ADD_PORT:
            _expect(words, 4, line_no, f"{CMD_ADD_PORT} <name> <in|out|inout> <width>")
            direction = words[2]
            if direction not in DIRECTIONS:
                raise TclError(
                    f"line {line_no}: direction {direction!r} must be one of "
                    f"{', '.join(DIRECTIONS)}"
                )
            design.ports.append(
                Port(words[1], direction, _parse_int(words[3], line_no, "width"))
            )

        elif cmd == CMD_ADD_PORT_BUS:
            _expect(words, 4, line_no,
                    f"{CMD_ADD_PORT_BUS} <name> <bus_type> <master|slave>")
            role = words[3]
            if role not in ROLES:
                raise TclError(
                    f"line {line_no}: role {role!r} must be one of {', '.join(ROLES)}"
                )
            design.bus_ports.append(BusPort(words[1], words[2], role))

        elif cmd == CMD_ADD_INSTANCE:
            _expect(words, 3, line_no, f"{CMD_ADD_INSTANCE} <instance> <ip>")
            design.instances.append(Instance(words[1], words[2]))

        elif cmd == CMD_CONNECT:
            _expect(words, 3, line_no, f"{CMD_CONNECT} <ref> <ref>")
            design.connections.append(
                Connection(parse_ref(words[1], line_no), parse_ref(words[2], line_no))
            )

        elif cmd == CMD_CONNECT_BUS:
            _expect(words, 3, line_no, f"{CMD_CONNECT_BUS} <ref> <ref>")
            design.bus_connections.append(
                BusConnection(parse_ref(words[1], line_no),
                              parse_ref(words[2], line_no))
            )

        elif cmd == CMD_SET_ADDRESS:
            _expect(words, 4, line_no, f"{CMD_SET_ADDRESS} <ref> <base> <size>")
            design.addresses.append(
                Address(parse_ref(words[1], line_no),
                        _parse_int(words[2], line_no, "base address"),
                        _parse_int(words[3], line_no, "size"))
            )

        elif cmd == CMD_TIE:
            _expect(words, 3, line_no, f"{CMD_TIE} <ref> <value>")
            design.tie_offs.append(TieOff(parse_ref(words[1], line_no), words[2]))

        else:
            raise TclError(f"line {line_no}: unknown command {cmd!r}")

    return design


def read_tcl_file(path) -> Design:
    """Read a script from disk. The file's stem becomes the design name."""
    from pathlib import Path
    path = Path(path)
    return read_tcl(path.read_text(encoding="utf-8"), name=path.stem)


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def write_tcl(design: Design) -> str:
    """
    Turn a Design back into a script.

    Sections come out in a fixed order and sorted inside each section, so the
    same design always produces exactly the same text. That makes diffs between
    runs meaningful instead of noisy.
    """
    out: list[str] = [f"# platform: {design.name}", ""]

    def section(title: str, lines: list[str]) -> None:
        if not lines:
            return
        out.append(f"# --- {title} ---")
        out.extend(sorted(lines))
        out.append("")

    section("top-level pins", [
        f"{CMD_ADD_PORT} {p.name} {p.direction} {p.width}" for p in design.ports
    ])
    section("top-level buses", [
        f"{CMD_ADD_PORT_BUS} {b.name} {b.bus_type} {b.role}" for b in design.bus_ports
    ])
    section("instances", [
        f"{CMD_ADD_INSTANCE} {i.name} {i.ip}" for i in design.instances
    ])
    section("bus connections", [
        f"{CMD_CONNECT_BUS} {format_ref(c.left)} {format_ref(c.right)}"
        for c in design.bus_connections
    ])
    section("address map", [
        f"{CMD_SET_ADDRESS} {format_ref(a.ref)} 0x{a.base:08x} 0x{a.size:x}"
        for a in design.addresses
    ])
    section("connections", [
        f"{CMD_CONNECT} {format_ref(c.left)} {format_ref(c.right)}"
        for c in design.connections
    ])
    section("tie-offs", [
        f"{CMD_TIE} {format_ref(t.ref)} {t.value}" for t in design.tie_offs
    ])

    # Exactly one trailing newline, no trailing blank line.
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def write_tcl_file(design: Design, path) -> None:
    from pathlib import Path
    Path(path).write_text(write_tcl(design), encoding="utf-8")
