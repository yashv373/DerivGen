"""
Retrieval: pulling the relevant few facts out of memory.

This is the "R" in RAG, and it is deliberately dull. The keys we search on --
tags, IP names, instance names -- are exact, so exact lookup beats similarity
search. There are no embeddings and no vector database, because there is
nothing fuzzy to match.

Two things get retrieved:

  1. the slice of the parent that the instruction is about (tagged instances
     plus whatever touches them directly), and
  2. one to three past derivatives whose instruction used similar words.

Both go into the prompt. Keeping the slice small is what lets a weak,
chat-only model cope: it sees fifteen lines about four instances, not the
whole platform.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .design import Design
from .library import Ip

# Words too common to tell two instructions apart.
_STOPWORDS = {
    "a", "an", "and", "the", "to", "of", "for", "from", "with", "without",
    "in", "on", "it", "its", "that", "this", "make", "create", "give", "me",
    "please", "variant", "version", "derivative", "platform", "soc", "all",
    "any", "out", "up", "i", "want", "need", "new",
}


def words(text: str) -> set[str]:
    """Lower-case words of three or more letters, minus the dull ones."""
    found = re.findall(r"[a-z0-9_]+", text.lower())
    return {w for w in found if len(w) >= 3 and w not in _STOPWORDS}


# ---------------------------------------------------------------------------
# Finding instances
# ---------------------------------------------------------------------------

def instances_with_tag(design: Design, library: dict[str, Ip], tag: str) -> list[str]:
    """Instance names whose IP carries this tag, sorted."""
    return sorted(
        inst.name for inst in design.instances
        if inst.ip in library and tag in library[inst.ip].tags
    )


def neighbours(design: Design, instance: str) -> list[str]:
    """
    Instances wired directly to this one, plus "<top>" if it touches a pin.

    This is the 1-hop neighbourhood. It is what answers "what breaks if I
    remove this?" without the model having to reason about the whole design.
    """
    found: set[str] = set()
    pairs = [(c.left, c.right) for c in design.connections]
    pairs += [(c.left, c.right) for c in design.bus_connections]
    for left, right in pairs:
        for near, far in ((left, right), (right, left)):
            if near.instance != instance:
                continue
            found.add(far.instance if far.instance else "<top>")
    found.discard(instance)
    return sorted(found)


def what_breaks_if_removed(design: Design, library: dict[str, Ip],
                           instance: str) -> list[str]:
    """
    Which inputs and pins lose their driver if this instance goes.

    Deterministic: it reads the design, so the answer cannot be made up.
    """
    inst = design.instance(instance)
    if inst is None or inst.ip not in library:
        return []
    ip = library[inst.ip]
    outputs = {p.name for p in ip.ports.values() if p.direction == "output"}

    losers: list[str] = []
    for conn in design.connections:
        for near, far in ((conn.left, conn.right), (conn.right, conn.left)):
            if near.instance != instance or near.port not in outputs:
                continue
            losers.append(str(far) if far.instance else f"{far.port} (top-level pin)")
    return sorted(set(losers))


# ---------------------------------------------------------------------------
# Describing a slice, for a prompt
# ---------------------------------------------------------------------------

def describe_slice(design: Design, library: dict[str, Ip],
                   focus: list[str]) -> str:
    """
    A short plain-text description of some instances and their surroundings.

    This is what goes in the prompt instead of the whole platform.
    """
    lines: list[str] = []
    ring = sorted({n for f in focus for n in neighbours(design, f)} - set(focus))

    lines.append("Instances the instruction is about:")
    for name in focus:
        inst = design.instance(name)
        if inst is None:
            continue
        tags = sorted(library[inst.ip].tags) if inst.ip in library else []
        lines.append(f"  {name}  (ip={inst.ip}, tags={','.join(tags) or 'none'})")
        breaks = what_breaks_if_removed(design, library, name)
        if breaks:
            lines.append(f"      if removed, these lose their driver: {', '.join(breaks)}")

    if ring:
        lines.append("")
        lines.append("Directly connected to those:")
        for name in ring:
            if name == "<top>":
                lines.append("  <top>  (the platform's own pins)")
                continue
            inst = design.instance(name)
            if inst is None:
                continue
            tags = sorted(library[inst.ip].tags) if inst.ip in library else []
            lines.append(f"  {name}  (ip={inst.ip}, tags={','.join(tags) or 'none'})")

    addresses = [a for a in design.addresses if a.ref.instance in set(focus) | set(ring)]
    if addresses:
        lines.append("")
        lines.append("Addresses in this area:")
        for a in sorted(addresses, key=lambda a: a.base):
            lines.append(f"  {a.ref}  0x{a.base:08x}  size 0x{a.size:x}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Past derivatives
# ---------------------------------------------------------------------------

@dataclass
class PastDerivative:
    case_id: str
    instruction: str
    parent: str
    derivative_type: str
    edits: list[dict] = field(default_factory=list)
    verified: bool = False

    @property
    def keywords(self) -> set[str]:
        return words(self.instruction)


def load_derivatives(directory) -> list[PastDerivative]:
    """Read every record.json under memory/derivatives/."""
    directory = Path(directory)
    out: list[PastDerivative] = []
    for record_path in sorted(directory.glob("*/record.json")):
        data = json.loads(record_path.read_text(encoding="utf-8"))
        out.append(PastDerivative(
            case_id=data.get("id", record_path.parent.name),
            instruction=data.get("instruction", ""),
            parent=data.get("parent", ""),
            derivative_type=data.get("derivative_type", ""),
            edits=data.get("edits", []),
            verified=bool(data.get("verified")),
        ))
    return out


def similar_derivatives(past: list[PastDerivative], instruction: str,
                        limit: int = 3,
                        exclude: str | None = None) -> list[PastDerivative]:
    """
    The most similar past derivatives, by how many words they share.

    Only verified ones are offered as examples -- an unchecked derivative is
    not something to copy. `exclude` drops one case by id, which is how the
    benchmark avoids showing a case its own answer.
    """
    target = words(instruction)
    scored = []
    for record in past:
        if not record.verified or record.case_id == exclude:
            continue
        shared = len(target & record.keywords)
        if shared:
            scored.append((shared, record.case_id, record))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [record for _, _, record in scored[:limit]]
