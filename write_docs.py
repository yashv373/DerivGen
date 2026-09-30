import os
import datetime

os.makedirs('docs', exist_ok=True)

with open('docs/learnings.md', 'w', encoding='utf-8') as f:
    f.write("""# Learnings Log

### [2026-09-30] Migen vs LiteX for Structural Assembly
* **Decision:** Recreate the Commercial EDA TCL flow using LiteX `SoCCore` to act as the EDA assembly engine.
* **Impact (Negative):** The script crashed with `ValueError: Cannot extract CSR name from code`. LiteX uses `migen` under the hood, which relies on Python's `inspect` module to auto-name registers based on variable assignments. Because our ML framework dynamically loads assembly files (like `instances.py`), the inspector loses the stack frame and crashes.
* **Fix:** We realized Commercial EDA's primary job isn't building CPUs or enforcing bus protocols—it is purely **Structural RTL Stitching** (instantiating modules and connecting wires). We stripped out the heavy LiteX `SoCCore` and replaced it with a bare `migen.Module`. Migen handles structural Verilog generation flawlessly, making it the perfect generic replacement for Commercial EDA without the opinionated CPU baggage of LiteX.
""")

with open('docs/how.md', 'w', encoding='utf-8') as f:
    f.write("""# How It Works

This repository acts as an open-source clone of commercial IP assembly flows (like Commercial Commercial EDA). 

### The Assembly Engine
Instead of a proprietary EDA tool, we use **Migen** (a Python-based hardware builder). Migen acts as the compiler. It reads instructions on what IPs to instantiate and how to wire them, and outputs a single `.v` SystemVerilog wrapper.

### The Modular Scripts
We broke the assembly process down into 5 modular scripts, mirroring traditional TCL workflows:
1. `instances.py`: Declares which IP blocks exist in the chip.
2. `bus_interfaces.py`: (Reserved) For connecting AXI/APB buses.
3. `adhoc_connections.py`: Wires point-to-point signals (like interrupts).
4. `tie_offs.py`: Hardcodes unconnected pins to `0` or `1` (GND/VCC).
5. `export_ports.py`: Routes internal signals to the top-level chip pins.

### The ML Integration
In the future, the Machine Learning model will not write raw Verilog. It will simply generate these 5 Python scripts. The Migen engine will then automatically compile them into the final Verilog wrapper, ensuring the syntax is always perfect.
""")

with open('docs/what.md', 'w', encoding='utf-8') as f:
    f.write("""# What Is DerivGen?

**DerivGen** is an ML-assisted IP packaging and SoC assembly framework for derivative RTL designs.

### Why is this helpful?
Building a derivative chip (scaling a flagship chip down for IoT, for example) requires manually removing IPs, tracking down broken dependencies, and editing thousands of lines of integration scripts. It is slow and prone to human error. DerivGen automates this.

### The Infrastructure
* **FuseSoC:** Acts as the package manager (replacing internal tools like Recital). It packages raw Verilog IPs.
* **Migen / LiteX:** Acts as the assembly engine (replacing tools like Commercial EDA). It stitches the IPs together and outputs the final RTL wrapper.

### What we are introducing through ML
We are introducing an AI architect. The ML model will take natural language commands (e.g., *"Remove the crypto core"*), mathematically resolve the hardware dependencies using Association Rules, and auto-generate the structural configuration scripts for the EDA tools.
""")

date_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
with open('docs/changelog.md', 'w', encoding='utf-8') as f:
    f.write(f"""# Changelog

## [v0.1.0] - {date_str}
### Added
* Initial EDA Framework directory structure (`eda_framework/`).
* Dummy Verilog IPs (`dummy_crypto.v`, `dummy_uart.v`) for testing packaging.
* Modular assembly scripts (`instances.py`, `bus_interfaces.py`, `adhoc_connections.py`, `tie_offs.py`, `export_ports.py`).
* Replaced LiteX `SoCCore` with `migen.Module` in `assemble_commercial_eda.py` to fix dynamic instantiation crashes and focus strictly on structural RTL stitching.
* Documentation folder with `learnings.md`, `what.md`, `how.md`, and `changelog.md`.
""")

print("Docs generated successfully.")
