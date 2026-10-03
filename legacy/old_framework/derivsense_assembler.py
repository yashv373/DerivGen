"""
DerivSense SoC Assembler
=========================
This script represents the Python EDA Framework's true role.
It ASSUMES the IP library (Verilog + FuseSoC .core files) already exists.
It strictly performs:
1. Instantiation and Wiring via Migen
2. Top-Level Verilog Wrapper Generation
3. IP-XACT IEEE 1685-2009 Generation
"""

import os
import sys

# Add the eda_framework dir so we can import the ipxact generator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "eda_framework"))

from migen import *
from migen.fhdl import verilog
from eda_framework.ipxact_generator import generate_full_ipxact_package

BUILD_DIR = "build/derivsense_strict"

# Note: We duplicate the spec dictionary here just to know what ports exist 
# to wire them up properly. In a full tool, this would be parsed directly 
# from the FuseSoC or IP-XACT metadata of the existing IPs.
from derivsense_ip_builder import ip_specs

class DerivSenseSoC(Module):
    def __init__(self):
        self.ios = set()
        self.ipxact_specs = []

        # --- Top-Level Pads (Exports) ---
        self.clk_ref = Signal(name="clk_ref")
        self.sys_rst = Signal(name="sys_rst")
        self.sensor_data_in = Signal(32 * 32, name="sensor_data_in")
        self.axi_awaddr = Signal(32, name="axi_awaddr")
        self.axi_wdata = Signal(32, name="axi_wdata")
        self.miso = Signal(name="miso")
        self.uart_rx = Signal(name="uart_rx")
        
        self.axi_m_awaddr = Signal(32, name="axi_m_awaddr")
        self.spi_mosi = Signal(name="spi_mosi")
        self.spi_sck = Signal(name="spi_sck")
        self.spi_cs = Signal(name="spi_cs")
        self.uart_tx = Signal(name="uart_tx")
        self.intr_threshold = Signal(name="intr_threshold")
        self.err_lockstep = Signal(name="err_lockstep")

        self.ios.update({
            self.clk_ref, self.sys_rst, self.sensor_data_in, 
            self.axi_awaddr, self.axi_wdata, self.miso, self.uart_rx,
            self.axi_m_awaddr, self.spi_mosi, self.spi_sck, self.spi_cs,
            self.uart_tx, self.intr_threshold, self.err_lockstep
        })

        # --- Clock & Reset Tree ---
        self.clk_fast = Signal(name="clk_fast")
        self.clk_slow = Signal(name="clk_slow")
        
        self.inst("PLL_Macro_IP", "pll_inst", i_clk_ref=self.clk_ref, o_clk_fast=self.clk_fast, o_clk_slow=self.clk_slow)

        self.clock_domains.cd_fast = ClockDomain("fast")
        self.clock_domains.cd_slow = ClockDomain("slow")

        self.inst("Global_Clk_Buf_IP", "bufg_fast", i_clk_in=self.clk_fast, o_clk_out=self.cd_fast.clk)
        self.inst("Global_Clk_Buf_IP", "bufg_slow", i_clk_in=self.clk_slow, o_clk_out=self.cd_slow.clk)

        # Wire reset globally
        self.comb += [self.cd_fast.rst.eq(self.sys_rst), self.cd_slow.rst.eq(self.sys_rst)]
        
        # --- System/Bus ---
        apb_bridge_out = Signal(32)
        self.inst("AXI4_Lite_Fabric_IP", "axi_fabric", i_clk=self.cd_fast.clk, i_rst=self.cd_fast.rst, i_s_axi_awaddr=self.axi_awaddr, i_s_axi_wdata=self.axi_wdata, o_m_axi_awaddr=self.axi_m_awaddr, o_m_axi_wdata=Signal(32))
        self.inst("APB_Bridge_IP", "apb_bridge", i_clk=self.cd_slow.clk, i_rst=self.cd_slow.rst, i_axi_in=self.axi_m_awaddr, o_apb_out=apb_bridge_out)
        self.inst("SPI_Master_IP", "spi_master", i_clk_slow=self.cd_slow.clk, i_rst=self.cd_slow.rst, i_apb_in=apb_bridge_out, i_miso=self.miso, o_mosi=self.spi_mosi, o_sck=self.spi_sck, o_cs=self.spi_cs)
        self.inst("UART_TX_IP", "uart_tx_inst", i_clk_slow=self.cd_slow.clk, i_rst=self.cd_slow.rst, i_apb_in=apb_bridge_out, o_tx=self.uart_tx)
        self.inst("UART_RX_IP", "uart_rx_inst", i_clk_slow=self.cd_slow.clk, i_rst=self.cd_slow.rst, i_rx=self.uart_rx, o_apb_out=Signal(32))

        # --- Control & Safety (Lockstep FSMs) ---
        fsm_out = Signal(32)
        shadow_out = Signal(32)
        
        # The 32 sensor streams will aggregate to drive the FSMs
        self.inst("Core_FSM_IP", "core_fsm", i_clk_fast=self.cd_fast.clk, i_rst=self.cd_fast.rst, i_sensor_data=Signal(32), o_state_out=fsm_out, o_mem_write=Signal())
        self.inst("Shadow_FSM_IP", "shadow_fsm", i_clk_fast=self.cd_fast.clk, i_rst=self.cd_fast.rst, i_sensor_data=Signal(32), o_state_out=shadow_out, o_mem_write=Signal())
        
        self.inst("Lockstep_Comparator_IP", "lockstep_cmp", i_fsm_a=fsm_out, i_fsm_b=shadow_out, o_err_lockstep=self.err_lockstep)

        # --- 32-WIDE SENSOR PATH ---
        alerts = []
        for i in range(32):
            fmt_out = Signal(32, name=f"fmt_data_{i}")
            alert_out = Signal(name=f"alert_{i}")
            
            # Formatter
            self.inst("Sensor_Formatter_IP", f"sensor_fmt_{i}", 
                      i_clk_fast=self.cd_fast.clk, i_rst=self.cd_fast.rst, i_raw_sensor_in=self.sensor_data_in[i*32:(i+1)*32], o_formatted_data=fmt_out)
            
            # Threshold Check
            self.inst("Threshold_Check_IP", f"thresh_chk_{i}",
                      i_clk_fast=self.cd_fast.clk, i_rst=self.cd_fast.rst, i_formatted_data=fmt_out, o_threshold_alert=alert_out)
                
            alerts.append(alert_out)
            
        # Combine alerts (Ad-hoc routing)
        self.comb += self.intr_threshold.eq(reduce(lambda a, b: a | b, alerts))

    def inst(self, module, inst_name, **kwargs):
        """Helper to instantiate a module and record it for IP-XACT."""
        instance = Instance(module, name=inst_name, **kwargs)
        self.specials += instance
        
        self.ipxact_specs.append({
            "module": module,
            "inst_name": inst_name,
            "inputs": ip_specs[module]["inputs"],
            "outputs": ip_specs[module]["outputs"]
        })

