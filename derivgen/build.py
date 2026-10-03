"""
The mini build tool: design + IP library -> Verilog wrapper.

In a production flow this job belongs to a commercial integration tool.
Keeping it in its own file makes the swap obvious: such a tool reads the
same script and the same IP-XACT, and DerivGen stops here.

It is strictly structural. It instantiates, declares wires, concatenates and
ties off. It never writes behaviour, and it never connects a port the IP-XACT
does not list -- if something is missing, the checker has already said so.
"""

from dataclasses import dataclass

from .check import bits_covered
from .design import Connection, Design, Ref
from .library import Ip

# The eight APB signals: width, and which way they travel.
APB_SIGNALS: dict[str, tuple[int, str]] = {
    "PADDR": (32, "to_slave"),
    "PSEL": (1, "to_slave"),
    "PENABLE": (1, "to_slave"),
    "PWRITE": (1, "to_slave"),
    "PWDATA": (32, "to_slave"),
    "PRDATA": (32, "to_master"),
    "PREADY": (1, "to_master"),
    "PSLVERR": (1, "to_master"),
}


class BuildError(Exception):
    """Raised when the design cannot be turned into Verilog."""


# ---------------------------------------------------------------------------
# Flattening buses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TopPin:
    name: str
    direction: str   # "input" or "output"
    width: int


def top_bus_pins(design: Design) -> list[TopPin]:
    """
    The individual pins a top-level bus port turns into.

    host_apb (slave) becomes host_apb_paddr, host_apb_psel, ... with the
    directions a slave sees.
    """
    pins: list[TopPin] = []
    for bus in design.bus_ports:
        for logical, (width, travels) in APB_SIGNALS.items():
            if bus.role == "slave":
                direction = "input" if travels == "to_slave" else "output"
            else:
                direction = "output" if travels == "to_slave" else "input"
            pins.append(TopPin(f"{bus.name}_{logical.lower()}", direction, width))
    return pins


def flatten_buses(design: Design, library: dict[str, Ip]) -> list[Connection]:
    """
    Turn each bus connection into one plain connection per bus signal.

    Everything downstream then deals with plain wires only.
    """
    out: list[Connection] = []

    def member(ref: Ref, logical: str) -> Ref:
        if ref.is_top:
            return Ref(None, f"{ref.port}_{logical.lower()}")
        instance = design.instance(ref.instance)
        if instance is None or instance.ip not in library:
            raise BuildError(f"connect_bus names unknown instance {ref.instance!r}")
        bus = library[instance.ip].bus_interfaces.get(ref.port)
        if bus is None:
            raise BuildError(
                f"{ref.instance}/{ref.port} is not a bus interface of "
                f"{instance.ip}"
            )
        physical = dict(bus.port_map).get(logical)
        if physical is None:
            raise BuildError(
                f"{ref.instance}/{ref.port} has no {logical} signal"
            )
        return Ref(ref.instance, physical)

    for conn in design.bus_connections:
        for logical in APB_SIGNALS:
            out.append(Connection(member(conn.left, logical),
                                  member(conn.right, logical)))
    return out


# ---------------------------------------------------------------------------
# Working out who drives what
# ---------------------------------------------------------------------------

def _port_of(ref: Ref, design: Design, library: dict[str, Ip]):
    instance = design.instance(ref.instance)
    if instance is None or instance.ip not in library:
        return None
    return library[instance.ip].ports.get(ref.port)


def _is_driver(ref: Ref, design: Design, library: dict[str, Ip],
               top_pins: dict[str, TopPin]) -> bool:
    """Does this end put a signal onto the net?"""
    if ref.is_top:
        pin = design.port(ref.port)
        if pin is not None:
            return pin.direction == "in"
        bus_pin = top_pins.get(ref.port)
        return bus_pin is not None and bus_pin.direction == "input"
    port = _port_of(ref, design, library)
    return port is not None and port.direction == "output"


def _width(ref: Ref, design: Design, library: dict[str, Ip],
           top_pins: dict[str, TopPin]) -> int:
    if ref.is_top:
        pin = design.port(ref.port)
        if pin is not None:
            return pin.width
        bus_pin = top_pins.get(ref.port)
        if bus_pin is None:
            raise BuildError(f"unknown top-level port {ref.port!r}")
        return bus_pin.width
    port = _port_of(ref, design, library)
    if port is None:
        raise BuildError(f"unknown port {ref}")
    return port.width


def _net_name(ref: Ref) -> str:
    """
    The wire a driving port feeds.

    Named after its driver, so the wrapper reads the way an engineer would
    write it: core_fsm0_state, not n17.
    """
    return ref.port if ref.is_top else f"{ref.instance}_{ref.port}"


def _slice_of(expression: str, ref: Ref) -> str:
    return expression + (ref.bits or "")


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------

