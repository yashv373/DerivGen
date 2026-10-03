"""
DerivSense IP Library Builder
==============================
Strictly generates the 42 unique IPs required for the DerivSense SoC.
For each IP, it generates:
1. A Verilog file with architecturally accurate ports.
2. A FuseSoC .core file packaging the IP.
"""

import os

IP_DIR = "eda_framework/ips/derivsense_lib"

# Define the exact ports for all 42 IPs based on the architecture spec
ip_specs = {
    # System / Bus
    "AXI4_Lite_Fabric_IP": {"inputs": [("clk",1),("rst",1),("s_axi_awaddr",32),("s_axi_wdata",32)], "outputs": [("m_axi_awaddr",32),("m_axi_wdata",32)]},
    "APB_Bridge_IP":       {"inputs": [("clk",1),("rst",1),("axi_in",32)], "outputs": [("apb_out",32)]},
    "SPI_Master_IP":       {"inputs": [("clk_slow",1),("rst",1),("apb_in",32),("miso",1)], "outputs": [("mosi",1),("sck",1),("cs",1)]},
    "UART_TX_IP":          {"inputs": [("clk_slow",1),("rst",1),("apb_in",32)], "outputs": [("tx",1)]},
    "UART_RX_IP":          {"inputs": [("clk_slow",1),("rst",1),("rx",1)], "outputs": [("apb_out",32)]},
    
    # Memory
    "SRAM_Macro_IP":       {"inputs": [("clk",1),("we",1),("addr",11),("din",32)], "outputs": [("dout",32)]},
    "SRAM_Ctrl_IP":        {"inputs": [("clk",1),("rst",1),("axi_in",32),("sram_dout",32)], "outputs": [("sram_we",1),("sram_addr",11),("sram_din",32)]},
    "Cache_Macro_IP":      {"inputs": [("clk",1),("re",1),("addr",6)], "outputs": [("dout",32)]},
    "Cache_Ctrl_IP":       {"inputs": [("clk",1),("rst",1),("axi_in",32),("cache_dout",32)], "outputs": [("cache_re",1),("cache_addr",6)]},
    
    # Control
    "Core_FSM_IP":         {"inputs": [("clk_fast",1),("rst",1),("sensor_data",32)], "outputs": [("state_out",32),("mem_write",1)]},
    "Shadow_FSM_IP":       {"inputs": [("clk_fast",1),("rst",1),("sensor_data",32)], "outputs": [("state_out",32),("mem_write",1)]},
    
    # Sensor Path
    "Sensor_Formatter_IP": {"inputs": [("clk_fast",1),("rst",1),("raw_sensor_in",32)], "outputs": [("formatted_data",32)]},
    "Threshold_Check_IP":  {"inputs": [("clk_fast",1),("rst",1),("formatted_data",32)], "outputs": [("threshold_alert",1)]},
    "Data_Aggregator_IP":  {"inputs": [("clk_fast",1),("rst",1),("alert_bus",32)], "outputs": [("aggregated_intr",1)]},
    
    # Safety
    "Lockstep_Comparator_IP": {"inputs": [("fsm_a",32),("fsm_b",32)], "outputs": [("err_lockstep",1)]},
    "Parity_Gen_IP":       {"inputs": [("data_in",32)], "outputs": [("parity_bit",1)]},
    "Parity_Check_IP":     {"inputs": [("data_in",32),("parity_bit",1)], "outputs": [("parity_err",1)]},
    
    # Registers & FIFOs
    "Complex_Parity_Flop_IP": {"inputs": [("clk",1),("rst_n",1),("en",1),("scan_in",1),("d",32)], "outputs": [("q",32),("parity_out",1)]},
    "Sync_FIFO_IP":        {"inputs": [("clk",1),("rst",1),("we",1),("re",1),("din",32)], "outputs": [("dout",32),("full",1),("empty",1)]},
    "Async_FIFO_IP":       {"inputs": [("wclk",1),("rclk",1),("rst",1),("we",1),("re",1),("din",32)], "outputs": [("dout",32),("full",1),("empty",1)]},
    "RegBank_IP":          {"inputs": [("clk",1),("rst",1),("apb_in",32)], "outputs": [("ctrl_regs",128)]},
    
    # Clock / Reset
    "PLL_Macro_IP":        {"inputs": [("clk_ref",1)], "outputs": [("clk_fast",1),("clk_slow",1)]},
    "Clk_Mux_IP":          {"inputs": [("sel",1),("clk0",1),("clk1",1)], "outputs": [("clk_out",1)]},
    "Global_Clk_Buf_IP":   {"inputs": [("clk_in",1)], "outputs": [("clk_out",1)]},
    "Sync_Reset_IP":       {"inputs": [("clk",1),("rst_in",1)], "outputs": [("rst_out",1)]},
    
    # Math
    "ALU_Add_IP":          {"inputs": [("a",32),("b",32)], "outputs": [("y",32)]},
    "ALU_Sub_IP":          {"inputs": [("a",32),("b",32)], "outputs": [("y",32)]},
    "ALU_Mult_IP":         {"inputs": [("a",32),("b",32)], "outputs": [("y",32)]},
    "Comparator_IP":       {"inputs": [("a",32),("b",32)], "outputs": [("eq",1),("gt",1)]},
    
    # Basic Logic
    "And2_IP":             {"inputs": [("a",1),("b",1)], "outputs": [("y",1)]},
    "And3_IP":             {"inputs": [("a",1),("b",1),("c",1)], "outputs": [("y",1)]},
    "Or2_IP":              {"inputs": [("a",1),("b",1)], "outputs": [("y",1)]},
    "Or3_IP":              {"inputs": [("a",1),("b",1),("c",1)], "outputs": [("y",1)]},
    "Xor2_IP":             {"inputs": [("a",1),("b",1)], "outputs": [("y",1)]},
    "Not_IP":              {"inputs": [("a",1)], "outputs": [("y",1)]},
    
    # Routing
    "Mux2to1_IP":          {"inputs": [("sel",1),("in0",32),("in1",32)], "outputs": [("y",32)]},
    "Mux4to1_IP":          {"inputs": [("sel",2),("in0",32),("in1",32),("in2",32),("in3",32)], "outputs": [("y",32)]},
    "Demux1to2_IP":        {"inputs": [("sel",1),("in0",32)], "outputs": [("out0",32),("out1",32)]},
    "Demux1to4_IP":        {"inputs": [("sel",2),("in0",32)], "outputs": [("out0",32),("out1",32),("out2",32),("out3",32)]},
    
    # Pads
    "In_Pad_IP":           {"inputs": [("pad_in",1)], "outputs": [("core_in",1)]},
    "Out_Pad_IP":          {"inputs": [("core_out",1)], "outputs": [("pad_out",1)]},
    "Inout_Pad_IP":        {"inputs": [("core_out",1),("oe",1),("pad_inout",1)], "outputs": [("core_in",1)]}
}

