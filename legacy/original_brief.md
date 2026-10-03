# DerivGen — Project Brief for Claude Code

Read this entire file before doing anything. It explains who I am, the real-world
problem, what I've already tried, the constraints that shape every design decision,
and how I want you to work.

---

## 1. Who I am

- Third-year B.Tech VLSI undergrad, currently a Digital IP Platform Design intern at
  STMicroelectronics.
- Strong on RTL, SoC integration, EDA flows. Weak on ML: one introductory course
  (mostly linear regression), plus small regression models for power and IR-drop
  prediction. I am not a data scientist.
- So: be precise with hardware terms, but explain every ML/LLM/data decision in plain
  language, including why it beats the simpler alternative.

## 2. The real problem (at ST)

This is for ST's internal hackathon (Iris). My team does **platform design**.

**What a platform is:** an abstraction layer between IP and SoC. A platform is a group
of instances (instantiations of Verilog modules / IPs, possibly the same module many
times) assembled into one block that does a particular job well. A **product**
(chipset) contains multiple platforms. ST has 10–12 shipped products across families
(e.g. Stellar and others), so there are potentially hundreds of platforms of
real, hand-built, silicon-verified history.

**The internal flow today:**
1. Each IP is packaged with IP-XACT.
2. A Tcl-based flow (Arteris Magillem-style) instantiates IPs, creates bus and port
   connections, and wires everything.
3. This generates the platform's top-level Verilog wrapper, where each IP is
   instantiated by IP name and the instance name assigned by the platform team.

**What my manager wants:** a natural-language request such as:
- "Give me a derivative of platform XYZ without the safety features"
  (safety = lockstep/redundant structures, comparators, monitors, ECC, etc.)
- "Remove the RAM controller and the RAM"
- "Remove X, keep Y"

...should produce a correct derivative platform **with all dependencies resolved**. The
output could be Tcl that the existing flow (Magillem) consumes, or the wrapper +
IP-XACT directly. Tcl is likely the most useful output inside ST.

**Three kinds of derivatives must be supported:**
1. **Direct derivative**: near one-to-one copy of the parent with modifications
   (like iPhone 14 → 15).
2. **Scale-down / child**: a subsystem carved from a parent (e.g. 20 of 40 IPs that do
   one job).
3. **Scale-up**: a bigger platform built from a smaller one (adding IPs / instances).

**Key insight:** this is NOT novel architecture generation. Every derivative reuses
existing, verified IPs and patterns from the parent and from past derivative pairs.
The system needs to learn and reuse those patterns, not invent hardware.

## 3. Hard constraints (these drive the architecture)

1. **No internal data or IP leaves ST.** This repo is an **open-source sandbox** that
   replicates ST's flow using open-source tools (FuseSoC, Migen, Yosys, Verilator,
   open-source IPs). Nothing ST-specific (names, IPs, file formats copied verbatim)
   goes in this repo. Design everything so it can be **ported** into ST later by
   swapping adapters and the LLM backend.
2. **Inside ST I only have weak, chat-only LLMs**: Microsoft Copilot (GPT-5.6-ThinkDeeper)
   and an internal "ST-ChatGPT". No Claude, no GitHub Copilot, no agentic tools, and
   possibly **no API access** at all. Therefore:
   - The LLM layer must be **backend-agnostic** (see §6).
   - It must work with a weaker model: small, focused prompts; heavy lifting done by
     deterministic code; the LLM only makes decisions it's actually good at.
   - It must support a **manual copy-paste mode**: the tool builds the full prompt,
     I paste it into the chat UI, paste the answer back, and the tool validates it.
3. **Internal data is messy and multi-format**: some teams produce CSV, my team uses a
   pickle-based format, plus IP-XACT XML and Tcl scripts. Manual feature engineering
   over millions of instances is not realistic for me.
4. **My seniors' guidance: build something that works, not a super-smart AI.**
   A reliable, demoable end-to-end pipeline beats a clever model. When in doubt,
   choose the simpler, more deterministic option.

## 4. What I've already tried (and what I learned)

- **Phase A — Classical ML:** Random Forest (keep/remove per IP) and Apriori
  (association rules) on synthetic tabular SoC configurations. It proved that keep/remove
  decisions are statistically predictable, but:
  - SoCs are graphs, not tables; tabular features lose the connectivity.
  - It can't handle natural-language instructions natively.
  - It needs retraining whenever an IP is added to the library.
  - Overfitting from small datasets was a recurring problem in my earlier experiments.
  Notebook: `notebooks/` (exported from Colab).
- **Phase B — Open-source flow:** I built a first version of the framework with
  FuseSoC + Migen, with most of the code generated by Google Antigravity from my
  instructions. It works partially but output quality was mediocre. **Treat the
  existing code as a draft: keep what's solid, rewrite what isn't.**
- **Pivot — RAG:** I found that ST's verification team built a RAG-based system on
  ST-ChatGPT to generate new test cases for derivative-design testbenches. That shows
  RAG + an internal LLM is practical and accepted inside ST, so DerivGen now follows
  the same approach.

## 5. Target architecture

**The single most important rule: the LLM never writes RTL or Tcl.** It only decides
*what* changes, as JSON. Deterministic code does everything else.

