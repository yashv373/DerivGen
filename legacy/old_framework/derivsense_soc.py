"""
DerivSense SoC (STA-SoC) - EDA Scale Test
==========================================
42 Distinct IPs. 103 Instances. 32-wide Sensor Array. 2 Clock Domains.

This script demonstrates generating a massive, highly-instantiated SoC
using Python loops for structural assembly, outputting Verilog and IP-XACT.
"""

import os
import sys

# Add the eda_framework dir so we can import the ipxact generator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "eda_framework"))

from migen import *
from migen.fhdl import verilog
from eda_framework.ipxact_generator import generate_full_ipxact_package

IP_DIR = "eda_framework/ips/derivsense"
BUILD_DIR = "build/derivsense"

# =========================================================================
# STEP 1: GENERATE 42 UNIQUE IPs
# =========================================================================
def generate_ips():
    os.makedirs(IP_DIR, exist_ok=True)
    
    # Template for standard clocked IPs (Complex/Dummy)
    clk_template = """\
module {name}(
    input wire clk,
    input wire rst,
    input wire [31:0] din,
    output wire [31:0] dout
);
    assign dout = din ^ 32'hDEADBEEF; // Dummy logic
endmodule
"""

    # We will generate 42 specific IPs requested by the spec
    ip_names = [
        # System/Bus
        "AXI4_Lite_Fabric_IP", "APB_Bridge_IP", "SPI_Master_IP", "UART_TX_IP", "UART_RX_IP",
        # Memory
        "SRAM_Macro_IP", "SRAM_Ctrl_IP", "Cache_Macro_IP", "Cache_Ctrl_IP",
        # Control
        "Core_FSM_IP", "Shadow_FSM_IP",
        # Sensor Path
        "Sensor_Formatter_IP", "Threshold_Check_IP", "Data_Aggregator_IP",
        # Safety
        "Lockstep_Comparator_IP", "Parity_Gen_IP", "Parity_Check_IP",
        # Registers
        "Complex_Parity_Flop_IP", "Sync_FIFO_IP", "Async_FIFO_IP", "RegBank_IP",
        # Math
        "ALU_Add_IP", "ALU_Sub_IP", "ALU_Mult_IP", "Comparator_IP",
        # Logic
        "And2_IP", "And3_IP", "Or2_IP", "Or3_IP", "Xor2_IP", "Not_IP",
        # Routing
        "Mux2to1_IP", "Mux4to1_IP", "Demux1to2_IP", "Demux1to4_IP",
        # Pads
        "In_Pad_IP", "Out_Pad_IP", "Inout_Pad_IP"
    ]

    # Special IPs that don't fit the generic clocked template
    special_ips = {
        "PLL_Macro_IP": "module PLL_Macro_IP(input ref_clk, output clk_fast, output clk_slow); assign clk_fast=ref_clk; assign clk_slow=ref_clk; endmodule",
        "Global_Clk_Buf_IP": "module Global_Clk_Buf_IP(input clk_in, output clk_out); assign clk_out=clk_in; endmodule",
        "Clk_Mux_IP": "module Clk_Mux_IP(input sel, input clk0, input clk1, output clk_out); assign clk_out = sel ? clk1 : clk0; endmodule",
        "Sync_Reset_IP": "module Sync_Reset_IP(input clk, input rst_in, output rst_out); assign rst_out = rst_in; endmodule",
        "Lockstep_Comparator_IP": "module Lockstep_Comparator_IP(input [31:0] a, input [31:0] b, output err); assign err = (a != b); endmodule",
        "Threshold_Check_IP": "module Threshold_Check_IP(input clk, input rst, input [31:0] din, output alert); assign alert = din[31]; endmodule"
    }

    # Generate files
    for name in ip_names + list(special_ips.keys()):
        # skip duplicates
        if name in special_ips and name in ip_names:
            ip_names.remove(name)

    all_ips = ip_names + list(special_ips.keys())
    assert len(all_ips) == 42, f"Expected 42 IPs, got {len(all_ips)}"

    for name in ip_names:
        with open(os.path.join(IP_DIR, f"{name}.v"), "w") as f:
            f.write(clk_template.format(name=name))
            
    for name, code in special_ips.items():
        with open(os.path.join(IP_DIR, f"{name}.v"), "w") as f:
            f.write(code + "\n")

    return all_ips


