"""
The dependency checker.

Given a design and the IP library, it answers one question: is this design
actually wirable? It checks, in order:

  1. every instance names an IP the library has
  2. every reference names a port that IP really has  <-- the big one
  3. every input is driven, on every bit
  4. no input is driven twice
  5. every top-level output is driven
  6. no bus slave is left unconnected or unaddressed
  7. no two address regions overlap

Check 2 is what the old framework got wrong: it wired ports like
`m0_axi_awaddr` onto modules that had no such port, and nothing noticed.
Every message names the instance and the port, so it is actionable.
"""

from dataclasses import dataclass

from .design import Design, Ref
from .library import Ip


@dataclass(frozen=True)
class Problem:
    severity: str    # "error" or "warning"
    where: str       # the instance/port the problem is about
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.where}: {self.message}"


# ---------------------------------------------------------------------------
# Bit ranges
# ---------------------------------------------------------------------------

def bits_covered(bits: str | None, width: int) -> set[int]:
    """
    Which bit numbers a reference covers.

    None means the whole port. "[5]" means just bit 5. "[7:4]" means 7,6,5,4.
    """
    if bits is None:
        return set(range(width))
    inner = bits.strip("[]")
    if ":" in inner:
        left, right = (int(x) for x in inner.split(":"))
        low, high = min(left, right), max(left, right)
        return set(range(low, high + 1))
    return {int(inner)}


def _describe_bits(missing: set[int], width: int) -> str:
    """Turn {2,3,4,9} into '[4:2], [9]' for a readable message."""
    if missing == set(range(width)):
        return "all bits"
    runs: list[str] = []
    for bit in sorted(missing):
        if runs and bit == _run_end(runs[-1]) + 1:
            runs[-1] = _extend(runs[-1], bit)
        else:
            runs.append(f"[{bit}]")
    return ", ".join(runs)


def _run_end(run: str) -> int:
    inner = run.strip("[]")
    return int(inner.split(":")[0])


def _extend(run: str, bit: int) -> str:
    inner = run.strip("[]")
    low = int(inner.split(":")[-1])
    return f"[{bit}:{low}]"


# ---------------------------------------------------------------------------
# Working out which end of a connection drives
# ---------------------------------------------------------------------------

_SOURCE, _SINK, _UNKNOWN = "source", "sink", "unknown"


def _role_of(ref: Ref, design: Design, library: dict[str, Ip]) -> str:
    """Does this end of a wire drive the net, or listen to it?"""
    if ref.is_top:
        pin = design.port(ref.port)
        if pin is None:
            return _UNKNOWN
        # An input pin brings a signal in, so inside the wrapper it drives.
        return _SOURCE if pin.direction == "in" else _SINK
    instance = design.instance(ref.instance)
    if instance is None:
        return _UNKNOWN
    ip = library.get(instance.ip)
    if ip is None:
        return _UNKNOWN
    port = ip.ports.get(ref.port)
    if port is None:
        return _UNKNOWN
    return _SOURCE if port.direction == "output" else _SINK


def _width_of(ref: Ref, design: Design, library: dict[str, Ip]) -> int | None:
    if ref.is_top:
        pin = design.port(ref.port)
        return pin.width if pin else None
    instance = design.instance(ref.instance)
    if instance is None:
        return None
    ip = library.get(instance.ip)
    if ip is None:
        return None
    port = ip.ports.get(ref.port)
    return port.width if port else None


# ---------------------------------------------------------------------------
# The checker
# ---------------------------------------------------------------------------

def check(design: Design, library: dict[str, Ip]) -> list[Problem]:
    """Return every problem found. An empty list means the design is clean."""
    problems: list[Problem] = []

    # -- 1. every instance names a known IP ---------------------------------
    for instance in design.instances:
        if instance.ip not in library:
            problems.append(Problem(
                "error", instance.name,
                f"IP {instance.ip!r} is not in the library"
            ))

    # -- 2. every reference names a real port -------------------------------
    problems += _check_references(design, library)

    # If any reference is bogus, the driver analysis below would be built on
    # sand. Report what we have and stop.
    if any(p.severity == "error" for p in problems):
        return _sorted(problems)

    # -- 3 & 4. inputs driven exactly once, on every bit --------------------
    problems += _check_drivers(design, library)

    # -- 6. bus slaves connected and addressed ------------------------------
    problems += _check_buses(design, library)

    # -- 7. address map --------------------------------------------------------
    problems += _check_addresses(design)

    return _sorted(problems)


def _sorted(problems: list[Problem]) -> list[Problem]:
    """Errors first, then alphabetical, so output is stable between runs."""
    return sorted(problems, key=lambda p: (p.severity != "error", p.where, p.message))


def _check_references(design: Design, library: dict[str, Ip]) -> list[Problem]:
    problems: list[Problem] = []

    def visit(ref: Ref, context: str) -> None:
        if ref.is_top:
            if design.port(ref.port) is None and design.bus_port(ref.port) is None:
                problems.append(Problem(
                    "error", ref.port,
                    f"{context} refers to a top-level port that does not exist"
                ))
            return
        instance = design.instance(ref.instance)
        if instance is None:
            problems.append(Problem(
                "error", str(ref),
                f"{context} refers to instance {ref.instance!r}, which is "
                f"not in the design"
            ))
            return
        ip = library.get(instance.ip)
        if ip is None:
            return   # already reported as an unknown IP
        # The reference may name a plain port or a whole bus interface.
        if ref.port in ip.ports or ref.port in ip.bus_interfaces:
            return
        problems.append(Problem(
            "error", str(ref),
            f"{context} refers to port {ref.port!r}, which {instance.ip} "
            f"does not have"
        ))

    for conn in design.connections:
        visit(conn.left, "connect")
        visit(conn.right, "connect")
    for conn in design.bus_connections:
        visit(conn.left, "connect_bus")
        visit(conn.right, "connect_bus")
    for address in design.addresses:
        visit(address.ref, "set_address")
    for tie in design.tie_offs:
        visit(tie.ref, "tie")

    return problems


