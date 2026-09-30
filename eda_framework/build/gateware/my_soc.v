/* Machine-generated using Migen */
module my_soc(
	output mlgeneratedsoc,
	output mlgeneratedsoc_1,
	input sys_clk,
	input sys_rst
);

wire mlgeneratedsoc0;
wire mlgeneratedsoc1;
wire mlgeneratedsoc2;
wire mlgeneratedsoc3;
wire mlgeneratedsoc4;

// synthesis translate_off
reg dummy_s;
initial dummy_s <= 1'd0;
// synthesis translate_on

assign mlgeneratedsoc3 = 1'd0;
assign mlgeneratedsoc1 = 1'd1;
assign mlgeneratedsoc = mlgeneratedsoc0;
assign mlgeneratedsoc_1 = mlgeneratedsoc4;

dummy_uart dummy_uart(
	.clk(sys_clk),
	.rst(sys_rst),
	.rx(mlgeneratedsoc1),
	.irq(mlgeneratedsoc2),
	.tx(mlgeneratedsoc0)
);

dummy_crypto dummy_crypto(
	.clk(sys_clk),
	.debug_enable(mlgeneratedsoc3),
	.rst(sys_rst),
	.status_out(mlgeneratedsoc4)
);

endmodule
