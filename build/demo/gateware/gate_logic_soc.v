/* Machine-generated using Migen */
module gate_logic_soc(
	input sys_clk,
	input sys_rst,
	input a_i,
	input b_i,
	output y_o
);

wire and_out;
wire or_out;
wire nand_out;
wire xor_out;
wire [1:0] lfsr_sel;
wire mux_y;

// synthesis translate_off
reg dummy_s;
initial dummy_s <= 1'd0;
// synthesis translate_on

assign y_o = mux_y;

gate_and gate_and(
	.a(a_i),
	.b(b_i),
	.y(and_out)
);

gate_or gate_or(
	.a(a_i),
	.b(b_i),
	.y(or_out)
);

gate_nand gate_nand(
	.a(a_i),
	.b(b_i),
	.y(nand_out)
);

gate_xor gate_xor(
	.a(a_i),
	.b(b_i),
	.y(xor_out)
);

mux4to1 mux4to1(
	.in0(and_out),
	.in1(or_out),
	.in2(nand_out),
	.in3(xor_out),
	.sel(lfsr_sel),
	.y(mux_y)
);

lfsr2bit lfsr2bit(
	.clk(sys_clk),
	.rst(sys_rst),
	.q(lfsr_sel)
);

endmodule
