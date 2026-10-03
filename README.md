# DerivGen

Turn a plain-English instruction into a derivative hardware platform, by
**editing an existing platform** rather than designing a new one.

```
$ python -m derivgen generate "Remove the safety features to make a low-cost variant"

how it decided:
  read the instruction as: remove
  word matched tag 'safety' -> lockstep_cmp0, parity_chk0, parity_gen0, shadow_fsm0
  round 1: checker found 2 problem(s)
    err_lockstep has no driver -> remove the pin
    err_parity has no driver -> remove the pin
  clean after 1 repair round(s)

edits:
  remove lockstep_cmp0
  remove parity_chk0
  remove parity_gen0
  remove shadow_fsm0
  remove top-level pin err_lockstep
  remove top-level pin err_parity

check:
clean: no problems found
```

---

## The idea in one paragraph

A derivative platform is not a new design. It is a verified parent with a few
things taken out, copied or moved. So DerivGen never builds a design: it
produces a **list of edits** to the parent, applies them, and checks the
result. A language model is used for exactly one thing — reading the
instruction and deciding which edits to make. Everything else is ordinary,
deterministic Python, because everything else is where correctness lives.

**The model never writes RTL, Tcl, or a port name.**

## How it works

```
instruction
   │
   ▼
1. retrieve   relevant slice of the parent + similar past derivatives
2. plan       -> a list of edits (rule-based, or a language model)
3. apply      edits -> child design
4. check      dangling inputs, orphan bus slaves, address overlaps
   │          problems go back to step 2 and it tries again
   ▼
5. build      child design -> Tcl script + Verilog wrapper
6. compare    child vs hand-written golden -> score
```

Only five edits exist. If a request cannot be expressed as these, the tool
**refuses** instead of guessing:

| Edit | Meaning |
|---|---|
| `remove` | delete an instance and every line that mentions it |
| `remove_port` | delete a top-level pin that lost its driver |
| `tie` | hold a remaining input at a constant |
| `clone` | copy an instance the parent already has |
| `readdress` | move an instance to a different address |

## Results

```
$ python -m derivgen bench

oracle           3/3   passed, mean F1 1.000
rules            11/14 passed, mean F1 0.856
rules/refuse     8/8   passed, mean F1 1.000
TOTAL 22/25
```

**Oracle mode** replays each case's stored edits and compares against the
hand-written golden. It is 100%, which is the result that matters: it means
the edit engine, the checker and the scorer are sound, so every other number
below is a measurement of the *planner* and not of plumbing bugs.

**rules** is the keyword baseline, with no language model at all. It handles
11 of 14 paraphrases. The three it misses are instructive:

| Instruction | What went wrong |
|---|---|
| "Remove the shadow FSM, the comparator and the parity blocks" | "FSM" matched the `control` tag, so it removed `core_fsm0` too |
| "Take out the UART" | "take out" is not in the synonym table, so the intent was unreadable |
| "Clone the config registers into the spare bus slot" | "bus" matched `interconnect`, so two instances matched and it gave up |

These are left failing on purpose. Each could be patched by adding another
synonym, and that whack-a-mole is exactly why a language model is worth
having. 0.856 is the number it has to beat.

**rules/refuse** checks that bad requests are declined. Moving the UART onto
the register bank's address, removing the interconnect everything hangs off,
and "port this to a 7nm process" are all correctly refused, with a reason.

## Why RAG, and why it is this simple

"Retrieval-augmented generation" here means: look up the few relevant facts,
put them in the prompt, ask the model. It does **not** mean embeddings or a
vector database, and it does not need to.

The keys we search on are exact. "Remove the safety features" resolves to
`tag == "safety"`, which is a dictionary lookup, not a similarity search. The
graph neighbourhood of those instances is read straight off the design. Exact
lookup beats cosine similarity when the keys are exact.

That matters practically: the prompt stays small enough to paste into a chat
window, which is the only kind of model available inside ST.

What goes into the prompt:

```
Instances the instruction is about:
  lockstep_cmp0  (ip=Lockstep_Comparator_IP, tags=lockstep,safety)
      if removed, these lose their driver: err_lockstep (top-level pin)
  shadow_fsm0  (ip=Shadow_FSM_IP, tags=lockstep,safety)
      if removed, these lose their driver: lockstep_cmp0/state_b
  ...
Directly connected to those:
  core_fsm0  (ip=Core_FSM_IP, tags=control)
```

The hard question — *what breaks if I remove this?* — is answered **before**
the model sees it, by reading the design. The model is never asked to work
out dependencies, only to decide intent.

## Memory

```
memory/
├── ip_library/      IP-XACT for each IP (+ tags), and the Verilog
├── platforms/       parent platforms, each one Tcl script
└── derivatives/     past derivatives: instruction, edits, golden child
```

Every verified derivative goes back into `memory/derivatives/`, and later
runs retrieve it as a worked example. The system gets better as it is used,
without retraining anything.

