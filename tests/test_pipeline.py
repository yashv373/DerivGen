"""
Edits, planning, comparison and the Verilog build, end to end.

The most important test here is test_golden_cases_match: it runs the planner
against hand-written golden children and insists on an exact match.
"""

import json
from pathlib import Path

import pytest

from derivgen.build import build_verilog
from derivgen.check import check, errors
from derivgen.compare import compare
from derivgen.design import Ref
from derivgen.edits import Edit, EditError, apply_edits
from derivgen.llm import build_prompt, parse_response, prompt_hash
from derivgen.plan import free_bus_ports, plan_rules
from derivgen.retrieve import (
    load_derivatives,
    neighbours,
    similar_derivatives,
    what_breaks_if_removed,
)
from derivgen.tcl import read_tcl_file

MEMORY = Path(__file__).parent.parent / "memory"
DERIVATIVES = MEMORY / "derivatives"


# ---------------------------------------------------------------------------
# Edits
# ---------------------------------------------------------------------------

def test_remove_takes_its_lines_with_it(parent, library):
    result = apply_edits(parent, [Edit("remove", instance="uart_tx0")], "child")
    design = result.design
    assert design.instance("uart_tx0") is None
    assert not any(c.left.instance == "uart_tx0" or c.right.instance == "uart_tx0"
                   for c in design.connections)
    assert not any(a.ref.instance == "uart_tx0" for a in design.addresses)


def test_the_parent_is_never_modified(parent, library):
    before = len(parent.instances)
    apply_edits(parent, [Edit("remove", instance="uart_tx0")], "child")
    assert len(parent.instances) == before


def test_removing_something_that_is_not_there_fails_loudly(parent):
    with pytest.raises(EditError, match="no such instance"):
        apply_edits(parent, [Edit("remove", instance="ghost0")], "child")


def test_clone_copies_wiring_and_lands_on_the_free_port(parent, library):
    result = apply_edits(parent, [Edit(
        "clone", source="reg_bank0", name="reg_bank1",
        bus_port="bus_fabric0/m3_apb", base=0x20003000)], "child")
    design = result.design
    assert design.instance("reg_bank1").ip == "RegBank_IP"
    # clock and reset came across
    assert any(c.right.instance == "reg_bank1" and c.right.port == "clk"
               for c in design.connections)
    # it sits on the spare port, at the new address
    assert any(c.left == Ref("bus_fabric0", "m3_apb")
               and c.right.instance == "reg_bank1"
               for c in design.bus_connections)
    assert any(a.ref.instance == "reg_bank1" and a.base == 0x20003000
               for a in design.addresses)
    # the placeholder tie-offs on m3 are gone, because something answers now
    assert not any(t.ref.port.startswith("m3_apb_") for t in design.tie_offs)
    assert not errors(check(design, library))


def test_clone_refuses_a_name_already_in_use(parent):
    with pytest.raises(EditError, match="already exists"):
        apply_edits(parent, [Edit("clone", source="reg_bank0",
                                  name="uart_tx0")], "child")


def test_readdress_moves_only_the_base(parent):
    design = apply_edits(parent, [Edit("readdress", ref="uart_tx0/apb",
                                       base=0x20003000)], "child").design
    address = next(a for a in design.addresses if a.ref.instance == "uart_tx0")
    assert address.base == 0x20003000
    assert address.size == 0x1000


def test_readdress_of_something_unaddressed_fails(parent):
    with pytest.raises(EditError, match="no address"):
        apply_edits(parent, [Edit("readdress", ref="core_fsm0/data_in",
                                  base=0x1000)], "child")


def test_edit_from_dict_demands_its_fields():
    with pytest.raises(EditError, match="needs a 'instance'"):
        Edit.from_dict({"edit": "remove"})
    with pytest.raises(EditError, match="unknown edit"):
        Edit.from_dict({"edit": "rewire", "instance": "x"})


def test_edit_from_dict_reads_hex_addresses():
    edit = Edit.from_dict({"edit": "readdress", "ref": "a/b", "base": "0x2000"})
    assert edit.base == 0x2000


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def test_neighbours_are_one_hop(parent):
    found = neighbours(parent, "lockstep_cmp0")
    assert set(found) == {"core_fsm0", "shadow_fsm0", "<top>"}


def test_what_breaks_if_removed_reads_the_design(parent, library):
    breaks = what_breaks_if_removed(parent, library, "lockstep_cmp0")
    assert breaks == ["err_lockstep (top-level pin)"]


def test_similar_derivatives_prefers_shared_words():
    past = load_derivatives(DERIVATIVES)
    found = similar_derivatives(past, "remove the uart please", limit=1)
    assert found and found[0].case_id == "d002_no_uart"


def test_similar_derivatives_can_exclude_a_case():
    past = load_derivatives(DERIVATIVES)
    found = similar_derivatives(past, "Remove the UART", exclude="d002_no_uart")
    assert all(f.case_id != "d002_no_uart" for f in found)


def test_free_bus_ports_finds_the_spare(parent, library):
    assert free_bus_ports(parent, library) == ["bus_fabric0/m3_apb"]


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

def test_planner_repairs_a_dangling_bus_port(parent, library):
    """pready must come back as 1'b1, copied from the parent's spare port."""
    plan = plan_rules("Remove the UART", parent, library, "child")
    assert plan.ok
    ties = {e.ref: e.value for e in plan.edits if e.kind == "tie"}
    assert ties["bus_fabric0/m2_apb_pready"] == "1'b1"
    assert ties["bus_fabric0/m2_apb_prdata"] == "32'b0"


def test_planner_refuses_an_unreadable_instruction(parent, library):
    plan = plan_rules("Port this to a 7nm process", parent, library, "child")
    assert not plan.ok
    assert "remove, add or move" in plan.refused