# =========================================================================
# STEP 2: SoC ASSEMBLY
# =========================================================================
class DerivSenseSoC(Module):
    def __init__(self):
        self.ios = set()
        self.ipxact_specs = []

        # --- Top-Level Pads (Exports) ---
        self.clk_ref = Signal(name="clk_ref")
        self.sys_rst = Signal(name="sys_rst")
        self.axi_bus = Signal(128, name="axi_bus")
        self.spi_bus = Signal(4, name="spi_bus")
        self.uart_tx = Signal(name="uart_tx")
        self.uart_rx = Signal(name="uart_rx")
        self.intr_threshold_met = Signal(name="intr_threshold_met")
        self.err_lockstep_out = Signal(name="err_lockstep_out")
        
        # Array of 32 sensor inputs (32-bit each) -> 1024 bits total
        self.sensor_data_in = Signal(32 * 32, name="sensor_data_in")

        self.ios.update({
            self.clk_ref, self.sys_rst, self.axi_bus, self.spi_bus, 
            self.uart_tx, self.uart_rx, self.intr_threshold_met, 
            self.err_lockstep_out, self.sensor_data_in
        })

        # --- Clock & Reset Tree ---
        self.clk_fast_raw = Signal(name="clk_fast_raw")
        self.clk_slow_raw = Signal(name="clk_slow_raw")
        
        self.inst("PLL_Macro_IP", "pll", 
            i_ref_clk=self.clk_ref, o_clk_fast=self.clk_fast_raw, o_clk_slow=self.clk_slow_raw,
            ipxact_inputs=[("ref_clk",1)], ipxact_outputs=[("clk_fast",1),("clk_slow",1)])

        # Clock domains (Migen infrastructure)
        self.clock_domains.cd_fast = ClockDomain("fast")
        self.clock_domains.cd_slow = ClockDomain("slow")

        self.inst("Global_Clk_Buf_IP", "bufg_fast", 
            i_clk_in=self.clk_fast_raw, o_clk_out=self.cd_fast.clk,
            ipxact_inputs=[("clk_in",1)], ipxact_outputs=[("clk_out",1)])
            
        self.inst("Global_Clk_Buf_IP", "bufg_slow", 
            i_clk_in=self.clk_slow_raw, o_clk_out=self.cd_slow.clk,
            ipxact_inputs=[("clk_in",1)], ipxact_outputs=[("clk_out",1)])

        # Wire reset globally
        self.comb += [self.cd_fast.rst.eq(self.sys_rst), self.cd_slow.rst.eq(self.sys_rst)]
        
        # Instantiate remaining Clock/Reset items
        self.inst("Clk_Mux_IP", "clk_mux_test", i_sel=0, i_clk0=self.cd_fast.clk, i_clk1=self.clk_ref, o_clk_out=Signal(),
            ipxact_inputs=[("sel",1),("clk0",1),("clk1",1)], ipxact_outputs=[("clk_out",1)])
        self.inst("Sync_Reset_IP", "sync_rst_fast", i_clk=self.cd_fast.clk, i_rst_in=self.sys_rst, o_rst_out=Signal(),
            ipxact_inputs=[("clk",1),("rst_in",1)], ipxact_outputs=[("rst_out",1)])

        # --- System/Bus ---
        dummy_in = Signal(32); dummy_out = Signal(32)
        self.inst_std("AXI4_Lite_Fabric_IP", "axi_fabric", "fast", dummy_in, dummy_out)
        self.inst_std("APB_Bridge_IP", "apb_bridge", "slow", dummy_in, dummy_out)
        self.inst_std("SPI_Master_IP", "spi_master", "slow", dummy_in, dummy_out)
        self.inst_std("UART_TX_IP", "uart_tx_inst", "slow", dummy_in, dummy_out)
        self.inst_std("UART_RX_IP", "uart_rx_inst", "slow", dummy_in, dummy_out)

        # --- Memory ---
        self.inst_std("SRAM_Macro_IP", "sram_macro", "fast", dummy_in, dummy_out)
        self.inst_std("SRAM_Ctrl_IP", "sram_ctrl", "fast", dummy_in, dummy_out)
        self.inst_std("Cache_Macro_IP", "cache_macro", "fast", dummy_in, dummy_out)
        self.inst_std("Cache_Ctrl_IP", "cache_ctrl", "fast", dummy_in, dummy_out)

        # --- Control (Redundant) ---
        fsm_out = Signal(32, name="core_fsm_out")
        shadow_out = Signal(32, name="shadow_fsm_out")
        self.inst_std("Core_FSM_IP", "core_fsm", "fast", dummy_in, fsm_out)
        self.inst_std("Shadow_FSM_IP", "shadow_fsm", "fast", dummy_in, shadow_out)
        
        # --- Safety (Lockstep) ---
        self.inst("Lockstep_Comparator_IP", "lockstep_cmp", 
            i_a=fsm_out, i_b=shadow_out, o_err=self.err_lockstep_out,
            ipxact_inputs=[("a",32), ("b",32)], ipxact_outputs=[("err",1)])

        self.inst_std("Parity_Gen_IP", "parity_gen", "fast", dummy_in, dummy_out)
        self.inst_std("Parity_Check_IP", "parity_chk", "fast", dummy_in, dummy_out)

        # --- 32-WIDE SENSOR PATH (The Power of Python Assembly) ---
        # Instead of 64 manual instantiation blocks in Tcl, we use a loop!
        alerts = []
        for i in range(32):
            fmt_out = Signal(32, name=f"fmt_data_{i}")
            alert_out = Signal(name=f"alert_{i}")
            
            # Formatter
            self.inst_std("Sensor_Formatter_IP", f"sensor_fmt_{i}", "fast", 
                          self.sensor_data_in[i*32:(i+1)*32], fmt_out)
            
            # Threshold Check
            self.inst("Threshold_Check_IP", f"thresh_chk_{i}",
                i_clk=self.cd_fast.clk, i_rst=self.cd_fast.rst, i_din=fmt_out, o_alert=alert_out,
                ipxact_inputs=[("clk",1),("rst",1),("din",32)], ipxact_outputs=[("alert",1)])
                
            alerts.append(alert_out)
            
        # Combine alerts (Ad-hoc routing)
        self.comb += self.intr_threshold_met.eq(reduce(lambda a, b: a | b, alerts))
        
        self.inst_std("Data_Aggregator_IP", "data_aggregator", "fast", dummy_in, dummy_out)

        # --- Registers ---
        self.inst_std("Complex_Parity_Flop_IP", "parity_flop_0", "fast", dummy_in, dummy_out)
        self.inst_std("Complex_Parity_Flop_IP", "parity_flop_1", "fast", dummy_in, dummy_out)
        self.inst_std("Sync_FIFO_IP", "sync_fifo", "fast", dummy_in, dummy_out)
        self.inst_std("Async_FIFO_IP", "async_fifo_0", "fast", dummy_in, dummy_out)
        self.inst_std("Async_FIFO_IP", "async_fifo_1", "slow", dummy_in, dummy_out)
        self.inst_std("RegBank_IP", "reg_bank", "fast", dummy_in, dummy_out)

        # --- Math & Logic (Instantiation for spec compliance) ---
        for mod in ["ALU_Add_IP", "ALU_Sub_IP", "ALU_Mult_IP", "Comparator_IP", 
                    "And2_IP", "And3_IP", "Or2_IP", "Or3_IP", "Xor2_IP", "Not_IP",
                    "Mux2to1_IP", "Mux4to1_IP", "Demux1to2_IP", "Demux1to4_IP",
                    "In_Pad_IP", "Out_Pad_IP", "Inout_Pad_IP"]:
            self.inst_std(mod, f"{mod.lower()}_inst", "fast", dummy_in, dummy_out)

    def inst(self, module, inst_name, ipxact_inputs, ipxact_outputs, **kwargs):
        """Helper to instantiate a module and record it for IP-XACT."""
        instance = Instance(module, name=inst_name, **kwargs)
        self.specials += instance
        
        self.ipxact_specs.append({
            "module": module,
            "inst_name": inst_name,
            "inputs": ipxact_inputs,
            "outputs": ipxact_outputs
        })
        
    def inst_std(self, module, inst_name, cd_name, sig_in, sig_out):
        """Helper for the standard clocked template (clk, rst, din, dout)"""
        clk_sig = self.cd_fast.clk if cd_name == "fast" else self.cd_slow.clk
        rst_sig = self.cd_fast.rst if cd_name == "fast" else self.cd_slow.rst
        
        self.inst(module, inst_name, 
            i_clk=clk_sig, i_rst=rst_sig, i_din=sig_in, o_dout=sig_out,
            ipxact_inputs=[("clk",1),("rst",1),("din",32)],
            ipxact_outputs=[("dout",32)])


