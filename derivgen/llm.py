"""
Talking to a language model, and the prompt we send it.

Three things live here:

  build_prompt()   assembles instruction + retrieved slice + past examples
  parse_response() pulls the edit list out of whatever the model replied
  backends         where the prompt goes and the reply comes from

The prompt is deliberately short. The model is shown four instances and their
neighbours, not the whole platform, because the model that has to run this at
ST is a chat window with no API and no patience. Everything the model would
otherwise have to work out -- what depends on what, what breaks if this goes
-- is already in the prompt, computed from the design.

Backends:
  ManualBackend  writes the prompt to a file, waits for the reply to be
                 pasted back. This is the one that works with a chat-only
                 internal model.
  MockBackend    replies from a cache on disk, keyed by the hash of the
                 prompt, so tests and benchmarks run offline and repeatably.
"""

import hashlib
import json
import re
from pathlib import Path

from .design import Design
from .library import Ip
from .retrieve import PastDerivative, describe_slice

# What we tell the model it may do. Kept in step with edits.KINDS.
RULES = """\
You are planning a derivative of an existing hardware platform.

You may only edit the parent. You may NOT invent new structure. Reply with a
JSON list of edits, using exactly these five forms:

  {"edit": "remove",      "instance": "<name>",  "reason": "..."}
  {"edit": "remove_port",  "port": "<pin>",      "reason": "..."}
  {"edit": "tie",          "ref": "<inst>/<port>", "value": "1'b0", "reason": "..."}
  {"edit": "clone",        "source": "<inst>", "name": "<new inst>",
                           "bus_port": "<inst>/<iface>", "base": "0x...", "reason": "..."}
  {"edit": "readdress",    "ref": "<inst>/<iface>", "base": "0x...", "reason": "..."}

Rules:
- Only remove instances that exist in the parent.
- clone may only copy an instance the parent already has.
- Do not add tie or remove_port edits for dependencies; they are worked out
  for you after you reply. Only list the changes the instruction asks for.
- If the instruction cannot be done with these edits, reply exactly:
  {"refused": "<short reason>"}

Reply with JSON only. No explanation outside the JSON.\
"""


def build_prompt(instruction: str, design: Design, library: dict[str, Ip],
                 focus: list[str], examples: list[PastDerivative],
                 problems: list[str] | None = None) -> str:
    """
    Assemble the prompt.

    `problems` is set on a repair round: the checker's complaints about the
    model's previous answer, fed back so it can try again.
    """
    parts = [RULES, "", f"Parent platform: {design.name}", ""]

    if focus:
        parts.append(describe_slice(design, library, focus))
    else:
        # Nothing matched by tag, so show the model what there is to pick from.
        parts.append("Instances in the parent:")
        for inst in sorted(design.instances, key=lambda i: i.name):
            tags = sorted(library[inst.ip].tags) if inst.ip in library else []
            parts.append(f"  {inst.name}  (ip={inst.ip}, tags={','.join(tags) or 'none'})")
    parts.append("")

    if examples:
        parts.append("Similar derivatives done before, for reference:")
        for example in examples:
            parts.append(f'  instruction: "{example.instruction}"')
            parts.append(f"  edits: {json.dumps(example.edits)}")
        parts.append("")

    if problems:
        parts.append("Your previous answer left these problems:")
        parts.extend(f"  {p}" for p in problems)
        parts.append("Fix them and reply with the corrected full edit list.")
        parts.append("")

    parts.append(f'Instruction: "{instruction}"')
    parts.append("")
    parts.append("JSON:")
    return "\n".join(parts)


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


class LlmError(Exception):
    """Raised when a reply cannot be understood."""


def parse_response(text: str) -> tuple[list[dict], str | None]:
    """
    Pull the edit list out of a reply.

    Returns (edits, refusal). Chat models like to wrap JSON in prose and code
    fences, so we find the outermost JSON value rather than insisting the
    whole reply is JSON.
    """
    cleaned = re.sub(r"^\s*```(?:json)?|```\s*$", "", text.strip(),
                     flags=re.MULTILINE)

    data = None
    for opener, closer in (("[", "]"), ("{", "}")):
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                data = json.loads(cleaned[start:end + 1])
                break
            except json.JSONDecodeError:
                continue

    if data is None:
        raise LlmError(f"no JSON found in the reply: {text[:200]!r}")

    if isinstance(data, dict):
        if "refused" in data:
            return [], str(data["refused"])
        if "edits" in data:
            data = data["edits"]
        else:
            data = [data]

    if not isinstance(data, list):
        raise LlmError(f"expected a list of edits, got {type(data).__name__}")
    return data, None


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------

class MockBackend:
    """
    Replies from a folder of cached answers, keyed by prompt hash.

    A missing answer is an error, not a guess -- a benchmark that silently
    invented replies would be worthless.
    """

    name = "mock"

    def __init__(self, cache_dir):
        self.cache_dir = Path(cache_dir)

    def complete(self, prompt: str) -> str:
        path = self.cache_dir / f"{prompt_hash(prompt)}.txt"
        if not path.exists():
            raise LlmError(
                f"no cached reply for this prompt (hash {prompt_hash(prompt)}).\n"
                f"Run with --llm manual once to record one into {self.cache_dir}."
            )
        return path.read_text(encoding="utf-8")


class ManualBackend:
    """
    Copy-and-paste mode: for a chat-only model with no API.

    Writes the prompt to a file, tells you to paste it into the chat, and
    waits for the reply. Replies are cached, so a benchmark can be replayed
    offline afterwards with MockBackend.
    """

    name = "manual"

    def __init__(self, cache_dir, work_dir=None):
        self.cache_dir = Path(cache_dir)
        self.work_dir = Path(work_dir) if work_dir else self.cache_dir

    def complete(self, prompt: str) -> str:
        digest = prompt_hash(prompt)
        cached = self.cache_dir / f"{digest}.txt"
        if cached.exists():
            return cached.read_text(encoding="utf-8")

        self.work_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = self.work_dir / f"prompt_{digest}.txt"
        prompt_path.write_text(prompt, encoding="utf-8")

        print()
        print("=" * 70)
        print(f"  Prompt written to {prompt_path}")
        print("  Paste it into the chat, then paste the reply below.")
        print("  Finish with a line containing only:  END")
        print("=" * 70)

        lines: list[str] = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip() == "END":
                break
            lines.append(line)
        reply = "\n".join(lines)

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cached.write_text(reply, encoding="utf-8")
        print(f"  reply cached as {cached.name}")
        return reply


def make_backend(kind: str, cache_dir, work_dir=None):
    if kind == "mock":
        return MockBackend(cache_dir)
    if kind == "manual":
        return ManualBackend(cache_dir, work_dir)
    raise LlmError(f"unknown backend {kind!r}; use 'mock' or 'manual'")
