"""
Reading the IP library.

The committed IP-XACT files are the source of truth for what ports an IP has.
The checker uses this to answer "is every input of this instance driven?" --
which is the whole reason we can promise never to invent a connection.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

SPIRIT = "http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009"
DERIVGEN = "http://derivgen.org/extensions"


def _tag(name: str) -> str:
    return f"{{{SPIRIT}}}{name}"


@dataclass(frozen=True)
class IpPort:
    name: str
    direction: str   # "input", "output" or "inout"
    width: int


@dataclass(frozen=True)
class IpBusInterface:
    name: str                      # e.g. "m0_apb"
    bus_type: str                  # e.g. "APB"
    role: str                      # "master" or "slave"
    ports: tuple[str, ...]         # the physical ports it is made of
    # Standard signal name -> this IP's port name, e.g. PRDATA -> m0_apb_prdata.
    # This is what lets us say "m2_apb_prdata and m3_apb_prdata are the same
    # signal on different ports" without splitting names on underscores.
    port_map: tuple[tuple[str, str], ...] = ()

    def logical_of(self, physical: str) -> str | None:
        for logical, actual in self.port_map:
            if actual == physical:
                return logical
        return None


@dataclass
class Ip:
    name: str
    ports: dict[str, IpPort] = field(default_factory=dict)
    bus_interfaces: dict[str, IpBusInterface] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)

    def inputs(self) -> list[IpPort]:
        return [p for p in self.ports.values() if p.direction == "input"]

    def bus_ports(self) -> set[str]:
        """Every physical port that belongs to some bus interface."""
        out: set[str] = set()
        for bus in self.bus_interfaces.values():
            out.update(bus.ports)
        return out

    def slave_interfaces(self) -> list[IpBusInterface]:
        return [b for b in self.bus_interfaces.values() if b.role == "slave"]

    def bus_signal(self, physical: str) -> str | None:
        """
        The standard signal name this port carries, if it is part of a bus.

        PRDATA for both m2_apb_prdata and m3_apb_prdata, so a tie-off value
        used on one can be reused on the other.
        """
        for bus in self.bus_interfaces.values():
            logical = bus.logical_of(physical)
            if logical:
                return logical
        return None


class LibraryError(Exception):
    """Raised when the library is missing something or is malformed."""


def read_ip(path: Path) -> Ip:
    """Read one IP-XACT component file."""
    root = ET.parse(path).getroot()

    name_elem = root.find(_tag("name"))
    if name_elem is None or not name_elem.text:
        raise LibraryError(f"{path.name}: component has no <name>")
    ip = Ip(name=name_elem.text)

    for port in root.iterfind(f".//{_tag('model')}/{_tag('ports')}/{_tag('port')}"):
        pname = port.findtext(_tag("name"))
        wire = port.find(_tag("wire"))
        if pname is None or wire is None:
            raise LibraryError(f"{ip.name}: a port is missing its name or wire")
        direction = wire.findtext(_tag("direction")) or "input"
        vector = wire.find(_tag("vector"))
        if vector is not None:
            left = int(vector.findtext(_tag("left")) or 0)
            right = int(vector.findtext(_tag("right")) or 0)
            width = abs(left - right) + 1
        else:
            width = 1
        ip.ports[pname] = IpPort(pname, direction, width)

    for bi in root.iterfind(f".//{_tag('busInterfaces')}/{_tag('busInterface')}"):
        bname = bi.findtext(_tag("name"))
        if not bname:
            raise LibraryError(f"{ip.name}: a bus interface is missing its name")
        bus_type_elem = bi.find(_tag("busType"))
        bus_type = "unknown"
        if bus_type_elem is not None:
            bus_type = bus_type_elem.get(f"{{{SPIRIT}}}name") or \
                       bus_type_elem.get("spirit:name") or "unknown"
        role = "master" if bi.find(_tag("master")) is not None else "slave"
        pairs = []
        for pm in bi.iterfind(f"{_tag('portMaps')}/{_tag('portMap')}"):
            logical = pm.findtext(f"{_tag('logicalPort')}/{_tag('name')}") or ""
            physical = pm.findtext(f"{_tag('physicalPort')}/{_tag('name')}") or ""
            pairs.append((logical, physical))
        ip.bus_interfaces[bname] = IpBusInterface(
            bname, bus_type, role,
            tuple(p for _, p in pairs), tuple(pairs),
        )

    tags = root.findtext(f".//{{{DERIVGEN}}}tags")
    if tags:
        ip.tags = {t.strip() for t in tags.split(",") if t.strip()}

    return ip


def read_library(directory) -> dict[str, Ip]:
    """Read every IP-XACT file in a directory, keyed by IP name."""
    directory = Path(directory)
    library: dict[str, Ip] = {}
    for path in sorted(directory.glob("*.xml")):
        ip = read_ip(path)
        library[ip.name] = ip
    if not library:
        raise LibraryError(f"no IP-XACT files found in {directory}")
    return library


def ips_with_tag(library: dict[str, Ip], tag: str) -> set[str]:
    """Names of every IP carrying this tag."""
    return {name for name, ip in library.items() if tag in ip.tags}


def all_tags(library: dict[str, Ip]) -> set[str]:
    out: set[str] = set()
    for ip in library.values():
        out |= ip.tags
    return out
