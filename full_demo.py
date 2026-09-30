"""
DerivGen EDA Framework - Full Manual Demo
==========================================
Demonstrates the COMPLETE packaging + assembly + IP-XACT flow.

Architecture:
                                                 
    a_i ---+---> [AND]  ---> mux_in0 --\          
           |                            \         
    b_i ---+---> [OR]   ---> mux_in1 ---[4:1 MUX]---> y_o
           |                            /    ^        
           +---> [NAND] ---> mux_in2 --/     |        
           |                                 |        
           +---> [XOR]  ---> mux_in3       sel[1:0]   
                                             |        
                                        [2-bit LFSR]  

6 IPs total. All hand-written, all hand-wired.
"""

import os
import sys

# Add the eda_framework dir so we can import the ipxact generator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "eda_framework"))

from migen import *
from migen.fhdl import verilog
from eda_framework.ipxact_generator import generate_full_ipxact_package

# =========================================================================
# STEP 1: WRITE THE VERILOG IPs
# =========================================================================
IP_DIR = "eda_framework/ips/demo"
os.makedirs(IP_DIR, exist_ok=True)

ips_verilog = {

"gate_and.v": """\
module gate_and(
    input  wire a,
    input  wire b,
    output wire y
);
    assign y = a & b;
endmodule
""",

"gate_or.v": """\
module gate_or(
    input  wire a,
    input  wire b,
    output wire y
);
    assign y = a | b;
endmodule
""",

"gate_nand.v": """\
module gate_nand(
    input  wire a,
    input  wire b,
    output wire y
);
    assign y = ~(a & b);
endmodule
""",

"gate_xor.v": """\
module gate_xor(
    input  wire a,
    input  wire b,
    output wire y
);
    assign y = a ^ b;
endmodule
""",

"mux4to1.v": """\
module mux4to1(
    input  wire in0,
    input  wire in1,
    input  wire in2,
    input  wire in3,
    input  wire [1:0] sel,
    output reg  y
);
    always @(*) begin
        case(sel)
            2'b00: y = in0;
            2'b01: y = in1;
            2'b10: y = in2;
            2'b11: y = in3;
        endcase
    end
endmodule
""",

"lfsr2bit.v": """\
module lfsr2bit(
    input  wire       clk,
    input  wire       rst,
    output reg  [1:0] q
);
    // 2-bit LFSR: taps at bits 1 and 0 (XOR feedback)
    // Sequence: 01 -> 10 -> 11 -> 01 -> ...
    always @(posedge clk or posedge rst) begin
        if (rst)
            q <= 2'b01;  // Seed (non-zero)
        else begin
            q[0] <= q[1];
            q[1] <= q[0] ^ q[1];
        end
    end
endmodule
"""
}

print("=" * 65)
print("  STEP 1: Writing Verilog IP Source Files")
print("=" * 65)
for fname, content in ips_verilog.items():
    path = os.path.join(IP_DIR, fname)
    with open(path, "w") as f:
        f.write(content)
    print(f"  [WRITE] {path}")


# =========================================================================
# STEP 2: ASSEMBLE THE SOC (replaces instances.py + adhoc + tie + export)
# =========================================================================
print("\n" + "=" * 65)
print("  STEP 2: Assembling the SoC (Migen Structural Stitching)")
print("=" * 65)

