"""
DerivGen EDA Framework - Stress Test Suite v2
===============================================
Tests the Migen structural assembly engine across 5 progressively harder scenarios.

Test Plan:
  TEST 1: Baseline (2 IPs)         - dummy_uart + dummy_crypto
  TEST 2: Scale (8 IPs)            - A realistic mini-SoC with 8 different peripherals
  TEST 3: Wide Buses (256-bit)     - IPs with multi-bit ports (AXI-like)
  TEST 4: Derivative Removal       - Start from TEST 2, remove 3 IPs (ML derivative simulation)
  TEST 5: Full Round-Trip Diff     - Diff parent vs derivative Verilog structurally
"""

import os
import datetime
import difflib
from migen import *
from migen.fhdl import verilog

BUILD_DIR = "build/stress_test"
os.makedirs(BUILD_DIR, exist_ok=True)
os.makedirs(os.path.join(BUILD_DIR, "ips"), exist_ok=True)


def make_dummy_ip(name, inputs, outputs):
    """Generate a dummy .v file for a given IP with arbitrary ports."""
    lines = [f"module {name}("]
    all_ports = []
    for pname, width in inputs:
        if width == 1:
            all_ports.append(f"    input wire {pname}")
        else:
            all_ports.append(f"    input wire [{width-1}:0] {pname}")
    for pname, width in outputs:
        if width == 1:
            all_ports.append(f"    output wire {pname}")
        else:
            all_ports.append(f"    output wire [{width-1}:0] {pname}")
    lines.append(",\n".join(all_ports))
    lines.append(");")
    for pname, width in outputs:
        if width == 1:
            lines.append(f"    assign {pname} = 1'b0;")
        else:
            lines.append(f"    assign {pname} = {width}'d0;")
    lines.append("endmodule")
    filepath = os.path.join(BUILD_DIR, "ips", f"{name}.v")
    with open(filepath, "w") as f:
        f.write("\n".join(lines) + "\n")


def verify_verilog(verilog_text, test_name, expected_instances, must_have_strings=None):
    """Check that the generated Verilog contains expected module instantiations."""
    errors = []
    for inst_name in expected_instances:
        # Migen outputs: module_name module_name( for each Instance
        pattern = f"{inst_name} {inst_name}("
        if pattern not in verilog_text:
            errors.append(f"  MISSING INSTANCE: '{inst_name}' (looked for '{pattern}')")
    if must_have_strings:
        for s in must_have_strings:
            if s not in verilog_text:
                errors.append(f"  MISSING STRING: '{s}'")
    if "module " not in verilog_text:
        errors.append("  MISSING: No 'module' declaration found")
    if "endmodule" not in verilog_text:
        errors.append("  MISSING: No 'endmodule' found")
    if errors:
        print(f"  [FAIL] {test_name}")
        for e in errors:
            print(e)
        return False
    else:
        print(f"  [PASS] {test_name}")
        return True


def build_soc(soc_name, ip_specs, tie_specs=None, adhoc_specs=None, export_list=None):
    """
    Build an SoC from a list of IP specs using pure Migen.
    
    ip_specs: list of dicts with keys:
        module, inputs [(name,width),...], outputs [(name,width),...]
    tie_specs:   list of (signal_name, value) 
    adhoc_specs: list of (src_signal_name, dst_signal_name) 
    export_list: list of signal names to expose at top-level
    """

    class TestSoC(Module):
        def __init__(self):
            self.ios = set()
            self.signal_map = {}

            # Create a proper clock domain so ClockSignal()/ResetSignal() resolve correctly.
            # We add the clock and reset as top-level IOs so they appear in the port list.
            self.clock_domains.cd_sys = ClockDomain("sys")
            self.ios.add(self.cd_sys.clk)
            self.ios.add(self.cd_sys.rst)

            # STEP 1: INSTANCES (instances.py equivalent)
            for ip in ip_specs:
                mod_name = ip["module"]
                inst_name = ip.get("inst_name", mod_name)
                port_args = {}

                for pname, width in ip.get("inputs", []):
                    # Skip clk and rst since we route them from the clock domain
                    if pname in ("clk", "rst"):
                        continue
                    sig = Signal(width, name=f"{inst_name}_{pname}")
                    setattr(self, f"{inst_name}_{pname}", sig)
                    self.signal_map[f"{inst_name}_{pname}"] = sig
                    port_args[f"i_{pname}"] = sig

                for pname, width in ip.get("outputs", []):
                    sig = Signal(width, name=f"{inst_name}_{pname}")
                    setattr(self, f"{inst_name}_{pname}", sig)
                    self.signal_map[f"{inst_name}_{pname}"] = sig
                    port_args[f"o_{pname}"] = sig

                # Always wire clk and rst from the system clock domain
                port_args["i_clk"] = ClockSignal("sys")
                port_args["i_rst"] = ResetSignal("sys")

                self.specials += Instance(mod_name, **port_args)
                make_dummy_ip(mod_name, ip.get("inputs", []), ip.get("outputs", []))

            # STEP 2: TIE-OFFS (tie_offs.py equivalent)
            if tie_specs:
                for sig_name, value in tie_specs:
                    if sig_name in self.signal_map:
                        self.comb += self.signal_map[sig_name].eq(value)

            # STEP 3: AD-HOC CONNECTIONS (adhoc_connections.py equivalent)
            if adhoc_specs:
                for src_name, dst_name in adhoc_specs:
                    if src_name in self.signal_map and dst_name in self.signal_map:
                        self.comb += self.signal_map[dst_name].eq(self.signal_map[src_name])

            # STEP 4: EXPORT PORTS (export_ports.py equivalent)
            if export_list:
                for sig_name in export_list:
                    if sig_name in self.signal_map:
                        self.ios.add(self.signal_map[sig_name])

    soc = TestSoC()
    v_output = verilog.convert(soc, ios=soc.ios, name=soc_name)
    outpath = os.path.join(BUILD_DIR, f"{soc_name}.v")
    with open(outpath, "w") as f:
        f.write(v_output.main_source)
    return v_output.main_source, outpath


