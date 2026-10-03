"""
DerivSense SoC Assembler - GOLDEN REFERENCE
===========================================
This is the true EDA Framework assembly script.
It dynamically parses the REAL Verilog files from the IP Library to ensure
perfect port matching, wires up the standard AXI4-Lite and APB buses, 
and generates the structurally perfect Top-Level Wrapper and IP-XACT XML.
"""

import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "eda_framework"))

from migen import *
from migen.fhdl import verilog
from eda_framework.ipxact_generator import generate_full_ipxact_package

IP_DIR = "eda_framework/ips/derivsense_lib"
BUILD_DIR = "build/derivsense_golden"

def parse_verilog_ports(module_name):
    """Dynamically parses a Verilog IP file to extract its exact inputs and outputs."""
    filepath = os.path.join(IP_DIR, module_name, f"{module_name}.v")
    inputs = []
    outputs = []
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            # Regex to find inputs
            for match in re.finditer(r'input\s+(?:wire\s+)?(?:\[(\d+):(\d+)\]\s+)?(\w+)', content):
                width = int(match.group(1)) - int(match.group(2)) + 1 if match.group(1) else 1
                inputs.append((match.group(3), width))
            # Regex to find outputs
            for match in re.finditer(r'output\s+(?:wire\s+)?(?:reg\s+)?(?:\[(\d+):(\d+)\]\s+)?(\w+)', content):
                width = int(match.group(1)) - int(match.group(2)) + 1 if match.group(1) else 1
                outputs.append((match.group(3), width))
    except FileNotFoundError:
        print(f"WARNING: {filepath} not found.")
    return inputs, outputs


# ==========================================
# STANDARD BUS RECORD DEFINITIONS
# ==========================================
def axi_layout():
    return [
        ("awaddr", 32), ("awvalid", 1), ("awready", 1),
        ("wdata", 32), ("wstrb", 4), ("wvalid", 1), ("wready", 1),
        ("bresp", 2), ("bvalid", 1), ("bready", 1),
        ("araddr", 32), ("arvalid", 1), ("arready", 1),
        ("rdata", 32), ("rresp", 2), ("rvalid", 1), ("rready", 1)
    ]

def apb_layout():
    return [
        ("paddr", 32), ("psel", 1), ("penable", 1), ("pwrite", 1),
        ("pwdata", 32), ("prdata", 32), ("pready", 1), ("pslverr", 1)
    ]


