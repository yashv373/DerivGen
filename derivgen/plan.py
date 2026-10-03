"""
Planning: turning an instruction into a list of edits.

Two planners live here and both return the same thing, so they are
interchangeable:

  plan_rules()  keyword -> tag -> instances. No LLM at all. This is the
                baseline and the fallback.
  plan_llm()    asks a language model, then checks its answer and feeds the
                problems back. See llm.py for the backends.

Both finish by running the same repair loop: apply the edits, check the
result, and fix what the checker complains about. That loop is the
"self-questioning" step, done deterministically -- the questions are answered
by reading the design, never by guessing.
"""

import re
from dataclasses import dataclass, field

from .check import check, errors
from .design import Design
from .edits import Edit, EditError, apply_edits
from .library import Ip
from .retrieve import instances_with_tag

MAX_REPAIR_ROUNDS = 3


@dataclass
class Plan:
    """What a planner produces."""
    derivative_name: str
    instruction: str
    edits: list[Edit] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)   # audit only, never applied
    refused: str | None = None                       # why, if it could not be done

    @property
    def ok(self) -> bool:
        return self.refused is None


# ---------------------------------------------------------------------------
# Words to tags
# ---------------------------------------------------------------------------

# Everyday words an engineer might use for each tag. This table is the whole
# "natural language understanding" of the rule-based planner, which is both
# its strength (predictable) and its weakness (no paraphrase it has not seen).
TAG_WORDS: dict[str, set[str]] = {
    "safety": {"safety", "safe", "redundancy", "redundant", "diagnostic", "diagnostics", "asil", "functional"},
    "lockstep": {"lockstep", "shadow", "comparator", "duplicate", "dual"},
    "parity": {"parity", "ecc", "checksum"},
    "comm": {"uart", "serial", "comm", "communication", "console"},
    "memory": {"memory", "ram", "sram", "storage", "scratchpad"},
    "sensor": {"sensor", "sensors", "sensing", "channel", "channels"},
    "control": {"control", "fsm", "controller"},
    "config": {"config", "configuration", "register", "registers", "regbank"},
    "interconnect": {"bus", "fabric", "interconnect", "crossbar"},
}

REMOVE_WORDS = {"remove", "removing", "strip", "stripped", "drop", "delete",
                "without", "cut", "omit", "exclude", "no", "minus", "lose",
                "eliminate", "deprive"}
ADD_WORDS = {"add", "adding", "second", "another", "extra", "more", "clone",
             "duplicate", "additional", "two", "expand", "spare"}
MOVE_WORDS = {"move", "moving", "relocate", "readdress", "remap", "shift",
              "rebase", "reposition"}


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def _intent(instruction: str) -> str:
    """Which of the three things the instruction is asking for."""
    found = set(_words(instruction))
    # Checked in this order: moving and adding are more specific asks than
    # removing, and "move X, remove Y" is not something we support anyway.
    if found & MOVE_WORDS:
        return "readdress"
    if found & ADD_WORDS:
        return "clone"
    if found & REMOVE_WORDS:
        return "remove"
    return "unknown"


def _matched_tags(instruction: str) -> list[str]:
    found = set(_words(instruction))
    return sorted(tag for tag, synonyms in TAG_WORDS.items() if found & synonyms)


def _matched_instances(instruction: str, design: Design) -> list[str]:
    """Instances the instruction names directly, or by their IP name."""
    text = instruction.lower()
    hits: set[str] = set()
    for inst in design.instances:
        if inst.name.lower() in text:
            hits.add(inst.name)
        # "uart" should match uart_tx0 via UART_TX_IP as well.
        stem = inst.ip.lower().removesuffix("_ip")
        if stem and stem in text:
            hits.add(inst.name)
    return sorted(hits)


