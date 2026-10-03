# DerivGen — notes for future sessions

Read `README.md` first. This file holds the decisions and the rules, not the
description.

## What this is

An open-source sandbox that mimics ST's platform-derivative flow so the
software framework can be validated before porting. Nothing ST-specific lives
here. Porting happens later, by swapping adapters.

## The rules that must not be broken

1. **The model never writes RTL, Tcl, or a port name.** It returns a JSON
   list of edits. Nothing else.
2. **Derive, never invent.** A derivative is an edited copy of the parent.
   Only the five edits in `edits.py` exist. If a request needs anything else,
   refuse with a reason that names the instance and port.
3. **Never connect a port that is not in the IP-XACT.** The checker enforces
   this. The previous version shipped exactly this bug.
4. **Nothing is "generated" until the checker approves it.** `build.py`
   raises rather than emitting a design the checker would have rejected.
5. **Deterministic output.** Same input, byte-identical files. Everything is
   sorted. No timestamps.
6. **No new dependencies** without a clear reason. Standard library only,
   today.

## Architecture, and why

**Model-first, not text-first.** The design lives in plain records
(`design.py`). Tcl is one way of writing it down (`tcl.py`). Edits, checks and
scoring all work on the records, never on text. This is what makes porting
cheap: swap the reader and writer, the middle is untouched.

**`build.py` is isolated on purpose.** It is Magillem's job. At ST it gets
deleted and the real tool reads the same Tcl and the same IP-XACT.

**Retrieval is exact lookup, not embeddings.** Tags and graph neighbourhoods
are exact keys. A dictionary beats cosine similarity here, and the prompt
stays small enough to paste into a chat window — which is the only model
available inside ST.

**The repair loop is deterministic.** The model proposes only what the
instruction asks for. Dependency edits (tie-offs, dropped pins) are worked out
afterwards by `plan.settle()` from the checker's output. Repairs reuse values
the parent already used on the same bus signal rather than picking constants
— that is `plan._remembered_tie`, and it is why removing the UART ties
`pready` to `1'b1` and not to zero.

## Where the bodies are buried

- The IP library RTL is **deliberately trivial**. Port lists are what matter;
  behaviour does not. Do not spend effort making the IPs realistic.
- `tools/package_ips.py` parses Verilog with a regex. That is only safe
  because the library files are written in one regular style, and
  `tests/test_library.py` cross-checks the committed XML against the RTL. If
  an IP's ports change, re-run the tool or that test fails.
- `Bus_Fabric_IP` has four master ports and the parent uses three. The spare
  is what scale-up clones into. Do not "tidy" it away.
- The parent ties `data_agg0/alert_bus[31:2]` because only two of the
  aggregator's 32 alert inputs are used.
- Three bench paraphrases fail on purpose (see README). They are the baseline
  the LLM planner has to beat. Do not patch the synonym table to make the
  number look better.

## Testing

```
pytest -q                    # 79 tests
python -m derivgen bench     # the benchmark
```

Oracle mode must stay at 100%. If it drops, the edit engine or the scorer
broke, and no planner result means anything until it is fixed.

Goldens in `memory/derivatives/*/child.tcl` marked `"golden_source":
"hand-written"` were written independently of the code, so they are a real
check on `apply_edits`. Keep at least two that way.

## Working style the user asked for

- Hardware engineer, not a software engineer. Plain words; explain software
  terms on first use.
- Simplicity is the guardrail. No abstraction "for later". A plain function
  with an `if` beats a class hierarchy.
- Small files, short functions, comments that say *why*.
- Stop at the end of a step, say what was built and how to run it, wait.
- Push back when something is wrong rather than quietly going along.
