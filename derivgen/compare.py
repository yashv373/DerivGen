"""
Comparing a generated derivative against a hand-written golden one.

The comparison is on the design, not the text: two scripts that say the same
thing in a different order score 100%. `connect a b` and `connect b a` are
the same wire, so each connection is normalised before comparing.

Six things are scored separately, because knowing *which* part went wrong is
the whole point of a benchmark:

  pins, buses, instances, connections, addresses, tie-offs
"""

from dataclasses import dataclass, field

from .design import Design


@dataclass
class Score:
    """How one category did."""
    name: str
    expected: set = field(default_factory=set)
    produced: set = field(default_factory=set)

    @property
    def hits(self) -> set:
        return self.expected & self.produced

    @property
    def missing(self) -> set:
        """In the golden, absent from ours."""
        return self.expected - self.produced

    @property
    def extra(self) -> set:
        """In ours, absent from the golden."""
        return self.produced - self.expected

    @property
    def precision(self) -> float:
        if not self.produced:
            return 1.0 if not self.expected else 0.0
        return len(self.hits) / len(self.produced)

    @property
    def recall(self) -> float:
        if not self.expected:
            return 1.0 if not self.produced else 0.0
        return len(self.hits) / len(self.expected)

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def perfect(self) -> bool:
        return not self.missing and not self.extra


@dataclass
class Comparison:
    scores: list[Score] = field(default_factory=list)

    @property
    def perfect(self) -> bool:
        return all(s.perfect for s in self.scores)

    @property
    def overall_f1(self) -> float:
        """Average F1 across categories that have anything in them."""
        used = [s for s in self.scores if s.expected or s.produced]
        return sum(s.f1 for s in used) / len(used) if used else 1.0

    def score(self, name: str) -> Score:
        return next(s for s in self.scores if s.name == name)

    def report(self) -> str:
        heading = (f"  {'category':<14}{'golden':>7}{'ours':>6}{'hit':>5}"
                   f"{'miss':>6}{'extra':>7}{'F1':>7}")
        lines = [heading, "  " + "-" * 52]
        for s in self.scores:
            lines.append(
                f"  {s.name:<14}{len(s.expected):>7}{len(s.produced):>6}"
                f"{len(s.hits):>5}{len(s.missing):>6}{len(s.extra):>7}"
                f"{s.f1:>7.3f}"
            )
        lines.append("  " + "-" * 52)
        verdict = "MATCH" if self.perfect else "DIFFERS"
        lines.append(f"  overall F1 {self.overall_f1:.3f}   {verdict}")

        for s in self.scores:
            for item in sorted(s.missing):
                lines.append(f"    missing from ours : {s.name[:-1]} {item}")
            for item in sorted(s.extra):
                lines.append(f"    not in golden     : {s.name[:-1]} {item}")
        return "\n".join(lines)


def _wire(left, right) -> tuple[str, str]:
    """A connection with its two ends in a fixed order, so a/b == b/a."""
    a, b = str(left), str(right)
    return (a, b) if a <= b else (b, a)


def compare(produced: Design, golden: Design) -> Comparison:
    """Score a generated design against a golden one."""
    return Comparison(scores=[
        Score("pins",
              {(p.name, p.direction, p.width) for p in golden.ports},
              {(p.name, p.direction, p.width) for p in produced.ports}),
        Score("buses",
              {(b.name, b.bus_type, b.role) for b in golden.bus_ports},
              {(b.name, b.bus_type, b.role) for b in produced.bus_ports}),
        Score("instances",
              {(i.name, i.ip) for i in golden.instances},
              {(i.name, i.ip) for i in produced.instances}),
        Score("connections",
              {_wire(c.left, c.right) for c in golden.connections}
              | {_wire(c.left, c.right) for c in golden.bus_connections},
              {_wire(c.left, c.right) for c in produced.connections}
              | {_wire(c.left, c.right) for c in produced.bus_connections}),
        Score("addresses",
              {(str(a.ref), a.base, a.size) for a in golden.addresses},
              {(str(a.ref), a.base, a.size) for a in produced.addresses}),
        Score("tie-offs",
              {(str(t.ref), t.value) for t in golden.tie_offs},
              {(str(t.ref), t.value) for t in produced.tie_offs}),
    ])