```
NL instruction
     │
     ▼
[1] Retrieval (deterministic)
     • Parent platform graph (from IP-XACT → canonical model → networkx)
     • Similar past derivative pairs (parent → child + the instruction that produced it)
       used as few-shot examples
     │
     ▼
[2] LLM planner (backend-agnostic, small prompts)
     • Initial extraction: identify target IPs/instances
     • Self-questioning: ask the graph tools "what depends on X?"
     • Emit a JSON derivative config (schema-validated)
     │
     ▼
[3] Dependency checker (deterministic)
     • Dangling inputs, orphaned bus slaves, broken clocks/resets, address-map gaps
     • If errors → feed them back to the LLM → repeat (max N rounds)
     │
     ▼
[4] Emitters (deterministic, pluggable)
     • Verilog top wrapper (Migen) + IEEE 1685 IP-XACT design XML  ← sandbox
     • Tcl script mimicking a Magillem-style integration flow         ← portable to ST
     │
     ▼
[5] Validation
     • Verilator lint + Yosys elaboration
     • Structural diff vs hand-built golden child → accuracy metrics
```

**Why this answers the "millions of instances, feature engineering" problem:** we don't
hand-engineer ML features. We write **adapters** that normalize each data format into
one canonical graph model (instances, ports, bus interfaces, connections, parameters,
address map). Retrieval and validation run on that graph. Historical derivative pairs
are used as **retrieved examples**, not as training rows. Explain this reasoning to me
clearly in the README; I need to defend it to my team.

## 6. LLM backend abstraction

One interface, e.g. `LLMBackend.complete(messages) -> str`, with implementations:
- `AnthropicBackend`: for development here (model and key via env vars).
- `OpenAICompatibleBackend`: generic endpoint/URL, in case ST exposes an API.
- `ManualBackend`: writes the prompt to a file and prints it, waits for me to paste
  the response, then continues. This is the most important one for using it at ST.
- `MockBackend`: returns cached or scripted responses for tests and CI.

Also:
- Cache responses by prompt hash so bench runs are reproducible.
- Keep prompts short and structured. Assume the production model is weaker than you:
  give it the relevant subgraph, not the whole platform; ask one question at a time
  in the self-questioning loop.
- Keep a `RuleBasedPlanner` baseline (keyword → tag lookup, e.g. IPs tagged `safety`)
  that runs with no LLM at all. It's the fallback and the baseline to beat.

## 7. Canonical data model & adapters

- Define a canonical model (pydantic): `IP`, `Port`, `BusInterface`, `Instance`,
  `Connection`, `Platform`, `Product`, `DerivativePair` (parent, child, instruction,
  derivative_type ∈ {direct, scale_down, scale_up}).
- Each IP and instance carries **tags** (e.g. `safety`, `memory`, `interconnect`,
  `debug`, `clock_reset`). Tags are how "remove safety features" becomes concrete;
  they come from IP-XACT vendor extensions or a tags file, not from the LLM.
- Adapters: `IpxactAdapter` (implemented now), plus stubbed `CsvAdapter`,
  `PickleAdapter`, `TclAdapter` with clear docstrings describing what I'd need to fill
  in at ST. Each adapter outputs the canonical model; nothing downstream knows
  which format the data came from.

## 8. Sandbox dataset (to replace ST's history)

Build a small open-source "product family" so the system has real history to retrieve:
- One base platform (STA-SoC): RISC-V core (e.g. PicoRV32), AXI4-Lite interconnect,
  AXI4-Lite→APB bridge, SRAM + controller, UART, GPIO, timer, and a safety island
  (lockstep shadow core, lockstep comparator, monitor FSM, ECC).
- 6–10 hand-specified derivatives covering all three derivative types, each stored as
  a `DerivativePair` with its NL instruction and a golden child wrapper.
- Propose the specific open-source IPs and their licenses first; wait for my approval
  before adding them. Record sources in `ip_library/MANIFEST.md`.

## 9. Validation & metrics

- Structural (not textual) diff: elaborate both generated and golden wrappers with
  Yosys to JSON netlists and compare instance sets, per-port connections, tie-offs
  and the address map.
- Metrics: instance precision/recall, % correctly connected ports, tie-off accuracy,
  address-map match, lint/synth pass rate, and number of LLM repair rounds needed.
- `derivgen bench` runs all cases and writes `results/<date>_<git-sha>/` with
  generated files, `metrics.json` and a Markdown summary. Results are committed.
- **Oracle mode** (feed the golden JSON configs directly) must score 100%. That proves
  the emitters and diff are correct before any LLM is evaluated.

## 10. Your first task (do this before writing new code)

1. **Audit the existing repo.** For each module: what it does, whether it works, its
   quality, and a keep / refactor / rewrite recommendation. Run whatever tests and
   generation commands exist and report the results honestly.
2. Read `notebooks/` and summarize what the Random Forest / Apriori experiments did.
3. Restate the problem and architecture in your own words, and list ambiguities,
   risks and anything in this brief you think is wrong or over-engineered.
4. Propose a phased plan whose **first milestone is a thin end-to-end demo**:
   one NL instruction ("remove the safety features") → RuleBasedPlanner → JSON →
   dependency check → wrapper + Tcl → lint passes → diff vs golden. Then improve
   each stage.
5. Stop and wait for my approval.

## 11. Engineering standards

- Python 3.11+, type hints, pydantic models, pytest, ruff.
- Deterministic output: same input → byte-identical files.
- Fail loudly with errors naming the instance and port; never silently invent or
  stub connections.
- GitHub Actions CI: install Verilator/Yosys/Icarus, run tests, run the bench with
  `MockBackend`.
- Small commits with clear messages; keep `CHANGELOG.md` updated, and update this file
  when an architectural decision changes.

## 12. How to work with me

- Stop at the end of each phase: summarize what you built, show results, list open
  issues, wait for my go-ahead.
- Explain ML/LLM concepts briefly when you introduce them; I want to learn, not just
  receive code.
- If a simpler approach would work, propose it. "Works reliably" beats "impressive".
- Push back if I'm wrong about something.