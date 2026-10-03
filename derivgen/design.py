"""
The in-memory description of a platform.

This is the "body" of the system. The Tcl script is just one way of writing it
down (the "skin", see tcl.py). Everything else -- edits, checks, scoring,
Verilog -- works on the objects in this file and never on text.

That split is what makes porting to a different script format cheap: you swap
the reader and the writer, and nothing in here changes.

"dataclass" below is just Python shorthand for "a record with named fields".
"""

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# A reference to one end of a connection.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Ref:
    """
    Points at either a top-level pin or a port on an instance.

      clk                     -> Ref(instance=None, port="clk")
      sram_ctrl0/s_axi        -> Ref(instance="sram_ctrl0", port="s_axi")
      data_agg0/alert_bus[0]  -> Ref(instance="data_agg0", port="alert_bus",
                                     bits="[0]")

    instance and port are kept as separate fields for good. We never recover
    them by splitting a joined name, because port names contain underscores
    (s_axi_awaddr) and any such guess is wrong sooner or later.

    frozen=True makes these read-only, which lets us put them in sets when
    comparing two designs.
    """
    instance: str | None   # None means a top-level pin
    port: str
    bits: str | None = None   # "[3:0]" or "[0]", kept verbatim; None = whole port

    def __str__(self) -> str:
        head = f"{self.instance}/{self.port}" if self.instance else self.port
        return head + (self.bits or "")

    @property
    def is_top(self) -> bool:
        return self.instance is None


# ---------------------------------------------------------------------------
# The pieces of a platform.
# ---------------------------------------------------------------------------

@dataclass
class Port:
    """A single top-level pin."""
    name: str
    direction: str   # "in", "out" or "inout"
    width: int


@dataclass
class BusPort:
    """
    A top-level bus interface, e.g. the AXI port a host drives the chip through.

    Declaring the 17 AXI signals one by one would bury the design in noise, so
    a whole bus gets one line, the same way IP-XACT groups them.
    """
    name: str
    bus_type: str    # "axi4lite" or "apb"
    role: str        # "master" or "slave"


@dataclass
class Instance:
    """One IP placed in the platform."""
    name: str        # e.g. "sram_ctrl0"
    ip: str          # e.g. "SRAM_Ctrl_IP"


@dataclass
class Connection:
    """A plain wire between two points."""
    left: Ref
    right: Ref


@dataclass
class BusConnection:
    """A whole bus joined to another bus (all its signals at once)."""
    left: Ref
    right: Ref


@dataclass
class Address:
    """Where a bus slave sits in the address map."""
    ref: Ref         # the slave's bus interface, e.g. sram_ctrl0/s_axi
    base: int
    size: int

    @property
    def end(self) -> int:
        """Last address inside this region."""
        return self.base + self.size - 1


@dataclass
class TieOff:
    """An input held at a constant because nothing drives it."""
    ref: Ref
    value: str       # Verilog literal, kept as written, e.g. "1'b0"


@dataclass
class Design:
    """A whole platform."""
    name: str
    ports: list[Port] = field(default_factory=list)
    bus_ports: list[BusPort] = field(default_factory=list)
    instances: list[Instance] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)
    bus_connections: list[BusConnection] = field(default_factory=list)
    addresses: list[Address] = field(default_factory=list)
    tie_offs: list[TieOff] = field(default_factory=list)

    # -- small lookups the rest of the code keeps needing --------------------

    def instance(self, name: str) -> Instance | None:
        for inst in self.instances:
            if inst.name == name:
                return inst
        return None

    def port(self, name: str) -> Port | None:
        for p in self.ports:
            if p.name == name:
                return p
        return None

    def bus_port(self, name: str) -> BusPort | None:
        for b in self.bus_ports:
            if b.name == name:
                return b
        return None

    def instance_names(self) -> set[str]:
        return {i.name for i in self.instances}