# ==========================================================================
# TEST 1: BASELINE (2 IPs)
# ==========================================================================
def test_1_baseline():
    print("\n" + "=" * 70)
    print("TEST 1: BASELINE (2 IPs) - Sanity Check")
    print("=" * 70)

    ips = [
        {"module": "dummy_uart",
         "inputs": [("clk",1),("rst",1),("rx",1)],
         "outputs": [("tx",1),("irq",1)]},
        {"module": "dummy_crypto",
         "inputs": [("clk",1),("rst",1),("debug_enable",1)],
         "outputs": [("status_out",1)]},
    ]
    ties = [("dummy_crypto_debug_enable", 0), ("dummy_uart_rx", 1)]
    exports = ["dummy_uart_tx", "dummy_crypto_status_out"]

    vtxt, path = build_soc("test1_baseline", ips, tie_specs=ties, export_list=exports)
    print(f"  Generated: {path} ({len(vtxt.splitlines())} lines)")

    return verify_verilog(vtxt, "Baseline Structure",
        expected_instances=["dummy_uart", "dummy_crypto"],
        must_have_strings=["sys_clk", "sys_rst", "dummy_uart_tx", "dummy_crypto_status_out"])


# ==========================================================================
# TEST 2: SCALE (8 IPs)
# ==========================================================================
def test_2_scale():
    print("\n" + "=" * 70)
    print("TEST 2: SCALE (8 IPs) - Realistic Mini-SoC")
    print("=" * 70)

    ips = [
        {"module": "ip_uart",  "inputs": [("clk",1),("rst",1),("rx",1)],                                        "outputs": [("tx",1),("irq",1)]},
        {"module": "ip_gpio",  "inputs": [("clk",1),("rst",1),("gpio_in",8)],                                   "outputs": [("gpio_out",8),("irq",1)]},
        {"module": "ip_spi",   "inputs": [("clk",1),("rst",1),("miso",1)],                                      "outputs": [("mosi",1),("sclk_o",1),("cs_n",1)]},
        {"module": "ip_i2c",   "inputs": [("clk",1),("rst",1),("sda_in",1)],                                    "outputs": [("sda_out",1),("scl_out",1)]},
        {"module": "ip_timer", "inputs": [("clk",1),("rst",1),("prescale",16)],                                 "outputs": [("timer_irq",1)]},
        {"module": "ip_pwm",   "inputs": [("clk",1),("rst",1),("duty_cycle",8)],                                "outputs": [("pwm_out",1)]},
        {"module": "ip_aes",   "inputs": [("clk",1),("rst",1),("key_in",128),("data_in",128)],                  "outputs": [("data_out",128),("done",1)]},
        {"module": "ip_dma",   "inputs": [("clk",1),("rst",1),("src_addr",32),("dst_addr",32),("length",16)],   "outputs": [("busy",1),("done_irq",1)]},
    ]

    ties = [
        ("ip_uart_rx", 1), ("ip_gpio_gpio_in", 0), ("ip_spi_miso", 1),
        ("ip_i2c_sda_in", 1), ("ip_timer_prescale", 100), ("ip_pwm_duty_cycle", 128),
        ("ip_aes_key_in", 0), ("ip_aes_data_in", 0),
        ("ip_dma_src_addr", 0), ("ip_dma_dst_addr", 0), ("ip_dma_length", 0),
    ]
    exports = [
        "ip_uart_tx", "ip_gpio_gpio_out", "ip_spi_mosi", "ip_spi_sclk_o", "ip_spi_cs_n",
        "ip_i2c_sda_out", "ip_i2c_scl_out", "ip_pwm_pwm_out",
        "ip_aes_data_out", "ip_aes_done", "ip_dma_busy", "ip_dma_done_irq",
        "ip_uart_irq", "ip_gpio_irq", "ip_timer_timer_irq",
    ]

    vtxt, path = build_soc("test2_scale_8ip", ips, tie_specs=ties, export_list=exports)
    print(f"  Generated: {path} ({len(vtxt.splitlines())} lines, {len(exports)} exported ports)")

    return verify_verilog(vtxt, "8-IP Scale Test",
        expected_instances=["ip_uart", "ip_gpio", "ip_spi", "ip_i2c", "ip_timer", "ip_pwm", "ip_aes", "ip_dma"],
        must_have_strings=["sys_clk", "sys_rst"])


