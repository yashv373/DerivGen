# How It Works

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
