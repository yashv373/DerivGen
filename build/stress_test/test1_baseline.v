/* Machine-generated using Migen */
module test1_baseline(
	input sys_clk,
	input sys_rst,
	output dummy_uart_tx,
	output dummy_crypto_status_out
);

wire dummy_uart_rx;
wire dummy_uart_irq;
wire dummy_crypto_debug_enable;

// synthesis translate_off
reg dummy_s;
initial dummy_s <= 1'd0;
// synthesis translate_on

assign dummy_crypto_debug_enable = 1'd0;
assign dummy_uart_rx = 1'd1;

dummy_uart dummy_uart(
	.clk(sys_clk),
	.rst(sys_rst),
	.rx(dummy_uart_rx),
	.irq(dummy_uart_irq),
	.tx(dummy_uart_tx)
);

dummy_crypto dummy_crypto(
	.clk(sys_clk),
	.debug_enable(dummy_crypto_debug_enable),
	.rst(sys_rst),
	.status_out(dummy_crypto_status_out)
);

endmodule
