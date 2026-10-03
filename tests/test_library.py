"""
The IP library, and whether the committed IP-XACT still matches the Verilog.

tools/package_ips.py generated the XML from the RTL once. If someone edits an
IP's port list and forgets to re-run it, the two drift apart silently and the
checker starts approving connections to ports that no longer exist. This test
is what stops that.
"""

import re
from pathlib import Path

import pytest

RTL = Path(__file__).parent.parent / "memory" / "ip_library" / "rtl"

_PORT_RE = re.compile(
    r"\b(input|output|inout)\s+(?:wire\s+|reg\s+)?(?:\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*)?"
    r"([A-Za-z_]\w*)"
)


def ports_from_verilog(path: Path) -> dict[str, tuple[str, int]]:
    text = re.sub(r"//[^\n]*", "", path.read_text(encoding="utf-8"))
    head = text.split("module", 1)[1].split(");", 1)[0]
    out = {}
    for direction, left, right, name in _PORT_RE.findall(head):
        out[name] = (direction, int(left) - int(right) + 1 if left else 1)
    return out


def test_library_is_not_empty(library):
    assert len(library) == 13


def test_every_packaged_ip_matches_its_verilog(library):
    for name, ip in library.items():
        verilog = ports_from_verilog(RTL / f"{name}.v")
        packaged = {p.name: (p.direction, p.width) for p in ip.ports.values()}
        assert packaged == verilog, (
            f"{name}: IP-XACT and Verilog disagree. "
            f"Re-run `python tools/package_ips.py`."
        )


def test_bus_interfaces_only_name_real_ports(library):
    for name, ip in library.items():
        for bus in ip.bus_interfaces.values():
            for port in bus.ports:
                assert port in ip.ports, (
                    f"{name}/{bus.name} maps {port!r}, which the IP does not have"
                )


def test_safety_tag_covers_the_whole_safety_group(library):
    tagged = {n for n, ip in library.items() if "safety" in ip.tags}
    assert tagged == {
        "Shadow_FSM_IP", "Lockstep_Comparator_IP",
        "Parity_Gen_IP", "Parity_Check_IP",
    }


def test_bus_signal_is_shared_across_ports(library):
    """m2_apb_prdata and m3_apb_prdata are both PRDATA."""
    fabric = library["Bus_Fabric_IP"]
    assert fabric.bus_signal("m2_apb_prdata") == "PRDATA"
    assert fabric.bus_signal("m3_apb_prdata") == "PRDATA"
    assert fabric.bus_signal("m2_apb_prdata") == fabric.bus_signal("m3_apb_prdata")


def test_plain_port_has_no_bus_signal(library):
    assert library["Core_FSM_IP"].bus_signal("data_in") is None


@pytest.mark.parametrize("ip,count", [("Bus_Fabric_IP", 5), ("RegBank_IP", 1)])
def test_bus_interface_counts(library, ip, count):
    assert len(library[ip].bus_interfaces) == count