**Honest caveat:** in this sandbox the past derivatives were written by us, so
retrieval can only rediscover our own labels. What is demonstrated here is the
*mechanism*. Its value appears where there are hundreds of real
parent/child pairs with real history behind them.

## Which EDA tools, and why not Migen

| Role | Tool |
|---|---|
| IP packaging | IP-XACT (IEEE 1685-2009), written with Python's stdlib XML |
| Platform description | a 7-command Tcl script — **this is the design** |
| Assembly ("build the wrapper") | `derivgen/build.py`, ours, ~300 lines |
| Lint / elaboration | Verilator / Yosys, in CI only |
| Dependencies | **none** — Python standard library only |

Migen, LiteX and Amaranth are *design* frameworks: they generate logic from
Python. We do not generate logic, we stitch existing IPs together, so they
cost more than they gave. Migen named nets things like
`derivsensesocgolden18`, and — worse — its `Instance` accepted connections to
ports the module did not have, silently. A structural emitter we control is
smaller, readable, and can refuse what it cannot verify.

`build.py` standing alone is the point: in ST's flow that job belongs to
Magillem. Replacing it changes one file. The edits, the checker, the memory
and the scoring do not know it happened.

## The Tcl format

Seven commands, all defined in `derivgen/tcl.py`. To match a different tool's
vocabulary, edit that one file.

```tcl
add_port       clk              in   1
add_port_bus   host_apb         apb  slave
add_instance   sram_ctrl0       SRAM_Ctrl_IP
connect        clk              core_fsm0/clk
connect        thresh_chk_0/alert   data_agg0/alert_bus[0]
connect_bus    bus_fabric0/m0_apb   sram_ctrl0/apb
set_address    sram_ctrl0/apb   0x20000000  0x1000
tie            bus_fabric0/m3_apb_pready  1'b1
```

A reference is `top_pin` or `instance/port`, optionally with `[3:0]`.
Instance and port are kept as separate fields everywhere, for good — a name
is never recovered by splitting on `_`, because port names contain
underscores (`m0_apb_prdata`) and that guess is wrong sooner or later.

## The sandbox platform

`derivsense` — a small sensor-monitoring SoC. 15 instances, 13 IP types.

```
host_apb ──► bus_fabric0 ──┬── m0 ──► sram_ctrl0 ──► sram_macro0
                           ├── m1 ──► reg_bank0
                           ├── m2 ──► uart_tx0
                           └── m3 ──► (spare slot, tied off)

sensor_data_in ──► sensor_fmt_0/1 ──► thresh_chk_0/1 ──► data_agg0 ──► intr

core_fsm0 ──┬──────────────────► lockstep_cmp0 ──► err_lockstep
shadow_fsm0 ┘                                            (safety)
sram data ──► parity_gen0 ──► parity_chk0 ──► err_parity (safety)
```

One bus protocol (APB), one clock, one active-low reset. The spare fabric port
is deliberate: it is what a scale-up derivative clones into.

## Commands

```bash
python -m derivgen generate "Remove the safety features"     # plan + build
python -m derivgen generate "..." --planner llm --llm manual # paste-in mode
python -m derivgen check memory/platforms/derivsense.tcl
python -m derivgen build memory/platforms/derivsense.tcl -o out/parent.v
python -m derivgen bench --json out/bench.json
pytest -q
```

### Using it with a chat-only model

`--llm manual` writes the prompt to a file, you paste it into whatever chat
window you have, paste the reply back, and it carries on. Replies are cached
by prompt hash, so a benchmark can be replayed offline afterwards with
`--llm mock`. There is no API key anywhere.

## Layout

```
derivgen/
  design.py    the platform, as plain records     <- the body
  tcl.py       read and write the script          <- the skin, swap this
  library.py   read IP-XACT
  edits.py     the five edits
  check.py     the dependency checker
  retrieve.py  tag lookup, neighbours, past examples
  plan.py      rule-based planner + LLM planner + repair loop
  llm.py       prompt building, manual and mock backends
  compare.py   scoring against a golden
  build.py     Verilog wrapper          <- Magillem's job, isolated here
  cli.py
memory/        the IP library, platforms and past derivatives
tools/         package_ips.py, run once to package the library
legacy/        the earlier attempt, kept for reference
```

## A note on the earlier version

`legacy/` holds the first attempt. It was replaced rather than fixed, for
reasons worth recording:

- The generated wrapper connected ports like `m0_axi_awvalid` on modules that
  had no such port. Migen's `Instance` does not check, so nothing noticed.
  `tests/test_check.py::test_connection_to_a_port_that_does_not_exist` exists
  because of this.
- 28 of its ~100 instances were wired to freshly created floating signals to
  inflate the instance count.
- `rtl_outputs/top_darjeeling_golden.sv` and `top_darjeeling_ml.sv` were
  byte-identical, so the 100% match they showed meant nothing.

The lesson built into this version: **nothing counts as generated until the
checker has approved it**, and no result counts until it is scored against a
golden somebody wrote by hand.
