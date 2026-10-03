"""
The five edits that turn a parent platform into a derivative.

This is the heart of "derive, never invent". A derivative is an edited copy of
the parent -- nothing else. If a request cannot be expressed as these five
edits, the tool refuses it instead of guessing:

    remove        delete an instance and every line that mentions it
    remove_port   delete a top-level pin that lost its driver
    tie           hold a remaining input at a constant
    clone         copy an existing instance under a new name
    readdress     move an instance to a different address

Nothing here invents a connection. clone only ever copies wiring that the
parent already had, and tie only ever uses a constant the planner asked for.
"""

import copy
from dataclasses import dataclass, field

from .design import Address, Design, Instance, Ref, TieOff
from .tcl import parse_ref

KINDS = ("remove", "remove_port", "tie", "clone", "readdress")


class EditError(Exception):
    """Raised when an edit cannot be applied. Says which edit and why."""


@dataclass
class Edit:
    """
    One change. Which fields matter depends on `kind`:

      remove       instance
      remove_port  port
      tie          ref, value
      clone        source, name, and optionally bus_port and base
      readdress    ref, base
    """
    kind: str
    instance: str | None = None
    port: str | None = None
    ref: str | None = None
    value: str | None = None
    source: str | None = None
    name: str | None = None
    bus_port: str | None = None
    base: int | None = None
    reason: str = ""

    @staticmethod
    def from_dict(data: dict) -> "Edit":
        """Build an Edit from parsed JSON, checking it names what it needs."""
        if not isinstance(data, dict):
            raise EditError(f"an edit must be an object, got {type(data).__name__}")
        kind = data.get("edit") or data.get("kind")
        if kind not in KINDS:
            raise EditError(
                f"unknown edit {kind!r}; must be one of {', '.join(KINDS)}"
            )

        base = data.get("base")
        if isinstance(base, str):
            try:
                base = int(base, 0)
            except ValueError:
                raise EditError(f"{kind}: base address {base!r} is not a number") from None

        edit = Edit(
            kind=kind,
            instance=data.get("instance"),
            port=data.get("port"),
            ref=data.get("ref"),
            value=data.get("value"),
            source=data.get("source"),
            name=data.get("name"),
            bus_port=data.get("bus_port"),
            base=base,
            reason=data.get("reason", ""),
        )

        required = {
            "remove": ["instance"],
            "remove_port": ["port"],
            "tie": ["ref", "value"],
            "clone": ["source", "name"],
            "readdress": ["ref", "base"],
        }[kind]
        for fieldname in required:
            if getattr(edit, fieldname) in (None, ""):
                raise EditError(f"{kind} edit needs a {fieldname!r}")
        return edit

    def to_dict(self) -> dict:
        """Back to JSON, leaving out fields this kind does not use."""
        out: dict = {"edit": self.kind}
        for fieldname in ("instance", "port", "ref", "value", "source", "name",
                          "bus_port"):
            val = getattr(self, fieldname)
            if val is not None:
                out[fieldname] = val
        if self.base is not None:
            out["base"] = f"0x{self.base:08x}"
        if self.reason:
            out["reason"] = self.reason
        return out

    def describe(self) -> str:
        if self.kind == "remove":
            return f"remove {self.instance}"
        if self.kind == "remove_port":
            return f"remove top-level pin {self.port}"
        if self.kind == "tie":
            return f"tie {self.ref} to {self.value}"
        if self.kind == "clone":
            where = f" onto {self.bus_port}" if self.bus_port else ""
            return f"clone {self.source} as {self.name}{where}"
        return f"readdress {self.ref} to 0x{self.base:08x}"


@dataclass
class EditResult:
    design: Design
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _touches(ref: Ref, instance: str) -> bool:
    return ref.instance == instance


def _is_top(ref: Ref, port: str) -> bool:
    return ref.instance is None and ref.port == port


def _same_target(a: Ref, b: Ref) -> bool:
    """Same instance and port, ignoring any bit range."""
    return a.instance == b.instance and a.port == b.port


def _rename(ref: Ref, old: str, new: str) -> Ref:
    if ref.instance != old:
        return ref
    return Ref(instance=new, port=ref.port, bits=ref.bits)


# ---------------------------------------------------------------------------
# The edits
# ---------------------------------------------------------------------------

def _remove_instance(design: Design, name: str, notes: list[str]) -> None:
    if design.instance(name) is None:
        raise EditError(
            f"cannot remove {name!r}: no such instance in {design.name}"
        )
    before = (len(design.connections) + len(design.bus_connections)
              + len(design.addresses) + len(design.tie_offs))

    design.instances = [i for i in design.instances if i.name != name]
    design.connections = [
        c for c in design.connections
        if not (_touches(c.left, name) or _touches(c.right, name))
    ]
    design.bus_connections = [
        c for c in design.bus_connections
        if not (_touches(c.left, name) or _touches(c.right, name))
    ]
    design.addresses = [a for a in design.addresses if not _touches(a.ref, name)]
    design.tie_offs = [t for t in design.tie_offs if not _touches(t.ref, name)]

    after = (len(design.connections) + len(design.bus_connections)
             + len(design.addresses) + len(design.tie_offs))
    notes.append(f"removed {name} and {before - after} lines that mentioned it")