def build_verilog(design: Design, library: dict[str, Ip],
                  header: str | None = None) -> str:
    """Emit the top-level Verilog wrapper for a design."""
    bus_pins = top_bus_pins(design)
    top_pins = {p.name: p for p in bus_pins}

    connections = list(design.connections) + flatten_buses(design, library)

    # -- for each listening port, collect the pieces that feed it ----------
    # (instance, port) -> list of (bits covered, expression)
    feeds: dict[tuple[str | None, str], list[tuple[set[int], str]]] = {}
    # nets we must declare: name -> width
    nets: dict[str, int] = {}

    for conn in connections:
        ends = [conn.left, conn.right]
        drivers = [e for e in ends if _is_driver(e, design, library, top_pins)]
        listeners = [e for e in ends if not _is_driver(e, design, library, top_pins)]
        if len(drivers) != 1 or len(listeners) != 1:
            raise BuildError(
                f"connection {conn.left} <-> {conn.right} does not have exactly "
                f"one driving end; the checker should have caught this"
            )
        driver, listener = drivers[0], listeners[0]

        net = _net_name(driver)
        if not driver.is_top:
            nets[net] = _width(driver, design, library, top_pins)

        expression = _slice_of(net, driver)
        width = _width(listener, design, library, top_pins)
        feeds.setdefault((listener.instance, listener.port), []).append(
            (bits_covered(listener.bits, width), expression)
        )

    # Tie-offs feed too.
    for tie in design.tie_offs:
        width = _width(tie.ref, design, library, top_pins)
        feeds.setdefault((tie.ref.instance, tie.ref.port), []).append(
            (bits_covered(tie.ref.bits, width), tie.value)
        )

    # Declare a wire for every instance output, even unused ones, so the
    # wrapper elaborates on its own.
    for instance in design.instances:
        ip = library.get(instance.ip)
        if ip is None:
            raise BuildError(f"{instance.name}: IP {instance.ip!r} not in library")
        for port in ip.ports.values():
            if port.direction == "output":
                nets.setdefault(f"{instance.name}_{port.name}", port.width)

    def expression_for(instance: str | None, port: str, width: int) -> str | None:
        """One expression feeding a port, concatenating if it arrives in pieces."""
        pieces = feeds.get((instance, port))
        if not pieces:
            return None
        whole = set(range(width))
        for covered, text in pieces:
            if covered == whole:
                return text
        # Arrives in pieces: build {high .. low}.
        ordered = sorted(pieces, key=lambda p: -max(p[0]))
        return "{" + ", ".join(text for _, text in ordered) + "}"

    # -- module header -----------------------------------------------------
    lines: list[str] = []
    if header:
        lines.extend(f"// {line}" for line in header.splitlines())
        lines.append("")

    declarations: list[str] = []
    for pin in design.ports:
        word = "input " if pin.direction == "in" else \
               "output" if pin.direction == "out" else "inout "
        size = f" [{pin.width - 1}:0]" if pin.width > 1 else ""
        declarations.append(f"    {word} wire{size} {pin.name}")
    for pin in bus_pins:
        word = "input " if pin.direction == "input" else "output"
        size = f" [{pin.width - 1}:0]" if pin.width > 1 else ""
        declarations.append(f"    {word} wire{size} {pin.name}")

    lines.append(f"module {design.name} (")
    lines.append(",\n".join(declarations))
    lines.append(");")
    lines.append("")

    # -- internal wires ----------------------------------------------------
    if nets:
        lines.append("    // internal nets, one per driving port")
        for name in sorted(nets):
            size = f" [{nets[name] - 1}:0]" if nets[name] > 1 else ""
            lines.append(f"    wire{size} {name};")
        lines.append("")

    # -- top-level outputs -------------------------------------------------
    output_assigns: list[str] = []
    for pin in design.ports:
        if pin.direction != "out":
            continue
        expression = expression_for(None, pin.name, pin.width)
        if expression is None:
            raise BuildError(
                f"top-level output {pin.name} has nothing driving it; the "
                f"checker should have caught this"
            )
        output_assigns.append(f"    assign {pin.name} = {expression};")
    for pin in bus_pins:
        if pin.direction != "output":
            continue
        expression = expression_for(None, pin.name, pin.width)
        if expression is None:
            raise BuildError(f"top-level output {pin.name} has nothing driving it")
        output_assigns.append(f"    assign {pin.name} = {expression};")

    if output_assigns:
        lines.append("    // drive the platform's outputs")
        lines.extend(sorted(output_assigns))
        lines.append("")

    # -- instances ---------------------------------------------------------
    for instance in sorted(design.instances, key=lambda i: i.name):
        ip = library[instance.ip]
        lines.append(f"    {instance.ip} {instance.name} (")
        port_lines: list[str] = []
        for port in sorted(ip.ports.values(), key=lambda p: p.name):
            if port.direction == "output":
                connected = f"{instance.name}_{port.name}"
            else:
                connected = expression_for(instance.name, port.name, port.width)
                if connected is None:
                    raise BuildError(
                        f"{instance.name}/{port.name} has nothing driving it; "
                        f"the checker should have caught this"
                    )
            port_lines.append(f"        .{port.name:<18}({connected})")
        lines.append(",\n".join(port_lines))
        lines.append("    );")
        lines.append("")

    lines.append("endmodule")
    return "\n".join(lines) + "\n"
