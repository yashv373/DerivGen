"""
One-time helper: package the IP library as IP-XACT.

This stands in for whatever an IP owner does in a real flow. It is NOT part of
the DerivGen pipeline -- it runs once, its XML output is committed, and from
then on the XML is the source of truth. Run it again only after changing an
IP's port list.

    python tools/package_ips.py

Reading ports with a regular expression is only safe because these library
files are written in one regular style. tests/test_library.py cross-checks the
committed XML against the Verilog, so a drift fails loudly.
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

RTL_DIR = Path(__file__).parent.parent / "memory" / "ip_library" / "rtl"
OUT_DIR = Path(__file__).parent.parent / "memory" / "ip_library"

SPIRIT = "http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009"
DERIVGEN = "http://derivgen.org/extensions"
ET.register_namespace("spirit", SPIRIT)
ET.register_namespace("derivgen", DERIVGEN)

# The eight APB signals, as named in the standard.
APB_SIGNALS = [
    ("PADDR", "paddr"), ("PSEL", "psel"), ("PENABLE", "penable"),
    ("PWRITE", "pwrite"), ("PWDATA", "pwdata"), ("PRDATA", "prdata"),
    ("PREADY", "pready"), ("PSLVERR", "pslverr"),
]

# Which bus interfaces each IP presents, and the port-name prefix of each.
# A physical port is always "<interface name>_<signal>", e.g. m0_apb_psel.
BUS_INTERFACES = {
    "Bus_Fabric_IP": [
        ("s_apb", "apb", "slave"),
        ("m0_apb", "apb", "master"),
        ("m1_apb", "apb", "master"),
        ("m2_apb", "apb", "master"),
        ("m3_apb", "apb", "master"),
    ],
    "SRAM_Ctrl_IP": [("apb", "apb", "slave")],
    "RegBank_IP": [("apb", "apb", "slave")],
    "UART_TX_IP": [("apb", "apb", "slave")],
}

# Tags are how "remove the safety features" becomes a concrete list of
# instances. They are metadata an IP owner sets, never something inferred.
TAGS = {
    "Bus_Fabric_IP": ["interconnect"],
    "SRAM_Ctrl_IP": ["memory"],
    "SRAM_Macro_IP": ["memory"],
    "RegBank_IP": ["config"],
    "UART_TX_IP": ["comm"],
    "Sensor_Formatter_IP": ["sensor"],
    "Threshold_Check_IP": ["sensor"],
    "Data_Aggregator_IP": ["sensor"],
    "Core_FSM_IP": ["control"],
    "Shadow_FSM_IP": ["safety", "lockstep"],
    "Lockstep_Comparator_IP": ["safety", "lockstep"],
    "Parity_Gen_IP": ["safety", "parity"],
    "Parity_Check_IP": ["safety", "parity"],
}

# Only these get packaged. The rest of the library is shelf-stock with no
# agreed port list yet.
PACKAGE = sorted(TAGS)

_PORT_RE = re.compile(
    r"\b(input|output|inout)\s+(?:wire\s+|reg\s+)?(?:\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*)?"
    r"([A-Za-z_]\w*)"
)


def read_ports(path: Path) -> list[tuple[str, str, int]]:
    """Return [(name, direction, width)] from a module's port list."""
    text = path.read_text(encoding="utf-8")
    # Strip comments first so commented-out ports are not picked up.
    text = re.sub(r"//[^\n]*", "", text)
    # Only look between "module" and the closing ");" of the port list.
    head = text.split("module", 1)[1]
    head = head.split(");", 1)[0]

    ports = []
    for direction, left, right, name in _PORT_RE.findall(head):
        width = int(left) - int(right) + 1 if left else 1
        ports.append((name, direction, width))
    return ports