def _remove_port(design: Design, name: str, notes: list[str]) -> None:
    is_pin = design.port(name) is not None
    is_bus = design.bus_port(name) is not None
    if not (is_pin or is_bus):
        raise EditError(
            f"cannot remove top-level port {name!r}: {design.name} has no such port"
        )

    design.ports = [p for p in design.ports if p.name != name]
    design.bus_ports = [b for b in design.bus_ports if b.name != name]
    design.connections = [
        c for c in design.connections
        if not (_is_top(c.left, name) or _is_top(c.right, name))
    ]
    design.bus_connections = [
        c for c in design.bus_connections
        if not (_is_top(c.left, name) or _is_top(c.right, name))
    ]
    notes.append(f"removed top-level port {name}")


def _tie(design: Design, ref_text: str, value: str, notes: list[str]) -> None:
    ref = parse_ref(ref_text)
    if ref.instance is not None and design.instance(ref.instance) is None:
        raise EditError(
            f"cannot tie {ref_text}: no instance named {ref.instance!r}"
        )
    # Replacing an existing tie on the same target is fine; two ties on one
    # port would be a double driver.
    design.tie_offs = [t for t in design.tie_offs if not _same_target(t.ref, ref)]
    design.tie_offs.append(TieOff(ref, value))
    notes.append(f"tied {ref_text} to {value}")


def _readdress(design: Design, ref_text: str, base: int, notes: list[str]) -> None:
    ref = parse_ref(ref_text)
    for address in design.addresses:
        if _same_target(address.ref, ref):
            old = address.base
            address.base = base
            notes.append(
                f"moved {ref_text} from 0x{old:08x} to 0x{base:08x}"
            )
            return
    raise EditError(
        f"cannot readdress {ref_text}: it has no address in {design.name}"
    )


def _clone(design: Design, source: str, new_name: str,
           bus_port: str | None, base: int | None, notes: list[str]) -> None:
    original = design.instance(source)
    if original is None:
        raise EditError(f"cannot clone {source!r}: no such instance")
    if design.instance(new_name) is not None:
        raise EditError(
            f"cannot clone to {new_name!r}: an instance by that name already exists"
        )

    design.instances.append(Instance(new_name, original.ip))

    # Copy every plain connection the original had.
    copied = 0
    for conn in list(design.connections):
        if _touches(conn.left, source) or _touches(conn.right, source):
            new_conn = copy.deepcopy(conn)
            new_conn.left = _rename(new_conn.left, source, new_name)
            new_conn.right = _rename(new_conn.right, source, new_name)
            design.connections.append(new_conn)
            copied += 1

    # Copy its bus connections. If the caller named a free bus port, the clone
    # hangs off that one instead of sharing the original's.
    target = parse_ref(bus_port) if bus_port else None
    for conn in list(design.bus_connections):
        left_is_source = _touches(conn.left, source)
        right_is_source = _touches(conn.right, source)
        if not (left_is_source or right_is_source):
            continue
        new_conn = copy.deepcopy(conn)
        new_conn.left = _rename(new_conn.left, source, new_name)
        new_conn.right = _rename(new_conn.right, source, new_name)
        if target is not None:
            # Whichever end is NOT the clone gets repointed at the free port.
            if left_is_source:
                new_conn.right = target
            else:
                new_conn.left = target
        design.bus_connections.append(new_conn)
        copied += 1

    # Copy its tie-offs.
    for tie in list(design.tie_offs):
        if _touches(tie.ref, source):
            design.tie_offs.append(
                TieOff(_rename(tie.ref, source, new_name), tie.value)
            )
            copied += 1

    # Copy its address, at the new base if one was given.
    for address in list(design.addresses):
        if _touches(address.ref, source):
            new_base = base if base is not None else address.base
            design.addresses.append(
                Address(_rename(address.ref, source, new_name),
                        new_base, address.size)
            )
            copied += 1

    # A free bus port carries placeholder tie-offs on its response inputs.
    # Something real answers there now, so those have to go.
    if target is not None:
        dropped = [t for t in design.tie_offs
                   if t.ref.instance == target.instance
                   and t.ref.port.startswith(target.port + "_")]
        if dropped:
            design.tie_offs = [t for t in design.tie_offs if t not in dropped]
            notes.append(
                f"dropped {len(dropped)} placeholder tie-offs on {bus_port}"
            )

    notes.append(f"cloned {source} as {new_name}, copying {copied} lines")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def apply_edits(parent: Design, edits: list[Edit], new_name: str) -> EditResult:
    """
    Apply edits to a copy of the parent and return the derivative.

    The parent is never modified. Edits are applied in the order given, so a
    later edit sees the result of an earlier one.
    """
    design = copy.deepcopy(parent)
    design.name = new_name
    notes: list[str] = []

    for position, edit in enumerate(edits, start=1):
        try:
            if edit.kind == "remove":
                _remove_instance(design, edit.instance, notes)
            elif edit.kind == "remove_port":
                _remove_port(design, edit.port, notes)
            elif edit.kind == "tie":
                _tie(design, edit.ref, edit.value, notes)
            elif edit.kind == "readdress":
                _readdress(design, edit.ref, edit.base, notes)
            elif edit.kind == "clone":
                _clone(design, edit.source, edit.name,
                       edit.bus_port, edit.base, notes)
        except EditError as err:
            raise EditError(f"edit {position} ({edit.describe()}): {err}") from None

    return EditResult(design=design, notes=notes)