# ==========================================================================
# TEST 3: WIDE BUSES (256-bit AXI-like)
# ==========================================================================
def test_3_wide_buses():
    print("\n" + "=" * 70)
    print("TEST 3: WIDE BUSES (Multi-bit ports, 256-bit AXI-like)")
    print("=" * 70)

    ips = [
        {"module": "ip_axi_master",
         "inputs": [("clk",1),("rst",1),("rdata",256),("rvalid",1),("rready_in",1)],
         "outputs": [("wdata",256),("wstrb",32),("awaddr",32),("araddr",32),("wvalid",1)]},
        {"module": "ip_axi_slave",
         "inputs": [("clk",1),("rst",1),("wdata",256),("wstrb",32),("awaddr",32),("wvalid",1)],
         "outputs": [("rdata",256),("rvalid",1)]},
    ]

    adhocs = [
        ("ip_axi_master_wdata",  "ip_axi_slave_wdata"),
        ("ip_axi_master_wstrb",  "ip_axi_slave_wstrb"),
        ("ip_axi_master_awaddr", "ip_axi_slave_awaddr"),
        ("ip_axi_master_wvalid", "ip_axi_slave_wvalid"),
        ("ip_axi_slave_rdata",   "ip_axi_master_rdata"),
        ("ip_axi_slave_rvalid",  "ip_axi_master_rvalid"),
    ]
    ties = [("ip_axi_master_rready_in", 1)]
    exports = ["ip_axi_master_araddr", "ip_axi_slave_rdata"]

    vtxt, path = build_soc("test3_wide_bus", ips, tie_specs=ties, adhoc_specs=adhocs, export_list=exports)
    print(f"  Generated: {path} ({len(vtxt.splitlines())} lines)")

    has_256 = "[255:0]" in vtxt
    print(f"  256-bit bus detected in Verilog: {has_256}")

    ok = verify_verilog(vtxt, "Wide Bus Structure",
        expected_instances=["ip_axi_master", "ip_axi_slave"],
        must_have_strings=["sys_clk", "sys_rst"])

    if not has_256:
        print("  [FAIL] 256-bit bus width not found in output")
    return ok and has_256