def _check_drivers(design: Design, library: dict[str, Ip]) -> list[Problem]:
    """
    Count, per sink bit, how many things drive it. Zero is a dangling input,
    more than one is a short.
    """
    problems: list[Problem] = []

    # (instance or None, port) -> {bit: number of drivers}
    drivers: dict[tuple[str | None, str], dict[int, int]] = {}
    # Every sink we know about, so we can report the ones nothing reaches.
    sinks: dict[tuple[str | None, str], int] = {}

    def note_sink(ref: Ref, width: int) -> None:
        key = (ref.instance, ref.port)
        sinks[key] = width
        drivers.setdefault(key, {})

    def add_driver(ref: Ref, width: int) -> None:
        key = (ref.instance, ref.port)
        counts = drivers.setdefault(key, {})
        for bit in bits_covered(ref.bits, width):
            counts[bit] = counts.get(bit, 0) + 1

    # Collect every input that needs driving. Bus member ports are included:
    # an unconnected master port leaves its response inputs dangling just as
    # surely as a loose plain wire, which is exactly what a removed peripheral
    # leaves behind.
    for instance in design.instances:
        ip = library[instance.ip]
        for port in ip.inputs():
            note_sink(Ref(instance.name, port.name), port.width)
    for pin in design.ports:
        if pin.direction == "out":
            note_sink(Ref(None, pin.name), pin.width)

    # Plain connections. Only the listening end needs counting -- a driving
    # end can feed as many listeners as it likes.
    for conn in design.connections:
        for end in (conn.left, conn.right):
            width = _width_of(end, design, library)
            if width is None:
                continue
            if _role_of(end, design, library) == _SINK:
                note_sink(end, width)
                add_driver(end, width)

    # Tie-offs drive too.
    for tie in design.tie_offs:
        width = _width_of(tie.ref, design, library)
        if width is None:
            continue
        note_sink(tie.ref, width)
        add_driver(tie.ref, width)

    # A bus connection drives every input on both ends at once.
    for conn in design.bus_connections:
        for end in (conn.left, conn.right):
            if end.is_top:
                continue
            instance = design.instance(end.instance)
            ip = library[instance.ip]
            bus = ip.bus_interfaces.get(end.port)
            if bus is None:
                continue
            for member in bus.ports:
                port = ip.ports.get(member)
                if port is None or port.direction != "input":
                    continue
                ref = Ref(end.instance, member)
                note_sink(ref, port.width)
                add_driver(ref, port.width)

    # Now report.
    for key, width in sorted(sinks.items(), key=lambda kv: (kv[0][0] or "", kv[0][1])):
        instance, port = key
        counts = drivers.get(key, {})
        where = f"{instance}/{port}" if instance else port
        undriven = {b for b in range(width) if counts.get(b, 0) == 0}
        doubled = {b for b in range(width) if counts.get(b, 0) > 1}
        if undriven:
            kind = "top-level output" if instance is None else "input"
            problems.append(Problem(
                "error", where,
                f"{kind} is not driven on {_describe_bits(undriven, width)}"
            ))
        if doubled:
            problems.append(Problem(
                "error", where,
                f"driven by more than one source on "
                f"{_describe_bits(doubled, width)}"
            ))

    return problems


def _check_buses(design: Design, library: dict[str, Ip]) -> list[Problem]:
    problems: list[Problem] = []

    connected: set[tuple[str, str]] = set()
    for conn in design.bus_connections:
        for end in (conn.left, conn.right):
            if not end.is_top:
                connected.add((end.instance, end.port))

    addressed = {(a.ref.instance, a.ref.port) for a in design.addresses}

    for instance in design.instances:
        ip = library[instance.ip]
        for bus in ip.slave_interfaces():
            key = (instance.name, bus.name)
            where = f"{instance.name}/{bus.name}"
            if key not in connected:
                problems.append(Problem(
                    "error", where,
                    "bus slave is not connected to anything, so nothing can "
                    "reach it"
                ))
            elif key not in addressed and "interconnect" not in ip.tags:
                # An interconnect's slave port is where accesses come in, not
                # a region to be decoded, so it needs no address of its own.
                problems.append(Problem(
                    "error", where,
                    "bus slave has no address, so it cannot be decoded"
                ))

    return problems


def _check_addresses(design: Design) -> list[Problem]:
    problems: list[Problem] = []
    ordered = sorted(design.addresses, key=lambda a: (a.base, str(a.ref)))
    for i, first in enumerate(ordered):
        for second in ordered[i + 1:]:
            if second.base > first.end:
                break   # sorted, so nothing later can overlap either
            problems.append(Problem(
                "error", str(first.ref),
                f"address region 0x{first.base:08x}-0x{first.end:08x} overlaps "
                f"{second.ref} at 0x{second.base:08x}-0x{second.end:08x}"
            ))
    return problems


def errors(problems: list[Problem]) -> list[Problem]:
    return [p for p in problems if p.severity == "error"]


def format_problems(problems: list[Problem]) -> str:
    if not problems:
        return "clean: no problems found"
    return "\n".join(f"  {p}" for p in problems)