# =========================================================================
# STEP 3: RUN THE BUILD
# =========================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  DerivSense SoC (STA-SoC) - EDA Framework Scale Test")
    print("=" * 60)
    
    print("1. Generating 42 distinct Verilog IPs...")
    all_ips = generate_ips()
    print(f"   Generated {len(all_ips)} files in {IP_DIR}")
    
    print("2. Assembling Migen SoC and routing instances...")
    soc = DerivSenseSoC()
    
    print("3. Generating Top-Level Verilog Wrapper...")
    os.makedirs(os.path.join(BUILD_DIR, "gateware"), exist_ok=True)
    v_output = verilog.convert(soc, ios=soc.ios, name="derivsense_soc")
    verilog_path = os.path.join(BUILD_DIR, "gateware", "derivsense_soc.v")
    with open(verilog_path, "w") as f:
        f.write(v_output.main_source)
    
    lines = len(v_output.main_source.splitlines())
    instances = v_output.main_source.count(" (") - v_output.main_source.count("module ") # Rough count
    print(f"   [WRITE] {verilog_path} ({lines} lines)")
    
    print(f"4. Generating IEEE 1685-2009 IP-XACT metadata...")
    comp_paths, design_path = generate_full_ipxact_package(
        "derivsense_soc", soc.ipxact_specs,
        output_dir=os.path.join(BUILD_DIR, "ipxact")
    )
    print(f"   Generated {len(comp_paths)} Component XMLs.")
    print(f"   Generated 1 Design XML: {os.path.basename(design_path)} ({os.path.getsize(design_path)} bytes)")
    
    print("=" * 60)
    print("  SUCCESS! Framework handled 42 IPs and 100+ instances.")
    print("=" * 60)