def find_targets(instruction: str, design: Design,
                 library: dict[str, Ip]) -> tuple[list[str], list[str]]:
    """
    Which instances the instruction is about, and how we decided.

    Returns (instance names, trace lines).
    """
    trace: list[str] = []
    targets: set[str] = set()

    for tag in _matched_tags(instruction):
        tagged = instances_with_tag(design, library, tag)
        if tagged:
            targets.update(tagged)
            trace.append(f"word matched tag {tag!r} -> {', '.join(tagged)}")

    named = _matched_instances(instruction, design)
    if named:
        targets.update(named)
        trace.append(f"named directly -> {', '.join(named)}")

    return sorted(targets), trace


# ---------------------------------------------------------------------------
# Repair: answering the checker
# ---------------------------------------------------------------------------

def _remembered_tie(parent: Design, library: dict[str, Ip],
                    instance: str, port: str, design: Design) -> str | None:
    """
    What the parent tied this same port to, if it tied it at all.

    This keeps repairs inside "derive, never invent": rather than picking a
    constant, we reuse the value the verified parent already used on the same
    port of the same IP.
    """
    inst = design.instance(instance)
    if inst is None or inst.ip not in library:
        return None
    ip = library[inst.ip]
    # If this port is part of a bus, a tie on the same bus signal of another
    # port of the same IP counts: PREADY is PREADY whichever port it is on.
    wanted_signal = ip.bus_signal(port)

    for tie in parent.tie_offs:
        if tie.ref.instance is None:
            continue
        other = parent.instance(tie.ref.instance)
        if other is None or other.ip != inst.ip:
            continue
        if tie.ref.port == port:
            return tie.value
        if wanted_signal and ip.bus_signal(tie.ref.port) == wanted_signal:
            return tie.value
    return None


def _width_for_value(design: Design, library: dict[str, Ip],
                     instance: str, port: str) -> int:
    inst = design.instance(instance)
    if inst is None or inst.ip not in library:
        return 1
    p = library[inst.ip].ports.get(port)
    return p.width if p else 1


def repair(parent: Design, design: Design, library: dict[str, Ip],
           problems) -> tuple[list[Edit], list[str]]:
    """
    Turn checker complaints into extra edits.

    Only two complaints can be repaired automatically:
      a top-level output with no driver  -> delete the pin
      an instance input with no driver   -> tie it

    Anything else is left for the planner to refuse, because guessing at it
    would mean inventing structure.
    """
    extra: list[Edit] = []
    trace: list[str] = []

    for problem in problems:
        if "not driven" not in problem.message:
            continue
        if "top-level output" in problem.message:
            extra.append(Edit(
                "remove_port", port=problem.where,
                reason="lost its driver when its source was removed",
            ))
            trace.append(f"{problem.where} has no driver -> remove the pin")
            continue

        if "/" in problem.where:
            instance, port = problem.where.split("/", 1)
            value = _remembered_tie(parent, library, instance, port, design)
            if value is None:
                width = _width_for_value(design, library, instance, port)
                value = f"{width}'b0" if width > 1 else "1'b0"
                why = "no driver left; held at zero"
            else:
                why = f"no driver left; parent uses {value} on this port"
            extra.append(Edit("tie", ref=problem.where, value=value, reason=why))
            trace.append(f"{problem.where} has no driver -> tie to {value}")

    return extra, trace


def settle(parent: Design, edits: list[Edit], library: dict[str, Ip],
           derivative_name: str) -> tuple[list[Edit], Design, list[str], list]:
    """
    Apply edits, check, repair, repeat until clean or out of rounds.

    Returns (final edits, final design, trace, remaining problems).
    """
    trace: list[str] = []
    current = list(edits)

    for round_number in range(1, MAX_REPAIR_ROUNDS + 1):
        result = apply_edits(parent, current, derivative_name)
        problems = check(result.design, library)
        remaining = errors(problems)
        if not remaining:
            if round_number > 1:
                trace.append(f"clean after {round_number - 1} repair round(s)")
            return current, result.design, trace, []

        extra, repair_trace = repair(parent, result.design, library, remaining)
        if not extra:
            trace.append(
                f"round {round_number}: {len(remaining)} problem(s) left that "
                f"cannot be repaired automatically"
            )
            return current, result.design, trace, remaining

        trace.append(f"round {round_number}: checker found {len(remaining)} problem(s)")
        trace.extend(f"  {line}" for line in repair_trace)
        current = current + extra

    result = apply_edits(parent, current, derivative_name)
    problems = errors(check(result.design, library))
    trace.append(f"gave up after {MAX_REPAIR_ROUNDS} repair rounds")
    return current, result.design, trace, problems


