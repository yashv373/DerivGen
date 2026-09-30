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