class GateLogicSoC(Module):
    def __init__(self):
        self.ios = set()

        # --- Clock Domain ---
        self.clock_domains.cd_sys = ClockDomain("sys")
        self.ios.add(self.cd_sys.clk)
        self.ios.add(self.cd_sys.rst)

        # === TOP-LEVEL PORTS (chip pins) ===
        self.a_i = Signal(name="a_i")       # Input A
        self.b_i = Signal(name="b_i")       # Input B
        self.y_o = Signal(name="y_o")       # Output Y (from MUX)
        self.ios.update({self.a_i, self.b_i, self.y_o})

        # === INTERNAL WIRES ===
        self.and_out  = Signal(name="and_out")
        self.or_out   = Signal(name="or_out")
        self.nand_out = Signal(name="nand_out")
        self.xor_out  = Signal(name="xor_out")
        self.lfsr_sel = Signal(2, name="lfsr_sel")
        self.mux_y    = Signal(name="mux_y")

        # === STEP 2a: INSTANCES (instances.py equivalent) ===
        print("  [INST] gate_and   (a, b) -> and_out")
        self.specials += Instance("gate_and",
            i_a=self.a_i, i_b=self.b_i, o_y=self.and_out)

        print("  [INST] gate_or    (a, b) -> or_out")
        self.specials += Instance("gate_or",
            i_a=self.a_i, i_b=self.b_i, o_y=self.or_out)

        print("  [INST] gate_nand  (a, b) -> nand_out")
        self.specials += Instance("gate_nand",
            i_a=self.a_i, i_b=self.b_i, o_y=self.nand_out)

        print("  [INST] gate_xor   (a, b) -> xor_out")
        self.specials += Instance("gate_xor",
            i_a=self.a_i, i_b=self.b_i, o_y=self.xor_out)

        print("  [INST] mux4to1    (in0..in3, sel) -> y")
        self.specials += Instance("mux4to1",
            i_in0=self.and_out, i_in1=self.or_out,
            i_in2=self.nand_out, i_in3=self.xor_out,
            i_sel=self.lfsr_sel, o_y=self.mux_y)

        print("  [INST] lfsr2bit   (clk, rst) -> q[1:0]")
        self.specials += Instance("lfsr2bit",
            i_clk=ClockSignal("sys"), i_rst=ResetSignal("sys"),
            o_q=self.lfsr_sel)

        # === STEP 2b: ADHOC CONNECTIONS (adhoc_connections.py equivalent) ===
        print("  [WIRE] mux_y -> y_o (chip output)")
        self.comb += self.y_o.eq(self.mux_y)

        # (No bus interfaces needed -- pure combinational + 1 sequential IP)
        # (No tie-offs needed -- all ports are connected)

print("  All 6 IPs instantiated and wired.")


# =========================================================================
# STEP 3: GENERATE THE VERILOG WRAPPER
# =========================================================================
print("\n" + "=" * 65)
print("  STEP 3: Generating Verilog RTL Wrapper")
print("=" * 65)

soc = GateLogicSoC()

BUILD_DIR = "build/demo"
os.makedirs(os.path.join(BUILD_DIR, "gateware"), exist_ok=True)

v_output = verilog.convert(soc, ios=soc.ios, name="gate_logic_soc")
verilog_path = os.path.join(BUILD_DIR, "gateware", "gate_logic_soc.v")
with open(verilog_path, "w") as f:
    f.write(v_output.main_source)

print(f"  [WRITE] {verilog_path}")
print(f"  Lines: {len(v_output.main_source.splitlines())}")


# =========================================================================
# STEP 4: GENERATE IP-XACT (IEEE 1685-2009)
# =========================================================================
print("\n" + "=" * 65)
print("  STEP 4: Generating IP-XACT XML (IEEE 1685-2009)")
print("=" * 65)

ip_specs_for_ipxact = [
    {"module": "gate_and",  "inputs": [("a",1),("b",1)],  "outputs": [("y",1)]},
    {"module": "gate_or",   "inputs": [("a",1),("b",1)],  "outputs": [("y",1)]},
    {"module": "gate_nand", "inputs": [("a",1),("b",1)],  "outputs": [("y",1)]},
    {"module": "gate_xor",  "inputs": [("a",1),("b",1)],  "outputs": [("y",1)]},
    {"module": "mux4to1",   "inputs": [("in0",1),("in1",1),("in2",1),("in3",1),("sel",2)], "outputs": [("y",1)]},
    {"module": "lfsr2bit",  "inputs": [("clk",1),("rst",1)], "outputs": [("q",2)]},
]

