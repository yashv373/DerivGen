# What Is DerivGen?

**DerivGen** is an ML-assisted IP packaging and SoC assembly framework for derivative RTL designs.

### Why is this helpful?
Building a derivative chip (scaling a flagship chip down for IoT, for example) requires manually removing IPs, tracking down broken dependencies, and editing thousands of lines of integration scripts. It is slow and prone to human error. DerivGen automates this.

### The Infrastructure
* **FuseSoC:** Acts as the package manager. It packages raw Verilog IPs.
* **Migen / LiteX:** Acts as the assembly engine (replacing tools like Commercial EDA). It stitches the IPs together and outputs the final RTL wrapper.

### What we are introducing through ML
We are introducing an AI architect. The ML model will take natural language commands (e.g., *"Remove the crypto core"*), mathematically resolve the hardware dependencies using Association Rules, and auto-generate the structural configuration scripts for the EDA tools.

### Standards Compliance
DerivGen generates IEEE 1685-2009 (IP-XACT) compliant XML for every IP and every SoC assembly. This means the metadata is not locked to any single tool. The same XML that our framework produces can be imported into Kactus2, Xilinx Vivado, Cadence, or any other IP-XACT compliant EDA tool.
