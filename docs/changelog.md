# Changelog

## [v0.1.0] - 2026-09-30 20:48:47
### Added
* Initial EDA Framework directory structure (`eda_framework/`).
* Dummy Verilog IPs (`dummy_crypto.v`, `dummy_uart.v`) for testing packaging.
* Modular assembly scripts (`instances.py`, `bus_interfaces.py`, `adhoc_connections.py`, `tie_offs.py`, `export_ports.py`).
* Replaced LiteX `SoCCore` with `migen.Module` in `assemble_commercial_eda.py` to fix dynamic instantiation crashes and focus strictly on structural RTL stitching.
* Documentation folder with `learnings.md`, `what.md`, `how.md`, and `changelog.md`.
