# Changelog

## [v0.1.0] - 2026-09-30 20:48:47
### Added
* Initial EDA Framework directory structure (`eda_framework/`).
* Dummy Verilog IPs (`dummy_crypto.v`, `dummy_uart.v`) for testing packaging.
* Modular assembly scripts (`instances.py`, `bus_interfaces.py`, `adhoc_connections.py`, `tie_offs.py`, `export_ports.py`).
* Replaced LiteX `SoCCore` with `migen.Module` in `assemble_commercial_eda.py` to fix dynamic instantiation crashes and focus strictly on structural RTL stitching.
* Documentation folder with `learnings.md`, `what.md`, `how.md`, and `changelog.md`.

## [v0.2.0] - 2026-09-30 21:10:30
### Added
* Stress test suite (eda_framework/stress_test.py) with 5 progressive test scenarios.
* Clock domain fix: All IP instances now share a proper sys_clk / sys_rst from a single ClockDomain.
* Generated test artifacts: 4 Verilog wrappers + 1 structural diff report in uild/stress_test/.
### Fixed
* Migen Instance objects must be added via self.specials += not self.submodules.
* ClockSignal()/ResetSignal() require an explicit ClockDomain to resolve correctly.
* Removed all proprietary tool/company name references from codebase.

## [v0.3.0] - 2026-09-30 21:19:15
### Added
* IP-XACT generator (eda_framework/ipxact_generator.py) producing IEEE 1685-2009 compliant XML.
* Generates per-IP component XMLs with VLNV, ports (with bus widths), views, and fileSets.
* Generates SoC-level design XML with componentInstances, adHocConnections, and vendorExtension tie-offs.
* Uses only Python standard library (xml.etree.ElementTree) -- zero external dependencies.
### Technical
* Component XML includes: vendor/library/name/version (VLNV), model/ports with direction and vector widths, views with envIdentifier, fileSets pointing to Verilog sources.
* Design XML includes: componentInstances with componentRef VLNV, adHocConnections with internalPortReference, vendorExtensions for tie-offs using derivgen namespace.

## [v0.4.0] - 2026-09-30 21:25:27
### Added
* Full end-to-end EDA demo (ull_demo.py) with 6 hand-written Verilog IPs.
* IPs: gate_and, gate_or, gate_nand, gate_xor, mux4to1, lfsr2bit.
* Demo SoC architecture: 4 gates feed a 4:1 MUX, LFSR drives select lines.
* Complete pipeline: IP authoring -> Migen assembly -> Verilog wrapper -> IP-XACT packaging -> FuseSoC .core.
* 11/11 structural verification checks passing.