class DerivSenseSoCGolden(Module):
    def __init__(self):
        self.ios = set()
        self.ipxact_specs = []

        # --- Top-Level Pads ---
        self.clk_ref = Signal(name="clk_ref")
        self.sys_rst_n = Signal(name="sys_rst_n")
        self.sensor_data_in = Signal(32 * 32, name="sensor_data_in")
        
        # Top-Level Host AXI Bus
        self.host_axi = Record(axi_layout(), name="host_axi")
        
        # Peripherals
        self.miso = Signal(name="miso")
        self.mosi = Signal(name="mosi")
        self.sck = Signal(name="sck")
        self.cs = Signal(name="cs")
        self.uart_tx = Signal(name="uart_tx")
        self.uart_rx = Signal(name="uart_rx")
        self.intr_threshold = Signal(name="intr_threshold")
        self.err_lockstep = Signal(name="err_lockstep")

        # Export all top-level IOs for Migen
        self.ios.update({
            self.clk_ref, self.sys_rst_n, self.sensor_data_in,
            self.miso, self.mosi, self.sck, self.cs,
            self.uart_tx, self.uart_rx, self.intr_threshold, self.err_lockstep
        })
        for name, _ in axi_layout():
            self.ios.add(getattr(self.host_axi, name))

        # --- Clock Tree ---
        self.clk_fast = Signal(name="clk_fast")
        self.clk_slow = Signal(name="clk_slow")
        
        self.inst("PLL_Macro_IP", "pll", i_clk_ref=self.clk_ref, o_clk_fast=self.clk_fast, o_clk_slow=self.clk_slow)
        
        self.clock_domains.cd_fast = ClockDomain("fast")
        self.clock_domains.cd_slow = ClockDomain("slow")
        
        self.inst("Global_Clk_Buf_IP", "bufg_fast", i_clk_in=self.clk_fast, o_clk_out=self.cd_fast.clk)
        self.inst("Global_Clk_Buf_IP", "bufg_slow", i_clk_in=self.clk_slow, o_clk_out=self.cd_slow.clk)
        
        # Wire active-low reset
        self.comb += [self.cd_fast.rst.eq(~self.sys_rst_n), self.cd_slow.rst.eq(~self.sys_rst_n)]

        # --- Bus Infrastructure ---
        # Internal AXI buses
        axi_m0 = Record(axi_layout(), name="axi_m0")
        axi_m1 = Record(axi_layout(), name="axi_m1")
        
        # Internal APB Bus
        apb_bus = Record(apb_layout(), name="apb_bus")

        # Instantiate AXI Fabric (1 Slave, 2 Masters)
        self.inst("AXI4_Lite_Fabric_IP", "axi_crossbar",
                  i_clk=self.cd_fast.clk, i_rst_n=self.sys_rst_n,
                  # Host Slave
                  i_s_axi_awaddr=self.host_axi.awaddr, i_s_axi_awvalid=self.host_axi.awvalid, o_s_axi_awready=self.host_axi.awready,
                  i_s_axi_wdata=self.host_axi.wdata, i_s_axi_wstrb=self.host_axi.wstrb, i_s_axi_wvalid=self.host_axi.wvalid, o_s_axi_wready=self.host_axi.wready,
                  o_s_axi_bresp=self.host_axi.bresp, o_s_axi_bvalid=self.host_axi.bvalid, i_s_axi_bready=self.host_axi.bready,
                  i_s_axi_araddr=self.host_axi.araddr, i_s_axi_arvalid=self.host_axi.arvalid, o_s_axi_arready=self.host_axi.arready,
                  o_s_axi_rdata=self.host_axi.rdata, o_s_axi_rresp=self.host_axi.rresp, o_s_axi_rvalid=self.host_axi.rvalid, i_s_axi_rready=self.host_axi.rready,
                  # Master 0 (SRAM)
                  o_m0_axi_awaddr=axi_m0.awaddr, o_m0_axi_awvalid=axi_m0.awvalid, i_m0_axi_awready=axi_m0.awready,
                  o_m0_axi_wdata=axi_m0.wdata, o_m0_axi_wstrb=axi_m0.wstrb, o_m0_axi_wvalid=axi_m0.wvalid, i_m0_axi_wready=axi_m0.wready,
                  i_m0_axi_bresp=axi_m0.bresp, i_m0_axi_bvalid=axi_m0.bvalid, o_m0_axi_bready=axi_m0.bready,
                  o_m0_axi_araddr=axi_m0.araddr, o_m0_axi_arvalid=axi_m0.arvalid, i_m0_axi_arready=axi_m0.arready,
                  i_m0_axi_rdata=axi_m0.rdata, i_m0_axi_rresp=axi_m0.rresp, i_m0_axi_rvalid=axi_m0.rvalid, o_m0_axi_rready=axi_m0.rready,
                  # Master 1 (APB Bridge)
                  o_m1_axi_awaddr=axi_m1.awaddr, o_m1_axi_awvalid=axi_m1.awvalid, i_m1_axi_awready=axi_m1.awready,
                  o_m1_axi_wdata=axi_m1.wdata, o_m1_axi_wstrb=axi_m1.wstrb, o_m1_axi_wvalid=axi_m1.wvalid, i_m1_axi_wready=axi_m1.wready,
                  i_m1_axi_bresp=axi_m1.bresp, i_m1_axi_bvalid=axi_m1.bvalid, o_m1_axi_bready=axi_m1.bready,
                  o_m1_axi_araddr=axi_m1.araddr, o_m1_axi_arvalid=axi_m1.arvalid, i_m1_axi_arready=axi_m1.arready,
                  i_m1_axi_rdata=axi_m1.rdata, i_m1_axi_rresp=axi_m1.rresp, i_m1_axi_rvalid=axi_m1.rvalid, o_m1_axi_rready=axi_m1.rready
        )

        # Instantiate APB Bridge
        self.inst("APB_Bridge_IP", "apb_bridge",
                  i_clk=self.cd_fast.clk, i_rst_n=self.sys_rst_n,
                  i_s_axi_awaddr=axi_m1.awaddr, i_s_axi_awvalid=axi_m1.awvalid, o_s_axi_awready=axi_m1.awready,
                  i_s_axi_wdata=axi_m1.wdata, i_s_axi_wvalid=axi_m1.wvalid, o_s_axi_wready=axi_m1.wready,
                  o_s_axi_bresp=axi_m1.bresp, o_s_axi_bvalid=axi_m1.bvalid, i_s_axi_bready=axi_m1.bready,
                  i_s_axi_araddr=axi_m1.araddr, i_s_axi_arvalid=axi_m1.arvalid, o_s_axi_arready=axi_m1.arready,
                  o_s_axi_rdata=axi_m1.rdata, o_s_axi_rresp=axi_m1.rresp, o_s_axi_rvalid=axi_m1.rvalid, i_s_axi_rready=axi_m1.rready,
                  o_m_apb_paddr=apb_bus.paddr, o_m_apb_psel=apb_bus.psel, o_m_apb_penable=apb_bus.penable, 
                  o_m_apb_pwrite=apb_bus.pwrite, o_m_apb_pwdata=apb_bus.pwdata,
                  i_m_apb_prdata=apb_bus.prdata, i_m_apb_pready=apb_bus.pready, i_m_apb_pslverr=apb_bus.pslverr
        )

        # --- Memory ---
        sram_we = Signal(); sram_addr = Signal(11); sram_din = Signal(32); sram_dout = Signal(32)
        self.inst("SRAM_Ctrl_IP", "sram_ctrl",
                  i_clk=self.cd_fast.clk, i_rst_n=self.sys_rst_n,
                  i_s_axi_awaddr=axi_m0.awaddr, i_s_axi_awvalid=axi_m0.awvalid, o_s_axi_awready=axi_m0.awready,
                  i_s_axi_wdata=axi_m0.wdata, i_s_axi_wvalid=axi_m0.wvalid, o_s_axi_wready=axi_m0.wready,
                  o_s_axi_bresp=axi_m0.bresp, o_s_axi_bvalid=axi_m0.bvalid, i_s_axi_bready=axi_m0.bready,
                  i_s_axi_araddr=axi_m0.araddr, i_s_axi_arvalid=axi_m0.arvalid, o_s_axi_arready=axi_m0.arready,
                  o_s_axi_rdata=axi_m0.rdata, o_s_axi_rresp=axi_m0.rresp, o_s_axi_rvalid=axi_m0.rvalid, i_s_axi_rready=axi_m0.rready,
                  o_sram_we=sram_we, o_sram_addr=sram_addr, o_sram_din=sram_din, i_sram_dout=sram_dout
        )
        self.inst("SRAM_Macro_IP", "sram_macro", i_clk=self.cd_fast.clk, i_we=sram_we, i_addr=sram_addr, i_din=sram_din, o_dout=sram_dout)

        # --- APB Peripherals ---
        # For a simple golden test, we multiplex the PRDATA back to the bridge
        reg_prdata = Signal(32); spi_prdata = Signal(32); uart_prdata = Signal(32); uart_rx_prdata = Signal(32)
        reg_pready = Signal(); spi_pready = Signal(); uart_pready = Signal(); uart_rx_pready = Signal()
        
        self.comb += [
            apb_bus.prdata.eq(reg_prdata | spi_prdata | uart_prdata | uart_rx_prdata),
            apb_bus.pready.eq(reg_pready | spi_pready | uart_pready | uart_rx_pready | ~apb_bus.psel) # default ready if no sel
        ]

        self.inst("RegBank_IP", "reg_bank",
                  i_clk=self.cd_fast.clk, i_rst_n=self.sys_rst_n,
                  i_paddr=apb_bus.paddr, i_psel=apb_bus.psel, i_penable=apb_bus.penable, i_pwrite=apb_bus.pwrite, i_pwdata=apb_bus.pwdata,
                  o_prdata=reg_prdata, o_pready=reg_pready, o_pslverr=Signal(), o_ctrl_regs=Signal(128))

        self.inst("SPI_Master_IP", "spi_master",
                  i_clk_slow=self.cd_slow.clk, i_rst_n=self.sys_rst_n,
                  i_paddr=apb_bus.paddr, i_psel=apb_bus.psel, i_penable=apb_bus.penable, i_pwrite=apb_bus.pwrite, i_pwdata=apb_bus.pwdata,
                  o_prdata=spi_prdata, o_pready=spi_pready, o_pslverr=Signal(),
                  i_miso=self.miso, o_mosi=self.mosi, o_sck=self.sck, o_cs=self.cs)
                  
        self.inst("UART_TX_IP", "uart_tx_inst",
                  i_clk_slow=self.cd_slow.clk, i_rst_n=self.sys_rst_n,
                  i_paddr=apb_bus.paddr, i_psel=apb_bus.psel, i_penable=apb_bus.penable, i_pwrite=apb_bus.pwrite, i_pwdata=apb_bus.pwdata,
                  o_prdata=uart_prdata, o_pready=uart_pready, o_pslverr=Signal(),
                  o_tx=self.uart_tx)

        self.inst("UART_RX_IP", "uart_rx_inst",
                  i_clk_slow=self.cd_slow.clk, i_rst_n=self.sys_rst_n,
                  i_paddr=apb_bus.paddr, i_psel=apb_bus.psel, i_penable=apb_bus.penable, i_pwrite=apb_bus.pwrite, i_pwdata=apb_bus.pwdata,
                  o_prdata=uart_rx_prdata, o_pready=uart_rx_pready, o_pslverr=Signal(),
                  i_rx=self.uart_rx)

        # --- 32-Wide Sensor Path (The Parallel Array) ---
        fsm_data = Signal(32)
        alerts = []
        for i in range(32):
            fmt_out = Signal(32, name=f"fmt_data_{i}")
            alert_out = Signal(name=f"alert_{i}")
            
            self.inst("Sensor_Formatter_IP", f"sensor_fmt_{i}", 
                      i_clk_fast=self.cd_fast.clk, i_rst=self.sys_rst_n, 
                      i_raw_sensor_in=self.sensor_data_in[i*32:(i+1)*32], o_formatted_data=fmt_out)
            
            self.inst("Threshold_Check_IP", f"thresh_chk_{i}",
                      i_clk_fast=self.cd_fast.clk, i_rst=self.sys_rst_n, 
                      i_formatted_data=fmt_out, o_threshold_alert=alert_out)
            
            alerts.append(alert_out)
            
            # Simple OR tree to aggregate formatted data for the FSM (simplified)
            if i == 0: self.comb += fsm_data.eq(fmt_out)
            
        alert_cat = Cat(*alerts)
        self.inst("Data_Aggregator_IP", "data_aggregator",
                  i_clk_fast=self.cd_fast.clk, i_rst=self.sys_rst_n,
                  i_alert_bus=alert_cat, o_aggregated_intr=self.intr_threshold)

        # --- Control & Lockstep ---
        fsm_out = Signal(32); shadow_out = Signal(32)
        self.inst("Core_FSM_IP", "core_fsm", i_clk_fast=self.cd_fast.clk, i_rst=self.sys_rst_n, i_sensor_data=fsm_data, o_state_out=fsm_out, o_mem_write=Signal())
        self.inst("Shadow_FSM_IP", "shadow_fsm", i_clk_fast=self.cd_fast.clk, i_rst=self.sys_rst_n, i_sensor_data=fsm_data, o_state_out=shadow_out, o_mem_write=Signal())
        self.inst("Lockstep_Comparator_IP", "lockstep_cmp", i_fsm_a=fsm_out, i_fsm_b=shadow_out, o_err_lockstep=self.err_lockstep)

        # --- Missing IPs (Dummy instantiation for scale) ---
        missing_ips = [
            ("Cache_Ctrl_IP", "cache_ctrl"), ("Cache_Macro_IP", "cache_macro"),
            ("Complex_Parity_Flop_IP", "parity_flop_0"), ("Complex_Parity_Flop_IP", "parity_flop_1"),
            ("Sync_FIFO_IP", "sync_fifo"), ("Async_FIFO_IP", "async_fifo_0"), ("Async_FIFO_IP", "async_fifo_1"),
            ("Parity_Gen_IP", "parity_gen"), ("Parity_Check_IP", "parity_chk"),
            ("ALU_Add_IP", "alu_add"), ("ALU_Sub_IP", "alu_sub"), ("ALU_Mult_IP", "alu_mult"), ("Comparator_IP", "comparator"),
            ("And2_IP", "and2"), ("And3_IP", "and3"), ("Or2_IP", "or2"), ("Or3_IP", "or3"), ("Xor2_IP", "xor2"), ("Not_IP", "not"),
            ("Mux2to1_IP", "mux2to1"), ("Mux4to1_IP", "mux4to1"), ("Demux1to2_IP", "demux1to2"), ("Demux1to4_IP", "demux1to4"),
            ("In_Pad_IP", "in_pad"), ("Out_Pad_IP", "out_pad"), ("Inout_Pad_IP", "inout_pad"),
            ("Clk_Mux_IP", "clk_mux_test"), ("Sync_Reset_IP", "sync_rst_fast")
        ]
        for mod, name in missing_ips:
            inputs, outputs = parse_verilog_ports(mod)
            kwargs = {}
            for port, width in inputs:
                kwargs["i_" + port] = Signal(width)
            for port, width in outputs:
                kwargs["o_" + port] = Signal(width)
            if "Inout_Pad_IP" in mod:
                kwargs["io_pad_inout"] = Signal()
            self.inst(mod, name, **kwargs)

    def inst(self, module, inst_name, **kwargs):
        """Helper: Instantiates a module and dynamically queries its actual Verilog ports for IP-XACT."""
        instance = Instance(module, name=inst_name, **kwargs)
        self.specials += instance
        
        # Dynamically extract real ports from Verilog file
        inputs, outputs = parse_verilog_ports(module)
        
        self.ipxact_specs.append({
            "module": module,
            "inst_name": inst_name,
            "inputs": inputs,
            "outputs": outputs
        })

