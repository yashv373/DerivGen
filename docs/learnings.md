# Learnings Log

### [2026-09-30] Migen vs LiteX for Structural Assembly
* **Decision:** Recreate the Commercial EDA TCL flow using LiteX `SoCCore` to act as the EDA assembly engine.
* **Impact (Negative):** The script crashed with `ValueError: Cannot extract CSR name from code`. LiteX uses `migen` under the hood, which relies on Python's `inspect` module to auto-name registers based on variable assignments. Because our ML framework dynamically loads assembly files (like `instances.py`), the inspector loses the stack frame and crashes.
* **Fix:** We realized Commercial EDA's primary job isn't building CPUs or enforcing bus protocols—it is purely **Structural RTL Stitching** (instantiating modules and connecting wires). We stripped out the heavy LiteX `SoCCore` and replaced it with a bare `migen.Module`. Migen handles structural Verilog generation flawlessly, making it the perfect generic replacement for Commercial EDA without the opinionated CPU baggage of LiteX.