def generate_verilog(name, spec, out_dir):
    """Generates a structurally correct Verilog stub for the IP."""
    lines = [f"module {name}("]
    
    ports = []
    for p_name, p_width in spec["inputs"]:
        width_str = f"[{p_width-1}:0] " if p_width > 1 else ""
        ports.append(f"    input wire {width_str}{p_name}")
        
    for p_name, p_width in spec["outputs"]:
        width_str = f"[{p_width-1}:0] " if p_width > 1 else ""
        ports.append(f"    output wire {width_str}{p_name}")
        
    lines.append(",\n".join(ports))
    lines.append(");")
    
    # Assign dummy logic to prevent synthesis optimization warnings
    for p_name, p_width in spec["outputs"]:
        if p_width == 1:
            lines.append(f"    assign {p_name} = 1'b0;")
        else:
            lines.append(f"    assign {p_name} = {p_width}'d0;")
            
    lines.append("endmodule\n")
    
    with open(os.path.join(out_dir, f"{name}.v"), "w") as f:
        f.write("\n".join(lines))

def generate_fusesoc_core(name, out_dir):
    """Generates a strict FuseSoC CAPI2 core file for the IP."""
    content = f"""\
CAPI=2:
name: derivgen:ip:{name.lower()}:1.0
description: Auto-packaged IP block for {name}

filesets:
  rtl:
    files:
      - {name}.v
    file_type: verilogSource

targets:
  default:
    filesets: [rtl]
"""
    with open(os.path.join(out_dir, f"{name}.core"), "w") as f:
        f.write(content)

if __name__ == "__main__":
    print(f"Building DerivSense IP Library in: {IP_DIR}")
    for ip_name, spec in ip_specs.items():
        # Create a dedicated directory for each IP to mimic a real library
        ip_path = os.path.join(IP_DIR, ip_name)
        os.makedirs(ip_path, exist_ok=True)
        
        generate_verilog(ip_name, spec, ip_path)
        generate_fusesoc_core(ip_name, ip_path)
        
    print(f"Successfully generated and packaged {len(ip_specs)} IPs via FuseSoC.")