def build_component(ip: str, ports: list[tuple[str, str, int]]) -> ET.Element:
    def tag(name):
        return f"{{{SPIRIT}}}{name}"

    comp = ET.Element(tag("component"))
    ET.SubElement(comp, tag("vendor")).text = "derivgen.org"
    ET.SubElement(comp, tag("library")).text = "derivsense"
    ET.SubElement(comp, tag("name")).text = ip
    ET.SubElement(comp, tag("version")).text = "1.0"

    port_names = {p[0] for p in ports}

    # -- bus interfaces --------------------------------------------------
    interfaces = BUS_INTERFACES.get(ip, [])
    if interfaces:
        bus_elem = ET.SubElement(comp, tag("busInterfaces"))
        for if_name, bus_type, role in interfaces:
            bi = ET.SubElement(bus_elem, tag("busInterface"))
            ET.SubElement(bi, tag("name")).text = if_name
            bt = ET.SubElement(bi, tag("busType"))
            bt.set("spirit:vendor", "amba.com")
            bt.set("spirit:library", "AMBA2")
            bt.set("spirit:name", bus_type.upper())
            bt.set("spirit:version", "r2p0")
            ET.SubElement(bi, tag("master" if role == "master" else "slave"))

            maps = ET.SubElement(bi, tag("portMaps"))
            for logical, suffix in APB_SIGNALS:
                physical = f"{if_name}_{suffix}"
                if physical not in port_names:
                    raise SystemExit(
                        f"{ip}: bus interface {if_name!r} expects port "
                        f"{physical!r}, which the Verilog does not have"
                    )
                pm = ET.SubElement(maps, tag("portMap"))
                lp = ET.SubElement(pm, tag("logicalPort"))
                ET.SubElement(lp, tag("name")).text = logical
                pp = ET.SubElement(pm, tag("physicalPort"))
                ET.SubElement(pp, tag("name")).text = physical

    # -- ports -----------------------------------------------------------
    model = ET.SubElement(comp, tag("model"))
    views = ET.SubElement(model, tag("views"))
    view = ET.SubElement(views, tag("view"))
    ET.SubElement(view, tag("name")).text = "rtl"
    ET.SubElement(view, tag("envIdentifier")).text = "::Verilog"

    ports_elem = ET.SubElement(model, tag("ports"))
    for name, direction, width in ports:
        p = ET.SubElement(ports_elem, tag("port"))
        ET.SubElement(p, tag("name")).text = name
        wire = ET.SubElement(p, tag("wire"))
        ET.SubElement(wire, tag("direction")).text = direction
        if width > 1:
            vec = ET.SubElement(wire, tag("vector"))
            ET.SubElement(vec, tag("left")).text = str(width - 1)
            ET.SubElement(vec, tag("right")).text = "0"

    # -- file set --------------------------------------------------------
    fs = ET.SubElement(comp, tag("fileSets"))
    fset = ET.SubElement(fs, tag("fileSet"))
    ET.SubElement(fset, tag("name")).text = "rtlSource"
    f = ET.SubElement(fset, tag("file"))
    ET.SubElement(f, tag("name")).text = f"rtl/{ip}.v"
    ET.SubElement(f, tag("fileType")).text = "verilogSource"

    # -- tags ------------------------------------------------------------
    tags = TAGS.get(ip, [])
    if tags:
        ext = ET.SubElement(comp, tag("vendorExtensions"))
        ET.SubElement(ext, f"{{{DERIVGEN}}}tags").text = ",".join(sorted(tags))

    return comp


def main() -> int:
    for ip in PACKAGE:
        rtl = RTL_DIR / f"{ip}.v"
        if not rtl.exists():
            raise SystemExit(f"missing RTL: {rtl}")
        ports = read_ports(rtl)
        comp = build_component(ip, ports)
        ET.indent(comp, space="  ")
        xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               + ET.tostring(comp, encoding="unicode") + "\n")
        (OUT_DIR / f"{ip}.xml").write_text(xml, encoding="utf-8")
        print(f"  {ip:<26} {len(ports):>2} ports  tags={','.join(TAGS.get(ip, [])) or '-'}")
    print(f"\npackaged {len(PACKAGE)} IPs into {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