def test_planner_refuses_an_address_clash(parent, library):
    plan = plan_rules("Move the UART to 0x20001000", parent, library, "child")
    assert not plan.ok
    assert "overlaps" in plan.refused


def test_planner_refuses_to_orphan_the_bus(parent, library):
    plan = plan_rules("Remove the bus fabric", parent, library, "child")
    assert not plan.ok


# ---------------------------------------------------------------------------
# The golden cases
# ---------------------------------------------------------------------------

def _cases_with_goldens():
    out = []
    for record in sorted(DERIVATIVES.glob("*/record.json")):
        data = json.loads(record.read_text(encoding="utf-8"))
        if data.get("child_tcl"):
            out.append(data["id"])
    return out


@pytest.mark.parametrize("case_id", _cases_with_goldens())
def test_oracle_mode_is_exact(case_id, parent, library):
    """Replaying the stored edits must reproduce the golden exactly."""
    data = json.loads((DERIVATIVES / case_id / "record.json").read_text())
    golden = read_tcl_file(DERIVATIVES / case_id / data["child_tcl"])
    edits = [Edit.from_dict(e) for e in data["edits"]]
    design = apply_edits(parent, edits, golden.name).design
    result = compare(design, golden)
    assert result.perfect, result.report()


@pytest.mark.parametrize("case_id", _cases_with_goldens())
def test_goldens_check_clean(case_id, library):
    data = json.loads((DERIVATIVES / case_id / "record.json").read_text())
    golden = read_tcl_file(DERIVATIVES / case_id / data["child_tcl"])
    assert not errors(check(golden, library))


@pytest.mark.parametrize("case_id", ["d001_no_safety", "d002_no_uart"])
def test_planner_matches_the_hand_written_golden(case_id, parent, library):
    data = json.loads((DERIVATIVES / case_id / "record.json").read_text())
    assert data["golden_source"] == "hand-written"
    golden = read_tcl_file(DERIVATIVES / case_id / data["child_tcl"])
    plan = plan_rules(data["instruction"], parent, library, golden.name)
    assert plan.ok, plan.refused
    design = apply_edits(parent, plan.edits, golden.name).design
    result = compare(design, golden)
    assert result.perfect, result.report()


def test_must_refuse_instructions_are_refused(parent, library):
    for record in sorted(DERIVATIVES.glob("*/record.json")):
        data = json.loads(record.read_text(encoding="utf-8"))
        for instruction in data.get("must_refuse", []):
            plan = plan_rules(instruction, parent, library, "child")
            assert not plan.ok, f"{instruction!r} should have been refused"


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def test_comparison_ignores_the_order_of_a_connection(parent):
    swapped = read_tcl_file(MEMORY / "platforms" / "derivsense.tcl")
    for conn in swapped.connections:
        conn.left, conn.right = conn.right, conn.left
    assert compare(swapped, parent).perfect


def test_comparison_notices_a_missing_instance(parent):
    smaller = apply_edits(parent, [Edit("remove", instance="uart_tx0")],
                          parent.name).design
    result = compare(smaller, parent)
    assert not result.perfect
    assert ("uart_tx0", "UART_TX_IP") in result.score("instances").missing


# ---------------------------------------------------------------------------
# Building Verilog
# ---------------------------------------------------------------------------

def test_build_is_stable(parent, library):
    first = build_verilog(parent, library)
    second = build_verilog(parent, library)
    assert first == second


def test_build_names_nets_after_their_driver(parent, library):
    verilog = build_verilog(parent, library)
    assert "wire [31:0] core_fsm0_state;" in verilog
    assert ".state_a           (core_fsm0_state)" in verilog


def test_build_concatenates_a_port_fed_in_pieces(parent, library):
    verilog = build_verilog(parent, library)
    assert ".alert_bus         ({30'b0, thresh_chk_1_alert, thresh_chk_0_alert})" \
        in verilog


def test_build_expands_a_top_level_bus(parent, library):
    verilog = build_verilog(parent, library)
    assert "input  wire [31:0] host_apb_paddr" in verilog
    assert "output wire [31:0] host_apb_prdata" in verilog


def test_build_instantiates_every_instance(parent, library):
    verilog = build_verilog(parent, library)
    for instance in parent.instances:
        assert f"{instance.ip} {instance.name} (" in verilog


# ---------------------------------------------------------------------------
# LLM plumbing (no model involved)
# ---------------------------------------------------------------------------

def test_prompt_mentions_the_instruction_and_the_slice(parent, library):
    prompt = build_prompt("Remove the safety features", parent, library,
                          ["lockstep_cmp0"], [])
    assert "Remove the safety features" in prompt
    assert "lockstep_cmp0" in prompt
    assert "if removed, these lose their driver: err_lockstep" in prompt


def test_prompt_hash_is_stable(parent, library):
    prompt = build_prompt("x", parent, library, [], [])
    assert prompt_hash(prompt) == prompt_hash(prompt)


def test_parse_response_survives_code_fences_and_prose():
    reply = """Sure! Here are the edits:
```json
[{"edit": "remove", "instance": "uart_tx0"}]
```
Hope that helps."""
    edits, refusal = parse_response(reply)
    assert refusal is None
    assert edits == [{"edit": "remove", "instance": "uart_tx0"}]


def test_parse_response_reads_a_refusal():
    edits, refusal = parse_response('{"refused": "cannot be derived"}')
    assert edits == []
    assert refusal == "cannot be derived"


def test_parse_response_rejects_nonsense():
    from derivgen.llm import LlmError
    with pytest.raises(LlmError):
        parse_response("I am afraid I cannot do that.")
