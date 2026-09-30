# Learnings Log

### [2026-09-30] Migen vs LiteX for Structural Assembly
* **Decision:** Recreate the Commercial EDA TCL flow using LiteX `SoCCore` to act as the EDA assembly engine.
* **Impact (Negative):** The script crashed with `ValueError: Cannot extract CSR name from code`. LiteX uses `migen` under the hood, which relies on Python's `inspect` module to auto-name registers based on variable assignments. Because our ML framework dynamically loads assembly files (like `instances.py`), the inspector loses the stack frame and crashes.
* **Fix:** We realized Commercial EDA's primary job isn't building CPUs or enforcing bus protocols—it is purely **Structural RTL Stitching** (instantiating modules and connecting wires). We stripped out the heavy LiteX `SoCCore` and replaced it with a bare `migen.Module`. Migen handles structural Verilog generation flawlessly, making it the perfect generic replacement for Commercial EDA without the opinionated CPU baggage of LiteX.

### [2026-09-30 21:10:30] Clock Domain Fix for Pure Migen
* **Decision:** Use ClockSignal()/ResetSignal() inside Instance() port maps for clk/rst routing.
* **Impact (Negative):** First attempt failed. Without an explicit ClockDomain, Migen creates isolated 
eg clk = 0 per instance instead of routing from a shared top-level clock. This would make the chip non-functional.
* **Fix:** Added self.clock_domains.cd_sys = ClockDomain('sys') and exported cd_sys.clk / cd_sys.rst to the top-level IOs. Now all IPs correctly share sys_clk and sys_rst.

### [2026-09-30 21:10:30] Stress Test Suite: All 5 Tests Passed
* **Decision:** Built a 5-level stress test: Baseline (2 IP), Scale (8 IP), Wide Bus (256-bit AXI), Derivative Removal (drop 3 IPs), Structural Diff.
* **Impact (Positive):** Framework handles 1-bit to 256-bit buses, 2 to 8 IP instantiations, ad-hoc cross-wiring between IPs, tie-offs, and derivative IP removal flawlessly.
* **Key finding:** The diff between the 8-IP parent (117 lines) and 5-IP derivative (74 lines) cleanly shows only the removed ip_aes, ip_dma, ip_pwm blocks disappearing. Zero false positives.

### [2026-09-30 21:19:15] IP-XACT IEEE 1685-2009 Integration
* **Decision:** Use Python built-in xml.etree.ElementTree instead of third-party pyEDAA.IPXACT to generate standards-compliant IP-XACT XML.
* **Impact (Positive):** Zero external dependencies. The generator produces clean spirit: namespaced component and design XML that any IEEE 1685-2009 compliant tool can consume.
* **Key learnings:**
  - ET.register_namespace() controls the prefix. Setting xmlns manually on elements causes duplicates that crash minidom.parseString().
  - ET.indent() (Python 3.9+) is far cleaner than minidom.toprettyxml() for pretty-printing.
  - Tie-offs have no native representation in IEEE 1685-2009 design XML. We use spirit:vendorExtensions with a custom derivgen:tieOff element.
  - FuseSoC supports IP-XACT component XML via the component key in .core files, but only for fileset parsing. We generate IP-XACT independently.

### [2026-09-30 21:25:27] Full Manual Demo - End to End Success
* **Decision:** Build a simple but complete SoC (4 gates + MUX + LFSR) to demonstrate the full EDA pipeline.
* **Impact (Positive):** All 6 IPs instantiated cleanly. The generated Verilog wrapper is 63 lines of correct structural RTL with human-readable signal names (a_i, b_i, y_o, and_out, or_out, etc.). No Migen auto-naming corruption.
* **Key insight:** Keeping IPs as pure combinational gates (no bus protocol) made the demo crystal clear. The LFSR is the only sequential element, proving the framework handles both combinational and clocked IPs.
