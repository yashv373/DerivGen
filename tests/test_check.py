"""
The checker. Each test breaks the parent in one specific way and expects the
checker to say so, naming the instance and the port.
"""

import pytest

from derivgen.check import bits_covered, check, errors
from derivgen.design import Address, Connection, Instance, Ref
from derivgen.edits import Edit, apply_edits


def test_parent_is_clean(parent, library):
    assert check(parent, library) == []


def test_removing_a_driver_is_caught(parent, library):
    """The headline case: no comparator means err_lockstep has no driver."""
    design = apply_edits(parent, [Edit("remove", instance="lockstep_cmp0")],
                         "broken").design
    found = errors(check(design, library))
    assert any(p.where == "err_lockstep" and "not driven" in p.message
               for p in found)


def test_removing_a_bus_slave_dangles_the_master_port(parent, library):
    """Less obvious: the fabric port it was on loses its response inputs."""
    design = apply_edits(parent, [Edit("remove", instance="uart_tx0")],
                         "broken").design
    dangling = {p.where for p in errors(check(design, library))}
    assert "bus_fabric0/m2_apb_prdata" in dangling
    assert "bus_fabric0/m2_apb_pready" in dangling


def test_connection_to_a_port_that_does_not_exist(parent, library):
    """
    The bug the old framework shipped: wiring a port the module lacks.

    Nothing downstream can catch this, so the checker must.
    """
    parent.connections.append(Connection(
        Ref(None, "clk"), Ref("core_fsm0", "m0_axi_awvalid")
    ))
    found = errors(check(parent, library))
    assert any("m0_axi_awvalid" in p.message and "does not have" in p.message
               for p in found)


def test_connection_to_an_instance_that_does_not_exist(parent, library):
    parent.connections.append(Connection(Ref(None, "clk"), Ref("ghost0", "clk")))
    found = errors(check(parent, library))
    assert any("ghost0" in p.message for p in found)


def test_unknown_ip_is_caught(parent, library):
    parent.instances.append(Instance("mystery0", "Not_A_Real_IP"))
    found = errors(check(parent, library))
    assert any(p.where == "mystery0" and "not in the library" in p.message
               for p in found)


def test_two_drivers_on_one_input(parent, library):
    parent.connections.append(Connection(
        Ref("sensor_fmt_1", "data_out"), Ref("core_fsm0", "data_in")
    ))
    found = errors(check(parent, library))
    assert any(p.where == "core_fsm0/data_in" and "more than one source" in p.message
               for p in found)


def test_overlapping_addresses(parent, library):
    parent.addresses.append(Address(Ref("reg_bank0", "apb"), 0x20000800, 0x1000))
    found = errors(check(parent, library))
    assert any("overlaps" in p.message for p in found)


def test_partial_drive_is_caught(parent, library):
    """Dropping the tie leaves 30 of the aggregator's 32 alert bits loose."""
    parent.tie_offs = [t for t in parent.tie_offs
                       if t.ref.port != "alert_bus"]
    found = errors(check(parent, library))
    problem = next(p for p in found if p.where == "data_agg0/alert_bus")
    assert "[31:2]" in problem.message


def test_bus_slave_without_an_address(parent, library):
    parent.addresses = [a for a in parent.addresses
                        if a.ref.instance != "reg_bank0"]
    found = errors(check(parent, library))
    assert any(p.where == "reg_bank0/apb" and "no address" in p.message
               for p in found)


def test_interconnect_slave_needs_no_address(parent, library):
    """The fabric's own slave port is an entry point, not a decoded region."""
    assert not any(p.where == "bus_fabric0/s_apb" for p in check(parent, library))


@pytest.mark.parametrize("bits,width,expected", [
    (None, 4, {0, 1, 2, 3}),
    ("[0]", 32, {0}),
    ("[3:1]", 8, {1, 2, 3}),
    ("[1:3]", 8, {1, 2, 3}),
])
def test_bits_covered(bits, width, expected):
    assert bits_covered(bits, width) == expected