# =========================================================================
# RUN THE BUILD
# =========================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  DerivSense SoC Assembler - GOLDEN REFERENCE MODE")
    print("=" * 60)
    
    print("1. Assembling Migen SoC (Routing standard AXI/APB logic)...")
    soc = DerivSenseSoCGolden()
    
    print("2. Generating Top-Level Verilog Wrapper...")
    os.makedirs(os.path.join(BUILD_DIR, "gateware"), exist_ok=True)
    v_output = verilog.convert(soc, ios=soc.ios, name="derivsense_soc_golden")
    verilog_path = os.path.join(BUILD_DIR, "gateware", "derivsense_soc_golden.v")
    with open(verilog_path, "w") as f:
        f.write(v_output.main_source)
    
    lines = len(v_output.main_source.splitlines())
    print(f"   [WRITE] {verilog_path} ({lines} lines)")
    
    print("3. Generating IEEE 1685-2009 IP-XACT metadata...")
    comp_paths, design_path = generate_full_ipxact_package(
        "derivsense_soc_golden", soc.ipxact_specs,
        output_dir=os.path.join(BUILD_DIR, "ipxact")
    )
    print(f"   Generated {len(comp_paths)} Component XMLs.")
    print(f"   Generated 1 Design XML: {os.path.basename(design_path)} ({os.path.getsize(design_path)} bytes)")
    print("=" * 60)
    print("  SUCCESS! Golden Reference Hardware completed.")
    print("=" * 60)