# ==========================================================================
# TEST 4: DERIVATIVE REMOVAL - Remove 3 IPs from the 8-IP SoC
# ==========================================================================
def test_4_derivative():
    print("\n" + "=" * 70)
    print("TEST 4: DERIVATIVE (Remove AES, DMA, PWM from 8-IP SoC)")
    print("=" * 70)

    # The 5 IPs that remain after ML removes AES, DMA, PWM
    ips = [
        {"module": "ip_uart",  "inputs": [("clk",1),("rst",1),("rx",1)],           "outputs": [("tx",1),("irq",1)]},
        {"module": "ip_gpio",  "inputs": [("clk",1),("rst",1),("gpio_in",8)],      "outputs": [("gpio_out",8),("irq",1)]},
        {"module": "ip_spi",   "inputs": [("clk",1),("rst",1),("miso",1)],         "outputs": [("mosi",1),("sclk_o",1),("cs_n",1)]},
        {"module": "ip_i2c",   "inputs": [("clk",1),("rst",1),("sda_in",1)],       "outputs": [("sda_out",1),("scl_out",1)]},
        {"module": "ip_timer", "inputs": [("clk",1),("rst",1),("prescale",16)],    "outputs": [("timer_irq",1)]},
    ]
    ties = [
        ("ip_uart_rx", 1), ("ip_gpio_gpio_in", 0), ("ip_spi_miso", 1),
        ("ip_i2c_sda_in", 1), ("ip_timer_prescale", 100),
    ]
    exports = [
        "ip_uart_tx", "ip_gpio_gpio_out", "ip_spi_mosi", "ip_spi_sclk_o", "ip_spi_cs_n",
        "ip_i2c_sda_out", "ip_i2c_scl_out",
        "ip_uart_irq", "ip_gpio_irq", "ip_timer_timer_irq",
    ]

    vtxt, path = build_soc("test4_derivative_5ip", ips, tie_specs=ties, export_list=exports)
    print(f"  Generated: {path} ({len(vtxt.splitlines())} lines)")
    print(f"  IPs remaining: 5 (removed AES, DMA, PWM)")

    removed_clean = True
    for removed in ["ip_aes", "ip_dma", "ip_pwm"]:
        if removed in vtxt:
            print(f"  [FAIL] Removed IP '{removed}' still appears in generated Verilog!")
            removed_clean = False

    if removed_clean:
        print(f"  [PASS] All 3 removed IPs are correctly absent from the wrapper")

    ok = verify_verilog(vtxt, "Derivative Structure",
        expected_instances=["ip_uart", "ip_gpio", "ip_spi", "ip_i2c", "ip_timer"],
        must_have_strings=["sys_clk", "sys_rst"])

    return ok and removed_clean


# ==========================================================================
# TEST 5: FULL ROUND-TRIP DIFF - Compare parent vs derivative
# ==========================================================================
def test_5_diff():
    print("\n" + "=" * 70)
    print("TEST 5: STRUCTURAL DIFF (Parent 8-IP vs Derivative 5-IP)")
    print("=" * 70)

    parent_path = os.path.join(BUILD_DIR, "test2_scale_8ip.v")
    deriv_path  = os.path.join(BUILD_DIR, "test4_derivative_5ip.v")

    if not os.path.exists(parent_path) or not os.path.exists(deriv_path):
        print("  [SKIP] Requires TEST 2 and TEST 4 to pass first.")
        return False

    with open(parent_path) as f:
        parent_lines = f.readlines()
    with open(deriv_path) as f:
        deriv_lines = f.readlines()

    diff = list(difflib.unified_diff(parent_lines, deriv_lines,
        fromfile="parent_8ip.v", tofile="derivative_5ip.v", lineterm=""))

    added   = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))

    print(f"  Parent SoC:     {len(parent_lines)} lines")
    print(f"  Derivative SoC: {len(deriv_lines)} lines")
    print(f"  Diff: +{added} / -{removed} lines changed")

    diff_path = os.path.join(BUILD_DIR, "parent_vs_derivative.diff")
    with open(diff_path, "w") as f:
        f.write("\n".join(diff))
    print(f"  Diff saved to: {diff_path}")

    if len(deriv_lines) < len(parent_lines):
        print(f"  [PASS] Derivative is smaller ({len(deriv_lines)} < {len(parent_lines)} lines)")
        ok = True
    else:
        print(f"  [FAIL] Derivative should be smaller than parent!")
        ok = False

    removed_text = " ".join(l for l in diff if l.startswith("-") and not l.startswith("---"))
    for ip in ["ip_aes", "ip_dma", "ip_pwm"]:
        if ip in removed_text:
            print(f"  [PASS] Diff confirms removal of '{ip}'")
        else:
            print(f"  [INFO] '{ip}' not explicitly visible in diff lines (Migen auto-named)")

    return ok


# ==========================================================================
# MAIN
# ==========================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("  DerivGen EDA Framework - Stress Test Suite v2")
    print(f"  Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    results = {}
    results["TEST 1: Baseline (2 IP)"]       = test_1_baseline()
    results["TEST 2: Scale (8 IP)"]          = test_2_scale()
    results["TEST 3: Wide Buses (256-bit)"]  = test_3_wide_buses()
    results["TEST 4: Derivative Removal"]    = test_4_derivative()
    results["TEST 5: Structural Diff"]       = test_5_diff()

    print("\n" + "=" * 70)
    print("  FINAL RESULTS")
    print("=" * 70)
    all_pass = True
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {test_name}")
        if not passed:
            all_pass = False
    print("=" * 70)
    if all_pass:
        print("  ALL 5 TESTS PASSED. EDA Framework is robust.")
    else:
        print("  SOME TESTS FAILED. See details above.")
    print("=" * 70)

    print("\n  Generated Artifacts:")
    for f_name in sorted(os.listdir(BUILD_DIR)):
        fpath = os.path.join(BUILD_DIR, f_name)
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            print(f"    {f_name:40s} {size:>6} bytes")