# =========================================================================
# STEP 3: RUN THE BUILD
# =========================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  DerivSense SoC Assembler - Strict Mode")
    print("=" * 60)
    
    print("1. Assembling Migen SoC (assuming IP library exists)...")
    soc = DerivSenseSoC()
    
    print("2. Generating Top-Level Verilog Wrapper...")
    os.makedirs(os.path.join(BUILD_DIR, "gateware"), exist_ok=True)
    v_output = verilog.convert(soc, ios=soc.ios, name="derivsense_soc_top")
    verilog_path = os.path.join(BUILD_DIR, "gateware", "derivsense_soc_top.v")
    with open(verilog_path, "w") as f:
        f.write(v_output.main_source)
    
    lines = len(v_output.main_source.splitlines())
    print(f"   [WRITE] {verilog_path} ({lines} lines)")
    
    print(f"3. Generating IEEE 1685-2009 IP-XACT metadata...")
    comp_paths, design_path = generate_full_ipxact_package(
        "derivsense_soc_top", soc.ipxact_specs,
        output_dir=os.path.join(BUILD_DIR, "ipxact")
    )
    print(f"   Generated {len(comp_paths)} Component XMLs.")
    print(f"   Generated 1 Design XML: {os.path.basename(design_path)} ({os.path.getsize(design_path)} bytes)")
    
    print("=" * 60)
    print("  SUCCESS! Assembly complete. Strict boundary respected.")
    print("=" * 60)