# ---------------------------------------------------------------------------
# Scale-up helpers
# ---------------------------------------------------------------------------

def free_bus_ports(design: Design, library: dict[str, Ip]) -> list[str]:
    """Master bus interfaces that nothing is connected to, as 'inst/iface'."""
    used: set[tuple[str, str]] = set()
    for conn in design.bus_connections:
        for end in (conn.left, conn.right):
            if not end.is_top:
                used.add((end.instance, end.port))

    free: list[str] = []
    for inst in design.instances:
        if inst.ip not in library:
            continue
        for bus in library[inst.ip].bus_interfaces.values():
            if bus.role == "master" and (inst.name, bus.name) not in used:
                free.append(f"{inst.name}/{bus.name}")
    return sorted(free)


def next_free_address(design: Design, size: int) -> int:
    """The first address above everything already mapped, aligned to size."""
    if not design.addresses:
        return 0
    top = max(a.end for a in design.addresses)
    base = top + 1
    if size and base % size:
        base += size - (base % size)
    return base


def _next_name(design: Design, source: str) -> str:
    """sensor_fmt_1 -> sensor_fmt_2; reg_bank0 -> reg_bank1."""
    match = re.match(r"^(.*?)(\d+)$", source)
    stem, number = (match.group(1), int(match.group(2))) if match else (source + "_", 0)
    existing = design.instance_names()
    candidate = number + 1
    while f"{stem}{candidate}" in existing:
        candidate += 1
    return f"{stem}{candidate}"


# ---------------------------------------------------------------------------
# The rule-based planner
# ---------------------------------------------------------------------------

def plan_rules(instruction: str, parent: Design, library: dict[str, Ip],
               derivative_name: str) -> Plan:
    """Plan with no language model: words -> tags -> instances -> edits."""
    plan = Plan(derivative_name=derivative_name, instruction=instruction)

    intent = _intent(instruction)
    plan.trace.append(f"read the instruction as: {intent}")
    if intent == "unknown":
        plan.refused = (
            "cannot tell whether this asks to remove, add or move something. "
            "Supported: remove an instance or group, add a copy of an existing "
            "instance, move something to a new address."
        )
        return plan

    targets, target_trace = find_targets(instruction, parent, library)
    plan.trace.extend(target_trace)

    if not targets:
        plan.refused = (
            "no instance in the parent matches this instruction. Known tags: "
            + ", ".join(sorted(TAG_WORDS))
        )
        return plan

    if intent == "remove":
        plan.edits = [
            Edit("remove", instance=name, reason="matched the instruction")
            for name in targets
        ]

    elif intent == "clone":
        if len(targets) != 1:
            plan.refused = (
                f"asked to add a copy, but the instruction matches "
                f"{len(targets)} instances ({', '.join(targets)}). Name one."
            )
            return plan
        source = targets[0]
        free = free_bus_ports(parent, library)
        inst = parent.instance(source)
        needs_bus = bool(library[inst.ip].slave_interfaces()) if inst else False

        if needs_bus and not free:
            plan.refused = (
                f"cannot add another {source}: every bus port on the parent is "
                f"already used, and adding one would mean changing the "
                f"interconnect rather than deriving from it."
            )
            return plan

        size = next((a.size for a in parent.addresses
                     if a.ref.instance == source), 0x1000)
        plan.edits = [Edit(
            "clone",
            source=source,
            name=_next_name(parent, source),
            bus_port=free[0] if needs_bus else None,
            base=next_free_address(parent, size) if needs_bus else None,
            reason="copy of an instance the parent already has",
        )]
        if needs_bus:
            plan.trace.append(f"free bus port available: {free[0]}")

    else:  # readdress
        address = _find_address(instruction)
        if address is None:
            plan.refused = (
                "asked to move something, but no target address was given. "
                "Say where, e.g. 'move the UART to 0x20003000'."
            )
            return plan
        addressed = [t for t in targets
                     if any(a.ref.instance == t for a in parent.addresses)]
        if len(addressed) != 1:
            plan.refused = (
                f"asked to move something to 0x{address:08x}, but the "
                f"instruction matches {len(addressed)} addressable instances "
                f"({', '.join(addressed) or 'none'}). Name one."
            )
            return plan
        ref = next(str(a.ref) for a in parent.addresses
                   if a.ref.instance == addressed[0])
        plan.edits = [Edit("readdress", ref=ref, base=address,
                           reason="instruction gave a new address")]

    # Apply, check, repair.
    try:
        final_edits, _, settle_trace, remaining = settle(
            parent, plan.edits, library, derivative_name
        )
    except EditError as err:
        plan.refused = str(err)
        return plan

    plan.edits = final_edits
    plan.trace.extend(settle_trace)
    if remaining:
        plan.refused = (
            "the result still has problems the tool cannot fix by deriving:\n"
            + "\n".join(f"  {p}" for p in remaining)
        )
    return plan


