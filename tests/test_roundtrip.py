"""
Round-trip tests: read a script, write it back, read it again.

If this passes, the reader and the writer agree with each other, which is the
foundation everything else sits on. It catches most format bugs in one go.
"""

from pathlib import Path

import pytest

from derivgen.design import Ref
from derivgen.tcl import TclError, parse_ref, read_tcl, read_tcl_file, write_tcl

PARENT = Path(__file__).parent.parent / "memory" / "platforms" / "derivsense.tcl"


# ---------------------------------------------------------------------------
# References: the part most likely to be got wrong by splitting strings.
# ---------------------------------------------------------------------------

def test_top_level_pin():
    assert parse_ref("clk") == Ref(instance=None, port="clk")


def test_instance_port():
    assert parse_ref("sram_ctrl0/s_axi") == Ref(instance="sram_ctrl0", port="s_axi")


def test_underscores_in_port_name_are_never_split():
    # The whole reason instance and port are separate fields.
    ref = parse_ref("sram_ctrl0/s_axi_awaddr")
    assert ref.instance == "sram_ctrl0"
    assert ref.port == "s_axi_awaddr"


def test_bit_select():
    ref = parse_ref("data_agg0/alert_bus[0]")
    assert ref.instance == "data_agg0"
    assert ref.port == "alert_bus"
    assert ref.bits == "[0]"


def test_bit_range_on_top_pin():
    ref = parse_ref("sensor_data_in[63:32]")
    assert ref.is_top
    assert ref.port == "sensor_data_in"
    assert ref.bits == "[63:32]"


@pytest.mark.parametrize("text", ["a/b/c", "", "9bad", "x/"])
def test_bad_reference_is_rejected(text):
    with pytest.raises(TclError):
        parse_ref(text, line_no=1)


# ---------------------------------------------------------------------------
# Errors name the line.
# ---------------------------------------------------------------------------

def test_unknown_command_names_the_line():
    with pytest.raises(TclError, match="line 2"):
        read_tcl("add_instance a B\nfly_to_the_moon x\n", name="t")


def test_wrong_argument_count_names_the_line():
    with pytest.raises(TclError, match="line 1"):
        read_tcl("add_port clk in\n", name="t")


def test_bad_direction_is_rejected():
    with pytest.raises(TclError, match="direction"):
        read_tcl("add_port clk sideways 1\n", name="t")


# ---------------------------------------------------------------------------
# Comments and blank lines.
# ---------------------------------------------------------------------------

def test_comments_and_blanks_are_ignored():
    design = read_tcl(
        "# a comment\n\n  add_instance a B   # trailing comment\n", name="t"
    )
    assert len(design.instances) == 1
    assert design.instances[0].name == "a"


# ---------------------------------------------------------------------------
# The parent platform.
# ---------------------------------------------------------------------------

def test_parent_loads():
    design = read_tcl_file(PARENT)
    assert design.name == "derivsense"
    assert len(design.instances) == 16
    assert design.instance("lockstep_cmp0").ip == "Lockstep_Comparator_IP"
    assert design.bus_port("host_axi").role == "slave"
    assert design.port("sensor_data_in").width == 64


def test_parent_addresses_parse_as_hex():
    design = read_tcl_file(PARENT)
    sram = next(a for a in design.addresses if a.ref.instance == "sram_ctrl0")
    assert sram.base == 0x20000000
    assert sram.size == 0x1000
    assert sram.end == 0x20000FFF


def _as_sets(design):
    """Compare designs ignoring the order things were written in."""
    return (
        {(p.name, p.direction, p.width) for p in design.ports},
        {(b.name, b.bus_type, b.role) for b in design.bus_ports},
        {(i.name, i.ip) for i in design.instances},
        {(str(c.left), str(c.right)) for c in design.connections},
        {(str(c.left), str(c.right)) for c in design.bus_connections},
        {(str(a.ref), a.base, a.size) for a in design.addresses},
        {(str(t.ref), t.value) for t in design.tie_offs},
    )


def test_roundtrip_keeps_every_fact():
    first = read_tcl_file(PARENT)
    second = read_tcl(write_tcl(first), name=first.name)
    assert _as_sets(first) == _as_sets(second)


def test_writing_is_stable():
    # Writing twice must give byte-identical text, so diffs between runs mean
    # something really changed.
    first = read_tcl_file(PARENT)
    once = write_tcl(first)
    twice = write_tcl(read_tcl(once, name=first.name))
    assert once == twice
