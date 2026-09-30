# What Is DerivGen?

**DerivGen** is an ML-assisted IP packaging and SoC assembly framework for derivative RTL designs.

### Why is this helpful?
Building a derivative chip (scaling a flagship chip down for IoT, for example) requires manually removing IPs, tracking down broken dependencies, and editing thousands of lines of integration scripts. It is slow and prone to human error. DerivGen automates this.

### The Infrastructure
* **FuseSoC:** Acts as the package manager (replacing internal tools like Recital). It packages raw Verilog IPs.
* **Migen / LiteX:** Acts as the assembly engine (replacing tools like Commercial EDA). It stitches the IPs together and outputs the final RTL wrapper.

### What we are introducing through ML
We are introducing an AI architect. The ML model will take natural language commands (e.g., *"Remove the crypto core"*), mathematically resolve the hardware dependencies using Association Rules, and auto-generate the structural configuration scripts for the EDA tools.