def _find_address(instruction: str) -> int | None:
    match = re.search(r"0x[0-9a-fA-F]+", instruction)
    return int(match.group(0), 16) if match else None


# ---------------------------------------------------------------------------
# The LLM planner
# ---------------------------------------------------------------------------

MAX_LLM_ROUNDS = 2


def plan_llm(instruction: str, parent: Design, library: dict[str, Ip],
             derivative_name: str, backend, past=None,
             exclude_case: str | None = None) -> Plan:
    """
    Plan by asking a language model, then checking what it said.

    The model only ever proposes the changes the instruction asks for. The
    dependency edits -- tie-offs and dropped pins -- are worked out afterwards
    by the same deterministic repair loop the rule-based planner uses. If
    problems remain, they go back to the model and it tries again.
    """
    from .llm import LlmError, build_prompt, parse_response
    from .retrieve import similar_derivatives

    plan = Plan(derivative_name=derivative_name, instruction=instruction)

    # Retrieval is the same tag lookup the rule-based planner uses; here it
    # decides what the model is shown rather than what it does.
    focus, focus_trace = find_targets(instruction, parent, library)
    plan.trace.extend(f"retrieved: {line}" for line in focus_trace)

    examples = similar_derivatives(past or [], instruction, limit=3,
                                   exclude=exclude_case)
    if examples:
        plan.trace.append(
            "examples from memory: " + ", ".join(e.case_id for e in examples)
        )

    problems_text: list[str] | None = None

    for round_number in range(1, MAX_LLM_ROUNDS + 1):
        prompt = build_prompt(instruction, parent, library, focus, examples,
                              problems_text)
        try:
            reply = backend.complete(prompt)
            raw_edits, refusal = parse_response(reply)
        except LlmError as err:
            plan.refused = f"model reply could not be used: {err}"
            return plan

        if refusal:
            plan.refused = f"model refused: {refusal}"
            return plan

        try:
            edits = [Edit.from_dict(item) for item in raw_edits]
        except EditError as err:
            problems_text = [f"your edit list was rejected: {err}"]
            plan.trace.append(f"round {round_number}: {err}")
            continue

        plan.trace.append(
            f"round {round_number}: model proposed {len(edits)} edit(s): "
            + "; ".join(e.describe() for e in edits)
        )

        try:
            final_edits, _, settle_trace, remaining = settle(
                parent, edits, library, derivative_name
            )
        except EditError as err:
            problems_text = [str(err)]
            plan.trace.append(f"round {round_number}: {err}")
            continue

        plan.trace.extend(settle_trace)
        if not remaining:
            plan.edits = final_edits
            return plan

        problems_text = [str(p) for p in remaining]
        plan.edits = final_edits

    plan.refused = (
        f"still not clean after {MAX_LLM_ROUNDS} rounds with the model:\n"
        + "\n".join(f"  {p}" for p in (problems_text or []))
    )
    return plan