comp_paths, design_path = generate_full_ipxact_package(
    "gate_logic_soc", ip_specs_for_ipxact,
    output_dir=os.path.join(BUILD_DIR, "ipxact")
)

for p in comp_paths:
    print(f"  [IPXACT] {os.path.basename(p):25s} ({os.path.getsize(p)} bytes)")
print(f"  [IPXACT] {os.path.basename(design_path):25s} ({os.path.getsize(design_path)} bytes)")


# =========================================================================
# STEP 5: GENERATE FuseSoC .core FILE
# =========================================================================
print("\n" + "=" * 65)
print("  STEP 5: Generating FuseSoC Package (.core)")
print("=" * 65)

core_content = """\
CAPI=2:
name: derivgen:demo:gate_logic_soc:1.0
description: Gate Logic SoC - DerivGen EDA Framework Demo

filesets:
  rtl_ips:
    files:
      - eda_framework/ips/demo/gate_and.v
      - eda_framework/ips/demo/gate_or.v
      - eda_framework/ips/demo/gate_nand.v
      - eda_framework/ips/demo/gate_xor.v
      - eda_framework/ips/demo/mux4to1.v
      - eda_framework/ips/demo/lfsr2bit.v
    file_type: verilogSource

  wrapper:
    files:
      - build/demo/gateware/gate_logic_soc.v
    file_type: verilogSource
    depend: [rtl_ips]

targets:
  default:
    filesets: [rtl_ips, wrapper]
    toplevel: gate_logic_soc
"""

core_path = os.path.join(BUILD_DIR, "gate_logic_soc.core")
with open(core_path, "w") as f:
    f.write(core_content)
print(f"  [WRITE] {core_path}")


# =========================================================================
# STEP 6: VERIFY -- Print the generated Verilog
# =========================================================================
print("\n" + "=" * 65)
print("  STEP 6: VERIFICATION -- Generated Verilog Wrapper")
print("=" * 65)

with open(verilog_path, "r") as f:
    verilog_text = f.read()

print(verilog_text)

# Quick structural checks
checks = {
    "gate_and":   "gate_and gate_and("   in verilog_text,
    "gate_or":    "gate_or gate_or("     in verilog_text,
    "gate_nand":  "gate_nand gate_nand(" in verilog_text,
    "gate_xor":   "gate_xor gate_xor("   in verilog_text,
    "mux4to1":    "mux4to1 mux4to1("     in verilog_text,
    "lfsr2bit":   "lfsr2bit lfsr2bit("   in verilog_text,
    "a_i input":  "a_i"                  in verilog_text,
    "b_i input":  "b_i"                  in verilog_text,
    "y_o output": "y_o"                  in verilog_text,
    "sys_clk":    "sys_clk"              in verilog_text,
    "sys_rst":    "sys_rst"              in verilog_text,
}

print("=" * 65)
print("  STRUCTURAL VERIFICATION")
print("=" * 65)
all_ok = True
for check_name, passed in checks.items():
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_ok = False
    print(f"  [{status}] {check_name}")

print("=" * 65)
if all_ok:
    print("  ALL CHECKS PASSED. SoC is structurally correct.")
else:
    print("  SOME CHECKS FAILED.")
print("=" * 65)

# Final summary
print("\n" + "=" * 65)
print("  BUILD ARTIFACTS SUMMARY")
print("=" * 65)
artifacts = [
    ("Verilog IPs", IP_DIR, 6),
    ("RTL Wrapper", verilog_path, 1),
    ("IP-XACT Components", os.path.join(BUILD_DIR, "ipxact", "components"), len(comp_paths)),
    ("IP-XACT Design", os.path.join(BUILD_DIR, "ipxact", "designs"), 1),
    ("FuseSoC Package", core_path, 1),
]
for name, path, count in artifacts:
    print(f"  {name:25s} -> {path}")
print("=" * 65)
